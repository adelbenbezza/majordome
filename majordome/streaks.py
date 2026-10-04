"""Habit streaks: "Gym 🔥 4 in a row"."""

from datetime import date, timedelta

from .db import Database, Routine

STREAK_TEXT = {"fr": "🔥 {count} d'affilée", "en": "🔥 {count} in a row"}

MAX_STREAK_DAYS = 400  # how far back to count


def routine_streak(routine: Routine, done_days: set[date], today: date) -> int:
    """How many of the routine's days in a row were done, counting back from today.

    Only the routine's own days count (gym on Mon/Tue: Wed-Sun don't break it). Today
    not being done yet doesn't break the streak either: the day isn't over.
    """
    count = 0
    for back in range(MAX_STREAK_DAYS):
        day = today - timedelta(days=back)
        if not routine.happens_on(day):
            continue
        if day in done_days:
            count += 1
        elif day != today:
            break
    return count


def streak_text(db: Database, routine: Routine, today: date, lang: str, minimum: int = 2) -> str:
    """" 🔥 4 in a row" when the streak reaches `minimum`, else "".

    Confirmations only mention streaks of 2 or more; the routine list shows them from 1.
    """
    count = routine_streak(routine, db.routine_check_days(routine.id), today)
    return f" {STREAK_TEXT[lang].format(count=count)}" if count >= minimum else ""
