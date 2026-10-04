from datetime import date, timedelta

from majordome.db import Database
from majordome.nudges import apply_nudge, due_nudges, nudge_message, parse_nudge

TODAY = date(2026, 10, 5)


def postponed_task(db, title, times):
    task = db.add_task(title, due_date=TODAY - timedelta(days=times))
    for i in range(times, 0, -1):
        db.reschedule_task(task.id, TODAY - timedelta(days=i - 1), None)
    return db.get_task(task.id)


def test_nudged_at_3_then_6():
    db = Database(":memory:")
    bank = postponed_task(db, "Bank", 3)
    postponed_task(db, "Milk", 2)  # not yet
    assert [t.title for t in due_nudges(db, TODAY)] == ["Bank"]
    db.mark_notified("task", bank.id, "postponed-3", "nudge")
    assert due_nudges(db, TODAY) == []  # asked once at 3
    db.reschedule_task(bank.id, TODAY + timedelta(days=1), None)
    db.reschedule_task(bank.id, TODAY + timedelta(days=2), None)
    assert due_nudges(db, TODAY) == []  # 5: still level 3, and not in today's list
    db.reschedule_task(bank.id, TODAY, None)  # earlier: not a postponement
    db.reschedule_task(bank.id, TODAY + timedelta(days=3), None)  # 6th
    assert db.get_task(bank.id).postponed == 6
    assert due_nudges(db, TODAY + timedelta(days=3))[0].title == "Bank"


def test_message_and_buttons():
    db = Database(":memory:")
    bank = postponed_task(db, "Bank", 3)
    text, keyboard = nudge_message(db, bank, "fr")
    assert text == "🤔 Tu as reporté « Bank » 3 fois. On fait quoi ?"
    assert [(b.text, b.callback_data) for b in keyboard.inline_keyboard[0]] == [
        ("💪 Aujourd'hui", f"nudge:today:{bank.id}:0"),
        ("🗑️ Abandonner", f"nudge:drop:{bank.id}:0"),
        ("✨ Un jour", f"nudge:someday:{bank.id}:0"),
    ]
    assert parse_nudge(f"nudge:drop:{bank.id}:0") == ("drop", bank.id, 0)
    assert parse_nudge("nudge:explode:1:0") is None


def test_choices():
    db = Database(":memory:")
    a, b, c = (postponed_task(db, name, 3) for name in ("A", "B", "C"))
    assert apply_nudge(db, "today", a.id, TODAY, "en") == "💪 Let's do it today: A"
    assert db.get_task(a.id).postponed == 0 and db.get_task(a.id).due_date == TODAY
    assert apply_nudge(db, "drop", b.id, TODAY, "en") == "🗑️ Dropped: B"
    assert db.get_task(b.id) is None
    assert apply_nudge(db, "someday", c.id, TODAY, "en") == "✨ Moved to Someday: C"
    assert [(i.title, i.category) for i in db.open_someday()] == [("C", "Later")]
    assert apply_nudge(db, "drop", b.id, TODAY, "en") is None  # already gone
