from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import get_settings


ROOT_DIR = Path(__file__).resolve().parents[2]
DATABASE_DIR = ROOT_DIR / "database"
LOGIC_DIR = ROOT_DIR / "logic"
INTERFACE_DIR = ROOT_DIR / "interface"

DATABASE_FILES = (
    "kb_00_history_rimmel.txt",
    "kb_01_kayne_personality_and_voice.txt",
    "kb_03_characters_rimmel.txt",
    "kb_04_five_houses_valentia.txt",
    "kb_05_bonus_system_rimmel.txt",
)
LOGIC_FILES = (
    "logic_00_core_behavior_and_system_prompt.txt",
    "logic_01_forbidden_topics_and_safe_exits.txt",
    "logic_02_edge_cases_and_unexpected_questions.txt",
    "logic_03_game_rules_for_script.txt",
    "logic_04_bot_flow_for_codex.txt",
)
INTERFACE_FILES = (
    "buttons_00_start_menu.txt",
    "buttons_01_callbacks_map.txt",
)
BONUS_DATABASE_FILENAME = "kb_05_bonus_system_rimmel.txt"

_SECTION_UNDERLINE_RE = re.compile(r"^-{5,}$")
_NORMALIZE_RE = re.compile(r"[^a-zа-яё0-9]+", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class TextSection:
    title: str
    body: str

    def render(self) -> str:
        return f"{self.title}\n{self.body}".strip()


class SplitPackageNotReadyError(FileNotFoundError):
    pass


def clear_repository_caches() -> None:
    _read_text_cached.cache_clear()
    _get_sections_cached.cache_clear()


def ensure_split_package_ready() -> None:
    missing: list[str] = []
    for directory in (DATABASE_DIR, LOGIC_DIR, INTERFACE_DIR):
        if not directory.exists():
            missing.append(str(directory))

    for filename in DATABASE_FILES:
        path = resolve_source_path("database", filename)
        if not path.exists():
            missing.append(str(path))

    for filename in LOGIC_FILES:
        path = resolve_source_path("logic", filename)
        if not path.exists():
            missing.append(str(path))

    for filename in INTERFACE_FILES:
        path = resolve_source_path("interface", filename)
        if not path.exists():
            missing.append(str(path))

    if missing:
        listed = "\n".join(f"- {path}" for path in missing)
        raise SplitPackageNotReadyError(
            "Не хватает файлов split-пакета Кейна:\n"
            f"{listed}"
        )


def resolve_source_path(source_kind: str, filename: str) -> Path:
    if source_kind == "database":
        if filename == BONUS_DATABASE_FILENAME:
            configured = get_settings().keyn_bonus_database_path
            if configured.exists():
                return configured
        return DATABASE_DIR / filename
    if source_kind == "logic":
        return LOGIC_DIR / filename
    if source_kind == "interface":
        return INTERFACE_DIR / filename
    raise ValueError(f"Неизвестный тип источника: {source_kind}")


def read_source_text(source_kind: str, filename: str) -> str:
    path = resolve_source_path(source_kind, filename)
    return _read_text_cached(str(path), _signature(path))


def get_sections(source_kind: str, filename: str) -> tuple[TextSection, ...]:
    path = resolve_source_path(source_kind, filename)
    return _get_sections_cached(str(path), _signature(path))


def get_section_text(source_kind: str, filename: str, heading: str) -> str:
    normalized_heading = _normalize(heading)
    sections = get_sections(source_kind, filename)

    for section in sections:
        if _normalize(section.title) == normalized_heading:
            return section.render()

    for section in sections:
        if normalized_heading and normalized_heading in _normalize(section.title):
            return section.render()

    return ""


def get_sections_text(source_kind: str, filename: str, headings: tuple[str, ...] | list[str]) -> str:
    parts: list[str] = []
    for heading in headings:
        text = get_section_text(source_kind, filename, heading)
        if text and text not in parts:
            parts.append(text)
    return "\n\n".join(parts).strip()


def get_full_context(source_kind: str, filename: str) -> str:
    return read_source_text(source_kind, filename)


@lru_cache(maxsize=64)
def _read_text_cached(path_str: str, signature: int) -> str:
    path = Path(path_str)
    if signature < 0 or not path.exists():
        raise FileNotFoundError(f"Не найден файл Кейна: {path}")
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=64)
def _get_sections_cached(path_str: str, signature: int) -> tuple[TextSection, ...]:
    text = _read_text_cached(path_str, signature)
    return tuple(_parse_sections(text))


def _parse_sections(text: str) -> list[TextSection]:
    lines = text.splitlines()
    sections: list[TextSection] = []
    index = 0

    while index < len(lines):
        title = lines[index].strip()
        is_section_title = (
            bool(title)
            and index + 1 < len(lines)
            and _SECTION_UNDERLINE_RE.fullmatch(lines[index + 1].strip()) is not None
        )
        if not is_section_title:
            index += 1
            continue

        body_start = index + 2
        body_end = body_start
        while body_end < len(lines):
            next_title = lines[body_end].strip()
            next_is_section = (
                bool(next_title)
                and body_end + 1 < len(lines)
                and _SECTION_UNDERLINE_RE.fullmatch(lines[body_end + 1].strip()) is not None
            )
            if next_is_section:
                break
            body_end += 1

        body = "\n".join(lines[body_start:body_end]).strip()
        sections.append(TextSection(title=title, body=body))
        index = body_end

    return sections


def _signature(path: Path) -> int:
    return path.stat().st_mtime_ns if path.exists() else -1


def _normalize(value: str) -> str:
    return _NORMALIZE_RE.sub(" ", value.lower().replace("ё", "е")).strip()
