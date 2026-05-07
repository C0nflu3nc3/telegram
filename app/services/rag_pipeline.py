from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.database.crud import clear_user_knowledge, create_document
from app.database.db import get_session
from app.services.file_parser import parse_text_message
from app.services.llm import generate_answer
from app.services.no_knowledge import (
    NO_ANSWER_TOKEN,
    NO_KNOWLEDGE_MESSAGES,
    get_random_guardrail_message,
    get_random_no_knowledge_message,
)
from app.services.question_guardrails import inspect_question
from app.services.text_splitter import split_text
from app.services.vector_store import (
    SearchResult,
    get_user_chunks,
    replace_user_chunks,
    search_user_chunks,
)


FULL_CONTEXT_MAX_CHUNKS = 4
FULL_CONTEXT_MAX_CHARS = 8000
FALLBACK_DISTANCE_THRESHOLD = 0.75
ANSWER_CONTEXT_MAX_CHUNKS = 5
ANSWER_CONTEXT_MAX_CHARS = 6500


@dataclass(frozen=True, slots=True)
class IngestionResult:
    document_id: int
    chunks_count: int
    text_length: int


@dataclass(frozen=True, slots=True)
class AnswerResult:
    answer: str
    context_found: bool
    matches: list[SearchResult]


def replace_user_knowledge(
    user_id: int,
    text: str,
    source_name: str | None,
    source_type: str,
) -> IngestionResult:
    settings = get_settings()
    normalized_text = parse_text_message(text)
    chunks = split_text(
        normalized_text,
        chunk_size=settings.chunk_size,
        overlap=settings.chunk_overlap,
    )
    if not chunks:
        raise ValueError("Не удалось выделить текстовые фрагменты для индексации.")

    with get_session() as session:
        clear_user_knowledge(session, user_id)
        document = create_document(
            session=session,
            user_id=user_id,
            source_name=source_name,
            source_type=source_type,
            text_length=len(normalized_text),
            chunks_count=len(chunks),
        )
        replace_user_chunks(user_id=user_id, document_id=document.id, chunks=chunks)

    return IngestionResult(
        document_id=document.id,
        chunks_count=len(chunks),
        text_length=len(normalized_text),
    )


def answer_user_question(user_id: int, question: str) -> AnswerResult:
    guardrail = inspect_question(question)
    if guardrail.blocked:
        return AnswerResult(
            answer=get_random_guardrail_message(),
            context_found=False,
            matches=[],
        )

    effective_question = guardrail.sanitized_question
    settings = get_settings()
    all_chunks = get_user_chunks(user_id)
    if not all_chunks:
        no_knowledge_message = get_random_no_knowledge_message()
        return AnswerResult(
            answer=no_knowledge_message,
            context_found=False,
            matches=[],
        )

    if _should_use_full_context(all_chunks):
        answer = generate_answer(question=effective_question, chunks=all_chunks)
        normalized_answer = _normalize_answer(answer)
        return AnswerResult(
            answer=normalized_answer,
            context_found=not _is_no_knowledge_answer(normalized_answer),
            matches=all_chunks,
        )

    matches = search_user_chunks(
        user_id=user_id,
        question=effective_question,
        top_k=settings.top_k,
    )

    relevant_matches = [
        match for match in matches if match.distance <= settings.similarity_threshold
    ]
    if not relevant_matches and matches:
        best_match = matches[0]
        if best_match.distance <= max(settings.similarity_threshold, FALLBACK_DISTANCE_THRESHOLD):
            relevant_matches = matches[: max(settings.top_k, 3)]

    if not relevant_matches:
        no_knowledge_message = get_random_no_knowledge_message()
        return AnswerResult(
            answer=no_knowledge_message,
            context_found=False,
            matches=[],
        )

    answer_chunks = _expand_answer_context(
        matches=relevant_matches,
        all_chunks=all_chunks,
        top_k=settings.top_k,
    )
    answer = generate_answer(question=effective_question, chunks=answer_chunks)
    normalized_answer = _normalize_answer(answer)

    return AnswerResult(
        answer=normalized_answer,
        context_found=not _is_no_knowledge_answer(normalized_answer),
        matches=answer_chunks,
    )


def _should_use_full_context(chunks: list[SearchResult]) -> bool:
    if len(chunks) <= FULL_CONTEXT_MAX_CHUNKS:
        return True

    total_chars = sum(len(chunk.text) for chunk in chunks)
    return total_chars <= FULL_CONTEXT_MAX_CHARS


def _normalize_answer(answer: str) -> str:
    normalized = answer.strip()
    if not normalized or normalized == NO_ANSWER_TOKEN:
        return get_random_no_knowledge_message()
    return normalized


def _is_no_knowledge_answer(answer: str) -> bool:
    return answer in NO_KNOWLEDGE_MESSAGES


def _expand_answer_context(
    matches: list[SearchResult],
    all_chunks: list[SearchResult],
    top_k: int,
) -> list[SearchResult]:
    if not matches:
        return []

    max_chunks = max(2, min(top_k + 1, ANSWER_CONTEXT_MAX_CHUNKS))
    selected: list[SearchResult] = []
    selected_ids: set[str] = set()
    current_chars = 0

    ordered_chunks = sorted(
        all_chunks,
        key=lambda item: (
            str(item.metadata.get("document_id", "")),
            int(item.metadata.get("chunk_index", 0)),
        ),
    )
    chunk_map = {
        (
            str(chunk.metadata.get("document_id", "")),
            int(chunk.metadata.get("chunk_index", 0)),
        ): chunk
        for chunk in ordered_chunks
    }

    def try_add(chunk: SearchResult | None) -> bool:
        nonlocal current_chars
        if chunk is None or chunk.chunk_id in selected_ids:
            return False
        if len(selected) >= max_chunks:
            return False

        next_chars = current_chars + len(chunk.text)
        if selected and next_chars > ANSWER_CONTEXT_MAX_CHARS:
            return False

        selected.append(chunk)
        selected_ids.add(chunk.chunk_id)
        current_chars = next_chars
        return True

    base_matches = matches[: max(2, min(len(matches), top_k))]
    for match in base_matches:
        try_add(match)

    for match in list(selected):
        document_id = str(match.metadata.get("document_id", ""))
        chunk_index = int(match.metadata.get("chunk_index", 0))
        for neighbor_index in (chunk_index - 1, chunk_index + 1):
            try_add(chunk_map.get((document_id, neighbor_index)))
            if len(selected) >= max_chunks:
                break
        if len(selected) >= max_chunks:
            break

    selected.sort(
        key=lambda item: (
            str(item.metadata.get("document_id", "")),
            int(item.metadata.get("chunk_index", 0)),
        )
    )
    return selected or matches
