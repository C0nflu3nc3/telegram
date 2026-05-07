from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import Message

from app.config import get_settings
from app.database.crud import create_message, upsert_user, user_has_knowledge
from app.database.db import get_session
from app.services.conversation_intents import detect_conversation_intent
from app.services.rag_pipeline import answer_user_question


router = Router()


@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def handle_question(message: Message) -> None:
    if not message.from_user or not message.text:
        return

    question = message.text.strip()
    if not question:
        await message.answer("Напишите вопрос текстом.")
        return

    quick_response = detect_conversation_intent(question)
    if quick_response:
        await message.answer(quick_response)
        return

    settings = get_settings()
    knowledge_owner_id = settings.knowledge_base_owner_id
    user = message.from_user
    with get_session() as session:
        upsert_user(session, user.id, user.username, user.full_name)
        has_knowledge = user_has_knowledge(session, knowledge_owner_id)

    if not has_knowledge:
        await message.answer(
            "Общая база знаний пока не загружена. Попросите администратора отправить /load или загрузить файл TXT, PDF, DOCX."
        )
        return

    result = answer_user_question(user_id=knowledge_owner_id, question=question)

    with get_session() as session:
        create_message(session, user.id, "user", question)
        create_message(session, user.id, "assistant", result.answer)

    await message.answer(result.answer)
