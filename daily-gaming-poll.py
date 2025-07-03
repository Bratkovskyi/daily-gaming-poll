import asyncio
import json
import logging
import os
from pathlib import Path
from typing import List
from zoneinfo import ZoneInfo
from datetime import time
from telegram import Update
from telegram.error import Conflict
from telegram.ext import ApplicationHandlerStop
from telegram.error import Forbidden
from telegram.error import ChatMigrated
from telegram.ext import (
    ApplicationBuilder,
    ChatMemberHandler,
    ContextTypes,
    AIORateLimiter,
)

###############################################################################
# Configuration
###############################################################################

# Load .env only locally
# from dotenv import load_dotenv
# if os.environ.get("RAILWAY_STATIC_URL") is None:
#     load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUPS_FILE = Path("groups.json")
POLL_QUESTION = "Кто будет сегодня заниматься?"
POLL_OPTIONS = ["Я буду", "Возможно позже", "Не сегодня"]
TIMEZONE = ZoneInfo("Europe/Kyiv")  # for run_daily

###############################################################################
# Logging
###############################################################################
logging.basicConfig(
    format="%(asctime)s | %(levelname)8s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


###############################################################################
# Error Handler
###############################################################################
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, (ApplicationHandlerStop, Conflict)):
        return
    log.error("Exception while handling update:", exc_info=context.error)

###############################################################################
# Working with groups.json file
###############################################################################
def load_groups() -> List[int]:
    if GROUPS_FILE.exists():
        return json.loads(GROUPS_FILE.read_text())
    return []


def save_groups(groups: List[int]) -> None:
    GROUPS_FILE.write_text(json.dumps(groups, indent=2))


def add_group(chat_id: int) -> None:
    groups = load_groups()
    if chat_id not in groups:
        groups.append(chat_id)
        save_groups(groups)
        log.info("Added group %s", chat_id)


def remove_group(chat_id: int) -> None:
    groups = load_groups()
    if chat_id in groups:
        groups.remove(chat_id)
        save_groups(groups)
        log.info("Removed group %s", chat_id)


###############################################################################
# Handler for detecting bot's status changes in a group
###############################################################################
async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    old_state = update.my_chat_member.old_chat_member.status
    new_state = update.my_chat_member.new_chat_member.status
    chat_id = chat.id
    title = chat.title or "Untitled"

    # Bot was added or re-added to the group
    if old_state in ("kicked", "left") and new_state in ("member", "administrator"):
        try:
            add_group(chat_id)
            await context.bot.send_message(
                chat_id,
                f"👋 Хеллоу Амигос, *{title}*!\n"
                "Теперь я буду, место Влада слать ежедневный опрос. "
                "Проверьте, что у меня есть право *«Создавать опросы»*.",
                parse_mode="Markdown",
            )
        except ChatMigrated as e:
            log.warning("Chat migrated to supergroup: %s → %s", chat_id, e.new_chat_id)
            remove_group(chat_id)
            add_group(e.new_chat_id)
            await context.bot.send_message(
                e.new_chat_id,
                f"✅ Group updated! New chat ID: `{e.new_chat_id}`",
                parse_mode="Markdown",
            )


###############################################################################
# Daily poll job (or every 30s for testing)
###############################################################################
async def daily_poll_job(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    groups = load_groups()
    for gid in groups[:]:  # copy to safely modify while iterating
        try:
            await bot.send_poll(
                chat_id=gid,
                question=POLL_QUESTION,
                options=POLL_OPTIONS,
                is_anonymous=False,
            )
            log.info("Poll sent to %s", gid)
        except ChatMigrated as e:
            log.warning("Group %s migrated to %s", gid, e.new_chat_id)
            remove_group(gid)
            add_group(e.new_chat_id)
        except Forbidden:
            log.warning("Bot was removed from group %s. Removing from list.", gid)
            remove_group(gid)
        except Exception as exc:
            log.error("Error sending poll to %s: %s", gid, exc)


###############################################################################
# Entry point
###############################################################################
async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set!")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .rate_limiter(AIORateLimiter())
        .build()
    )

    # Handle bot being added or removed from a group
    app.add_handler(
        ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER)
    )

    # Global Error Handler
    app.add_error_handler(error_handler)

    # Delete any existing webhook to prevent conflicts with polling
    await app.bot.delete_webhook(drop_pending_updates=True)

    # Schedule the daily poll job
    poll_time = time(hour=19, minute=10, tzinfo=TIMEZONE)
    app.job_queue.run_daily(daily_poll_job, poll_time)

    log.info("Bot started. Waiting to be added to groups…")
    await app.run_polling()  # blocks until Ctrl+C


if __name__ == "__main__":
    import nest_asyncio

    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
