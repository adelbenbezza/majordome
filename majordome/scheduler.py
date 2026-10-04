"""Messages the bot sends on its own, at set times (JobQueue).

JobQueue is python-telegram-bot's built-in scheduler: we tell it "run this function
every day at 08:00 Europe/Paris" and it calls it, handling daylight saving time.
Jobs live in memory, so they're set up again from the database at every start.
"""

import logging
from datetime import datetime

from telegram.ext import Application, ContextTypes

from .actions import format_brief
from .config import Config
from .db import Database

log = logging.getLogger(__name__)

BRIEF_JOB = "morning_brief"


def owner_id(config: Config, db: Database) -> int | None:
    """Who to send messages to. In a private chat, the chat id is the user's id."""
    return config.owner_telegram_id or db.get_owner_id()


async def send_brief(context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    chat_id = owner_id(config, db)
    if chat_id is None:
        log.info("No owner yet, skipping the morning brief")
        return
    text = format_brief(db, datetime.now(config.timezone), db.get_language())
    await context.bot.send_message(chat_id, text)


def schedule_brief(app: Application) -> None:
    """(Re)schedule the daily brief from the time saved in the database."""
    config: Config = app.bot_data["config"]
    db: Database = app.bot_data["db"]

    for job in app.job_queue.get_jobs_by_name(BRIEF_JOB):
        job.schedule_removal()

    brief_time = db.get_brief_time()
    if brief_time is None:
        log.info("Morning brief is off")
        return
    # Attaching the timezone makes JobQueue fire at 08:00 Paris time, summer and winter.
    app.job_queue.run_daily(send_brief, time=brief_time.replace(tzinfo=config.timezone), name=BRIEF_JOB)
    log.info("Morning brief scheduled every day at %s (%s)", f"{brief_time:%H:%M}", config.timezone)
