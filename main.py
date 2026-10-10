import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import (
    init_db, get_all_categories, add_category, delete_category,
    add_shopping_item, get_shopping_list_by_category, toggle_shopping_item, delete_shopping_item, clear_category_items,
    add_note, get_notes, delete_note, check_congratulated, set_congratulated
)

TOKEN = "8875243977:AAGuhD8Pe8z9EYvZms6pHzIpu6z4Cel0Esg"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Europe/Sofia")  # Часовой пояс


class Form(StatesGroup):
    waiting_for_shopping = State()
    waiting_for_note_text = State()
    waiting_for_note_time = State()
    waiting_for_category = State()


def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Список покупок"), KeyboardButton(text="📝 Семейные заметки")]
        ],
        resize_keyboard=True
    )


async def get_categories_keyboard():
    categories = await get_all_categories()
    buttons = []
    for cat in categories:
        buttons.append([InlineKeyboardButton(text=cat, callback_data=f"select_cat_{cat}")])
    buttons.append([InlineKeyboardButton(text="➕ Добавить категорию", callback_data="add_category_btn")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    is_congr = await check_congratulated(user_id)

    if not is_congr:
        await set_congratulated(user_id)
        congr_text = (
            "🎉 **С юбилеем, с 35-летием!** 🎉\n\n"
            "Дорогая моя сестричка! В этот особенный день хочу сказать тебе огромное спасибо за твое тепло, заботу и уют, которые ты создаешь вокруг.\n"
            "Этот бот — твой личный карманный помощник, созданный с любовью, чтобы облегчить тебе повседневные хлопоты! 💖\n\n"
            "Пользуйся на здоровье!"
        )
        await message.answer(congr_text, parse_mode="Markdown")

    welcome_text = f"Привет, {message.from_user.first_name}! 🏡 Выбирай нужный раздел на клавиатуре ниже:"
    await message.answer(welcome_text, reply_markup=get_main_menu())


# --- РАЗДЕЛ: ПОКУПКИ ---
@dp.message(F.text == "🛒 Список покупок")
async def show_categories(message: types.Message):
    keyboard = await get_categories_keyboard()
    await message.answer("🛒 **Выбери категорию покупок:**", reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "add_category_btn")
async def ask_new_category(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введи название новой категории:", parse_mode="Markdown")
    await state.set_state(Form.waiting_for_category)
    await callback.answer()


@dp.message(Form.waiting_for_category)
async def save_new_category(message: types.Message, state: FSMContext):
    cat_name = message.text.strip()
    await add_category(cat_name)
    await state.clear()

    keyboard = await get_categories_keyboard()
    await message.answer(f"✅ Категория **{cat_name}** успешно создана!", reply_markup=get_main_menu(),
                         parse_mode="Markdown")
    await message.answer("🛒 **Выбери категорию покупок:**", reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("select_cat_"))
async def show_category_items(callback: types.CallbackQuery, state: FSMContext):
    cat_name = callback.data.replace("select_cat_", "")
    items = await get_shopping_list_by_category(cat_name)

    text = f"Категория: **{cat_name}**\n\n"
    keyboard_buttons = []

    if not items:
        text += "Список в этой категории пока пуст."
    else:
        text += "Нажми на товар, чтобы отметить его купленным:\n"
        for item_id, item_name, is_bought in items:
            status_icon = "✅" if is_bought == 1 else "⬜️"
            display_text = f"{status_icon} {item_name}"

            keyboard_buttons.append([
                InlineKeyboardButton(text=display_text, callback_data=f"toggle_item_{item_id}_{cat_name}"),
                InlineKeyboardButton(text="❌ Удалить", callback_data=f"del_shop_{item_id}_{cat_name}")
            ])

        keyboard_buttons.append([
            InlineKeyboardButton(text="🧹 Очистить всю категорию", callback_data=f"clear_cat_{cat_name}")
        ])

    keyboard_buttons.append([InlineKeyboardButton(text="➕ Добавить товар", callback_data=f"add_shop_{cat_name}")])
    keyboard_buttons.append([
        InlineKeyboardButton(text="🗑 Удалить категорию", callback_data=f"del_cat_{cat_name}"),
        InlineKeyboardButton(text="🔙 К категориям", callback_data="back_to_cats")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "back_to_cats")
async def back_categories(callback: types.CallbackQuery):
    keyboard = await get_categories_keyboard()
    await callback.message.edit_text("🛒 **Выбери категорию покупок:**", reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data.startswith("del_cat_"))
async def delete_user_category(callback: types.CallbackQuery):
    cat_name = callback.data.replace("del_cat_", "")
    await delete_category(cat_name)
    await callback.answer(f"Категория «{cat_name}» удалена!")

    keyboard = await get_categories_keyboard()
    await callback.message.edit_text(f"🗑 Категория **{cat_name}** удалена.\n\n🛒 **Выбери категорию покупок:**",
                                     reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("toggle_item_"))
async def toggle_item_status(callback: types.CallbackQuery):
    data_parts = callback.data.replace("toggle_item_", "").split("_", 1)
    item_id = int(data_parts[0])
    cat_name = data_parts[1]

    await toggle_shopping_item(item_id)
    await callback.answer("Статус обновлен!")

    items = await get_shopping_list_by_category(cat_name)
    text = f"Категория: **{cat_name}**\n\n"
    keyboard_buttons = []

    if not items:
        text += "Список в этой категории пока пуст."
    else:
        text += "Нажми на товар, чтобы отметить его купленным:\n"
        for item_id, item_name, is_bought in items:
            status_icon = "✅" if is_bought == 1 else "⬜️"
            display_text = f"{status_icon} {item_name}"

            keyboard_buttons.append([
                InlineKeyboardButton(text=display_text, callback_data=f"toggle_item_{item_id}_{cat_name}"),
                InlineKeyboardButton(text="❌ Удалить", callback_data=f"del_shop_{item_id}_{cat_name}")
            ])

        keyboard_buttons.append([
            InlineKeyboardButton(text="🧹 Очистить всю категорию", callback_data=f"clear_cat_{cat_name}")
        ])

    keyboard_buttons.append([InlineKeyboardButton(text="➕ Добавить товар", callback_data=f"add_shop_{cat_name}")])
    keyboard_buttons.append([
        InlineKeyboardButton(text="🗑 Удалить категорию", callback_data=f"del_cat_{cat_name}"),
        InlineKeyboardButton(text="🔙 К категориям", callback_data="back_to_cats")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("add_shop_"))
async def ask_shop_item(callback: types.CallbackQuery, state: FSMContext):
    cat_name = callback.data.replace("add_shop_", "")
    await state.update_data(current_cat_name=cat_name)
    await callback.message.answer(f"Напиши, что добавить в категорию **{cat_name}**:", parse_mode="Markdown")
    await state.set_state(Form.waiting_for_shopping)
    await callback.answer()


@dp.message(Form.waiting_for_shopping)
async def save_shop_item(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cat_name = data.get("current_cat_name", "Продукты")
    item_text = message.text
    await add_shopping_item(item_text, cat_name)
    await state.clear()
    await message.answer(f"✅ Добавлено в **{cat_name}**: *{item_text}*", reply_markup=get_main_menu(),
                         parse_mode="Markdown")


@dp.callback_query(F.data.startswith("del_shop_"))
async def delete_shop(callback: types.CallbackQuery):
    data_parts = callback.data.replace("del_shop_", "").split("_", 1)
    item_id = int(data_parts[0])
    cat_name = data_parts[1]

    await delete_shopping_item(item_id)
    await callback.answer("Товар удален!")

    items = await get_shopping_list_by_category(cat_name)
    text = f"Категория: **{cat_name}**\n\n"
    keyboard_buttons = []
    if not items:
        text += "Список в этой категории пока пуст."
    else:
        text += "Нажми на товар, чтобы отметить его купленным:\n"
        for i_id, i_name, is_bought in items:
            status_icon = "✅" if is_bought == 1 else "⬜️"
            display_text = f"{status_icon} {i_name}"
            keyboard_buttons.append([
                InlineKeyboardButton(text=display_text, callback_data=f"toggle_item_{i_id}_{cat_name}"),
                InlineKeyboardButton(text="❌ Удалить", callback_data=f"del_shop_{i_id}_{cat_name}")
            ])
        keyboard_buttons.append([
            InlineKeyboardButton(text="🧹 Очистить всю категорию", callback_data=f"clear_cat_{cat_name}")
        ])

    keyboard_buttons.append([InlineKeyboardButton(text="➕ Добавить товар", callback_data=f"add_shop_{cat_name}")])
    keyboard_buttons.append([
        InlineKeyboardButton(text="🗑 Удалить категорию", callback_data=f"del_cat_{cat_name}"),
        InlineKeyboardButton(text="🔙 К категориям", callback_data="back_to_cats")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("clear_cat_"))
async def clear_cat(callback: types.CallbackQuery):
    cat_name = callback.data.replace("clear_cat_", "")
    await clear_category_items(cat_name)
    await callback.answer("Категория очищена!")

    keyboard_buttons = [
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data=f"add_shop_{cat_name}")],
        [
            InlineKeyboardButton(text="🗑 Удалить категорию", callback_data=f"del_cat_{cat_name}"),
            InlineKeyboardButton(text="🔙 К категориям", callback_data="back_to_cats")
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(f"Категория: **{cat_name}**\n\nСписок в этой категории пока пуст.",
                                     reply_markup=keyboard, parse_mode="Markdown")


# --- РАЗДЕЛ: СЕМЕЙНЫЕ ЗАМЕТКИ С ТАЙМЕРОМ ---
@dp.message(F.text == "📝 Семейные заметки")
async def show_notes(message: types.Message):
    notes = await get_notes()
    keyboard_buttons = []
    text = "📝 **Семейные заметки и напоминалки:**\n\n"

    if not notes:
        text += "Заметок пока нет."
    else:
        for note_id, note_text, remind_time in notes:
            time_str = f" (Напомнить в: {remind_time})" if remind_time else ""
            text += f"• {note_text}{time_str}\n"
            keyboard_buttons.append([
                InlineKeyboardButton(text="❌ Удалить заметку", callback_data=f"del_note_{note_id}")
            ])

    keyboard_buttons.append([InlineKeyboardButton(text="➕ Добавить заметку с таймером", callback_data="add_note_btn")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "add_note_btn")
async def ask_note_text(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напиши текст заметки или напоминания:", parse_mode="Markdown")
    await state.set_state(Form.waiting_for_note_text)
    await callback.answer()


@dp.message(Form.waiting_for_note_text)
async def process_note_text(message: types.Message, state: FSMContext):
    await state.update_data(note_text=message.text)
    await message.answer(
        "Через сколько минут напомнить? (Напиши число, например: `10`, или `0` если таймер не нужен)",
        parse_mode="Markdown"
    )
    await state.set_state(Form.waiting_for_note_time)


# Функция отправки напоминания 3 раза подряд
async def send_triple_reminder(bot_instance: Bot, chat_id: int, note_text: str):
    for i in range(3):
        try:
            await bot_instance.send_message(
                chat_id,
                f"⏰ **НАПОМИНАНИЕ ({i + 1}/3):**\n\n{note_text}",
                parse_mode="Markdown"
            )
            if i < 2:
                await asyncio.sleep(1)  # Пауза 1 секунда между сообщениями
        except Exception as e:
            logging.error(f"Ошибка отправки напоминания: {e}")


@dp.message(Form.waiting_for_note_time)
async def process_note_time(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    note_text = user_data.get("note_text")
    user_id = message.from_user.id

    try:
        minutes = int(message.text.strip())
    except ValueError:
        minutes = 0

    remind_time_str = None
    if minutes > 0:
        # Вычисляем точное время срабатывания
        target_time = datetime.now() + timedelta(minutes=minutes)
        remind_time_str = target_time.strftime("%H:%M")

        # Планируем задачу через apscheduler
        scheduler.add_job(
            send_triple_reminder,
            'date',
            run_date=target_time,
            args=[bot, user_id, note_text]
        )

    await add_note(note_text, user_id, remind_time_str)
    await state.clear()

    time_msg = f" (напоминание через {minutes} мин.)" if minutes > 0 else ""
    await message.answer(f"✅ Заметка сохранена!{time_msg}", reply_markup=get_main_menu(), parse_mode="Markdown")


@dp.callback_query(F.data.startswith("del_note_"))
async def delete_user_note(callback: types.CallbackQuery):
    note_id = int(callback.data.split("_")[2])
    await delete_note(note_id)
    await callback.message.answer("🗑 Заметка удалена!")
    await callback.answer()


# --- Запуск ---
async def main():
    await init_db()
    scheduler.start()  # Запускаем планировщик
    print("Бот успешно запущен с таймерами заметок!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())