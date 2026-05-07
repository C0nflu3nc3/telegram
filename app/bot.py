from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import get_settings
from app.database.db import init_db
from app.handlers.admin import router as admin_router
from app.handlers.ask import router as ask_router
from app.handlers.start import router as start_router
from app.handlers.upload import router as upload_router


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(start_router)
    dispatcher.include_router(admin_router)
    dispatcher.include_router(upload_router)
    dispatcher.include_router(ask_router)
    return dispatcher


def create_bot() -> Bot:
    settings = get_settings()
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def start_bot() -> None:
    settings = get_settings()
    settings.validate()
    settings.ensure_directories()
    init_db()

    bot = create_bot()
    dispatcher = create_dispatcher()

    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)
