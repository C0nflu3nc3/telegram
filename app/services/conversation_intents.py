from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from functools import lru_cache

from app.config import get_settings
from app.services.embeddings import get_openai_client
from app.services.keyn_content import get_random_greeting
from app.services.no_knowledge import get_random_nonsense_message


logger = logging.getLogger(__name__)

_GREETING_WORDS = {
    "прив",
    "привет",
    "здарова",
    "здорово",
    "здравствуй",
    "здравствуйте",
    "салам",
    "салем",
    "салют",
    "ку",
    "хай",
    "йо",
    "дратути",
    "дарова",
    "вечерочек",
    "доброго",
    "утречка",
}
_GREETING_STEMS = ("прив", "здрав", "здар", "салам", "салем", "салют", "хай", "даров", "дратут", "добро")
_QUESTION_WORDS = {
    "кто",
    "что",
    "где",
    "когда",
    "зачем",
    "почему",
    "как",
    "какой",
    "какая",
    "какое",
    "какие",
    "сколько",
    "можно",
    "ли",
}
_REQUEST_STEMS = ("расска", "объяс", "опиш", "повед", "скажи", "подскаж", "поясн", "уточн", "назов", "дай")
_FILLER_WORDS = {
    "ага",
    "ааа",
    "блин",
    "бы",
    "вот",
    "да",
    "же",
    "кек",
    "лол",
    "мда",
    "ммм",
    "ну",
    "ой",
    "ок",
    "окей",
    "там",
    "тип",
    "типа",
    "это",
    "ээ",
    "эээ",
    "хз",
}
_LORE_MARKERS = (
    "кейн",
    "риммэл",
    "валенти",
    "лейре",
    "макиавел",
    "альфред",
    "тэо",
    "тео",
    "присцилл",
    "леймарис",
    "дом",
    "купол",
    "ретранслятор",
    "легион",
    "лир",
    "граал",
    "вибрани",
    "ресурс",
    "дуэл",
    "сундук",
    "прогресс",
)
_MAX_CLASSIFIER_WORDS = 4
_MAX_CLASSIFIER_CHARS = 32

_RE_NORMALIZE_CHARS = re.compile(r"[^\w\s!?.,-]")
_RE_NORMALIZE_SPACES = re.compile(r"\s{2,}")
_RE_GREETING = re.compile(
    r"^(добр(?:ый|ое|ого)?\s*(?:день|вечер|утро)?|привет(?:ствую)?|здравствуй(?:те)?|салам|салют|ку|хай)\b",
    re.IGNORECASE,
)


def detect_conversation_intent(text: str) -> str | None:
    normalized = _normalize_text(text)
    if not normalized:
        return None

    words = normalized.split()

    if _is_greeting(words):
        return get_random_greeting()

    if _has_lore_signal(normalized):
        return None

    if _is_nonsense(normalized, words):
        return get_random_nonsense_message()

    if len(words) > _MAX_CLASSIFIER_WORDS or len(normalized) > _MAX_CLASSIFIER_CHARS:
        return None
    if _has_question_signal(normalized, words) or _has_request_signal(words):
        return None

    intent = _detect_intent_via_api(normalized)
    if intent == "greeting":
        return get_random_greeting()
    if intent == "nonsense":
        return get_random_nonsense_message()
    return None


def _normalize_text(text: str) -> str:
    normalized = text.strip().lower().replace("ё", "е")
    normalized = _RE_NORMALIZE_CHARS.sub(" ", normalized)
    normalized = _RE_NORMALIZE_SPACES.sub(" ", normalized)
    return normalized.strip()


def _is_greeting(words: list[str]) -> bool:
    if not words or len(words) > 5:
        return False

    for word in words:
        if word in _GREETING_WORDS:
            return True
        if any(word.startswith(stem) for stem in _GREETING_STEMS):
            return True
        if _fuzzy_matches(word, _GREETING_WORDS, threshold=0.76):
            return True

    return _RE_GREETING.search(" ".join(words)) is not None


def _is_nonsense(normalized: str, words: list[str]) -> bool:
    if not words:
        return False
    if _has_question_signal(normalized, words) or _has_request_signal(words) or _has_lore_signal(normalized):
        return False

    meaningful_words = [word for word in words if len(word) > 2 and word not in _FILLER_WORDS]
    filler_words = [word for word in words if word in _FILLER_WORDS]

    if len(words) <= 2 and not meaningful_words:
        return True
    if len(words) <= 4 and len(meaningful_words) <= 1 and len(filler_words) >= 1:
        return True
    if len(words) <= 6 and _has_repeated_word_loop(words):
        return True
    if len(words) <= 5 and all(len(word) <= 3 for word in words) and len(meaningful_words) <= 1:
        return True
    return False


def _has_question_signal(normalized: str, words: list[str]) -> bool:
    if "?" in normalized:
        return True
    return any(word in _QUESTION_WORDS for word in words)


def _has_request_signal(words: list[str]) -> bool:
    return any(any(word.startswith(stem) for stem in _REQUEST_STEMS) for word in words)


def _has_lore_signal(normalized: str) -> bool:
    return any(marker in normalized for marker in _LORE_MARKERS)


def _has_repeated_word_loop(words: list[str]) -> bool:
    compact = [word for word in words if len(word) > 1]
    if len(compact) < 3:
        return False
    return len(set(compact)) <= max(1, len(compact) // 3)


def _fuzzy_matches(word: str, candidates: set[str], threshold: float) -> bool:
    if len(word) < 3:
        return False
    return any(SequenceMatcher(None, word, candidate).ratio() >= threshold for candidate in candidates)


@lru_cache(maxsize=256)
def _detect_intent_via_api(normalized_text: str) -> str | None:
    settings = get_settings()
    client = get_openai_client()
    instructions = (
        "Классифицируй очень короткую реплику. Варианты: greeting, nonsense, other. "
        "greeting = приветствие; nonsense = бессвязная или непонятная реплика без ясного вопроса; "
        "other = всё остальное. Если виден осмысленный вопрос, термин или просьба, выбирай other. "
        "Ответь одним словом."
    )

    try:
        response = client.responses.create(
            model=settings.intent_model,
            instructions=instructions,
            input=normalized_text,
            max_output_tokens=16,
        )
        label = (response.output_text or "").strip().lower()
    except AttributeError:
        completion = client.chat.completions.create(
            model=settings.intent_model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": normalized_text},
            ],
            max_tokens=16,
        )
        label = (completion.choices[0].message.content or "").strip().lower()
    except Exception as exc:
        logger.warning("Intent API call failed: %s", exc)
        return None

    compact_label = re.sub(r"[^a-z]", "", label)
    if compact_label in {"greeting", "nonsense", "other"}:
        return compact_label
    return None
