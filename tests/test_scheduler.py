import asyncio
from dataclasses import replace
from datetime import time
from types import SimpleNamespace

from telegram.ext import Application

from majordome.config import load_config
from majordome.db import Database
from majordome.scheduler import BRIEF_JOB, schedule_brief, send_brief

CONFIG = load_config({"TELEGRAM_BOT_TOKEN": "123:abc", "OPENAI_API_KEY": "o", "ANTHROPIC_API_KEY": "a"})


def make_app(db):
    app = Application.builder().token(CONFIG.telegram_bot_token).build()  # no network until started
    app.bot_data.update(config=CONFIG, db=db)
    return app


def brief_jobs(app):
    # schedule_removal() only marks a job; ignore the ones marked for removal.
    return [job for job in app.job_queue.get_jobs_by_name(BRIEF_JOB) if not job.removed]


def test_brief_scheduled_at_saved_time_in_owner_timezone():
    db = Database(":memory:")
    db.set_brief_time(time(7, 30))
    app = make_app(db)
    schedule_brief(app)
    [job] = brief_jobs(app)
    trigger = job.job.trigger
    assert str(trigger.timezone) == "Europe/Paris"
    assert (str(trigger.fields[5]), str(trigger.fields[6])) == ("7", "30")  # hour, minute


def test_rescheduling_replaces_the_job_and_off_removes_it():
    db = Database(":memory:")
    app = make_app(db)
    schedule_brief(app)
    db.set_brief_time(time(9, 0))
    schedule_brief(app)
    assert len(brief_jobs(app)) == 1
    db.set_brief_time(None)
    schedule_brief(app)
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
