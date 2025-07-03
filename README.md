🗳️ Daily Poll Telegram Bot

A simple Telegram bot that sends a daily poll to all connected group chats at a specified time (default: 21:00 Kyiv time).

## 🚀 Features

- Automatically tracks which groups added the bot.
- Sends a daily non-anonymous poll.
- Easily configurable poll question and options.
- Built-in scheduler (via `JobQueue` from python-telegram-bot).
- Uses `.env` file for token and configuration.
- Supports timezone-based scheduling (default: Europe/Kyiv).

## 🛠️ Requirements

- Python 3.10+
- See `requirements.txt` for Python dependencies.

Install them with:

```bash
pip install -r requirements.txt
