import os
import json
import logging
import random
import http.server
import socketserver
import threading
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from apscheduler.schedulers.background import BackgroundScheduler
from gtts import gTTS
from dotenv import load_dotenv

# Загрузка токенов
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Основной конфиг
MASTER_ADMIN_ID = 5104062125
DATA_FILES = {
    "admins": "admins.json",
    "users": "users.json",
    "settings": "user_settings.json",
    "profiles": "user_profile.json",
    "reminders": "reminders.json",
    "history": "history.json",
}

# Логгирование
logging.basicConfig(level=logging.INFO)

# ===== УТИЛИТЫ =====

def load_json(name):
    try:
        with open(DATA_FILES[name], "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(name, data):
    with open(DATA_FILES[name], "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_admin(user_id):
    return user_id == MASTER_ADMIN_ID or str(user_id) in load_json("admins")

def add_to_history(user_id, q, a):
    history = load_json("history")
    history.setdefault(str(user_id), []).append({
        "q": q,
        "a": a,
        "at": datetime.now().isoformat()
    })
    save_json("history", history)

def get_user_settings(user_id):
    settings = load_json("settings")
    return settings.get(str(user_id), {"voice": False, "mood": "normal"})

# ====== HANDLERS ======

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users = load_json("users")
    users[str(user_id)] = True
    save_json("users", users)

    keyboard = ReplyKeyboardMarkup([
        ["📆 Напоминание", "🧬 Персонализация"],
        ["🔍 Анализ состава", "🧠 Настроение"],
        ["🔊 Формат ответа", "🗃 Моя история"]
    ], resize_keyboard=True)

    await update.message.reply_text("Привет, я Полина Павловна 🌸 Твой AI-косметолог.", reply_markup=keyboard)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message.text

    if msg == "🧬 Персонализация":
        await update.message.reply_text("Какой у тебя тип кожи? (сухая / жирная / комбинированная)")
        return 1

    if msg == "📆 Напоминание":
        await update.message.reply_text("Напиши в формате: 21:00 нанести ночной крем")
        return 2

    if msg == "🔍 Анализ состава":
        await update.message.reply_text("Пришли состав или название продукта для анализа")
        return 3

    if msg == "🔊 Формат ответа":
        await update.message.reply_text("Выбери:", reply_markup=ReplyKeyboardMarkup(
            [["📝 Текст"], ["🔊 Голос"]], resize_keyboard=True
        ))
        return 4

    if msg == "🧠 Настроение":
        await update.message.reply_text("Как ты себя чувствуешь?", reply_markup=ReplyKeyboardMarkup(
            [["😄 Хорошо", "😐 Нормально", "😔 Плохо"]], resize_keyboard=True
        ))
        return 5

    if msg == "🗃 Моя история":
        history = load_json("history").get(str(user_id), [])
        if not history:
            await update.message.reply_text("История пока пуста.")
        else:
            reply = "\n\n".join([f"❓ {h['q']}\n💬 {h['a']}" for h in history[-5:]])
            await update.message.reply_text(reply)

async def personalization_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profiles = load_json("profiles")
    profiles[str(user_id)] = {"skin": update.message.text}
    save_json("profiles", profiles)
    await update.message.reply_text("Запомнила 🌸")
    return ConversationHandler.END

async def reminder_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    time_text = update.message.text
    try:
        t, note = time_text.split(" ", 1)
        hour, minute = map(int, t.split(":"))
        scheduler.add_job(
            lambda: context.bot.send_message(chat_id=user_id, text=f"🔔 Напоминание: {note}"),
            trigger="cron", hour=hour, minute=minute, id=f"{user_id}_{note}"
        )
        await update.message.reply_text("Напоминание установлено ✅")
    except:
        await update.message.reply_text("Неверный формат. Пример: 21:00 нанести крем.")
    return ConversationHandler.END

async def analyze_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.message.text
    # Эмуляция анализа
    result = f"🧪 Анализ:\n\n{query}\n\n🌿 Это средство может быть полезным, если не содержит спирта."
    add_to_history(user_id, query, result)

    settings = get_user_settings(user_id)
    if settings.get("voice"):
        tts = gTTS(result, lang="ru")
        audio_file = f"/tmp/{user_id}_voice.ogg"
        tts.save(audio_file)
        with open(audio_file, "rb") as f:
            await update.message.reply_voice(voice=f)
    else:
        await update.message.reply_text(result)
    return ConversationHandler.END

async def voice_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    choice = update.message.text
    settings = load_json("settings")
    settings[str(user_id)] = settings.get(str(user_id), {})
    settings[str(user_id)]["voice"] = True if "Голос" in choice else False
    save_json("settings", settings)
    await update.message.reply_text("Настройка сохранена ✅")
    return ConversationHandler.END

async def mood_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mood = "good" if "Хорошо" in update.message.text else "bad" if "Плохо" in update.message.text else "normal"
    settings = load_json("settings")
    settings[str(user_id)] = settings.get(str(user_id), {})
    settings[str(user_id)]["mood"] = mood
    save_json("settings", settings)
    await update.message.reply_text("Учту это в своих ответах 🧠")
    return ConversationHandler.END

# ===== СЕРВЕР ДЛЯ RENDER =====

def run_dummy_server():
    PORT = int(os.environ.get("PORT", 10000))
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving dummy server at port {PORT}")
        httpd.serve_forever()

# ===== ОСНОВНОЙ ЗАПУСК =====

def main():
    global scheduler
    scheduler = BackgroundScheduler()
    scheduler.start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT, text_handler)],
        states={
            1: [MessageHandler(filters.TEXT, personalization_step)],
            2: [MessageHandler(filters.TEXT, reminder_step)],
            3: [MessageHandler(filters.TEXT, analyze_step)],
            4: [MessageHandler(filters.TEXT, voice_setting)],
            5: [MessageHandler(filters.TEXT, mood_setting)],
        },
        fallbacks=[]
    ))

    app.run_polling()

# 🔥 Запуск порта + бота
threading.Thread(target=run_dummy_server, daemon=True).start()
main()
