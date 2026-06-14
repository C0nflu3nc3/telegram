from __future__ import annotations

import random
from dataclasses import dataclass

from app.services.keyn_repository import (
    clear_repository_caches,
    ensure_split_package_ready,
    get_full_context,
    get_section_text,
    get_sections_text,
)


MAIN_MENU_BUTTONS = (
    "📜 История Риммэля",
    "🤖 Кто такой Кейн",
    "👑 Персонажи",
    "🏰 Пять домов",
    "💰 Бонусная система",
    "⚙️ Правила игры",
    "❓ Задать вопрос Кейну",
)
ASK_DIRECTLY_BUTTON = MAIN_MENU_BUTTONS[6]

START_MENU_TEXT = "Ты можешь спросить Кейна свободно или открыть один из разделов ниже."
HOW_TO_TALK_TEXT = (
    "Задай Кейну вопрос свободным сообщением или открой нужный раздел кнопками. "
    "Он отвечает только в мире Риммэля: по истории, персонажам, домам, бонусной системе и правилам игры."
)

NON_RUSSIAN_REPLY = "Житель, Кейн слышит тебя. Задай свой вопрос."
BROKEN_SIGNAL_REPLY = "Сигнал искажён. Кейн не смог расшифровать послание. Попробуй ещё раз, Житель."

GREETINGS = (
    "Мои кристаллы засветились — значит, у тебя вопрос. Говори, Житель.",
    "Валентия слышит тебя. Кейн здесь.",
    "Интересный запрос. Мои архивы уже ищут ответ, Житель.",
    "Связь установлена. Чем могу служить королевству?",
    "Кейн слышит. Что тревожит жителя Валентии?",
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


@dataclass(frozen=True, slots=True)
class SectionSpec:
    key: str
    button: str
    title: str
    intro: str
    source_kind: str
    source_filename: str


@dataclass(frozen=True, slots=True)
class TopicSpec:
    key: str
    section: str
    title: str
    prompt: str
    source_kind: str
    source_filename: str
    headings: tuple[str, ...]


SECTIONS = {
    "history": SectionSpec(
        key="history",
        button="📜 История Риммэля",
        title="История Риммэля",
        intro="Летописи Риммэля раскрыты. Выбери, какой след прошлого тебе нужен, Житель.",
        source_kind="database",
        source_filename="kb_00_history_rimmel.txt",
    ),
    "kayn": SectionSpec(
        key="kayn",
        button="🤖 Кто такой Кейн",
        title="Кто такой Кейн",
        intro="Спрашивай о самом Кейне. Я открою ровно столько, сколько архивам позволено.",
        source_kind="database",
        source_filename="kb_01_kayne_personality_and_voice.txt",
    ),
    "characters": SectionSpec(
        key="characters",
        button="👑 Персонажи",
        title="Персонажи",
        intro="Имена двора и тех, кто меняет судьбу Риммэля, уже перед тобой.",
        source_kind="database",
        source_filename="kb_03_characters_rimmel.txt",
    ),
    "houses": SectionSpec(
        key="houses",
        button="🏰 Пять домов",
        title="Пять домов",
        intro="Пять домов Валентии готовы к представлению. Выбери тот, чей след тебе интересен.",
        source_kind="database",
        source_filename="kb_04_five_houses_valentia.txt",
    ),
    "bonus": SectionSpec(
        key="bonus",
        button="💰 Бонусная система",
        title="Бонусная система",
        intro="Открываю расчётные архивы Валентии. Здесь всё про лиры, Граали, прогресс и силу домов.",
        source_kind="database",
        source_filename="kb_05_bonus_system_rimmel.txt",
    ),
    "rules": SectionSpec(
        key="rules",
        button="⚙️ Правила игры",
        title="Правила игры",
        intro="Формальные правила Большого совета перед тобой. Выбери, что именно разобрать.",
        source_kind="logic",
        source_filename="logic_03_game_rules_for_script.txt",
    ),
}

TOPICS = (
    TopicSpec(
        "history_age",
        "history",
        "Сколько лет королевству",
        "Кратко расскажи, сколько лет королевству Риммэль и почему эта цифра важна.",
        "database",
        "kb_00_history_rimmel.txt",
        ("СКОЛЬКО ЛЕТ КОРОЛЕВСТВУ",),
    ),
    TopicSpec(
        "history_founder",
        "history",
        "Кто основал Риммэль",
        "Кратко объясни, кто основал Риммэль и какую роль это сыграло в судьбе королевства.",
        "database",
        "kb_00_history_rimmel.txt",
        ("КТО ОСНОВАЛ РИММЭЛЬ",),
    ),
    TopicSpec(
        "history_epochs",
        "history",
        "Три эпохи Риммэля",
        "Кратко перескажи три эпохи Риммэля и чем они отличаются друг от друга.",
        "database",
        "kb_00_history_rimmel.txt",
        ("ТРИ ЭПОХИ РИММЭЛЯ",),
    ),
    TopicSpec(
        "history_retranslator",
        "history",
        "Ретранслятор и купол",
        "Кратко расскажи, что такое энергетический ретранслятор и купол над Валентией.",
        "database",
        "kb_00_history_rimmel.txt",
        ("ЭНЕРГЕТИЧЕСКИЙ РЕТРАНСЛЯТОР И КУПОЛ",),
    ),
    TopicSpec(
        "history_outside",
        "history",
        "Мир за пределами купола",
        "Кратко расскажи, что находится за пределами купола и почему это опасно.",
        "database",
        "kb_00_history_rimmel.txt",
        ("МИР ЗА ПРЕДЕЛАМИ КУПОЛА",),
    ),
    TopicSpec(
        "history_rulers",
        "history",
        "Правители Риммэля",
        "Кратко расскажи, кто правит Риммэлем и как устроена эта власть.",
        "database",
        "kb_00_history_rimmel.txt",
        ("ПРАВИТЕЛИ РИММЭЛЯ",),
    ),
    TopicSpec(
        "history_legion",
        "history",
        "Легион",
        "Кратко расскажи, что такое Легион и как он связан с Риммэлем.",
        "database",
        "kb_00_history_rimmel.txt",
        ("ЛЕГИОН — СОЮЗНОЕ ГОСУДАРСТВО",),
    ),
    TopicSpec(
        "kayn_identity",
        "kayn",
        "Кто такой Кейн",
        "Кратко объясни, кто такой Кейн и какое место он занимает в мире Риммэля.",
        "database",
        "kb_01_kayne_personality_and_voice.txt",
        ("КТО ТАКОЙ КЕЙН",),
    ),
    TopicSpec(
        "kayn_favorite_topics",
        "kayn",
        "Любимые темы Кейна",
        "Кратко расскажи, о чём Кейн любит говорить больше всего.",
        "database",
        "kb_01_kayne_personality_and_voice.txt",
        ("ЛЮБИМЫЕ ТЕМЫ КЕЙНА",),
    ),
    TopicSpec(
        "kayn_speech",
        "kayn",
        "Как Кейн говорит",
        "Кратко опиши, как Кейн говорит, приветствует, прощается и ведёт себя в разговоре.",
        "logic",
        "logic_00_core_behavior_and_system_prompt.txt",
        ("СТИЛЬ, ПРИВЕТСТВИЯ, ПРОЩАНИЯ, НЕЗНАНИЕ",),
    ),
    TopicSpec(
        "kayn_relationships",
        "kayn",
        "Отношение Кейна к персонажам",
        "Кратко расскажи, как Кейн относится к персонажам и жителям Риммэля.",
        "database",
        "kb_01_kayne_personality_and_voice.txt",
        ("ОТНОШЕНИЕ К ПЕРСОНАЖАМ",),
    ),
    TopicSpec(
        "char_leyreya",
        "characters",
        "Принцесса Лейрея",
        "Кратко расскажи о Принцессе Лейрее.",
        "database",
        "kb_03_characters_rimmel.txt",
        ("ПРИНЦЕССА ЛЕЙРЕЯ",),
    ),
    TopicSpec(
        "char_machiavelli",
        "characters",
        "Принц Макиавелли",
        "Кратко расскажи о Принце Макиавелли.",
        "database",
        "kb_03_characters_rimmel.txt",
        ("ПРИНЦ МАКИАВЕЛЛИ",),
    ),
    TopicSpec(
        "char_alfred",
        "characters",
        "Альфред Магзумеев",
        "Кратко расскажи об Альфреде Магзумееве.",
        "database",
        "kb_03_characters_rimmel.txt",
        ("АЛЬФРЕД МАГЗУМЕЕВ",),
    ),
    TopicSpec(
        "char_teo",
        "characters",
        "Тэо",
        "Кратко расскажи о Тэо.",
        "database",
        "kb_03_characters_rimmel.txt",
        ("ТЭО",),
    ),
    TopicSpec(
        "char_priscilla",
        "characters",
        "Присцилла",
        "Кратко расскажи о Присцилле.",
        "database",
        "kb_03_characters_rimmel.txt",
        ("ПРИСЦИЛЛА",),
    ),
    TopicSpec(
        "char_leymarises",
        "characters",
        "Леймарисы",
        "Кратко расскажи о Леймарисах.",
        "database",
        "kb_03_characters_rimmel.txt",
        ("ЛЕЙМАРИСЫ",),
    ),
    TopicSpec(
        "houses_general",
        "houses",
        "Общее о домах",
        "Кратко объясни, как устроены пять домов Валентии и чем они отличаются.",
        "database",
        "kb_04_five_houses_valentia.txt",
        ("ОБЩЕЕ О ДОМАХ",),
    ),
    TopicSpec(
        "house_sweets",
        "houses",
        "Дом Зачарованных Сладостей",
        "Кратко расскажи о Доме Зачарованных Сладостей.",
        "database",
        "kb_04_five_houses_valentia.txt",
        ("ДОМ ЗАЧАРОВАННЫХ СЛАДОСТЕЙ",),
    ),
    TopicSpec(
        "house_nature",
        "houses",
        "Дом Природы",
        "Кратко расскажи о Доме Природы.",
        "database",
        "kb_04_five_houses_valentia.txt",
        ("ДОМ ПРИРОДЫ",),
    ),
    TopicSpec(
        "house_inventors",
        "houses",
        "Дом Изобретателей",
        "Кратко расскажи о Доме Изобретателей.",
        "database",
        "kb_04_five_houses_valentia.txt",
        ("ДОМ ИЗОБРЕТАТЕЛЕЙ",),
    ),
    TopicSpec(
        "house_alchemy",
        "houses",
        "Дом Алхимии",
        "Кратко расскажи о Доме Алхимии.",
        "database",
        "kb_04_five_houses_valentia.txt",
        ("ДОМ АЛХИМИИ",),
    ),
    TopicSpec(
        "house_astronomy",
        "houses",
        "Дом Астрономии",
        "Кратко расскажи о Доме Астрономии.",
        "database",
        "kb_04_five_houses_valentia.txt",
        ("ДОМ АСТРОНОМИИ",),
    ),
    TopicSpec(
        "houses_danger",
        "houses",
        "Опасность за куполом",
        "Кратко объясни, какая опасность скрыта за куполом Валентии.",
        "database",
        "kb_04_five_houses_valentia.txt",
        ("ОБ ОПАСНОСТИ ЗА КУПОЛОМ",),
    ),
    TopicSpec(
        "bonus_goal",
        "bonus",
        "Главная цель",
        "Кратко объясни главную цель бонусной системы.",
        "database",
        "kb_05_bonus_system_rimmel.txt",
        ("ГЛАВНАЯ ЦЕЛЬ",),
    ),
    TopicSpec(
        "bonus_places",
        "bonus",
        "Два главных места",
        "Кратко расскажи о двух главных местах бонусной системы и зачем они нужны.",
        "database",
        "kb_05_bonus_system_rimmel.txt",
        ("ДВА ГЛАВНЫХ МЕСТА",),
    ),
    TopicSpec(
        "bonus_lira",
        "bonus",
        "Лиры",
        "Кратко объясни, что такое лиры и как они работают.",
        "database",
        "kb_05_bonus_system_rimmel.txt",
        ("ЛИРЫ — ВАЛЮТА КОРОЛЕВСТВА",),
    ),
    TopicSpec(
        "bonus_progress",
        "bonus",
        "Шкала прогресса",
        "Кратко расскажи, как работает шкала прогресса.",
        "database",
        "kb_05_bonus_system_rimmel.txt",
        ("ШКАЛА ПРОГРЕССА",),
    ),
    TopicSpec(
        "bonus_resources",
        "bonus",
        "Ресурсы",
        "Кратко объясни, какие бывают ресурсы и зачем они нужны.",
        "database",
        "kb_05_bonus_system_rimmel.txt",
        ("РЕСУРСЫ",),
    ),
    TopicSpec(
        "bonus_vibranium",
        "bonus",
        "Вибраниум",
        "Кратко объясни, что такое Вибраниум и как он связан с Граалями.",
        "database",
        "kb_05_bonus_system_rimmel.txt",
        ("ВИБРАНИУМ",),
    ),
    TopicSpec(
        "bonus_buildings",
        "bonus",
        "Карта и постройки",
        "Кратко расскажи о карте Валентии, территориях и постройках.",
        "database",
        "kb_05_bonus_system_rimmel.txt",
        ("КАРТА ВАЛЕНТИИ И ПОСТРОЙКИ",),
    ),
    TopicSpec(
        "bonus_retranslator",
        "bonus",
        "Ретранслятор",
        "Кратко объясни, как работает энергетический ретранслятор в бонусной системе.",
        "database",
        "kb_05_bonus_system_rimmel.txt",
        ("ЭНЕРГЕТИЧЕСКИЙ РЕТРАНСЛЯТОР",),
    ),
    TopicSpec(
        "bonus_chests",
        "bonus",
        "Сундуки",
        "Кратко расскажи, как работают сундуки.",
        "database",
        "kb_05_bonus_system_rimmel.txt",
        ("СУНДУКИ",),
    ),
    TopicSpec(
        "bonus_orders",
        "bonus",
        "Доска заказов",
        "Кратко расскажи, как работает доска заказов.",
        "database",
        "kb_05_bonus_system_rimmel.txt",
        ("ДОСКА ЗАКАЗОВ",),
    ),
    TopicSpec(
        "bonus_duels",
        "bonus",
        "Дуэли",
        "Кратко расскажи, как устроены дуэли между домами.",
        "database",
        "kb_05_bonus_system_rimmel.txt",
        ("ДУЭЛИ",),
    ),
    TopicSpec(
        "bonus_management",
        "bonus",
        "Управление королевством",
        "Кратко расскажи, как дома управляют королевством и что на это влияет.",
        "database",
        "kb_05_bonus_system_rimmel.txt",
        ("УПРАВЛЕНИЕ КОРОЛЕВСТВОМ",),
    ),
    TopicSpec(
        "rules_grail",
        "rules",
        "Как получить Грааль",
        "Кратко объясни, как получить Грааль по правилам игры.",
        "logic",
        "logic_03_game_rules_for_script.txt",
        ("ВАЛЮТА И ПОБЕДА",),
    ),
    TopicSpec(
        "rules_exchange",
        "rules",
        "Как работает обменник",
        "Кратко объясни, как работает обменник.",
        "logic",
        "logic_03_game_rules_for_script.txt",
        ("ОБМЕННИК",),
    ),
    TopicSpec(
        "rules_vibranium",
        "rules",
        "Как крафтить Вибраниум",
        "Кратко объясни, как крафтить Вибраниум.",
        "logic",
        "logic_03_game_rules_for_script.txt",
        ("ВИБРАНИУМ",),
    ),
    TopicSpec(
        "rules_buildings",
        "rules",
        "Как строить постройки",
        "Кратко объясни, как строить постройки.",
        "logic",
        "logic_03_game_rules_for_script.txt",
        ("ПОСТРОЙКИ",),
    ),
    TopicSpec(
        "rules_retranslator",
        "rules",
        "Как платить в Ретранслятор",
        "Кратко объясни, как дома платят в Ретранслятор.",
        "logic",
        "logic_03_game_rules_for_script.txt",
        ("РЕТРАНСЛЯТОР",),
    ),
    TopicSpec(
        "rules_penalties",
        "rules",
        "Какие штрафы бывают",
        "Кратко объясни, какие штрафы бывают по правилам игры.",
        "logic",
        "logic_03_game_rules_for_script.txt",
        ("РЕТРАНСЛЯТОР", "ДУЭЛИ"),
    ),
)

TOPIC_BY_KEY = {topic.key: topic for topic in TOPICS}
TOPICS_BY_SECTION = {
    section_key: tuple(topic for topic in TOPICS if topic.section == section_key)
    for section_key in SECTIONS
}
SECTION_BY_BUTTON = {section.button: section.key for section in SECTIONS.values()}


def clear_keyn_caches() -> None:
    clear_repository_caches()


def ensure_keyn_ready() -> None:
    ensure_split_package_ready()


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


def get_topic_context(topic_key: str) -> str:
    topic = get_topic_spec(topic_key)
    if topic is None:
        return ""
    return get_sections_text(topic.source_kind, topic.source_filename, topic.headings)


def get_section_context(section_key: str) -> str:
    section = get_section_spec(section_key)
    if section is None:
        return ""

    parts: list[str] = []
    for topic in TOPICS_BY_SECTION.get(section_key, ()):  # pragma: no branch
        context = get_topic_context(topic.key)
        if context and context not in parts:
            parts.append(context)

    if not parts:
        parts.append(get_full_context(section.source_kind, section.source_filename))

    return "\n\n".join(parts).strip()


def get_core_system_instruction() -> str:
    text = get_section_text(
        "logic",
        "logic_00_core_behavior_and_system_prompt.txt",
        "СИСТЕМНАЯ ИНСТРУКЦИЯ ИЗ ИСХОДНИКА",
    )
    return text or get_full_context("logic", "logic_00_core_behavior_and_system_prompt.txt")


def get_forbidden_logic_text() -> str:
    return get_full_context("logic", "logic_01_forbidden_topics_and_safe_exits.txt")


def get_edge_logic_text() -> str:
    return get_full_context("logic", "logic_02_edge_cases_and_unexpected_questions.txt")


def get_game_rules_text() -> str:
    return get_full_context("logic", "logic_03_game_rules_for_script.txt")
