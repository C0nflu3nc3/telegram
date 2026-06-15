from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.services.keyn_repository import BONUS_DATABASE_FILENAME, DATABASE_DIR, INTERFACE_DIR, LOGIC_DIR


@dataclass(frozen=True, slots=True)
class ManagedTextFile:
    key: str
    command: str
    source_kind: str
    filename: str
    title: str
    description: str


MANAGED_TEXT_FILES = (
    ManagedTextFile(
        key="history_db",
        command="load_history",
        source_kind="database",
        filename="kb_00_history_rimmel.txt",
        title="истории Риммэля",
        description="Основная историческая база Риммэля.",
    ),
    ManagedTextFile(
        key="kayn_db",
        command="load_kayn",
        source_kind="database",
        filename="kb_01_kayne_personality_and_voice.txt",
        title="базы о Кейне",
        description="Личность, голос и характер Кейна.",
    ),
    ManagedTextFile(
        key="characters_db",
        command="load_characters",
        source_kind="database",
        filename="kb_03_characters_rimmel.txt",
        title="базы персонажей",
        description="Персонажи Риммэля и их описания.",
    ),
    ManagedTextFile(
        key="houses_db",
        command="load_houses",
        source_kind="database",
        filename="kb_04_five_houses_valentia.txt",
        title="базы пяти домов",
        description="Пять домов Валентии.",
    ),
    ManagedTextFile(
        key="bonus_db",
        command="load_bonus",
        source_kind="database",
        filename="kb_05_bonus_system_rimmel.txt",
        title="бонусной системы",
        description="Лиры, Граали, прогресс, ресурсы и правила бонусной системы.",
    ),
    ManagedTextFile(
        key="logic_core",
        command="load_logic_core",
        source_kind="logic",
        filename="logic_00_core_behavior_and_system_prompt.txt",
        title="ядра логики Кейна",
        description="Системный промпт, стиль, приветствия и прощания.",
    ),
    ManagedTextFile(
        key="logic_forbidden",
        command="load_logic_forbidden",
        source_kind="logic",
        filename="logic_01_forbidden_topics_and_safe_exits.txt",
        title="запретных тем",
        description="Запретные темы и фразы-уходы.",
    ),
    ManagedTextFile(
        key="logic_edge",
        command="load_logic_edge",
        source_kind="logic",
        filename="logic_02_edge_cases_and_unexpected_questions.txt",
        title="нестандартных вопросов",
        description="Edge-cases, личные вопросы, оффтоп и провокации.",
    ),
    ManagedTextFile(
        key="logic_rules",
        command="load_rules",
        source_kind="logic",
        filename="logic_03_game_rules_for_script.txt",
        title="правил игры",
        description="Формальные игровые правила для сценариев и ответов.",
    ),
    ManagedTextFile(
        key="logic_flow",
        command="load_flow",
        source_kind="logic",
        filename="logic_04_bot_flow_for_codex.txt",
        title="технического flow",
        description="Техническая логика и приоритеты ответа бота.",
    ),
    ManagedTextFile(
        key="interface_menu",
        command="load_menu",
        source_kind="interface",
        filename="buttons_00_start_menu.txt",
        title="меню и кнопок",
        description="Стартовый текст и структура меню.",
    ),
    ManagedTextFile(
        key="interface_callbacks",
        command="load_callbacks",
        source_kind="interface",
        filename="buttons_01_callbacks_map.txt",
        title="callback-карты",
        description="Соответствие кнопок, callback и файлов базы.",
    ),
)

MANAGED_TEXT_FILE_BY_KEY = {item.key: item for item in MANAGED_TEXT_FILES}
MANAGED_TEXT_FILE_BY_COMMAND = {item.command: item for item in MANAGED_TEXT_FILES}
MANAGED_TEXT_COMMANDS = tuple(item.command for item in MANAGED_TEXT_FILES)


def get_managed_text_file_by_key(key: str | None) -> ManagedTextFile | None:
    if not key:
        return None
    return MANAGED_TEXT_FILE_BY_KEY.get(key)


def get_managed_text_file_by_command(command: str | None) -> ManagedTextFile | None:
    if not command:
        return None
    return MANAGED_TEXT_FILE_BY_COMMAND.get(command)


def get_managed_text_file_path(item: ManagedTextFile) -> Path:
    settings = get_settings()

    if item.source_kind == "database":
        if item.filename == BONUS_DATABASE_FILENAME:
            return settings.keyn_bonus_database_path
        if item.filename == settings.keyn_database_path.name:
            return settings.keyn_database_path
        return DATABASE_DIR / item.filename
    if item.source_kind == "logic":
        return LOGIC_DIR / item.filename
    if item.source_kind == "interface":
        return INTERFACE_DIR / item.filename
    raise ValueError(f"Unknown source kind: {item.source_kind}")


def render_commands_guide() -> str:
    lines = [
        "Команды бота",
        "===========",
        "",
        "Пользовательские команды:",
        "/start — запустить бота и открыть главное меню.",
        "/help — краткая помощь по использованию.",
        "/whoami — показать свой user_id и статус админа.",
        "/cancel — отменить режим загрузки txt-файла.",
        "",
        "Админ-команды обновления txt:",
    ]

    for item in MANAGED_TEXT_FILES:
        lines.append(f"/{item.command} — обновить {item.title} ({item.filename}).")

    lines.extend(
        [
            "",
            "Как загружать:",
            "1. Введи нужную /load_команду.",
            "2. Отправь новый TXT-файл или просто текст сообщением.",
            "3. Бот перезапишет только выбранный файл и сбросит кеш знаний.",
        ]
    )
    return "\n".join(lines).strip() + "\n"
