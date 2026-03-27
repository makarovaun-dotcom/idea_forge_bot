import logging
import requests
import uuid
import os
from datetime import datetime
import google.genai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from config import TELEGRAM_TOKEN, GEMINI_API_KEY
from database import init_db, get_user, set_lang, increment_count, log_generation, log_event, update_feedback
from prompts.ru import prompts_ru
from prompts.en import prompts_en
# В самом верху, после других импортов
from flask import Flask
import threading

app_web = Flask(__name__)

@app_web.route('/')
def health_check():
    return "Idea Forge Bot is running", 200

def run_web():
    app_web.run(host='0.0.0.0', port=8080)

# В функции main() перед app.run_polling() добавьте:
threading.Thread(target=run_web, daemon=True).start()
# Инициализация клиента Gemini
client = genai.Client(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "gemini-1.5-flash"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

user_context = {}

def set_commands():
    commands_ru = [
        {"command": "start", "description": "Начать работу с ботом"},
        {"command": "help", "description": "Помощь и информация"},
        {"command": "feedback", "description": "Связаться с автором"}
    ]
    commands_en = [
        {"command": "start", "description": "Start working with the bot"},
        {"command": "help", "description": "Help and info"},
        {"command": "feedback", "description": "Contact the author"}
    ]
    commands_default = [
        {"command": "start", "description": "Start / Начать"},
        {"command": "help", "description": "Help / Помощь"},
        {"command": "feedback", "description": "Contact / Связаться"}
    ]

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setMyCommands"
    try:
        requests.post(url, json={"commands": commands_ru, "language_code": "ru"})
        requests.post(url, json={"commands": commands_en, "language_code": "en"})
        requests.post(url, json={"commands": commands_default})
        logging.info("Commands set successfully")
    except Exception as e:
        logging.error(f"Failed to set commands: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Русский", callback_data="ru")],
        [InlineKeyboardButton("English", callback_data="en")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose your language / Выберите язык:", reply_markup=reply_markup)

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
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text_en if lang == "en" else text_ru, reply_markup=reply_markup)

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
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
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
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(idea, reply_markup=reply_markup)

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
    await update.message.reply_text(
        "Available commands:\n/start - choose language and start\n/help - this message\n/feedback - contact author"
    )

async def general_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please send your feedback or suggestions in a text message.")
    context.user_data['general_feedback'] = True

def main():
    init_db()
    set_commands()

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
