from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from majordome.db import Database, Routine
from majordome.review import format_review
from majordome.streaks import routine_streak

PARIS = ZoneInfo("Europe/Paris")
SUNDAY = date(2026, 10, 4)


def gym(weekdays=(0, 1)):
    return Routine(1, "Gym", tuple(weekdays), time(18, 0), True)


def days(*dates):
    return {date.fromisoformat(d) for d in dates}


def test_streak_counts_only_the_routines_days():
    # Gym on Mon/Tue: done the last two Mondays and Tuesdays. Wed-Sun don't break it.
    done = days("2026-09-28", "2026-09-29", "2026-09-21", "2026-09-22")
    assert routine_streak(gym(), done, SUNDAY) == 4
    # Last Tuesday missed: the streak is broken.
    assert routine_streak(gym(), days("2026-09-28", "2026-09-21", "2026-09-22"), SUNDAY) == 0
    # Last Monday missed but Tuesday done: 1.
    assert routine_streak(gym(), days("2026-09-29", "2026-09-21", "2026-09-22"), SUNDAY) == 1


def test_today_not_done_yet_does_not_break_the_streak():
    daily = gym(range(7))
    assert routine_streak(daily, days("2026-10-03", "2026-10-02"), SUNDAY) == 2
    assert routine_streak(daily, days("2026-10-04", "2026-10-03", "2026-10-02"), SUNDAY) == 3
    assert routine_streak(daily, days("2026-10-02"), SUNDAY) == 0  # yesterday missed


def test_weekly_review():
    db = Database(":memory:")
    week_start = datetime(2026, 9, 28, 8, 0, tzinfo=PARIS)
    with patch("majordome.db.utc_now", return_value=week_start.astimezone(timezone.utc)):
        gym_routine = db.add_routine("Gym", [0, 1], time(18, 0))
        pills = db.add_routine("Supplements", list(range(7)))
    db.check_routine(gym_routine.id, date(2026, 9, 28))
    db.check_routine(gym_routine.id, date(2026, 9, 29))
    for d in range(28, 31):
        db.check_routine(pills.id, date(2026, 9, d))
    done = db.add_task("Bank")
    db.complete_task(done.id)
    db.add_task("Late", due_date=date(2026, 10, 1))
    db.add_task("Dentist", due_date=date(2026, 10, 8))
    db.add_someday("Learn guitar", "Learning")

    review = format_review(db, datetime(2026, 10, 4, 19, 0, tzinfo=PARIS), "en", choose=lambda items: items[0])
    assert review == (
        "🗓️ Your week (Mon Sep 28 to today)\n"
        "\n"
        "✅ 1 task(s) done\n"
        "\n"
        "🔁 Routines:\n"
        "• Gym: 2/2 🔥 2 in a row\n"
        "• Supplements: 3/7\n"
        "\n"
        "📋 Still open: 1 task(s), 1 overdue\n"
        "📅 Next week: 1 task(s) planned\n"
        "\n"
        "✨ An idea from your Someday list: Learn guitar. Want to fit it in this week? Just tell me which day."
    )
