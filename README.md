# Idea Forge Bot

Idea Forge — это Telegram-бот, генерирующий креативные идеи для контент-креаторов, маркетологов и стартапов. Использует Google Gemini AI.

## 🚀 Быстрый старт (деплой на Render)

Нажмите на кнопку ниже, чтобы развернуть бота на Render:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

После нажатия на кнопку:
1. Войдите в свой аккаунт Render (или создайте новый).
2. Укажите имя для сервиса.
3. Добавьте переменные окружения:
   - `TELEGRAM_TOKEN` – токен вашего бота от @BotFather.
   - `GEMINI_API_KEY` – API-ключ от Google AI Studio.
4. Нажмите "Apply". Бот будет собран и запущен автоматически.

## 🔧 Локальный запуск

1. Клонируйте репозиторий.
2. Создайте виртуальное окружение: `python -m venv venv`
3. Активируйте: `venv\Scripts\activate` (Windows) или `source venv/bin/activate` (Linux/Mac)
4. Установите зависимости: `pip install -r requirements.txt`
5. Создайте файл `.env` и добавьте в него свои ключи (по примеру `.env.example`).
6. Запустите бота: `python bot.py`

## 📝 Команды бота

- `/start` – выбор языка и начало работы
- `/help` – справка
- `/feedback` – отправить отзыв

## 🔒 Лицензия

MIT
