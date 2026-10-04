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
from zoneinfo import ZoneInfo

from telegram.ext import Application, ContextTypes

from .actions import brief_facts, day_items, format_brief, format_checkin
from .calendar_feed import CalendarError, fetch_events
from .buttons import evening_keyboard, single_keyboard, today_keyboard
from .config import Config
from .db import DAILY_MESSAGES, Database
from .reminders import due_notices
from .nudges import due_nudges, level, nudge_message
from .review import format_review

log = logging.getLogger(__name__)

CLOCK_JOB = "clock"


def owner_id(config: Config, db: Database) -> int | None:
    """Who to send messages to. In a private chat, the chat id is the user's id."""
    return config.owner_telegram_id or db.get_owner_id()


def owner_timezone(config: Config, db: Database) -> ZoneInfo:
    """The owner's timezone: set by talking to the bot, else the TIMEZONE variable."""
    return db.get_timezone(config.timezone)


def _owner_context(context: ContextTypes.DEFAULT_TYPE):
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    return owner_id(config, db), db, datetime.now(owner_timezone(config, db)), db.get_language()


async def brief_text(db: Database, now: datetime, lang: str, brain=None) -> str:
    """The brief, with today's calendar events if a calendar is linked, opened by a few
    lines from Claude if `brain` is given.

    Neither a calendar problem nor a Claude problem ever stops the brief.
    """
    url = db.get_calendar_url()
    events, failed = [], False
    if url:
        try:
            events = await fetch_events(url, now.date(), now.tzinfo)
        except CalendarError as error:
            log.warning("Calendar failed: %s", error)
            failed = True
    intro = None
    if brain is not None and (events or day_items(db, now.date(), now, lang)):
        intro = await brain.brief_intro(brief_facts(db, now, events), lang)
    return format_brief(db, now, lang, events, calendar_failed=failed, intro=intro)


async def send_brief(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id, db, now, lang = _owner_context(context)
    if chat_id is None:
        log.info("No owner yet, skipping the morning brief")
        return
    text = await brief_text(db, now, lang, context.bot_data.get("brain"))
    await context.bot.send_message(chat_id, text, reply_markup=today_keyboard(db, now, lang))
    await send_nudges(context.bot, chat_id, db, now, lang)


async def send_nudges(bot, chat_id: int, db: Database, now: datetime, lang: str) -> None:
    """After the brief: ask about tasks postponed again and again (see nudges.py)."""
    for task in due_nudges(db, now.date()):
        db.mark_notified("task", task.id, f"postponed-{level(task)}", "nudge")
        text, keyboard = nudge_message(db, task, lang)
        await bot.send_message(chat_id, text, reply_markup=keyboard)


async def send_review(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id, db, now, lang = _owner_context(context)
    if chat_id is None:
        return
    await context.bot.send_message(chat_id, format_review(db, now, lang))


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


DAILY_SENDERS = {"brief": send_brief, "checkin": send_checkin, "review": send_review}
# Which days each message goes out. Careful: JobQueue counts 0 = Sunday ... 6 = Saturday,
# unlike Python's date.weekday() (0 = Monday).
EVERY_DAY = tuple(range(7))
SEND_DAYS = {"brief": EVERY_DAY, "checkin": EVERY_DAY, "review": (0,)}


def schedule_daily(app: Application) -> None:
    """(Re)schedule the brief and the check-in from the times saved in the database."""
    config: Config = app.bot_data["config"]
    db: Database = app.bot_data["db"]

    tz = owner_timezone(config, db)
    for name in DAILY_MESSAGES:
        for job in app.job_queue.get_jobs_by_name(name):
            job.schedule_removal()
        at = db.get_daily_time(name)
        if at is None:
            log.info("Daily message %s is off", name)
            continue
        # Attaching the timezone makes JobQueue fire at 08:00 Paris time, summer and winter.
        app.job_queue.run_daily(DAILY_SENDERS[name], time=at.replace(tzinfo=tz), days=SEND_DAYS[name], name=name)
        log.info("Daily message %s scheduled at %s (%s)", name, f"{at:%H:%M}", tz)


def start_clock(app: Application) -> None:
    app.job_queue.run_repeating(clock, interval=60, first=10, name=CLOCK_JOB)
