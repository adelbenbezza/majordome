"""Messages the bot sends on its own, at set times (JobQueue).

JobQueue is python-telegram-bot's built-in scheduler: we tell it "run this function
every day at 08:00 Europe/Paris" and it calls it, handling daylight saving time.
Jobs live in memory, so they're set up again from the database at every start.

Two kinds of jobs:
- daily messages (morning brief, evening check-in), at the times saved in settings;
- a clock that runs every minute and sends whatever reminders are due (reminders.py).
  Checking every minute is simpler than scheduling one job per reminder, which would
  have to be redone whenever a task changes or the bot restarts.
"""

import logging
from datetime import datetime

from telegram.ext import Application, ContextTypes

from .actions import format_brief, format_checkin
from .buttons import evening_keyboard, single_keyboard, today_keyboard
from .config import Config
from .db import DAILY_MESSAGES, Database
from .reminders import due_notices

log = logging.getLogger(__name__)

CLOCK_JOB = "clock"


def owner_id(config: Config, db: Database) -> int | None:
    """Who to send messages to. In a private chat, the chat id is the user's id."""
    return config.owner_telegram_id or db.get_owner_id()


def _owner_context(context: ContextTypes.DEFAULT_TYPE):
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    return owner_id(config, db), db, datetime.now(config.timezone), db.get_language()


async def send_brief(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id, db, now, lang = _owner_context(context)
    if chat_id is None:
        log.info("No owner yet, skipping the morning brief")
        return
    await context.bot.send_message(chat_id, format_brief(db, now, lang), reply_markup=today_keyboard(db, now, lang))


async def send_checkin(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id, db, now, lang = _owner_context(context)
    if chat_id is None:
        return
    await context.bot.send_message(chat_id, format_checkin(db, now, lang), reply_markup=evening_keyboard(db, now, lang))


async def clock(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Every minute: send the reminders and follow-ups that are due."""
    chat_id, db, now, lang = _owner_context(context)
    if chat_id is None:
        return
    for notice in due_notices(db, now, lang):
        # Record first: if sending failed and we retried every minute, a broken message
        # could be sent over and over. Missing one reminder is the lesser evil.
        if db.mark_notified(notice.kind, notice.item_id, notice.slot, notice.type):
            keyboard = single_keyboard(db, notice.kind, notice.item_id, notice.day, lang)
            await context.bot.send_message(chat_id, notice.text, reply_markup=keyboard)


DAILY_SENDERS = {"brief": send_brief, "checkin": send_checkin}


def schedule_daily(app: Application) -> None:
    """(Re)schedule the brief and the check-in from the times saved in the database."""
    config: Config = app.bot_data["config"]
    db: Database = app.bot_data["db"]

    for name in DAILY_MESSAGES:
        for job in app.job_queue.get_jobs_by_name(name):
            job.schedule_removal()
        at = db.get_daily_time(name)
        if at is None:
            log.info("Daily message %s is off", name)
            continue
        # Attaching the timezone makes JobQueue fire at 08:00 Paris time, summer and winter.
        app.job_queue.run_daily(DAILY_SENDERS[name], time=at.replace(tzinfo=config.timezone), name=name)
        log.info("Daily message %s scheduled at %s (%s)", name, f"{at:%H:%M}", config.timezone)


def start_clock(app: Application) -> None:
    app.job_queue.run_repeating(clock, interval=60, first=10, name=CLOCK_JOB)
