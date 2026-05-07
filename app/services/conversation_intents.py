from __future__ import annotations

import logging
import random
import re
from difflib import SequenceMatcher
from functools import lru_cache

from app.config import get_settings
from app.services.embeddings import get_openai_client
from app.services.no_knowledge import get_random_nonsense_message

logger = logging.getLogger(__name__)

GREETING_RESPONSES = (
    "Приветствую тебя, юный странник. Что бы ты хотел узнать?",
    "Рад видеть тебя у свитков знания, юный странник. О чем ты желаешь спросить?",
    "Привет тебе, юный странник. Какую тайну ты хочешь раскрыть сегодня?",
    "Добро пожаловать, юный странник. Какой ответ ты ищешь в этот час?",
    "Мир тебе, юный странник. Что ты хотел бы узнать из хранимого знания?",
)
PERSONAL_RESPONSES = (
    "Не трать время на столь ненужные и пустые вопросы, юный странник. Лучше спроси о том, что действительно скрыто в свитках знания.",
    "Юный странник, не растрачивай слова на пустое. Направь вопрос туда, где знание может принести тебе пользу.",
    "Оставь праздное любопытство, юный странник. Лучше спроси о том, что ведет к сути, а не к пустому разговору.",
    "Не ищи во мне предмета для пустой беседы, юный странник. Спроси лучше о том, что сокрыто в знаниях.",
    "Юный странник, не стоит терять время на вопросы без пользы. Обратись лучше к тому, что действительно важно.",
)

_SHORT_GREETING_WORDS = {
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
    "куку",
    "хай",
    "хелло",
    "hello",
    "hi",
    "йо",
    "дратути",
    "дарова",
    "вечерочек",
}
_GREETING_STEMS = ("прив", "здрав", "здар", "салам", "салем", "салют", "хай", "хелл", "даров", "дратут")
_SECOND_PERSON_MARKERS = (
    "ты",
    "тебя",
    "тебе",
    "тобой",
    "тобою",
    "твой",
    "твое",
    "твоя",
    "твои",
    "бот",
)
_PERSONAL_MARKERS = (
    "чувств",
    "зовут",
    "лет",
    "жив",
    "настроен",
    "дела",
    "личн",
    "нравит",
    "одинок",
    "имя",
)
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
    "чей",
    "чья",
    "чье",
    "чьи",
    "можно",
    "ли",
}
_REQUEST_STEMS = (
    "расска",
    "объяс",
    "опиш",
    "повед",
    "скажи",
    "подскаж",
    "поясн",
    "уточн",
    "назов",
    "дай",
    "перечисл",
    "напомн",
)
_FILLER_WORDS = {
    "ага",
    "ааа",
    "блин",
    "бля",
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
    "такое",
    "такой",
    "это",
    "ээ",
    "эээ",
    "хз",
}
_MAX_CLASSIFIER_WORDS = 12
_MAX_CLASSIFIER_CHARS = 96

# Pre-compiled regex patterns (avoids recompilation on every call)
_RE_NORMALIZE_CHARS = re.compile(r"[^\w\s!?.,-]")
_RE_NORMALIZE_SPACES = re.compile(r"\s{2,}")
_RE_GREETING = re.compile(
    r"^(добр(?:ый|ое)\s+(?:день|вечер|утро)|привет(?:ствую)?|здравствуй(?:те)?|салам|салют|ку|хай)\b",
    re.IGNORECASE,
)
_PERSONAL_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bкак\s+ты\b",
        r"\bкак\s+дела\b",
        r"\bкак\s+себя\s+чувствуешь\b",
        r"\bчто\s+ты\s+чувствуешь\b",
        r"\bкто\s+ты\b",
        r"\bкак\s+тебя\s+зовут\b",
        r"\bсколько\s+тебе\s+лет\b",
        r"\bты\s+жив(?:ой|ая)\b",
        r"\bтебе\s+хорошо\b",
        r"\bтебе\s+нравится\b",
        r"\bу\s+тебя\s+есть\s+чувства\b",
        r"\bтебе\s+одиноко\b",
    )
]


def detect_conversation_intent(text: str) -> str | None:
    normalized = _normalize_text(text)
    if not normalized:
        return None

    words = normalized.split()

    if _is_greeting_by_heuristic(words):
        return random.choice(GREETING_RESPONSES)

    if _is_personal_by_heuristic(normalized, words):
        return random.choice(PERSONAL_RESPONSES)

    if _is_nonsense_by_heuristic(normalized, words):
        return get_random_nonsense_message()

    if len(words) > _MAX_CLASSIFIER_WORDS or len(normalized) > _MAX_CLASSIFIER_CHARS:
        return None

    intent = _detect_intent_via_api(normalized)
    if intent == "greeting":
        return random.choice(GREETING_RESPONSES)
    if intent == "personal":
        return random.choice(PERSONAL_RESPONSES)
    if intent == "nonsense":
        return get_random_nonsense_message()

    return None


def _normalize_text(text: str) -> str:
    normalized = text.strip().lower().replace("ё", "е")
    normalized = _RE_NORMALIZE_CHARS.sub(" ", normalized)
    normalized = _RE_NORMALIZE_SPACES.sub(" ", normalized)
    return normalized.strip()


def _is_greeting_by_heuristic(words: list[str]) -> bool:
    if not words or len(words) > 6:
        return False

    for word in words:
        if word in _SHORT_GREETING_WORDS:
            return True
        if any(word.startswith(stem) for stem in _GREETING_STEMS):
            return True
        if _fuzzy_matches(word, _SHORT_GREETING_WORDS, threshold=0.76):
            return True

    return _RE_GREETING.search(" ".join(words)) is not None


def _is_personal_by_heuristic(normalized: str, words: list[str]) -> bool:
    if not _has_personal_focus(normalized, words):
        return False
    return any(p.search(normalized) for p in _PERSONAL_PATTERNS)


def _has_personal_focus(normalized: str, words: list[str]) -> bool:
    if any(word in _SECOND_PERSON_MARKERS for word in words):
        return True
    return any(marker in normalized for marker in _PERSONAL_MARKERS)


def _is_nonsense_by_heuristic(normalized: str, words: list[str]) -> bool:
    if not words or _has_question_signal(normalized, words):
        return False

    # Single pass instead of three separate list comprehensions
    short_words, filler_words, meaningful_words = [], [], []
    for word in words:
        if word in _FILLER_WORDS:
            filler_words.append(word)
        elif len(word) > 2:
            meaningful_words.append(word)
        else:
            short_words.append(word)

    if len(words) <= 3 and len(meaningful_words) == 0:
        return True

    if len(words) <= 6 and len(meaningful_words) <= 1 and (len(filler_words) >= 2 or len(short_words) >= 2):
        return True

    if len(words) <= 8 and len(meaningful_words) >= 3 and not _has_request_signal(words):
        return True

    if len(words) <= 8 and _has_repeated_word_loop(words):
        return True

    return False


def _has_question_signal(normalized: str, words: list[str]) -> bool:
    if "?" in normalized:
        return True
    return any(word in _QUESTION_WORDS for word in words)


def _has_request_signal(words: list[str]) -> bool:
    return any(
        any(word.startswith(stem) for stem in _REQUEST_STEMS)
        for word in words
    )


def _has_repeated_word_loop(words: list[str]) -> bool:
    compact = [word for word in words if len(word) > 1]
    if len(compact) < 3:
        return False
    return len(set(compact)) <= max(1, len(compact) // 3)


def _fuzzy_matches(word: str, candidates: set[str], threshold: float) -> bool:
    if len(word) < 3:
        return False
    return any(SequenceMatcher(None, word, candidate).ratio() >= threshold for candidate in candidates)


@lru_cache(maxsize=512)
def _detect_intent_via_api(normalized_text: str) -> str | None:
    settings = get_settings()
    client = get_openai_client()
    instructions = (
        "Классифицируй короткое сообщение. "
        "Варианты: greeting, personal, nonsense, other. "
        "greeting = приветствие боту; personal = вопрос о самом боте; "
        "nonsense = бессвязная или непонятная реплика без ясного вопроса; "
        "other = любой осмысленный вопрос или просьба. "
        "Если есть понятный вопрос или просьба, выбирай other. "
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
    except Exception as e:
        logger.warning("Intent API call failed: %s", e)
        return None

    if label in {"greeting", "personal", "nonsense", "other"}:
        return label

    compact_label = re.sub(r"[^a-z]", "", label)
    if compact_label in {"greeting", "personal", "nonsense", "other"}:
        return compact_label

    return None
