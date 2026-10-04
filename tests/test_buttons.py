from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from majordome.buttons import Tap, callback_data, parse_callback, tick, today_keyboard
from majordome.db import Database

PARIS = ZoneInfo("Europe/Paris")
MONDAY = date(2026, 10, 5)
NOW = datetime(2026, 10, 5, 7, 0, tzinfo=PARIS)


def test_callback_data_roundtrip():
    data = callback_data("routine", 3, MONDAY)
    assert data == "done:r:3:2026-10-05"
    assert len(data.encode()) <= 64  # Telegram's limit
    assert parse_callback(data) == Tap("routine", 3, MONDAY)
    assert parse_callback("done:t:12:2026-10-05") == Tap("task", 12, MONDAY)


def test_bad_callback_data_is_ignored():
    for data in ["", "done:x:1:2026-10-05", "done:t:abc:2026-10-05", "done:t:1:tomorrow", "other:t:1:2026-10-05"]:
        assert parse_callback(data) is None


def test_keyboard_has_one_button_per_item_left():
    db = Database(":memory:")
    assert today_keyboard(db, NOW, "en") is None
    gym = db.add_routine("Gym", [0], time(18, 0))
    task = db.add_task("Bank", due_date=MONDAY)
    rows = today_keyboard(db, NOW, "en").inline_keyboard
    assert [(row[0].text, row[0].callback_data) for row in rows] == [
        ("✅ Gym (18:00)", f"done:r:{gym.id}:2026-10-05"),
        ("✅ Bank", f"done:t:{task.id}:2026-10-05"),
    ]


def test_tick_once():
    db = Database(":memory:")
    gym = db.add_routine("Gym", [0], time(18, 0))
    task = db.add_task("Bank")
    assert tick(db, Tap("routine", gym.id, MONDAY)) == "Gym"
    assert tick(db, Tap("routine", gym.id, MONDAY)) is None  # second tap: already done
    assert tick(db, Tap("task", task.id, MONDAY)) == "Bank"
    assert tick(db, Tap("task", 999, MONDAY)) is None
    assert today_keyboard(db, NOW, "en") is None


def test_tapping_a_button_refreshes_todays_list():
    import asyncio
    from types import SimpleNamespace

    from majordome.bot import on_done
    from majordome.config import load_config

    config = load_config({"TELEGRAM_BOT_TOKEN": "t", "OPENAI_API_KEY": "o", "ANTHROPIC_API_KEY": "a"})
    db = Database(":memory:")
    bank = db.add_task("Bank")
    db.add_task("Milk")
    today = datetime.now(config.timezone).date()
    calls = []

    async def answer(text=None):
        calls.append(("answer", text))

    async def edit_message_text(text, reply_markup=None):
        calls.append(("edit", text, [row[0].text for row in reply_markup.inline_keyboard]))

    query = SimpleNamespace(data=callback_data("task", bank.id, today), answer=answer, edit_message_text=edit_message_text)
    update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(language_code="en"))
    context = SimpleNamespace(bot_data={"config": config, "db": db})

    asyncio.run(on_done(update, context))
    assert calls == [("answer", "✅ Bank"), ("edit", "📋 Still to do:\n• Milk", ["✅ Milk"])]
    asyncio.run(on_done(update, context))  # tapping the same (stale) button again
    assert calls[2] == ("answer", "Already done 👍")
