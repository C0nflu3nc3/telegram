from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")


def _get_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return default


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


def _default_data_root() -> Path:
    railway_mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if railway_mount:
        return Path(railway_mount)
    return PROJECT_DIR / "data"


def _resolve_path(value: str | None, default_path: Path) -> Path:
    path = Path(value) if value else default_path
    if not path.is_absolute():
        path = PROJECT_DIR / path
    return path


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    openai_api_key: str
    admin_id: int
    database_path: Path
    chroma_path: Path
    upload_path: Path
    keyn_database_path: Path
    chroma_collection: str
    embedding_model: str
    chat_model: str
    intent_model: str
    assistant_style: str
    chunk_size: int
    chunk_overlap: int
    top_k: int
    similarity_threshold: float

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self.upload_path.mkdir(parents=True, exist_ok=True)

    @property
    def knowledge_base_owner_id(self) -> int:
        return self.admin_id

    def is_admin(self, user_id: int) -> bool:
        return self.admin_id > 0 and user_id == self.admin_id

    def validate(self) -> None:
        missing = []
        if not self.bot_token:
            missing.append("TELEGRAM_BOT_TOKEN/BOT_TOKEN")
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(
                f"Не заданы обязательные переменные окружения: {joined}. "
                "Заполните файл .env перед запуском."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data_root = _default_data_root()
    return Settings(
        bot_token=_get_env("TELEGRAM_BOT_TOKEN", "BOT_TOKEN"),
        openai_api_key=_get_env("OPENAI_API_KEY"),
        admin_id=_get_int("ADMIN_ID", 0),
        database_path=_resolve_path(os.getenv("DATABASE_PATH"), data_root / "app.db"),
        chroma_path=_resolve_path(os.getenv("CHROMA_PATH"), data_root / "chroma_db"),
        upload_path=_resolve_path(os.getenv("UPLOAD_PATH"), data_root / "uploads"),
        keyn_database_path=_resolve_path(
            os.getenv("KEYN_DATABASE_PATH"),
            PROJECT_DIR / "keyn_start_database.txt",
        ),
        chroma_collection=_get_env("CHROMA_COLLECTION", default="knowledge_base"),
        embedding_model=_get_env("EMBEDDING_MODEL", default="text-embedding-3-small"),
        chat_model=_get_env("OPENAI_MODEL", "CHAT_MODEL", default="gpt-5.4-mini"),
        intent_model=_get_env("INTENT_MODEL", "CHAT_MODEL", "OPENAI_MODEL", default="gpt-5.4-nano"),
        assistant_style=_get_env("ASSISTANT_STYLE"),
        chunk_size=_get_int("CHUNK_SIZE", 500),
        chunk_overlap=_get_int("CHUNK_OVERLAP", 100),
        top_k=_get_int("TOP_K", 5),
        similarity_threshold=_get_float("SIMILARITY_THRESHOLD", 0.35),
    )
