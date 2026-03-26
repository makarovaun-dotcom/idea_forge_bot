import logging
import requests
import uuid
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from prompts.ru import prompts_ru
from prompts.en import prompts_en
import google.generativeai as genai

# Получаем переменные окружения
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-1.5-flash"  # стабильная модель

# База данных будет работать с SQLite, файл создастся автоматически
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "users.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  lang TEXT,
                  daily_count INTEGER,
                  last_reset TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS generations
                 (generation_id TEXT PRIMARY KEY,
                  user_id INTEGER,
                  category TEXT,
                  topic TEXT,
                  prompt TEXT,
                  response TEXT,
                  tokens_used INTEGER,
                  timestamp TEXT,
                  feedback_rating INTEGER,
                  feedback_comment TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS events
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  event_type TEXT,
                  details TEXT,
                  timestamp TEXT)''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT lang, daily_count, last_reset FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def set_lang(user_id, lang):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (user_id, lang, daily_count, last_reset) VALUES (?, ?, 0, ?)",
              (user_id, lang, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def increment_count(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET daily_count = daily_count + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def log_generation(generation_id, user_id, category, topic, prompt, response, tokens_used, timestamp):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO generations
                 (generation_id, user_id, category, topic, prompt, response, tokens_used, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (generation_id, user_id, category, topic, prompt, response, tokens_used, timestamp))
    conn.commit()
    conn.close()

def log_event(user_id, event_type, details):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    c.execute('''INSERT INTO events (user_id, event_type, details, timestamp)
                 VALUES (?, ?, ?, ?)''', (user_id, event_type, details, timestamp))
    conn.commit()
    conn.close()

def update_feedback(generation_id, rating, comment):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''UPDATE generations
                 SET feedback_rating = ?, feedback_comment = ?
                 WHERE generation_id = ?''', (rating, comment, generation_id))
    conn.commit()
    conn.close()

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
user_context = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Русский", callback_data="ru")],
                [InlineKeyboardButton("English", callback_data="en")]]
    await update.message.reply_text("Choose your language / Выберите язык:", reply_markup=InlineKeyboardMarkup(keyboard))

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data
    user_id = query.from_user.id
    set_lang(user_id, lang)
    text_ru = "Отлично! Теперь выбери категорию для генерации идеи:"
    text_en = "Great! Now choose a category for idea generation:"
    keyboard = [
        [InlineKeyboardButton("Post idea", callback_data="post"),
         InlineKeyboardButton("Brand name", callback_data="brand")],
        [InlineKeyboardButton("Slogan", callback_data="slogan"),
         InlineKeyboardButton("Video script", callback_data="video")],
        [InlineKeyboardButton("Product concept", callback_data="product"),
         InlineKeyboardButton("Random idea", callback_data="random")]
    ]
    await query.edit_message_text(text_en if lang == "en" else text_ru, reply_markup=InlineKeyboardMarkup(keyboard))

async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    category = query.data
    user_context[user_id] = {'category': category}
    lang = get_user(user_id)[0]
    prompt_text = ("Please enter the topic or niche (e.g., 'vegan snacks', 'AI tools'):"
                   if lang == "en" else "Введите тему или нишу (например, 'веганские снеки', 'инструменты AI'):")
    await query.edit_message_text(prompt_text)

async def generate_idea(update: Update, context: ContextTypes.DEFAULT_TYPE, topic: str, category: str, user_id: int, lang: str):
    prompts = prompts_en if lang == "en" else prompts_ru
    prompt_template = prompts.get(category, prompts["random"])
    prompt = prompt_template.format(topic=topic)

    generation_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()

    log_event(user_id, "generation_start", f"category={category}, topic={topic}")

    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        idea = response.text
        tokens_used = 0
    except Exception as e:
        logging.error(f"Gemini error: {e}")
        idea = ("Sorry, something went wrong. Please try again later."
                if lang == "en" else "Извините, произошла ошибка. Попробуйте позже.")
        tokens_used = 0
        log_event(user_id, "generation_error", str(e))

    log_generation(generation_id, user_id, category, topic, prompt, idea, tokens_used, timestamp)

    keyboard = [
        [InlineKeyboardButton("👍 Good", callback_data=f"fb_good_{generation_id}"),
         InlineKeyboardButton("👎 Bad", callback_data=f"fb_bad_{generation_id}")],
        [InlineKeyboardButton("💬 Comment", callback_data=f"fb_comment_{generation_id}")]
    ]
    await update.message.reply_text(idea, reply_markup=InlineKeyboardMarkup(keyboard))
    increment_count(user_id)
    del user_context[user_id]

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if 'general_feedback' in context.user_data:
        del context.user_data['general_feedback']
        log_event(user_id, "general_feedback", text)
        await update.message.reply_text("Thank you! Your feedback helps us improve.")
        return

    if 'pending_feedback_gid' in context.user_data:
        gid = context.user_data.pop('pending_feedback_gid')
        update_feedback(gid, None, text)
        await update.message.reply_text("Thank you for your comment!")
        log_event(user_id, "feedback_comment", f"generation_id={gid}, comment={text[:100]}")
        return

    if user_id not in user_context or 'category' not in user_context[user_id]:
        await update.message.reply_text("Please start over with /start")
        return

    category = user_context[user_id]['category']
    user_data = get_user(user_id)
    if not user_data:
        await update.message.reply_text("Please /start first")
        return
    lang = user_data[0]

    daily_count = user_data[1] if user_data[1] else 0
    if daily_count >= 5:
        msg = ("You've reached your daily limit (5 ideas). Upgrade to premium for unlimited!"
               if lang == "en" else "Вы исчерпали дневной лимит (5 идей). Оформите подписку для безлимитной генерации!")
        await update.message.reply_text(msg)
        return

    await generate_idea(update, context, text, category, user_id, lang)

async def feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("fb_good_"):
        generation_id = data.split("_")[2]
        update_feedback(generation_id, 1, "")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Thanks for your feedback! 👍")
        log_event(user_id, "feedback_good", f"generation_id={generation_id}")

    elif data.startswith("fb_bad_"):
        generation_id = data.split("_")[2]
        update_feedback(generation_id, 0, "")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Thanks for your feedback! We'll improve.")
        log_event(user_id, "feedback_bad", f"generation_id={generation_id}")

    elif data.startswith("fb_comment_"):
        generation_id = data.split("_")[2]
        context.user_data['pending_feedback_gid'] = generation_id
        await query.message.reply_text("Please send your comment in a text message.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Available commands:\n/start - choose language and start\n/help - this message\n/feedback - contact author")

async def general_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please send your feedback or suggestions in a text message.")
    context.user_data['general_feedback'] = True

def main():
    init_db()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("feedback", general_feedback))
    app.add_handler(CallbackQueryHandler(language_callback, pattern="^(ru|en)$"))
    app.add_handler(CallbackQueryHandler(category_callback, pattern="^(post|brand|slogan|video|product|random)$"))
    app.add_handler(CallbackQueryHandler(feedback_callback, pattern="^fb_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()
