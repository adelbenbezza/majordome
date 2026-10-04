"""✅ buttons under the day's list (Telegram "inline keyboard").

Each button carries a short text that comes back to the bot when tapped (callback
data, max 64 bytes), e.g. "done:t:12:2026-10-05" = task 12, or "done:r:3:2026-10-05" =
routine 3 for 5 October. The day matters for routines: tapping yesterday's brief
ticks off yesterday's gym, not today's.
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


def callback_data(kind: str, item_id: int, day: date) -> str:
    return f"{PREFIX}:{kind[0]}:{item_id}:{day.isoformat()}"


def parse_callback(data: str) -> Tap | None:
    try:
        prefix, kind, item_id, day = data.split(":")
        if prefix != PREFIX or kind not in KINDS:
            return None
        return Tap(KINDS[kind], int(item_id), date.fromisoformat(day))
    except ValueError:
        return None


def today_keyboard(db: Database, now: datetime, lang: str) -> InlineKeyboardMarkup | None:
    """One ✅ button per thing left today, or None when there's nothing left."""
    today = now.date()
    rows = [
        [InlineKeyboardButton(f"✅ {item.text.removeprefix('🔁 ')}", callback_data=callback_data(item.kind, item.id, today))]
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
