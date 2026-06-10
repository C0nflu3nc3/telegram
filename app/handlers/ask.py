from __future__ import annotations

from io import BytesIO

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.config import get_settings
from app.database.crud import (
    create_message,
    get_or_create_user_state,
    register_normal_message,
    register_violation,
    set_user_context,
    upsert_user,
)
from app.database.db import get_session
from app.services.conversation_intents import detect_conversation_intent
from app.services.keyn_content import (
    HOW_TO_TALK_TEXT,
    MAIN_MENU_BUTTONS,
    SECTION_BY_BUTTON,
    clear_keyn_caches,
    get_random_farewell,
    get_random_unknown_answer,
    get_random_violation_reply,
    get_section_spec,
    get_topic_spec,
)
from app.services.keyn_keyboard import BACK_TO_MENU_CALLBACK, TOPIC_CALLBACK_PREFIX, build_main_menu, build_section_keyboard
from app.services.keyn_logic import (
    detect_forbidden_topic_kind,
    detect_violation_kind,
    ensure_keyn_ready,
    generate_keyn_answer,
    generate_topic_answer,
    get_broken_signal_reply,
    get_forbidden_topic_reply,
    get_non_russian_reply,
    is_russian_text,
)


router = Router()
_HELP_BUTTON_TEXT = MAIN_MENU_BUTTONS[4]


class BonusUploadState(StatesGroup):
    waiting_for_bonus_content = State()


@router.message(Command("load_bonus"))
async def command_load_bonus(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    settings = get_settings()
    if not settings.is_admin(message.from_user.id):
        return

    await state.set_state(BonusUploadState.waiting_for_bonus_content)
    await message.answer(
        "Отправь новый файл бонусной системы в формате TXT или просто пришли текст сообщением. "
        "Я заменю только бонусный архив, не трогая остальную базу.\n\n"
        "Если передумаешь, используй /cancel.",
        reply_markup=build_main_menu(),
    )


@router.message(Command("cancel"))
async def command_cancel(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state != BonusUploadState.waiting_for_bonus_content.state:
        return

    await state.clear()
    await message.answer("Загрузка бонусного архива отменена.", reply_markup=build_main_menu())


@router.message(BonusUploadState.waiting_for_bonus_content, F.document)
async def handle_bonus_document(message: Message, state: FSMContext) -> None:
    if not message.from_user or not message.document:
        return

    settings = get_settings()
    if not settings.is_admin(message.from_user.id):
        return

    file_name = (message.document.file_name or "").lower()
    if not file_name.endswith(".txt"):
        await message.answer("Нужен именно TXT-файл с обновлённой бонусной системой.")
        return

    try:
        text = await _read_document_text(message)
    except UnicodeDecodeError:
        await message.answer("Не смог прочитать этот TXT. Сохрани файл в UTF-8 или Windows-1251 и пришли снова.")
        return
    except Exception:
        await message.answer("Не удалось загрузить файл. Попробуй отправить его ещё раз.")
        return

    await _save_bonus_override(text)
    await state.clear()
    await message.answer(
        "Бонусный архив обновлён. Кейн уже будет отвечать по новой версии бонусной системы.",
        reply_markup=build_main_menu(),
    )


@router.message(BonusUploadState.waiting_for_bonus_content, F.text, ~F.text.startswith("/"))
async def handle_bonus_text(message: Message, state: FSMContext) -> None:
    if not message.from_user or not message.text:
        return

    settings = get_settings()
    if not settings.is_admin(message.from_user.id):
        return

    text = message.text.strip()
    if not text:
        await message.answer("Текст пуст. Пришли содержимое бонусной системы ещё раз.")
        return

    await _save_bonus_override(text)
    await state.clear()
    await message.answer(
        "Бонусный архив обновлён. Новые числа и правила уже подхвачены.",
        reply_markup=build_main_menu(),
    )


@router.message(BonusUploadState.waiting_for_bonus_content)
async def handle_bonus_invalid_payload(message: Message) -> None:
    if not message.from_user:
        return

    settings = get_settings()
    if not settings.is_admin(message.from_user.id):
        return

    await message.answer("Пришли TXT-файл или текст сообщением. Другие форматы я в бонусный архив не запишу.")


@router.callback_query(F.data == BACK_TO_MENU_CALLBACK)
async def handle_back_to_menu(callback: CallbackQuery) -> None:
    if not callback.from_user:
        await callback.answer()
        return

    with get_session() as session:
        upsert_user(session, callback.from_user.id, callback.from_user.username, callback.from_user.full_name)
        set_user_context(session, callback.from_user.id, None, None)

    await callback.answer()
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.message.answer(
            "Главные архивы снова перед тобой, Житель.",
            reply_markup=build_main_menu(),
        )


@router.callback_query(F.data.startswith(TOPIC_CALLBACK_PREFIX))
async def handle_topic_callback(callback: CallbackQuery) -> None:
    if not callback.from_user:
        await callback.answer()
        return

    topic_key = callback.data.removeprefix(TOPIC_CALLBACK_PREFIX)
    topic = get_topic_spec(topic_key)
    if topic is None:
        await callback.answer()
        return

    try:
        ensure_keyn_ready()
    except FileNotFoundError:
        await callback.answer()
        if callback.message:
            await callback.message.answer(
                "Архивы Кейна пока не найдены. Администратору нужно добавить keyn_start_database.txt.",
                reply_markup=build_main_menu(),
            )
        return

    with get_session() as session:
        upsert_user(session, callback.from_user.id, callback.from_user.username, callback.from_user.full_name)
        set_user_context(session, callback.from_user.id, topic.section, topic.key)

    answer = generate_topic_answer(topic_key)
    await callback.answer()
    if callback.message:
        await callback.message.answer(answer)


@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def handle_text(message: Message) -> None:
    if not message.from_user or not message.text:
        return

    text = message.text.strip()
    if not text:
        await message.answer(get_broken_signal_reply())
        return

    try:
        ensure_keyn_ready()
    except FileNotFoundError:
        await message.answer(
            "Архивы Кейна пока не найдены. Администратору нужно добавить keyn_start_database.txt.",
            reply_markup=build_main_menu(),
        )
        return

    user = message.from_user
    with get_session() as session:
        upsert_user(session, user.id, user.username, user.full_name)
        state = get_or_create_user_state(session, user.id)
        section_key = state.current_section
        topic_key = state.current_topic

    if text in SECTION_BY_BUTTON:
        section_key = SECTION_BY_BUTTON[text]
        section = get_section_spec(section_key)
        if section is None:
            await message.answer(get_random_unknown_answer(), reply_markup=build_main_menu())
            return

        with get_session() as session:
            set_user_context(session, user.id, section_key, None)

        await message.answer(section.intro, reply_markup=build_section_keyboard(section_key))
        return

    if text == _HELP_BUTTON_TEXT:
        await message.answer(HOW_TO_TALK_TEXT, reply_markup=build_main_menu())
        return

    if not is_russian_text(text):
        answer = get_non_russian_reply()
        _store_dialog(user.id, text, answer)
        await message.answer(answer)
        return

    quick_response = detect_conversation_intent(text)
    if quick_response:
        _store_dialog(user.id, text, quick_response)
        await message.answer(quick_response)
        return

    violation_kind = detect_violation_kind(text)
    if violation_kind == "broken_signal":
        answer = get_broken_signal_reply()
        _store_dialog(user.id, text, answer)
        await message.answer(answer)
        return

    if violation_kind == "violation":
        with get_session() as session:
            level = register_violation(session, user.id)
        answer = get_random_violation_reply(level)
        _store_dialog(user.id, text, answer)
        await message.answer(answer)
        return

    forbidden_kind = detect_forbidden_topic_kind(text)
    if forbidden_kind:
        answer = get_forbidden_topic_reply(forbidden_kind)
        answer = _append_farewell_if_needed(user.id, answer)
        _store_dialog(user.id, text, answer)
        await message.answer(answer)
        return

    answer = generate_keyn_answer(text, section_key, topic_key)
    answer = _append_farewell_if_needed(user.id, answer)
    _store_dialog(user.id, text, answer)
    await message.answer(answer)


async def _read_document_text(message: Message) -> str:
    telegram_file = await message.bot.get_file(message.document.file_id)
    buffer = BytesIO()
    await message.bot.download_file(telegram_file.file_path, destination=buffer)
    raw = buffer.getvalue()
    return _decode_bytes(raw)


async def _save_bonus_override(text: str) -> None:
    settings = get_settings()
    cleaned = text.strip()
    settings.keyn_bonus_database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.keyn_bonus_database_path.write_text(cleaned, encoding="utf-8")
    clear_keyn_caches()


def _decode_bytes(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("bonus", raw, 0, len(raw), "Unsupported text encoding")


def _append_farewell_if_needed(user_id: int, answer: str) -> str:
    with get_session() as session:
        should_add_farewell = register_normal_message(session, user_id)

    if not should_add_farewell:
        return answer
    return f"{answer}\n\n{get_random_farewell()}"


def _store_dialog(user_id: int, user_text: str, answer: str) -> None:
    with get_session() as session:
        create_message(session, user_id, "user", user_text)
        create_message(session, user_id, "assistant", answer)
