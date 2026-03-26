# Idea Forge Bot

Telegram-бот, который генерирует креативные идеи для контента, маркетинга и стартапов с помощью Google Gemini.

## Deploy to Render

1. Нажмите кнопку:
   [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=YOUR_REPO_URL)

   Замените `YOUR_REPO_URL` на ссылку вашего репозитория.

2. Добавьте переменные окружения:
   - `TELEGRAM_TOKEN` — токен вашего бота от @BotFather
   - `GEMINI_API_KEY` — ключ от Google AI Studio

3. Наслаждайтесь!

## Локальный запуск

```bash
pip install -r requirements.txt
python bot.py
