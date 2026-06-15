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
    ASK_DIRECTLY_BUTTON,
    SECTION_BY_BUTTON,
    clear_keyn_caches,
    get_random_farewell,
    get_random_violation_reply,
    get_section_spec,
    get_topic_spec,
)
from app.services.keyn_keyboard import BACK_TO_MENU_CALLBACK, TOPIC_CALLBACK_PREFIX, build_main_menu, build_section_keyboard
from app.services.keyn_logic import (
    detect_edge_case_response,
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
from app.services.keyn_managed_files import (
    MANAGED_TEXT_COMMANDS,
    get_managed_text_file_by_command,
    get_managed_text_file_by_key,
    get_managed_text_file_path,
)


router = Router()


class ManagedTextUploadState(StatesGroup):
    waiting_for_text_content = State()


def _missing_database_text() -> str:
    return (
        "Архивы Кейна пока не собраны. "
        "Администратору нужно добавить в проект папки database, logic и interface со всеми файлами."
    )


@router.message(Command(commands=MANAGED_TEXT_COMMANDS))
async def command_load_text_file(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    settings = get_settings()
    if not settings.is_admin(message.from_user.id):
        return

    command_name = _extract_command_name(message)
    target = get_managed_text_file_by_command(command_name)
    if target is None:
        return

    await state.set_state(ManagedTextUploadState.waiting_for_text_content)
    await state.update_data(target_file_key=target.key)
    await message.answer(
        f"Отправь новый TXT-файл или просто текст сообщением для {target.title}. "
        f"Я обновлю только `{target.filename}`.\n\n"
        "Если передумаешь, используй /cancel.",
        reply_markup=build_main_menu(),
    )


@router.message(Command("cancel"))
async def command_cancel(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state != ManagedTextUploadState.waiting_for_text_content.state:
        return

    await state.clear()
    await message.answer("Загрузка txt-файла отменена.", reply_markup=build_main_menu())


@router.message(ManagedTextUploadState.waiting_for_text_content, F.document)
async def handle_managed_document(message: Message, state: FSMContext) -> None:
    if not message.from_user or not message.document:
        return

    settings = get_settings()
    if not settings.is_admin(message.from_user.id):
        return

    target = await _get_target_from_state(state)
    if target is None:
        await state.clear()
        await message.answer("Не удалось определить, какой файл нужно обновить. Запусти команду загрузки ещё раз.")
        return

    file_name = (message.document.file_name or "").lower()
    if not file_name.endswith(".txt"):
        await message.answer("Нужен именно TXT-файл.")
        return

    try:
        text = await _read_document_text(message)
    except UnicodeDecodeError:
        await message.answer("Не смог прочитать этот TXT. Сохрани файл в UTF-8 или Windows-1251 и пришли снова.")
        return
    except Exception:
        await message.answer("Не удалось загрузить файл. Попробуй отправить его ещё раз.")
        return

    await _save_managed_text(target.key, text)
    await state.clear()
    await message.answer(
        f"Файл `{target.filename}` обновлён. Кейн уже использует новую версию.",
        reply_markup=build_main_menu(),
    )


@router.message(ManagedTextUploadState.waiting_for_text_content, F.text, ~F.text.startswith("/"))
async def handle_managed_text(message: Message, state: FSMContext) -> None:
    if not message.from_user or not message.text:
        return

    settings = get_settings()
    if not settings.is_admin(message.from_user.id):
        return

    target = await _get_target_from_state(state)
    if target is None:
        await state.clear()
        await message.answer("Не удалось определить, какой файл нужно обновить. Запусти команду загрузки ещё раз.")
        return

    text = message.text.strip()
    if not text:
        await message.answer("Текст пуст. Пришли содержимое файла ещё раз.")
        return

    await _save_managed_text(target.key, text)
    await state.clear()
    await message.answer(
        f"Файл `{target.filename}` обновлён. Новая версия уже подхвачена.",
        reply_markup=build_main_menu(),
    )


@router.message(ManagedTextUploadState.waiting_for_text_content)
async def handle_managed_invalid_payload(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return

    settings = get_settings()
    if not settings.is_admin(message.from_user.id):
        return

    target = await _get_target_from_state(state)
    if target is None:
        await state.clear()
        return

    await message.answer(
        f"Для `{target.filename}` пришли TXT-файл или текст сообщением. Другие форматы я не запишу."
    )


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
            await callback.message.answer(_missing_database_text(), reply_markup=build_main_menu())
        return

    with get_session() as session:
        upsert_user(session, callback.from_user.id, callback.from_user.username, callback.from_user.full_name)
        set_user_context(session, callback.from_user.id, topic.section, topic.key)

    answer = _append_farewell_if_needed(callback.from_user.id, generate_topic_answer(topic_key))
    _store_dialog(callback.from_user.id, f"[topic] {topic.title}", answer)

    await callback.answer()
    if callback.message:
        await callback.message.answer(answer, reply_markup=build_section_keyboard(topic.section))


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
        await message.answer(_missing_database_text(), reply_markup=build_main_menu())
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
            return

        with get_session() as session:
            set_user_context(session, user.id, section_key, None)

        await message.answer(section.intro, reply_markup=build_section_keyboard(section_key))
        return

    if text == ASK_DIRECTLY_BUTTON:
        with get_session() as session:
            set_user_context(session, user.id, None, None)
        await message.answer("Архивы открыты. Говори, Житель.", reply_markup=build_main_menu())
        return

    if not is_russian_text(text):
        answer = _append_farewell_if_needed(user.id, get_non_russian_reply())
        _store_dialog(user.id, text, answer)
        await message.answer(answer)
        return

    violation_kind = detect_violation_kind(text)
    if violation_kind == "broken_signal":
        answer = _append_farewell_if_needed(user.id, get_broken_signal_reply())
        _store_dialog(user.id, text, answer)
        await message.answer(answer)
        return

    if violation_kind == "violation":
        with get_session() as session:
            level = register_violation(session, user.id)
        answer = _append_farewell_if_needed(user.id, get_random_violation_reply(level))
        _store_dialog(user.id, text, answer)
        await message.answer(answer)
        return

    forbidden_kind = detect_forbidden_topic_kind(text)
    if forbidden_kind:
        answer = _append_farewell_if_needed(user.id, get_forbidden_topic_reply(forbidden_kind))
        _store_dialog(user.id, text, answer)
        await message.answer(answer)
        return

    quick_response = detect_conversation_intent(text)
    if quick_response:
        answer = _append_farewell_if_needed(user.id, quick_response)
        _store_dialog(user.id, text, answer)
        await message.answer(answer)
        return

    edge_response = detect_edge_case_response(text)
    if edge_response:
        answer = _append_farewell_if_needed(user.id, edge_response)
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


async def _get_target_from_state(state: FSMContext):
    data = await state.get_data()
    return get_managed_text_file_by_key(data.get("target_file_key"))


async def _save_managed_text(target_key: str, text: str) -> None:
    target = get_managed_text_file_by_key(target_key)
    if target is None:
        raise ValueError(f"Unknown managed text target: {target_key}")

    cleaned = text.strip()
    path = get_managed_text_file_path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cleaned, encoding="utf-8")
    clear_keyn_caches()


def _decode_bytes(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("managed_text", raw, 0, len(raw), "Unsupported text encoding")


def _extract_command_name(message: Message) -> str:
    raw_text = (message.text or "").strip()
    command_token = raw_text.split(maxsplit=1)[0]
    command_name = command_token.lstrip("/").split("@", 1)[0]
    return command_name.lower()


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
