import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import io
from datetime import datetime
import yt_dlp

API_TOKEN = "8445916348:AAEnSc8jcu8or3vlBFlSa5fmt2jKbxhu_m8"
ADMIN_ID = 1086839553

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

users_data = {}
FREE_LIMIT = 3

# -------------------- Клавиатуры --------------------
def lang_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    kb.add(KeyboardButton("🇷🇺 Русский"), KeyboardButton("🇬🇧 English"), KeyboardButton("🇦🇿 Azərbaycanca"))
    return kb

def pro_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    kb.add(KeyboardButton("💎 1 месяц — $3.99"))
    kb.add(KeyboardButton("💎 6 месяцев — $19.99"))
    kb.add(KeyboardButton("💎 12 месяцев — $43.99"))
    return kb

# -------------------- Команды --------------------
@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    await message.reply("Выберите язык / Select language / Dil seçin:", reply_markup=lang_keyboard())

@dp.message_handler(lambda message: message.text in ["🇷🇺 Русский", "🇬🇧 English", "🇦🇿 Azərbaycanca"])
async def set_language(message: types.Message):
    users_data[message.from_user.id] = {
        "language": message.text,
        "pro": False,
        "plan": None,
        "downloads_today": 0,
        "last_download": None,
        "waiting_for_check": False
    }
    await message.reply("Выберите тариф PRO-подписки:", reply_markup=pro_keyboard())

@dp.message_handler(lambda message: message.text in ["💎 1 месяц — $3.99", "💎 6 месяцев — $19.99", "💎 12 месяцев — $43.99"])
async def set_pro(message: types.Message):
    user = users_data[message.from_user.id]
    user["plan"] = message.text
    user["waiting_for_check"] = True
    await message.reply(
        f"💳 Оплатите на карту: <b><u>4169 7388 1194 7708</u></b>\n"
        "После оплаты отправьте сюда чек (скрин/файл) для проверки администратором.",
        parse_mode="HTML"
    )

# -------------------- Обработка чека --------------------
@dp.message_handler(content_types=["photo", "document"])
async def receive_check(message: types.Message):
    user = users_data.get(message.from_user.id)
    if user and user.get("waiting_for_check"):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{message.from_user.id}"))
        kb.add(InlineKeyboardButton("❌ Отказать", callback_data=f"reject_{message.from_user.id}"))

        text = f"📥 Поступил чек от {message.from_user.first_name} ({message.from_user.id})\nТариф: {user['plan']}"
        if message.photo:
            await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=text, reply_markup=kb)
        elif message.document:
            await bot.send_document(ADMIN_ID, message.document.file_id, caption=text, reply_markup=kb)

        await message.reply("Чек отправлен админу. После проверки вы получите PRO-доступ.")
    else:
        await message.reply("Сначала выберите тариф PRO-подписки и оплатите.")

# -------------------- Обработка кнопок админа --------------------
@dp.callback_query_handler(lambda c: c.data and c.data.startswith(("confirm_", "reject_")))
async def process_check_callback(callback_query: types.CallbackQuery):
    action, user_id_str = callback_query.data.split("_")
    user_id = int(user_id_str)
    user = users_data.get(user_id)
    if not user:
        await callback_query.answer("Пользователь не найден.", show_alert=True)
        return

    if action == "confirm":
        user["pro"] = True
        user["waiting_for_check"] = False
        await bot.send_message(user_id, "✅ Ваша оплата подтверждена! PRO-доступ активирован.")
        await callback_query.message.edit_caption(f"✅ Подтверждено администратором.\nТариф: {user['plan']}")
    elif action == "reject":
        user["pro"] = False
        user["waiting_for_check"] = False
        await bot.send_message(user_id, "❌ Ваша оплата отклонена администратором. Попробуйте снова или свяжитесь с поддержкой.")
        await callback_query.message.edit_caption(f"❌ Отклонено администратором.\nТариф: {user['plan']}")

    await callback_query.answer()

# -------------------- Скачивание TikTok через yt-dlp --------------------
def download_tiktok_video(url):
    buffer = io.BytesIO()
    ydl_opts = {
        'format': 'mp4',
        'quiet': True,
        'outtmpl': 'video.mp4',
        'noplaylist': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        with open("video.mp4", "rb") as f:
            buffer.write(f.read())
        buffer.seek(0)
        return buffer.read(), None
    except Exception as e:
        return None, str(e)

@dp.message_handler(lambda message: "tiktok.com" in message.text)
async def handle_tiktok(message: types.Message):
    user = users_data.get(message.from_user.id)
    if not user:
        await message.reply("Сначала выберите язык и тариф PRO.")
        return

    now = datetime.now()
    last_download = user.get("last_download")
    if last_download and last_download.date() < now.date():
        user["downloads_today"] = 0

    if not user["pro"] and user.get("downloads_today", 0) >= FREE_LIMIT:
        await message.reply("🚫 Лимит бесплатных скачиваний (3 раза в день) достигнут.")
        return

    await message.reply("⏳ Скачиваю видео без водяного знака...")
    url = message.text
    video, error = download_tiktok_video(url)
    if video:
        await message.answer_document(InputFile(io.BytesIO(video), filename="tiktok_video.mp4"))
        user["downloads_today"] += 1
        user["last_download"] = now
    else:
        await message.reply(f"❌ Ошибка при скачивании видео: {error}")

# -------------------- Запуск бота --------------------
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
