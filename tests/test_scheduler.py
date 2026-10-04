import asyncio
from dataclasses import replace
from datetime import time
from types import SimpleNamespace

from telegram.ext import Application

from majordome.config import load_config
from majordome.db import Database
from majordome.scheduler import CLOCK_JOB, clock, schedule_daily, send_brief, start_clock

CONFIG = load_config({"TELEGRAM_BOT_TOKEN": "123:abc", "OPENAI_API_KEY": "o", "ANTHROPIC_API_KEY": "a"})


def make_app(db):
    app = Application.builder().token(CONFIG.telegram_bot_token).build()  # no network until started
    app.bot_data.update(config=CONFIG, db=db)
    return app


def brief_jobs(app, name="brief"):
    # schedule_removal() only marks a job; ignore the ones marked for removal.
    return [job for job in app.job_queue.get_jobs_by_name(name) if not job.removed]


def test_brief_scheduled_at_saved_time_in_owner_timezone():
    db = Database(":memory:")
    db.set_daily_time("brief", time(7, 30))
    app = make_app(db)
    schedule_daily(app)
    [job] = brief_jobs(app)
    trigger = job.job.trigger
    assert str(trigger.timezone) == "Europe/Paris"
    assert (str(trigger.fields[5]), str(trigger.fields[6])) == ("7", "30")  # hour, minute


def test_rescheduling_replaces_the_job_and_off_removes_it():
    db = Database(":memory:")
    app = make_app(db)
    schedule_daily(app)
    db.set_daily_time("brief", time(9, 0))
    schedule_daily(app)
    assert len(brief_jobs(app)) == 1
    db.set_daily_time("brief", None)
    schedule_daily(app)
    assert brief_jobs(app) == []


def test_send_brief_goes_to_owner_in_their_language():
    db = Database(":memory:")
    db.claim_owner(42)
    db.set_language("fr")
    sent, keyboards = [], []

    async def send_message(chat_id, text, reply_markup=None):
        sent.append((chat_id, text))
        keyboards.append(reply_markup)

    context = SimpleNamespace(bot_data={"config": CONFIG, "db": db}, bot=SimpleNamespace(send_message=send_message))
    asyncio.run(send_brief(context))
    assert sent == [(42, "☀️ Bonjour ! Rien de prévu aujourd'hui. Profite bien 🙂")]
    assert keyboards == [None]  # nothing to tick off

    db.add_task("Bank")
    asyncio.run(send_brief(context))
    assert [row[0].text for row in keyboards[-1].inline_keyboard] == ["✅ Bank"]

    # The owner from OWNER_TELEGRAM_ID wins over the one in the database.
    context.bot_data["config"] = replace(CONFIG, owner_telegram_id=7)
    asyncio.run(send_brief(context))
    assert sent[-1][0] == 7


def test_check_in_is_scheduled_and_can_be_turned_off():
    db = Database(":memory:")
    app = make_app(db)
    schedule_daily(app)
    [job] = brief_jobs(app, "checkin")
    assert (str(job.job.trigger.fields[5]), str(job.job.trigger.fields[6])) == ("21", "0")  # default 21:00
    db.set_daily_time("checkin", None)
    schedule_daily(app)
    assert brief_jobs(app, "checkin") == [] and len(brief_jobs(app)) == 1  # the brief is untouched


def test_clock_runs_every_minute_and_sends_each_reminder_once():
    from datetime import datetime, timedelta

    db = Database(":memory:")
    app = make_app(db)
    start_clock(app)
    [job] = app.job_queue.get_jobs_by_name(CLOCK_JOB)
    assert job.job.trigger.interval.total_seconds() == 60

    db.claim_owner(42)
    soon = datetime.now(CONFIG.timezone) + timedelta(minutes=20)
    # created an hour ago, so the "30 minutes before" reminder is due now
    from unittest.mock import patch

    with patch("majordome.db.utc_now", return_value=datetime.now(CONFIG.timezone) - timedelta(hours=1)):
        db.add_task("Bank", due_date=soon.date(), due_at=soon)
    sent = []

    async def send_message(chat_id, text, reply_markup=None):
        sent.append((chat_id, text, reply_markup.inline_keyboard[0][0].text))

    context = SimpleNamespace(bot_data={"config": CONFIG, "db": db}, bot=SimpleNamespace(send_message=send_message))
    asyncio.run(clock(context))
    asyncio.run(clock(context))
    assert len(sent) == 1
    assert sent[0][0] == 42 and sent[0][1].startswith("⏰ In ") and sent[0][2] == "✅ Done"


def test_daily_messages_follow_the_timezone_set_by_talking():
    from zoneinfo import ZoneInfo

    db = Database(":memory:")
    db.set_timezone(ZoneInfo("America/Montreal"))
    app = make_app(db)
    schedule_daily(app)
    [job] = brief_jobs(app)
    assert str(job.job.trigger.timezone) == "America/Montreal"


def test_setup_message_only_on_first_start():
    from majordome.bot import start

    db = Database(":memory:")
    sent = []

    async def reply_text(text):
        sent.append(text)

    update = SimpleNamespace(
        effective_message=SimpleNamespace(reply_text=reply_text),
        effective_user=SimpleNamespace(language_code="fr"),
    )
    context = SimpleNamespace(bot_data={"config": CONFIG, "db": db})
    asyncio.run(start(update, context))
    assert len(sent) == 2 and sent[1].startswith("⚙️ Avant de commencer")
    assert "Fuseau horaire : Europe/Paris" in sent[1]
    asyncio.run(start(update, context))
    assert len(sent) == 3  # just the welcome the second time


def test_weekly_review_only_on_sundays():
    db = Database(":memory:")
    app = make_app(db)
    schedule_daily(app)
    [review] = brief_jobs(app, "review")
    # APScheduler's day_of_week counts from Monday: "sun" is what JobQueue's 0 becomes.
    assert str(review.job.trigger.fields[4]) == "sun"
    assert (str(review.job.trigger.fields[5]), str(review.job.trigger.fields[6])) == ("19", "0")
    [brief] = brief_jobs(app)
    assert str(brief.job.trigger.fields[4]) in ("*", "mon-sun", "sun,mon,tue,wed,thu,fri,sat")


def test_brief_survives_a_broken_calendar(monkeypatch):
    from datetime import datetime

    from majordome import scheduler
    from majordome.calendar_feed import CalendarError

    async def broken(url, day, tz):
        raise CalendarError("download failed")

    monkeypatch.setattr(scheduler, "fetch_events", broken)
    db = Database(":memory:")
    db.set_calendar_url("https://example.com/cal.ics")
    text = asyncio.run(scheduler.brief_text(db, datetime.now(CONFIG.timezone), "en"))
    assert "📅 (I couldn't read your calendar today)" in text


def test_pasted_calendar_link_is_never_sent_to_claude(monkeypatch):
    from majordome import bot
    from majordome.calendar_feed import Event

    async def fake_fetch(url, day, tz):
        return [Event("Dentist", None, None)]

    class NoClaude:
        async def interpret(self, *args):
            raise AssertionError("the secret link reached Claude")

    monkeypatch.setattr(bot, "fetch_events", fake_fetch)
    db = Database(":memory:")
    replies = []

    async def reply_text(text, **kwargs):
        replies.append(text)

    async def send_action(action):
        pass

    link = "https://calendar.google.com/calendar/ical/me%40gmail.com/private-abc/basic.ics"
    message = SimpleNamespace(text=link, reply_text=reply_text, chat=SimpleNamespace(send_action=send_action))
    update = SimpleNamespace(effective_message=message, effective_user=SimpleNamespace(language_code="en"))
    context = SimpleNamespace(bot_data={"config": CONFIG, "db": db, "brain": NoClaude()})
    asyncio.run(bot.handle_text(update, context))
    assert replies == ["📅 Calendar connected! 1 event(s) today. I'll put them in your morning brief."]
    assert db.get_calendar_url() == link


def test_morning_brief_with_intro_then_nudge():
    from datetime import datetime, timedelta

    from majordome.scheduler import send_brief

    db = Database(":memory:")
    db.claim_owner(42)
    today = datetime.now(CONFIG.timezone).date()
    bank = db.add_task("Bank", due_date=today - timedelta(days=3))
    for back in (2, 1, 0):
        db.reschedule_task(bank.id, today - timedelta(days=back), None)
    sent = []

    async def send_message(chat_id, text, reply_markup=None):
        sent.append(text)

    class FakeBrain:
        async def brief_intro(self, facts, lang):
            assert "moved to a later day 3 times" in facts
            return "The bank call keeps slipping: do it first."

    context = SimpleNamespace(
        bot_data={"config": CONFIG, "db": db, "brain": FakeBrain()}, bot=SimpleNamespace(send_message=send_message)
    )
    asyncio.run(send_brief(context))
    assert sent[0].startswith("☀️ The bank call keeps slipping: do it first.\n\n• Bank")
    assert sent[1] == '🤔 You\'ve postponed "Bank" 3 times. What shall we do?'
    asyncio.run(send_brief(context))
    assert len(sent) == 3  # the nudge isn't repeated the next time


def test_brief_without_claude_intro_still_goes_out():
    from datetime import datetime

    from majordome import scheduler

    class BrokenBrain:
        async def brief_intro(self, facts, lang):
            return None  # what brief_intro returns on any API problem

    db = Database(":memory:")
    db.add_task("Bank")
    text = asyncio.run(scheduler.brief_text(db, datetime.now(CONFIG.timezone), "en", BrokenBrain()))
    assert text == "☀️ Good morning! Here's your day:\n• Bank"
