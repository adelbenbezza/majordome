import asyncio
import time
from datetime import datetime
from types import SimpleNamespace

from majordome.bot import on_done, on_move, on_reset
from majordome.buttons import callback_data
from majordome.config import load_config
from majordome.db import Database

CONFIG = load_config({"TELEGRAM_BOT_TOKEN": "t", "OPENAI_API_KEY": "o", "ANTHROPIC_API_KEY": "a"})


def tap(db, data):
    """Simulate tapping a button with callback `data`; return what the bot did."""
    calls = []

    async def answer(text=None):
        calls.append(("answer", text))

    async def edit_message_text(text, reply_markup=None):
        calls.append(("edit", text))

    async def edit_message_reply_markup(reply_markup=None):
        calls.append(("buttons", reply_markup))

    query = SimpleNamespace(
        data=data, answer=answer, edit_message_text=edit_message_text, edit_message_reply_markup=edit_message_reply_markup
    )
    update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(language_code="en"))
    context = SimpleNamespace(bot_data={"config": CONFIG, "db": db})
    handler = {"reset": on_reset, "move": on_move}.get(data.split(":")[0], on_done)
    asyncio.run(handler(update, context))
    return calls


def test_cancel_and_expired_delete_nothing():
    db = Database(":memory:")
    db.add_task("Bank")
    assert tap(db, "reset:no")[-1] == ("edit", "Cancelled, nothing was deleted.")
    expired = int(time.time()) - 1
    assert tap(db, f"reset:yes:{expired}")[-1][1].startswith("This confirmation expired")
    assert len(db.open_tasks()) == 1


def test_confirmed_reset_wipes_and_old_buttons_stop_working():
    db = Database(":memory:")
    old_task = db.add_task("Bank")
    today = datetime.now(CONFIG.timezone).date()
    old_button = callback_data("task", old_task.id, today, db.get_generation())

    assert tap(db, f"reset:yes:{int(time.time()) + 60}")[-1] == ("edit", "🗑️ Everything's deleted. Fresh start!")
    assert db.open_tasks() == []

    new_task = db.add_task("Dentist")
    assert new_task.id == old_task.id  # SQLite reuses the number...
    calls = tap(db, old_button)
    assert calls == [("answer", "This list is from before the reset."), ("buttons", None)]
    assert db.get_task(new_task.id).done_at is None  # ...but the old button didn't tick the new task


def test_move_all_to_tomorrow_button():
    from datetime import timedelta

    from majordome.buttons import move_callback

    db = Database(":memory:")
    today = datetime.now(CONFIG.timezone).date()
    db.add_task("Bank", due_date=today)
    calls = tap(db, move_callback(today, db.get_generation()))
    assert calls[0] == ("answer", "➡️ Moved to tomorrow")
    assert calls[1][1].startswith("➡️ Moved to tomorrow:\n• Bank (tomorrow)")
    assert db.open_tasks()[0].due_date == today + timedelta(days=1)


def test_done_button_under_a_reminder_just_disappears():
    db = Database(":memory:")
    task = db.add_task("Bank")
    today = datetime.now(CONFIG.timezone).date()
    calls = tap(db, callback_data("task", task.id, today, db.get_generation(), "s"))
    assert calls == [("answer", "✅ Bank"), ("buttons", None)]


def test_a_button_tap_can_be_undone():
    from majordome.actions import format_undo

    db = Database(":memory:")
    task = db.add_task("Bank")
    today = datetime.now(CONFIG.timezone).date()
    tap(db, callback_data("task", task.id, today, db.get_generation(), "s"))
    assert db.get_task(task.id).done_at is not None
    assert format_undo(db.undo_last(), "en") == "↩️ Undone:\n✅ Bank"
    assert db.get_task(task.id).done_at is None
