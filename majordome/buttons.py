"""✅ buttons under the day's list (Telegram "inline keyboard").

Each button carries a short text that comes back to the bot when tapped (callback
data, max 64 bytes), e.g. "done:t:12:2026-10-05:0" = task 12, or "done:r:3:2026-10-05:0" =
routine 3 for 5 October. The day matters for routines: tapping yesterday's brief
ticks off yesterday's gym, not today's. The last number is the database generation
(see Database.wipe_history): buttons from before a /reset are ignored. The optional
last letter says which message the button is on, so a tap refreshes the right thing:
"l" a day's list (default), "e" the evening check-in, "s" a single reminder.
"""

from dataclasses import dataclass
from datetime import date, datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .actions import TEXT, day_items
from .db import Database
from .streaks import streak_text

PREFIX = "done"
KINDS = {"t": "task", "r": "routine"}


@dataclass(frozen=True)
class Tap:
    kind: str  # "task" or "routine"
    id: int
    day: date
    generation: int = 0
    view: str = "l"  # "l" list, "e" evening check-in, "s" single reminder


def callback_data(kind: str, item_id: int, day: date, generation: int = 0, view: str = "l") -> str:
    return f"{PREFIX}:{kind[0]}:{item_id}:{day.isoformat()}:{generation}:{view}"


def parse_callback(data: str) -> Tap | None:
    parts = data.split(":")
    # Older buttons had no generation and/or view.
    parts += ["0", "l"][len(parts) - 4 :] if 4 <= len(parts) < 6 else []
    try:
        prefix, kind, item_id, day, generation, view = parts
        if prefix != PREFIX or kind not in KINDS or view not in ("l", "e", "s"):
            return None
        return Tap(KINDS[kind], int(item_id), date.fromisoformat(day), int(generation), view)
    except ValueError:
        return None


def move_callback(day: date, generation: int) -> str:
    return f"move:{day.isoformat()}:{generation}"


def parse_move(data: str) -> tuple[date, int] | None:
    try:
        prefix, day, generation = data.split(":")
        return (date.fromisoformat(day), int(generation)) if prefix == "move" else None
    except ValueError:
        return None


def _item_rows(db: Database, now: datetime, lang: str, view: str) -> list[list[InlineKeyboardButton]]:
    today, generation = now.date(), db.get_generation()
    return [
        [InlineKeyboardButton(f"✅ {item.text.removeprefix('🔁 ')}", callback_data=callback_data(item.kind, item.id, today, generation, view))]
        for item in day_items(db, today, now, lang)
    ]


def today_keyboard(db: Database, now: datetime, lang: str) -> InlineKeyboardMarkup | None:
    """One ✅ button per thing left today, or None when there's nothing left."""
    rows = _item_rows(db, now, lang, "l")
    return InlineKeyboardMarkup(rows) if rows else None


def evening_keyboard(db: Database, now: datetime, lang: str) -> InlineKeyboardMarkup | None:
    """The check-in's ✅ buttons, plus "Move all to tomorrow" when there are dated tasks left."""
    rows = _item_rows(db, now, lang, "e")
    if any(task.due_date for task in db.tasks_left(now.date())):
        rows.append([InlineKeyboardButton(TEXT[lang]["move_button"], callback_data=move_callback(now.date(), db.get_generation()))])
    return InlineKeyboardMarkup(rows) if rows else None


def single_keyboard(db: Database, kind: str, item_id: int, day: date, lang: str) -> InlineKeyboardMarkup:
    """A lone ✅ button under a reminder or follow-up."""
    data = callback_data(kind, item_id, day, db.get_generation(), "s")
    return InlineKeyboardMarkup([[InlineKeyboardButton(TEXT[lang]["done_button"], callback_data=data)]])


def tick(db: Database, tap: Tap) -> str | None:
    """Mark the tapped item done. Returns its title, or None if it was already done or is gone."""
    if tap.kind == "task":
        task = db.complete_task(tap.id)
        return task.title if task else None
    routine = db.check_routine(tap.id, tap.day)
    return routine.title + streak_text(db, routine, tap.day, db.get_language()) if routine else None
