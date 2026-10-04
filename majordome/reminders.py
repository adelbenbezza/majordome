"""What the bot should say on its own right now: reminders and routine follow-ups.

A job runs this every minute (see scheduler.py). It only looks at the database and
the clock, which makes the timing rules easy to test: just pass another `now`.
Each message is recorded once sent (Database.mark_notified), so it never repeats.
"""

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from .actions import TEXT, format_task
from .db import Database

LATE = timedelta(minutes=10)  # still worth saying "it's time" up to this long after
FOLLOW_UP_AFTER = timedelta(hours=1)  # ask "did you do it?" this long after a routine's time


@dataclass(frozen=True)
class Notice:
    kind: str  # "task" or "routine"
    item_id: int
    slot: str  # which occurrence: the task's due time, or the routine's day
    type: str  # "reminder" or "followup"
    day: date  # the day it's for (for the ✅ button)
    text: str


def _reminder_text(start: datetime, now: datetime, item: str, lang: str) -> str:
    if now >= start:
        return TEXT[lang]["reminder_now"].format(item=item)
    minutes = math.ceil((start - now).total_seconds() / 60)
    return TEXT[lang]["reminder_in"].format(minutes=minutes, item=item)


def in_quiet_hours(moment: time, quiet: tuple[time, time] | None) -> bool:
    """Whether `moment` falls in the quiet hours, which can run past midnight (22:00-07:00)."""
    if quiet is None:
        return False
    start, end = quiet
    if start <= end:
        return start <= moment < end
    return moment >= start or moment < end


def due_notices(db: Database, now: datetime, lang: str) -> list[Notice]:
    """Messages due at `now` (in the owner's timezone) that haven't been sent yet.

    During quiet hours nothing is due. Nothing is marked as sent either, so a reminder
    that's still relevant when the quiet hours end goes out then.
    """
    lead = timedelta(minutes=db.get_reminder_minutes())
    if not lead or in_quiet_hours(now.time(), db.get_quiet_hours()):
        return []  # reminders (and follow-ups) are off, or it's quiet time
    today = now.date()
    notices = []

    for task in db.timed_tasks_between(now - LATE, now + lead):
        start = task.due_at.astimezone(now.tzinfo)
        slot = task.due_at.isoformat()
        if db.was_notified("task", task.id, slot, "reminder"):
            continue
        added_late = task.created_at and task.created_at > start - lead
        # Normally: remind `lead` before. A task added inside that window ("remind me in
        # 10 minutes") is reminded at its time instead, not straight away.
        if now >= start or (now >= start - lead and not added_late):
            item = format_task(task, now, lang, hide_day=today)
            notices.append(Notice("task", task.id, slot, "reminder", start.date(), _reminder_text(start, now, item, lang)))

    for routine in db.routines_left(today):
        if routine.time is None:
            continue  # untimed routines are covered by the brief and the evening check-in
        start = datetime.combine(today, routine.time, tzinfo=now.tzinfo)
        slot = today.isoformat()
        item = f"{routine.title} ({routine.time:%H:%M})"
        if start - lead <= now < start + LATE and not db.was_notified("routine", routine.id, slot, "reminder"):
            notices.append(Notice("routine", routine.id, slot, "reminder", today, _reminder_text(start, now, item, lang)))
        new_today = routine.created_at and routine.created_at > start
        if now >= start + FOLLOW_UP_AFTER and not new_today and not db.was_notified("routine", routine.id, slot, "followup"):
            text = TEXT[lang]["followup"].format(title=item)
            notices.append(Notice("routine", routine.id, slot, "followup", today, text))

    return notices
