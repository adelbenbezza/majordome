"""✅ buttons under the day's list (Telegram "inline keyboard").

Each button carries a short text that comes back to the bot when tapped (callback
data, max 64 bytes), e.g. "done:t:12:2026-10-05:0" = task 12, or "done:r:3:2026-10-05:0" =
routine 3 for 5 October. The day matters for routines: tapping yesterday's brief
ticks off yesterday's gym, not today's. The last number is the database generation
(see Database.wipe_history): buttons from before a /reset are ignored.
"""

from dataclasses import dataclass
from datetime import date, datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .actions import day_items
from .db import Database

PREFIX = "done"
KINDS = {"t": "task", "r": "routine"}


@dataclass(frozen=True)
class Tap:
    kind: str  # "task" or "routine"
    id: int
    day: date
    generation: int = 0


def callback_data(kind: str, item_id: int, day: date, generation: int = 0) -> str:
    return f"{PREFIX}:{kind[0]}:{item_id}:{day.isoformat()}:{generation}"


def parse_callback(data: str) -> Tap | None:
    parts = data.split(":")
    if len(parts) == 4:  # buttons sent before generations existed
        parts.append("0")
    try:
        prefix, kind, item_id, day, generation = parts
        if prefix != PREFIX or kind not in KINDS:
            return None
        return Tap(KINDS[kind], int(item_id), date.fromisoformat(day), int(generation))
    except ValueError:
        return None


def today_keyboard(db: Database, now: datetime, lang: str) -> InlineKeyboardMarkup | None:
    """One ✅ button per thing left today, or None when there's nothing left."""
    today, generation = now.date(), db.get_generation()
    rows = [
        [InlineKeyboardButton(f"✅ {item.text.removeprefix('🔁 ')}", callback_data=callback_data(item.kind, item.id, today, generation))]
        for item in day_items(db, today, now, lang)
    ]
    return InlineKeyboardMarkup(rows) if rows else None


def tick(db: Database, tap: Tap) -> str | None:
    """Mark the tapped item done. Returns its title, or None if it was already done or is gone."""
    if tap.kind == "task":
        task = db.complete_task(tap.id)
        return task.title if task else None
    routine = db.check_routine(tap.id, tap.day)
    return routine.title if routine else None
