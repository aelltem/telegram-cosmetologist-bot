import os
import json
import logging
import random
import threading
import http.server
import socketserver
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from gtts import gTTS
from apscheduler.schedulers.background import BackgroundScheduler
import httpx

# === Загрузка токенов ===
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = "openchat/openchat-7b"

logging.basicConfig(level=logging.INFO)

FILES = {
    "users": "users.json",
    "settings": "user_settings.json",
    "profile": "user_profile.json",
    "history": "history.json",
    "reminders": "reminders.json",
    "facts": "facts.py"
}

scheduler = BackgroundScheduler()
scheduler.start()

def load_json(name):
    try:
        with open(FILES[name], "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_json(name, data):
    with open(FILES[name], "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = load_json("users")
    users[str(user.id)] = user.username or user.first_name
    save_json("users", users)

    keyboard = ReplyKeyboardMarkup([
        ["💬 Консультация"],
        ["🔍 Анализ состава"],
        ["📆 Напоминание"],
        ["💡 Интересный факт"],
        ["⚙️ Настройки"]
    ], resize_keyboard=True)

    greeting = f"Привет, {user.first_name}! Я Полина Павловна 🌸\n" \
               f"Я помогу тебе с уходом за кожей, составом средств и напоминаниями. Всё в одном месте!"

    await update.message.reply_text(greeting, reply_markup=keyboard)

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = str(update.effective_user.id)

    if text == "⚙️ Настройки":
        keyboard = ReplyKeyboardMarkup([
            ["🎯 Персонализация"],
            ["🔊 Формат ответа"],
            ["🧠 Настроение"],
            ["🗃 Моя история"],
            ["⬅️ Назад"]
        ], resize_keyboard=True)
        await update.message.reply_text("Выберите настройку:", reply_markup=keyboard)

    elif text == "⬅️ Назад":
        await start(update, context)

    elif text == "🎯 Персонализация":
        await update.message.reply_text("Какой у тебя тип кожи?", reply_markup=ReplyKeyboardMarkup([
            ["сухая", "жирная", "комбинированная"],
            ["⬅️ Назад"]
        ], resize_keyboard=True))

    elif text == "🔊 Формат ответа":
        await update.message.reply_text("Выбери формат ответа:", reply_markup=ReplyKeyboardMarkup([
            ["📝 Текст", "🔊 Голос"],
            ["⬅️ Назад"]
        ], resize_keyboard=True))

    elif text == "🧠 Настроение":
        await update.message.reply_text("Как ты себя чувствуешь?", reply_markup=ReplyKeyboardMarkup([
            ["😄 Хорошо", "😐 Нормально", "😔 Плохо"],
            ["⬅️ Назад"]
        ], resize_keyboard=True))

    elif text == "🗃 Моя история":
        history = load_json("history").get(user_id, [])
        if not history:
            await update.message.reply_text("История пока пуста.")
        else:
            reply = "\n\n".join([f"❓ {h['q']}\n💬 {h['a']}" for h in history[-5:]])
            await update.message.reply_text(reply, reply_markup=ReplyKeyboardMarkup([
                ["⬅️ Назад"]
            ], resize_keyboard=True))

    elif text == "💡 Интересный факт":
        try:
            from facts import INTERESTING_FACTS
        except:
            INTERESTING_FACTS = []
        facts = load_json("history").get("facts", [])
        unused = [f for f in INTERESTING_FACTS if f not in facts]
        if not unused:
            facts = []
            unused = INTERESTING_FACTS
        if unused:
            fact = random.choice(unused)
            facts.append(fact)
            h = load_json("history")
            h["facts"] = facts
            save_json("history", h)
            await update.message.reply_text(f"💡 Факт: {fact}")

    elif text == "📆 Напоминание":
        await update.message.reply_text("Напиши напоминание в формате:\n21:00 нанести крем", reply_markup=ReplyKeyboardMarkup([
            ["⬅️ Назад"]
        ], resize_keyboard=True))

    elif text == "🔍 Анализ состава":
        context.user_data["mode"] = "analyze"
        await update.message.reply_text("Введи название средства или состав — я разберу!", reply_markup=ReplyKeyboardMarkup([
            ["⬅️ Назад"]
        ], resize_keyboard=True))

    elif text == "💬 Консультация":
        context.user_data["mode"] = "recommend"
        await update.message.reply_text("Опиши проблему или задай вопрос:", reply_markup=ReplyKeyboardMarkup([
            ["⬅️ Назад"]
        ], resize_keyboard=True))

    elif text in ["сухая", "жирная", "комбинированная"]:
        profile = load_json("profile")
        profile[user_id] = {"skin": text}
        save_json("profile", profile)
        await update.message.reply_text("Запомнила тип кожи 💖")

    elif text in ["📝 Текст", "🔊 Голос"]:
        settings = load_json("settings")
        settings[user_id] = settings.get(user_id, {})
        settings[user_id]["voice"] = "Голос" in text
        save_json("settings", settings)
        await update.message.reply_text("Формат ответа сохранён 🎙")

    elif text in ["😄 Хорошо", "😐 Нормально", "😔 Плохо"]:
        mood = "good" if "Хорошо" in text else "bad" if "Плохо" in text else "normal"
        settings = load_json("settings")
        settings[user_id] = settings.get(user_id, {})
        settings[user_id]["mood"] = mood
        save_json("settings", settings)
        await update.message.reply_text("Настроение учтено ❤️")

    elif ":" in text and len(text) >= 8 and text[:5].isdigit():
        hour, minute = map(int, text[:5].split(":"))
        note = text[6:]
        reminders = load_json("reminders")
        reminders.setdefault(user_id, []).append({"time": f"{hour:02}:{minute:02}", "text": note})
        save_json("reminders", reminders)
        await update.message.reply_text("Напоминание сохранено ✅")

    elif "mode" in context.user_data:
        mode = context.user_data.pop("mode")
        if mode == "recommend":
            prompt = f"Посоветуй, пожалуйста, как поступить. {text}"
        else:
            prompt = text
        result = await analyze_ingredients(prompt)
        await send_response(update, context, user_id, text, result)

def add_to_history(user_id, q, a):
    history = load_json("history")
    history.setdefault(str(user_id), []).append({"q": q, "a": a, "at": datetime.now().isoformat()})
    save_json("history", history)

async def send_response(update, context, user_id, query, answer):
    settings = load_json("settings").get(user_id, {})
    add_to_history(user_id, query, answer)
    if settings.get("voice"):
        tts = gTTS(answer, lang="ru")
        file = f"/tmp/{user_id}_resp.ogg"
        tts.save(file)
        with open(file, "rb") as f:
            await update.message.reply_voice(voice=f)
    else:
        await update.message.reply_text(answer)

async def analyze_ingredients(text):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/polina_pavlovna_bot",
        "X-Title": "Cosmetologist Bot"
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "Ты косметолог. Помоги или проанализируй состав."},
            {"role": "user", "content": text}
        ]
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            data = resp.json()
            logging.info(f"OpenRouter response: {data}")
            return data.get("choices", [{}])[0].get("message", {}).get("content", "Ответ не получен.")
    except Exception as e:
        logging.error(f"Ошибка анализа: {e}")
        return f"Ошибка анализа: {e}"

def check_reminders(bot):
    now = datetime.now().strftime("%H:%M")
    reminders = load_json("reminders")
    for uid, entries in reminders.items():
        for item in entries:
            if item["time"] == now:
                try:
                    bot.send_message(chat_id=int(uid), text=f"🔔 Напоминание: {item['text']}")
                except Exception as e:
                    logging.error(f"Ошибка отправки напоминания: {e}")

def run_dummy_server():
    PORT = int(os.environ.get("PORT", 10000))
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving dummy server at port {PORT}")
        httpd.serve_forever()

def main():
    app = Application.builder().token(TOKEN).build()
    global bot
    bot = app.bot
    scheduler.add_job(lambda: check_reminders(bot), "interval", minutes=1)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))

    threading.Thread(target=run_dummy_server, daemon=True).start()
    app.run_polling()

if __name__ == "__main__":
    main()
