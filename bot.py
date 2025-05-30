
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.utils import executor
from aiogram.dispatcher.filters import Command
import sqlite3
import logging
from config import BOT_TOKEN, MASTER_ID

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Инициализация базы данных
conn = sqlite3.connect("referrals.db")
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    referral_code TEXT UNIQUE
)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_id INTEGER,
    car_brand TEXT,
    plate_number TEXT
)""")
conn.commit()

def generate_referral_code(user_id):
    return f"U{user_id}"

@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT referral_code FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        referral_code = row[0]
    else:
        referral_code = generate_referral_code(user_id)
        cursor.execute("INSERT OR IGNORE INTO users (user_id, referral_code) VALUES (?, ?)", (user_id, referral_code))
        conn.commit()
    await message.answer(f"Привет! Твой реферальный код: <code>{referral_code}</code>", parse_mode=ParseMode.HTML)

@dp.message_handler(commands=["добавить"])
async def add_referral(message: types.Message):
    parts = message.text.split()
    if len(parts) != 3:
        return await message.reply("Используй формат: /добавить [Марка] [Номер]")
    brand, plate = parts[1], parts[2].upper()
    referrer_id = message.from_user.id
    cursor.execute("INSERT INTO referrals (referrer_id, car_brand, plate_number) VALUES (?, ?, ?)", (referrer_id, brand, plate))
    conn.commit()
    await message.answer(f"Машина {brand} с номером {plate} сохранена.")
    await bot.send_message(MASTER_ID, f"🔔 Новый клиент от @{message.from_user.username} ({referrer_id}): {brand} {plate}")

@dp.message_handler(commands=["мои"])
async def list_referrals(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT car_brand, plate_number FROM referrals WHERE referrer_id = ?", (user_id,))
    rows = cursor.fetchall()
    if not rows:
        return await message.reply("У тебя пока нет сохранённых клиентов.")
    text = "\n".join([f"{b} {p}" for b, p in rows])
    await message.answer(f"Твои рекомендации:\n{text}")

@dp.message_handler(commands=["удалить"])
async def delete_referral(message: types.Message):
    parts = message.text.split()
    if len(parts) != 2:
        return await message.reply("Используй формат: /удалить [Номер]")
    plate = parts[1].upper()
    cursor.execute("DELETE FROM referrals WHERE referrer_id = ? AND plate_number = ?", (message.from_user.id, plate))
    conn.commit()
    await message.answer(f"Запись с номером {plate} удалена.")

@dp.message_handler(commands=["редактировать"])
async def edit_referral(message: types.Message):
    parts = message.text.split()
    if len(parts) != 3:
        return await message.reply("Формат: /редактировать [Старый номер] [Новый номер]")
    old_plate, new_plate = parts[1].upper(), parts[2].upper()
    cursor.execute("UPDATE referrals SET plate_number = ? WHERE referrer_id = ? AND plate_number = ?", (new_plate, message.from_user.id, old_plate))
    conn.commit()
    await message.answer(f"Номер {old_plate} изменён на {new_plate}.")

@dp.message_handler(commands=["поиск"])
async def search_referral(message: types.Message):
    query = message.text.split(maxsplit=1)
    if len(query) != 2:
        return await message.reply("Формат: /поиск [Марка или Номер]")
    term = query[1].upper()
    cursor.execute("""
        SELECT u.referral_code, r.car_brand, r.plate_number 
        FROM referrals r
        JOIN users u ON r.referrer_id = u.user_id
        WHERE r.car_brand LIKE ? OR r.plate_number LIKE ?
    """, (f"%{term}%", f"%{term}%"))
    rows = cursor.fetchall()
    if not rows:
        return await message.reply("Совпадений не найдено.")
    text = "\n".join([f"{b} {p} → код: {c}" for c, b, p in rows])
    await message.answer(f"Найдено:\n{text}")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
