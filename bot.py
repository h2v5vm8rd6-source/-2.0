 import asyncio
import logging
import os
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.getenv("TOKEN")
DB_NAME = "database.db"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

class ProfileForm(StatesGroup):
    game = State()
    nickname = State()
    info = State()

# Главное меню
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Заполнить анкету"), KeyboardButton(text="🗑 Удалить анкету")],
        [KeyboardButton(text="🔍 Найти напарника")]
    ],
    resize_keyboard=True
)

# Функция для создания таблицы в базе данных
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY,
                game TEXT,
                nickname TEXT,
                info TEXT,
                tg_username TEXT
            )
        """)
        await db.commit()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я помогу тебе найти тиммейтов для игр.\nВыбери действие в меню ниже:",
        reply_markup=main_kb
    )

# --- БЛОК СОЗДАНИЯ АНКЕТЫ ---
@dp.message(F.text == "📝 Заполнить анкету")
async def start_form(message: types.Message, state: FSMContext):
    await message.answer("В какую игру ты ищешь напарников? (Например: CS2, Dota 2, Valorant)")
    await state.set_state(ProfileForm.game)

@dp.message(ProfileForm.game)
async def process_game(message: types.Message, state: FSMContext):
    await state.update_data(game=message.text)
    await message.answer("Отлично! Напиши свой игровой никнейм или Discord:")
    await state.set_state(ProfileForm.nickname)

@dp.message(ProfileForm.nickname)
async def process_nickname(message: types.Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await message.answer("Расскажи немного о себе: какой у тебя ранг, роль и во сколько играешь?")
    await state.set_state(ProfileForm.info)

@dp.message(ProfileForm.info)
async def process_info(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username or "Скрыт"
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR REPLACE INTO profiles (user_id, game, nickname, info, tg_username)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, data["game"], data["nickname"], message.text, username))
        await db.commit()
    
    await state.clear()
    await message.answer("✅ Твоя анкета сохранена! Теперь тебя могут найти другие игроки.", reply_markup=main_kb)

# --- УДАЛЕНИЕ АНКЕТЫ ---
@dp.message(F.text == "🗑 Удалить анкету")
async def delete_profile(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        # Проверяем, была ли вообще анкета
        async with db.execute("SELECT user_id FROM profiles WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            await message.answer("У тебя еще нет активной анкеты.")
            return

        # Удаляем
        await db.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))
        await db.commit()
    
    await message.answer("🗑 Твоя анкета успешно удалена.", reply_markup=main_kb)

# --- ПОИСК НАПАРНИКОВ (ФИЛЬТРАЦИЯ ПО ИГРАМ) ---
@dp.message(F.text == "🔍 Найти напарника")
async def choose_game_to_search(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT DISTINCT game FROM profiles") as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await message.answer("Пока нет ни одной анкеты. Будь первым!")
        return

    # Создаем инлайн-кнопки с названиями игр, которые есть в базе
    keyboard_builder = []
    for row in rows:
        game_name = row[0]
        keyboard_builder.append([InlineKeyboardButton(text=game_name, callback_data=f"game_{game_name}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_builder)
    await message.answer("🎮 Выбери игру, по которой хочешь найти тиммейтов:", reply_markup=keyboard)

# Обработка нажатия на конкретную игру
@dp.callback_query(F.data.startswith("game_"))
async def show_filtered_profiles(callback: types.CallbackQuery):
    selected_game = callback.data.replace("game_", "")
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT nickname, info, tg_username FROM profiles WHERE game = ?", (selected_game,)) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await callback.message.answer(f"По игре {selected_game} пока никого нет.")
        await callback.answer()
        return

    response = f"🎮 **Игроки по запросу: {selected_game}**\n\n"
    for row in rows:
        nickname, info, tg_username = row
        response += (
            f"👤 **Ник:** {nickname}\n"
            f"📝 **О себе:** {info}\n"
            f"📩 **Telegram:** @{tg_username}\n"
            f"-------------------\n"
        )
    
    await callback.message.answer(response, parse_mode="Markdown")
    await callback.answer()

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
