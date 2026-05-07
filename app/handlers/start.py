from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.config import get_settings


router = Router()


START_TEXT = "Что бы вы хотели узнать сегодня?"


@router.message(CommandStart())
async def command_start(message: Message) -> None:
    await message.answer(START_TEXT)


@router.message(Command("help"))
async def command_help(message: Message) -> None:
    settings = get_settings()
    user_id = message.from_user.id if message.from_user else 0

    if settings.is_admin(user_id):
        await message.answer(
            "Команды администратора:\n"
            "/load - загрузить новую базу знаний\n"
            "/clear - очистить текущую базу знаний\n"
            "/status - посмотреть состояние базы\n"
            "/cancel - выйти из режима загрузки"
        )
        return

    await message.answer(START_TEXT)
