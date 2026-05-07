from __future__ import annotations

import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Document, Message

from app.config import get_settings
from app.database.crud import upsert_user
from app.database.db import get_session
from app.services.file_parser import parse_file, parse_text_message
from app.services.rag_pipeline import replace_user_knowledge
from app.utils.filters import is_supported_document


router = Router()


class UploadKnowledgeState(StatesGroup):
    waiting_for_text = State()


@router.message(Command("load"))
async def command_load(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    settings = get_settings()
    if not settings.is_admin(message.from_user.id):
        return

    await state.set_state(UploadKnowledgeState.waiting_for_text)
    await message.answer(
        "Отправьте текст одним сообщением, и я заменю им текущую общую базу знаний. "
        "Также можно отправить файл TXT, PDF или DOCX."
    )


@router.message(Command("cancel"))
async def command_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Режим загрузки отключен.")


@router.message(UploadKnowledgeState.waiting_for_text, F.text)
async def upload_text_message(message: Message, state: FSMContext) -> None:
    if not message.from_user or not message.text:
        return

    settings = get_settings()
    if not settings.is_admin(message.from_user.id):
        await state.clear()
        return

    await _register_user(message)

    try:
        text = parse_text_message(message.text)
        result = replace_user_knowledge(
            user_id=settings.knowledge_base_owner_id,
            text=text,
            source_name="text_message",
            source_type="text",
        )
    except ValueError as error:
        await message.answer(str(error))
        return

    await state.clear()
    await message.answer(
        "Общая база знаний успешно сохранена.\n"
        f"Создано чанков: {result.chunks_count}\n"
        "Теперь все пользователи могут задавать вопросы обычными сообщениями."
    )


@router.message(F.document)
async def upload_document(message: Message, bot: Bot, state: FSMContext) -> None:
    if not message.from_user or not message.document:
        return

    settings = get_settings()
    if not settings.is_admin(message.from_user.id):
        return

    document = message.document
    if not is_supported_document(document.file_name):
        await message.answer("Поддерживаются только файлы TXT, PDF и DOCX.")
        return

    await _register_user(message)

    try:
        file_path = await _download_document(bot, settings.knowledge_base_owner_id, document)
        text = parse_file(file_path)
        result = replace_user_knowledge(
            user_id=settings.knowledge_base_owner_id,
            text=text,
            source_name=document.file_name,
            source_type=Path(document.file_name or "").suffix.lower().lstrip(".") or "file",
        )
    except ValueError as error:
        await message.answer(str(error))
        return

    await state.clear()
    await message.answer(
        "Файл обработан, общая база знаний обновлена.\n"
        f"Источник: {document.file_name}\n"
        f"Создано чанков: {result.chunks_count}"
    )


@router.message(UploadKnowledgeState.waiting_for_text)
async def upload_invalid_content(message: Message) -> None:
    await message.answer("В режиме загрузки отправьте текст или файл TXT, PDF, DOCX.")


async def _register_user(message: Message) -> None:
    if not message.from_user:
        return

    user = message.from_user
    with get_session() as session:
        upsert_user(session, user.id, user.username, user.full_name)


async def _download_document(bot: Bot, user_id: int, document: Document) -> Path:
    settings = get_settings()
    user_dir = settings.upload_path / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    filename = _sanitize_filename(document.file_name or "uploaded_file")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    destination = user_dir / f"{timestamp}_{filename}"

    file_info = await bot.get_file(document.file_id)
    file_bytes = BytesIO()
    await bot.download_file(file_info.file_path, destination=file_bytes)
    destination.write_bytes(file_bytes.getvalue())

    return destination


def _sanitize_filename(filename: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return sanitized or "uploaded_file"
