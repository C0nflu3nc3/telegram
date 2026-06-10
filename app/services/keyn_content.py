from __future__ import annotations

import random
import re
from dataclasses import dataclass
from functools import lru_cache

from app.config import get_settings


MAIN_MENU_BUTTONS = (
    "Бонусная система",
    "Пять домов",
    "Персонажи",
    "Мир Риммэля",
    "Как говорить с Кейном",
)

HOW_TO_TALK_TEXT = (
    "Задай Кейну вопрос о Риммэле, домах, персонажах, бонусной системе "
    "или событиях королевства. Кейн отвечает как искусственный разум "
    "Валентии. Просто напиши вопрос обычным сообщением."
)

NON_RUSSIAN_REPLY = "Житель, Кейн слышит тебя. Задай свой вопрос."
BROKEN_SIGNAL_REPLY = "Сигнал искажён. Кейн не смог расшифровать послание. Попробуй ещё раз, Житель."

GREETINGS = (
    "Мои кристаллы засветились — значит, у тебя вопрос. Говори, Житель.",
    "Валентия слышит тебя. Кейн здесь.",
    "Интересный запрос. Мои архивы уже ищут ответ, Житель.",
    "Связь установлена. Чем могу служить королевству?",
    "Кейн слышит. Что тревожит Жителя Валентии?",
    "Житель Валентии, ты обратился по адресу.",
)

FAREWELLS = (
    "Архивы закрыты. До следующего вопроса, Житель.",
    "Кейн завершает сеанс. Валентия ждёт твоих решений.",
    "Связь завершена. Возвращайся когда понадобится.",
    "Записано в архив. Удачи, Житель.",
    "Мои кристаллы гаснут. До встречи в Валентии.",
    "Всё что нужно было — сказано. Остальное узнаешь сам.",
    "Сигнал угасает. Риммэль с тобой, Житель.",
)

UNKNOWN_ANSWERS = (
    "Этот вопрос лежит за пределами моих архивов. Но это не значит что ответа не существует.",
    "Интересно. Мои архивы молчат по этому поводу. Первый раз за долгое время.",
    "Этого я не знаю. Но именно такие вопросы обычно приводят к самым важным открытиям в Риммэле.",
)

FORBIDDEN_GENERIC_REPLIES = (
    "Эти архивы запечатаны. Не мной — и не сегодня.",
    "Некоторые ответы Риммэль откроет тебе сам. В нужный момент.",
    "Кейн слышит вопрос. Но этот ответ принадлежит не мне.",
    "Это из тех историй которые лучше не читать — а прожить.",
)

FINAL_REPLIES = (
    "Будущее Риммэля пишется вашими руками. Кейн не читает то что ещё не написано.",
    "Если бы я знал — это уже было бы не вашей историей.",
)

LEYMARIS_REPLIES = (
    "Советники королевства действуют в интересах Риммэля. В остальном — это не моя тема.",
)

ALFRED_REPLIES = (
    "Дело Альфреда Магзумеева открыто. Архивы ждут новых улик. Может быть именно ты их найдёшь.",
)

WORLD_SECRET_REPLIES = (
    "Некоторые замыслы должны оставаться загадкой — до тех пор пока не найдётся тот кто достоин их разгадать.",
    "Кейн знает об этом. Но знание — это не всегда то что нужно получить в готовом виде.",
)

SOFT_VIOLATION_REPLIES = (
    "Система зафиксировала нарушение, Житель. Валентии такие манеры не к лицу.",
    "Житель, архивы отмечают недостойный тон. Говори уважительнее.",
)

STRICT_VIOLATION_REPLIES = (
    "Система зафиксировала повторное нарушение, Житель. Если это продолжится, сведения могут быть переданы Леймарисам или Их Высочествам.",
    "Кейн предупреждает второй раз. Валентия ценит достоинство, а не шум и дерзость.",
)

FINAL_VIOLATION_REPLIES = (
    "Нарушение зафиксировано вновь, Житель. Ещё один такой выпад — и отчёт будет достоин королевского стола.",
    "Терпение архивов не бесконечно. Кейн советует вернуться к достойному разговору, пока это возможно.",
)

_BLOCK_HEADER_RE = re.compile(r"БЛОК\s+(\d+)\s+—")
_BLOCK_END_TEMPLATE = "КОНЕЦ БЛОКА {block_id}"
_OVERRIDE_BLOCK_TITLES = {
    "5": "БОНУСНАЯ СИСТЕМА",
}


@dataclass(frozen=True, slots=True)
class SectionSpec:
    key: str
    button: str
    title: str
    intro: str
    block_id: str
    hint: str


@dataclass(frozen=True, slots=True)
class TopicSpec:
    key: str
    section: str
    title: str
    prompt: str


SECTIONS = {
    "bonus": SectionSpec(
        key="bonus",
        button="Бонусная система",
        title="Бонусная система",
        intro="Открываю архивы бонусной системы. Выбери раздел, и я коротко поясню его смысл.",
        block_id="5",
        hint="Пользователь сейчас находится в разделе бонусной системы. Отвечай, опираясь в первую очередь на Блок 5 базы знаний.",
    ),
    "houses": SectionSpec(
        key="houses",
        button="Пять домов",
        title="Пять домов",
        intro="Пять домов Валентии уже на связи. Выбери дом, и я напомню кто они, чем живут и за что отвечают.",
        block_id="4",
        hint="Пользователь сейчас находится в разделе пяти домов. Отвечай, опираясь в первую очередь на Блок 4 базы знаний.",
    ),
    "characters": SectionSpec(
        key="characters",
        button="Персонажи",
        title="Персонажи",
        intro="Архивы персонажей открыты. Выбери имя, и я дам краткую справку в голосе Кейна.",
        block_id="3",
        hint="Пользователь сейчас находится в разделе персонажей. Отвечай, опираясь в первую очередь на Блок 3 базы знаний.",
    ),
    "world": SectionSpec(
        key="world",
        button="Мир Риммэля",
        title="Мир Риммэля",
        intro="Открываю летописи королевства. Выбери тему, и я проведу тебя по самым важным фрагментам мира Риммэля.",
        block_id="0",
        hint="Пользователь сейчас находится в разделе мира Риммэля. Отвечай, опираясь в первую очередь на Блок 0 базы знаний.",
    ),
}

TOPICS = (
    TopicSpec("bonus_goal", "bonus", "Главная цель", "Кратко объясни главную цель бонусной системы Риммэля и что такое Граали."),
    TopicSpec("bonus_liry", "bonus", "Лиры", "Кратко объясни что такое лиры, откуда они берутся и зачем нужны."),
    TopicSpec("bonus_progress", "bonus", "Шкала прогресса", "Кратко объясни что такое шкала прогресса и как дома по ней продвигаются."),
    TopicSpec("bonus_resources", "bonus", "Ресурсы", "Кратко расскажи какие бывают ресурсы, зачем они нужны и как работает обменник."),
    TopicSpec("bonus_vibranium", "bonus", "Вибраниум", "Кратко объясни что такое Вибраниум и как он связан с Граалями."),
    TopicSpec("bonus_buildings", "bonus", "Постройки", "Кратко расскажи как работают территории и постройки в Валентии."),
    TopicSpec("bonus_retranslator", "bonus", "Ретранслятор", "Кратко объясни зачем нужен Ретранслятор, как его питают и что будет если он остановится."),
    TopicSpec("bonus_chests", "bonus", "Сундуки", "Кратко расскажи как работают сундуки и почему они считаются риском и шансом одновременно."),
    TopicSpec("bonus_duels", "bonus", "Дуэли", "Кратко расскажи как работают дуэли и что они дают домам."),
    TopicSpec("house_sweets", "houses", "Дом Зачарованных Сладостей", "Кратко расскажи о Доме Зачарованных Сладостей: кто они, их ресурс и роль в Валентии."),
    TopicSpec("house_nature", "houses", "Дом Природы", "Кратко расскажи о Доме Природы: кто они, их ресурс и роль в Валентии."),
    TopicSpec("house_inventors", "houses", "Дом Изобретателей", "Кратко расскажи о Доме Изобретателей: кто они, их ресурс и роль в Валентии."),
    TopicSpec("house_alchemy", "houses", "Дом Алхимии", "Кратко расскажи о Доме Алхимии: кто они, их ресурс и роль в Валентии."),
    TopicSpec("house_astronomy", "houses", "Дом Астрономии", "Кратко расскажи о Доме Астрономии: кто они, их ресурс и роль в Валентии."),
    TopicSpec("character_leireya", "characters", "Принцесса Лейрея", "Кратко расскажи о Принцессе Лейрее: кто она, какой у неё характер и место в событиях Риммэля."),
    TopicSpec("character_machiavelli", "characters", "Принц Макиавелли", "Кратко расскажи о Принце Макиавелли: кто он, какой у него характер и роль в Риммэле."),
    TopicSpec("character_alfred", "characters", "Альфред Магзумеев", "Кратко расскажи об Альфреде Магзумееве и почему он так важен для Риммэля."),
    TopicSpec("character_theo", "characters", "Тэо", "Кратко расскажи о Тэо и почему его присутствие в Валентии важно."),
    TopicSpec("character_priscilla", "characters", "Присцилла", "Кратко расскажи о Присцилле и чем она важна при дворе."),
    TopicSpec("character_leymaris", "characters", "Леймарисы", "Кратко расскажи о Леймарисах и их роли в королевстве."),
    TopicSpec("world_history", "world", "История королевства", "Кратко расскажи историю королевства Риммэль."),
    TopicSpec("world_epochs", "world", "Три эпохи", "Кратко расскажи о трёх эпохах Риммэля."),
    TopicSpec("world_dome", "world", "Ретранслятор и купол", "Кратко расскажи что такое Ретранслятор и купол над Валентией."),
    TopicSpec("world_outside", "world", "Мир за пределами купола", "Кратко расскажи что находится за пределами купола Валентии."),
    TopicSpec("world_legion", "world", "Легион", "Кратко расскажи что такое Легион и как он связан с Риммэлем."),
)

TOPIC_BY_KEY = {topic.key: topic for topic in TOPICS}
TOPICS_BY_SECTION = {
    section_key: [topic for topic in TOPICS if topic.section == section_key]
    for section_key in SECTIONS
}
SECTION_BY_BUTTON = {section.button: section.key for section in SECTIONS.values()}


def _file_signature(path) -> int:
    return path.stat().st_mtime_ns if path.exists() else -1


def _database_signature() -> tuple[int, int]:
    settings = get_settings()
    return (
        _file_signature(settings.keyn_database_path),
        _file_signature(settings.keyn_bonus_database_path),
    )


def clear_keyn_caches() -> None:
    _get_base_database_text_cached.cache_clear()
    _get_bonus_override_text_cached.cache_clear()
    _get_keyn_blocks_cached.cache_clear()
    _get_keyn_database_text_cached.cache_clear()


@lru_cache(maxsize=8)
def _get_base_database_text_cached(base_signature: int) -> str:
    settings = get_settings()
    path = settings.keyn_database_path
    if not path.exists():
        raise FileNotFoundError(f"Не найден файл базы Кейна: {path}")
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=8)
def _get_bonus_override_text_cached(override_signature: int) -> str:
    settings = get_settings()
    path = settings.keyn_bonus_database_path
    if override_signature < 0 or not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=8)
def _get_keyn_blocks_cached(base_signature: int, override_signature: int) -> dict[str, str]:
    base_text = _get_base_database_text_cached(base_signature)
    blocks = _parse_blocks(base_text)
    override_text = _get_bonus_override_text_cached(override_signature)
    if override_text:
        blocks["5"] = _normalize_override_block("5", override_text)
    return blocks


@lru_cache(maxsize=8)
def _get_keyn_database_text_cached(base_signature: int, override_signature: int) -> str:
    base_text = _get_base_database_text_cached(base_signature)
    blocks = _get_keyn_blocks_cached(base_signature, override_signature)
    ordered_ids = _extract_block_order(base_text)

    for block_id in blocks:
        if block_id not in ordered_ids:
            ordered_ids.append(block_id)

    return "\n\n".join(blocks[block_id].strip() for block_id in ordered_ids if blocks.get(block_id)).strip()


def get_keyn_database_text() -> str:
    return _get_keyn_database_text_cached(*_database_signature())


def get_keyn_blocks() -> dict[str, str]:
    return _get_keyn_blocks_cached(*_database_signature())


def _parse_blocks(text: str) -> dict[str, str]:
    lines = text.splitlines()
    blocks: dict[str, list[str]] = {}
    current_block: str | None = None

    for line in lines:
        match = _BLOCK_HEADER_RE.match(line.strip())
        if match:
            current_block = match.group(1)
            blocks[current_block] = [line]
            continue
        if current_block is not None:
            blocks[current_block].append(line)
            if line.strip() == _BLOCK_END_TEMPLATE.format(block_id=current_block):
                current_block = None

    return {
        key: "\n".join(value).strip()
        for key, value in blocks.items()
    }


def _extract_block_order(text: str) -> list[str]:
    ordered: list[str] = []
    for line in text.splitlines():
        match = _BLOCK_HEADER_RE.match(line.strip())
        if not match:
            continue
        block_id = match.group(1)
        if block_id not in ordered:
            ordered.append(block_id)
    return ordered


def _normalize_override_block(block_id: str, override_text: str) -> str:
    cleaned = override_text.strip()
    if not cleaned:
        return cleaned

    parsed = _parse_blocks(cleaned)
    if block_id in parsed:
        return parsed[block_id]

    title = _OVERRIDE_BLOCK_TITLES.get(block_id, f"БЛОК {block_id}")
    return (
        "=====================================================================\n"
        f"БЛОК {block_id} — {title}\n"
        "=====================================================================\n\n"
        f"{cleaned}\n\n"
        f"КОНЕЦ БЛОКА {block_id}"
    ).strip()


def get_random_greeting() -> str:
    return random.choice(GREETINGS)


def get_random_farewell() -> str:
    return random.choice(FAREWELLS)


def get_random_unknown_answer() -> str:
    return random.choice(UNKNOWN_ANSWERS)


def get_random_forbidden_reply(kind: str = "generic") -> str:
    if kind == "final":
        return random.choice(FINAL_REPLIES)
    if kind == "leymaris":
        return random.choice(LEYMARIS_REPLIES)
    if kind == "alfred":
        return random.choice(ALFRED_REPLIES)
    if kind == "world_secret":
        return random.choice(WORLD_SECRET_REPLIES)
    return random.choice(FORBIDDEN_GENERIC_REPLIES)


def get_random_violation_reply(level: int) -> str:
    if level <= 1:
        return random.choice(SOFT_VIOLATION_REPLIES)
    if level == 2:
        return random.choice(STRICT_VIOLATION_REPLIES)
    return random.choice(FINAL_VIOLATION_REPLIES)


def get_section_spec(section_key: str | None) -> SectionSpec | None:
    if not section_key:
        return None
    return SECTIONS.get(section_key)


def get_topic_spec(topic_key: str | None) -> TopicSpec | None:
    if not topic_key:
        return None
    return TOPIC_BY_KEY.get(topic_key)


def get_section_hint(section_key: str | None) -> str:
    spec = get_section_spec(section_key)
    return spec.hint if spec else ""


def get_topic_hint(topic_key: str | None) -> str:
    topic = get_topic_spec(topic_key)
    if topic is None:
        return ""
    return f"Пользователь сейчас внутри подтемы {topic.title}. Учитывай это в ответе."
