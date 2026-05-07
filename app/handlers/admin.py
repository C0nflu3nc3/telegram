from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import get_settings
from app.database.crud import clear_user_knowledge, get_last_document, get_user_document_count, upsert_user
from app.database.db import get_session
from app.services.vector_store import clear_user_chunks


router = Router()


@router.message(Command("clear"))
async def command_clear(message: Message) -> None:
    if not message.from_user:
        return

    settings = get_settings()
    if not settings.is_admin(message.from_user.id):
        return

    user = message.from_user
    with get_session() as session:
        upsert_user(session, user.id, user.username, user.full_name)
        clear_user_knowledge(session, settings.knowledge_base_owner_id)
    clear_user_chunks(settings.knowledge_base_owner_id)

    await message.answer("Общая база знаний удалена. Можно загрузить новую через /load или файлом.")


@router.message(Command("status"))
async def command_status(message: Message) -> None:
    if not message.from_user:
        return

    settings = get_settings()
    user = message.from_user
    with get_session() as session:
        upsert_user(session, user.id, user.username, user.full_name)
        count = get_user_document_count(session, settings.knowledge_base_owner_id)
        last_document = get_last_document(session, settings.knowledge_base_owner_id)

    if count == 0 or last_document is None:
        await message.answer(
            "Общая база знаний пока пустая. Администратор должен загрузить текст через /load или отправить файл."
        )
        return

    source = last_document.source_name or "текстовое сообщение"
    await message.answer(
        "Общая база знаний загружена.\n"
        f"Источник: {source}\n"
        f"Тип: {last_document.source_type}\n"
        f"Чанков: {last_document.chunks_count}\n"
        f"Символов текста: {last_document.text_length}"
    )
