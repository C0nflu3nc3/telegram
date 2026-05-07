from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import get_settings
from app.services.embeddings import create_embedding, create_embeddings
from app.services.text_splitter import TextChunk


@dataclass(frozen=True, slots=True)
class SearchResult:
    chunk_id: str
    text: str
    distance: float
    metadata: dict[str, Any]


_STORE_LOCK = Lock()


def _store_file_path() -> Path:
    settings = get_settings()
    settings.ensure_directories()
    return settings.chroma_path / "vector_store.json"


def _load_store() -> dict[str, dict[str, list[dict[str, Any]]]]:
    store_path = _store_file_path()
    if not store_path.exists():
        return {"users": {}}

    try:
        raw_data = json.loads(store_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"users": {}}

    if not isinstance(raw_data, dict):
        return {"users": {}}

    users = raw_data.get("users")
    if not isinstance(users, dict):
        return {"users": {}}

    return {"users": users}


def _save_store(store: dict[str, dict[str, list[dict[str, Any]]]]) -> None:
    store_path = _store_file_path()
    store_path.write_text(
        json.dumps(store, ensure_ascii=False),
        encoding="utf-8",
    )


def _cosine_distance(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 1.0

    dot_product = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))

    if left_norm == 0 or right_norm == 0:
        return 1.0

    similarity = dot_product / (left_norm * right_norm)
    similarity = max(min(similarity, 1.0), -1.0)
    return 1.0 - similarity


def clear_user_chunks(user_id: int) -> None:
    user_key = str(user_id)
    with _STORE_LOCK:
        store = _load_store()
        store["users"].pop(user_key, None)
        _save_store(store)


def replace_user_chunks(
    user_id: int,
    document_id: int,
    chunks: list[TextChunk],
) -> int:
    if not chunks:
        return 0

    documents = [chunk.content for chunk in chunks]
    embeddings = create_embeddings(documents)
    user_key = str(user_id)

    entries = []
    for chunk, embedding in zip(chunks, embeddings):
        entries.append(
            {
                "chunk_id": f"{user_id}:{document_id}:{chunk.index}",
                "text": chunk.content,
                "embedding": embedding,
                "metadata": {
                    "user_id": user_key,
                    "document_id": str(document_id),
                    "chunk_index": chunk.index,
                    "word_count": chunk.word_count,
                },
            }
        )

    with _STORE_LOCK:
        store = _load_store()
        store["users"][user_key] = entries
        _save_store(store)

    return len(chunks)


def search_user_chunks(user_id: int, question: str, top_k: int) -> list[SearchResult]:
    user_key = str(user_id)
    with _STORE_LOCK:
        store = _load_store()
        entries = list(store["users"].get(user_key, []))

    if not entries:
        return []

    question_embedding = create_embedding(question)

    results: list[SearchResult] = []
    for entry in entries:
        text = entry.get("text")
        if not text:
            continue

        embedding = entry.get("embedding") or []
        distance = _cosine_distance(question_embedding, embedding)
        results.append(
            SearchResult(
                chunk_id=str(entry.get("chunk_id", "")),
                text=text,
                distance=float(distance),
                metadata=entry.get("metadata") or {},
            )
        )

    results.sort(key=lambda item: item.distance)
    return results[:top_k]


def get_user_chunks(user_id: int) -> list[SearchResult]:
    user_key = str(user_id)
    with _STORE_LOCK:
        store = _load_store()
        entries = list(store["users"].get(user_key, []))

    results: list[SearchResult] = []
    for entry in sorted(
        entries,
        key=lambda item: int((item.get("metadata") or {}).get("chunk_index", 0)),
    ):
        text = entry.get("text")
        if not text:
            continue

        results.append(
            SearchResult(
                chunk_id=str(entry.get("chunk_id", "")),
                text=text,
                distance=0.0,
                metadata=entry.get("metadata") or {},
            )
        )

    return results
