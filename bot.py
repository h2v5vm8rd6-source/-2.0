 import asyncio
import logging
import os
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.getenv("TOKEN")
DB_NAME = "database.db"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

class ProfileForm(StatesGroup):
    game = State()
    nickname = State()
    info = State()

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Заполнить анкету")],
        [KeyboardButton(text="🔍 Найти напарника")]
    ],
    resize_keyboard=True
)

# Функция для создания таблицы в базе данных при запуске
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
    
    # Сохраняем или обновляем анкету в базе данных SQLite
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR REPLACE INTO profiles (user_id, game, nickname, info, tg_username)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, data["game"], data["nickname"], message.text, username))
        await db.commit()
    
    await state.clear()
    await message.answer("✅ Твоя анкета сохранена! Теперь тебя могут найти другие игроки.", reply_markup=main_kb)

@dp.message(F.text == "🔍 Найти напарника")
async def find_teammates(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT game, nickname, info, tg_username FROM profiles") as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await message.answer("Пока нет ни одной анкеты. Будь первым!")
        return

    response = "🎮 **Доступные игроки:**\n\n"
    for row in rows:
        game, nickname, info, tg_username = row
        response += (
            f"🕹 **Игра:** {game}\n"
            f"👤 **Ник:** {nickname}\n"
            f"📝 **О себе:** {info}\n"
            f"📩 **Telegram:** @{tg_username}\n"
            f"-------------------\n"
        )
    
    await message.answer(response, parse_mode="Markdown")

# Запуск бота с инициализацией базы данных
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
