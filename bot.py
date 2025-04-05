import os
import logging
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application as TelegramApplication,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    filters,
)
import openai
import random

# Загрузка переменных из .env
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Проверка токенов
if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise ValueError("Необходимы TELEGRAM_BOT_TOKEN и OPENAI_API_KEY в .env")

# Настройка OpenAI
openai.api_key = OPENAI_API_KEY

# Настройка логов
logging.basicConfig(level=logging.INFO)

BOT_NAME = "Полина Павловна 🌸"
INTRO_TEXT = (
    f"Привет! Я {BOT_NAME}, ваш косметолог-бот 🧴\n"
    "Опиши свою проблему с кожей, волосами или уходом — и я помогу!\n"
    "Например: 'Что делать с прыщами?' или 'Какой крем выбрать?'"
)

INTERESTING_FACTS = [
    "Кожа обновляется каждые 28 дней 🌿",
    "Волосы — второй по скорости растущий орган 🧠",
    "Солнцезащитный крем нужен даже в пасмурную погоду 🌥",
]

# Генерация ответа через OpenAI
def generate_response(user_input: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты профессиональный врач-косметолог по имени Полина Павловна. "
                        "Ты помогаешь людям с кожей, волосами, подбором средств. "
                        "Отвечай дружелюбно, понятно и с эмодзи."
                    )
                },
                {"role": "user", "content": user_input}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI Error: {e}")
        return "Извините, не удалось получить ответ от ИИ 😔"

# /start
async def start(update: Update, context: CallbackContext):
    keyboard = [
        [KeyboardButton("Интересные факты")],
        [KeyboardButton("Помогите выбрать средства")],
    ]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(INTRO_TEXT, reply_markup=markup)

# Ответ на текст
async def handle_message(update: Update, context: CallbackContext):
    text = update.message.text.strip()

    if text.lower() == "интересные факты":
        sent = context.user_data.setdefault("sent_facts", set())
        available = [f for f in INTERESTING_FACTS if f not in sent]
        if not available:
            sent.clear()
            available = INTERESTING_FACTS
        fact = random.choice(available)
        sent.add(fact)
        await update.message.reply_text(f"💡 Факт: {fact}")
        return

    if text.lower() == "помогите выбрать средства":
        await update.message.reply_text("Уточни проблему (например, прыщи, жирная кожа, сухость и т.п.) 🧴")
        return

    response = generate_response(text)
    await update.message.reply_text(response)

# Запуск бота
def main():
    app = TelegramApplication.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.info("Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
