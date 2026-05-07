from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")


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
        return user_id == self.admin_id

    def validate(self) -> None:
        missing = []
        if not self.bot_token:
            missing.append("BOT_TOKEN")
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if self.admin_id <= 0:
            missing.append("ADMIN_ID")

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
        bot_token=os.getenv("BOT_TOKEN", "").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        admin_id=_get_int("ADMIN_ID", 0),
        database_path=_resolve_path(os.getenv("DATABASE_PATH"), data_root / "app.db"),
        chroma_path=_resolve_path(os.getenv("CHROMA_PATH"), data_root / "chroma_db"),
        upload_path=_resolve_path(os.getenv("UPLOAD_PATH"), data_root / "uploads"),
        chroma_collection=os.getenv("CHROMA_COLLECTION", "knowledge_base").strip(),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small").strip(),
        chat_model=os.getenv("CHAT_MODEL", "gpt-4.1-mini").strip(),
        intent_model=os.getenv("INTENT_MODEL", "").strip()
        or os.getenv("CHAT_MODEL", "gpt-4.1-mini").strip(),
        assistant_style=os.getenv("ASSISTANT_STYLE", "").strip(),
        chunk_size=_get_int("CHUNK_SIZE", 500),
        chunk_overlap=_get_int("CHUNK_OVERLAP", 100),
        top_k=_get_int("TOP_K", 5),
        similarity_threshold=_get_float("SIMILARITY_THRESHOLD", 0.35),
    )
