from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.services.keyn_content import MAIN_MENU_BUTTONS, TOPICS_BY_SECTION


BACK_TO_MENU_CALLBACK = "keyn:main"
TOPIC_CALLBACK_PREFIX = "keyn:topic:"


def build_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MAIN_MENU_BUTTONS[0]), KeyboardButton(text=MAIN_MENU_BUTTONS[1])],
            [KeyboardButton(text=MAIN_MENU_BUTTONS[2]), KeyboardButton(text=MAIN_MENU_BUTTONS[3])],
            [KeyboardButton(text=MAIN_MENU_BUTTONS[4]), KeyboardButton(text=MAIN_MENU_BUTTONS[5])],
            [KeyboardButton(text=MAIN_MENU_BUTTONS[6])],
        ],
        resize_keyboard=True,
        input_field_placeholder="Спроси Кейна о Риммэле...",
    )


def build_section_keyboard(section_key: str) -> InlineKeyboardMarkup | None:
    topics = TOPICS_BY_SECTION.get(section_key, ())
    if not topics:
        return None

    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for topic in topics:
        row.append(
            InlineKeyboardButton(
                text=topic.title,
                callback_data=f"{TOPIC_CALLBACK_PREFIX}{topic.key}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data=BACK_TO_MENU_CALLBACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
