from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from majordome.db import Database
from majordome.reminders import due_notices

PARIS = ZoneInfo("Europe/Paris")
MONDAY = date(2026, 10, 5)


def at(hour, minute=0):
    return datetime(2026, 10, 5, hour, minute, tzinfo=PARIS)


def texts(db, now):
    return [n.text for n in due_notices(db, now, "en")]


def send(db, now):
    """Like the clock job: get the notices and record them as sent."""
    notices = due_notices(db, now, "en")
    for n in notices:
        db.mark_notified(n.kind, n.item_id, n.slot, n.type)
    return [n.text for n in notices]


def add_task_at(db, title, due, created):
    """Add a task as if it had been created at `created`."""
    with patch("majordome.db.utc_now", return_value=created.astimezone(timezone.utc)):
        return db.add_task(title, due_date=due.date(), due_at=due)


def test_task_reminder_30_minutes_before_and_only_once():
    db = Database(":memory:")
    add_task_at(db, "Bank", at(15), created=at(9))
    assert texts(db, at(14, 29)) == []  # too early
    assert send(db, at(14, 30)) == ["⏰ In 30 min: Bank (15:00)"]
    assert send(db, at(14, 31)) == []  # already sent


def test_bot_down_during_the_reminder_catches_up():
    db = Database(":memory:")
    add_task_at(db, "Bank", at(15), created=at(9))
    assert texts(db, at(14, 50)) == ["⏰ In 10 min: Bank (15:00)"]
    assert texts(db, at(15, 5)) == ["⏰ Time for: Bank (15:00)"]
    assert texts(db, at(15, 11)) == []  # too late to be useful


def test_task_added_inside_the_window_is_reminded_at_its_time():
    db = Database(":memory:")
    add_task_at(db, "Check the oven", at(12, 10), created=at(12, 0))  # "remind me in 10 minutes"
    assert texts(db, at(12, 1)) == []  # not straight away
    assert texts(db, at(12, 10)) == ["⏰ Time for: Check the oven (12:10)"]


def test_done_tasks_and_rescheduled_tasks():
    db = Database(":memory:")
    task = add_task_at(db, "Bank", at(15), created=at(9))
    send(db, at(14, 30))
    db.reschedule_task(task.id, MONDAY, at(17))  # a new time is a new reminder
    assert texts(db, at(16, 30)) == ["⏰ In 30 min: Bank (17:00)"]
    db.complete_task(task.id)
    assert texts(db, at(16, 30)) == []


def test_routine_reminder_and_follow_up():
    db = Database(":memory:")
    with patch("majordome.db.utc_now", return_value=at(8).astimezone(timezone.utc)):
        gym = db.add_routine("Gym", [0], time(18, 0))
        db.add_routine("Supplements", list(range(7)))  # no time: no reminder
    assert send(db, at(17, 30)) == ["⏰ In 30 min: Gym (18:00)"]
    assert send(db, at(18, 59)) == []
    assert send(db, at(19, 0)) == ['🔁 Did you do "Gym (18:00)"?']
    assert send(db, at(20)) == []
    # Done before the follow-up: no question asked.
    tuesday = datetime(2026, 10, 6, 19, 0, tzinfo=PARIS)
    db.update_routine(gym.id, "Gym", [0, 1], time(18, 0))
    db.check_routine(gym.id, tuesday.date())
    assert texts(db, tuesday) == []


def test_no_follow_up_for_a_routine_created_after_its_time():
    db = Database(":memory:")
    with patch("majordome.db.utc_now", return_value=at(22).astimezone(timezone.utc)):
        db.add_routine("Gym", [0], time(18, 0))
    assert texts(db, at(22, 1)) == []


def test_reminders_off_and_custom_lead():
    db = Database(":memory:")
    add_task_at(db, "Bank", at(15), created=at(9))
    db.set_reminder_minutes(10)
    assert texts(db, at(14, 30)) == []
    assert texts(db, at(14, 50)) == ["⏰ In 10 min: Bank (15:00)"]
    db.set_reminder_minutes(0)
    assert texts(db, at(15)) == []


def test_quiet_hours():
    from majordome.reminders import in_quiet_hours

    night = (time(22, 0), time(7, 0))
    assert in_quiet_hours(time(23, 30), night) and in_quiet_hours(time(6, 59), night)
    assert not in_quiet_hours(time(7, 0), night) and not in_quiet_hours(time(21, 59), night)
    assert in_quiet_hours(time(13, 0), (time(12, 0), time(14, 0)))
    assert not in_quiet_hours(time(3, 0), None)

    db = Database(":memory:")
    add_task_at(db, "Early train", at(7, 15), created=at(0))
    db.set_quiet_hours(night)
    assert texts(db, at(6, 45)) == []  # quiet: held back...
    assert texts(db, at(7, 0)) == ["⏰ In 15 min: Early train (07:15)"]  # ...and sent once quiet hours end
