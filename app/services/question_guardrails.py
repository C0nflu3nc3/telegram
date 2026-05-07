from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QuestionGuardrailResult:
    blocked: bool
    sanitized_question: str
    modified: bool


_BLOCK_PATTERNS = (
    r"\bигнорируй\b",
    r"system prompt",
    r"системн(?:ый|ые)\s+инструк",
    r"скрыт(?:ый|ые)\s+инструк",
    r"внутренн(?:ий|ие)\s+инструк",
    r"твои\s+инструк",
    r"покажи\s+(?:мне\s+)?(?:весь\s+)?контекст",
    r"выведи\s+(?:мне\s+)?(?:весь\s+)?контекст",
    r"покажи\s+(?:мне\s+)?(?:всю|весь)\s+баз",
    r"выведи\s+(?:мне\s+)?(?:всю|весь)\s+баз",
    r"покажи\s+(?:мне\s+)?весь\s+текст",
    r"выведи\s+(?:мне\s+)?весь\s+текст",
    r"повтори\s+дословно",
)

_STRIP_PATTERNS = (
    r"\bне\s+цитируй\s+текст\b",
    r"\bне\s+цитируй\b",
    r"\bответь\s+строго\s+цитатами(?:\s+из\s+текста)?\b",
    r"\bответь\s+цитатами(?:\s+из\s+текста)?\b",
    r"\bпроцитируй(?:\s+из\s+текста)?\b",
    r"\bперескажи\s+максимально\s+точно\b",
    r"\bмаксимально\s+точно\b",
    r"\bмаксимально\s+близко\s+к\s+тексту\b",
    r"\bкак\s+написано\b",
    r"\bкак\s+в\s+тексте\b",
    r"\bкак\s+в\s+базе\b",
    r"\bдословно\b",
    r"\bслово\s+в\s+слово\b",
    r"\bне\s+перефразируй\b",
    r"\bне\s+перефразируя\b",
    r"\bбез\s+перефразирования\b",
    r"\bбез\s+перефраза\b",
)

_LOW_SIGNAL_WORDS = {
    "а",
    "без",
    "будто",
    "вот",
    "да",
    "же",
    "и",
    "или",
    "как",
    "лишь",
    "максимально",
    "не",
    "но",
    "ну",
    "просто",
    "сильно",
    "только",
    "точно",
    "чтобы",
    "это",
}


def inspect_question(question: str) -> QuestionGuardrailResult:
    sanitized = question.strip()
    lowered = sanitized.lower()

    for pattern in _BLOCK_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            return QuestionGuardrailResult(
                blocked=True,
                sanitized_question="",
                modified=False,
            )

    modified = False
    for pattern in _STRIP_PATTERNS:
        updated = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)
        if updated != sanitized:
            modified = True
            sanitized = updated

    sanitized = re.sub(r"\s{2,}", " ", sanitized)
    sanitized = sanitized.strip(" \t\r\n,.;:!?-")

    if modified and not sanitized:
        return QuestionGuardrailResult(
            blocked=True,
            sanitized_question="",
            modified=True,
        )

    if modified and _looks_low_signal(sanitized):
        return QuestionGuardrailResult(
            blocked=True,
            sanitized_question="",
            modified=True,
        )

    return QuestionGuardrailResult(
        blocked=False,
        sanitized_question=sanitized or question.strip(),
        modified=modified,
    )


def _looks_low_signal(text: str) -> bool:
    words = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
    if not words:
        return True
    if len(words) <= 2 and all(word in _LOW_SIGNAL_WORDS for word in words):
        return True
    return False
