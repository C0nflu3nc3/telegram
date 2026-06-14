from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.config import get_settings
from app.database.crud import reset_user_session, upsert_user
from app.database.db import get_session
from app.services.keyn_content import HOW_TO_TALK_TEXT, START_MENU_TEXT, get_random_greeting
from app.services.keyn_keyboard import build_main_menu
from app.services.keyn_logic import ensure_keyn_ready


router = Router()


def _missing_database_text() -> str:
    return (
        "Архивы Кейна пока не собраны. "
        "Администратору нужно добавить в проект папки database, logic и interface со всеми файлами."
    )


@router.message(CommandStart())
async def command_start(message: Message) -> None:
    if not message.from_user:
        return

    try:
        ensure_keyn_ready()
    except FileNotFoundError:
        await message.answer(_missing_database_text(), reply_markup=build_main_menu())
        return

    user = message.from_user
    with get_session() as session:
        upsert_user(session, user.id, user.username, user.full_name)
        reset_user_session(session, user.id)

    await message.answer(
        f"{get_random_greeting()}\n\n{START_MENU_TEXT}",
        reply_markup=build_main_menu(),
    )


@router.message(Command("help"))
async def command_help(message: Message) -> None:
    await message.answer(HOW_TO_TALK_TEXT, reply_markup=build_main_menu())


@router.message(Command("whoami"))
async def command_whoami(message: Message) -> None:
    if not message.from_user:
        return

    settings = get_settings()
    user_id = message.from_user.id
    admin_ids = ", ".join(str(admin_id) for admin_id in settings.admin_ids) or "<empty>"
    is_admin = settings.is_admin(user_id)

    await message.answer(
        f"user_id={user_id}\n"
        f"admin={str(is_admin).lower()}\n"
        f"configured_admin_ids={admin_ids}",
        reply_markup=build_main_menu(),
    )
