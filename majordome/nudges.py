"""Spotting procrastination: "You've postponed 'call the bank' 3 times..."

After the morning brief, a task in today's list that was pushed back 3 times gets one
question with three buttons: do it today, drop it, or move it to the Someday list.
It's asked again at 6 and 9 postponements, never every day.
"""

from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .db import Database, Task

EVERY = 3  # ask at 3, 6, 9... postponements
MAX_PER_DAY = 2

TEXT = {
    "fr": {
        "question": "🤔 Tu as reporté « {title} » {count} fois. On fait quoi ?",
        "today": "💪 Aujourd'hui",
        "drop": "🗑️ Abandonner",
        "someday": "✨ Un jour",
        "done_today": "💪 C'est parti pour aujourd'hui : {title}",
        "done_drop": "🗑️ Abandonné : {title}",
        "done_someday": "✨ Déplacé dans « Un jour » : {title}",
        "category": "Plus tard",
    },
    "en": {
        "question": "🤔 You've postponed \"{title}\" {count} times. What shall we do?",
        "today": "💪 Today",
        "drop": "🗑️ Drop it",
        "someday": "✨ Someday",
        "done_today": "💪 Let's do it today: {title}",
        "done_drop": "🗑️ Dropped: {title}",
        "done_someday": "✨ Moved to Someday: {title}",
        "category": "Later",
    },
}


def level(task: Task) -> int:
    """3 for 3-5 postponements, 6 for 6-8... (0 below 3)."""
    return task.postponed // EVERY * EVERY


def due_nudges(db: Database, today: date) -> list[Task]:
    """Tasks of today's list that deserve a nudge and haven't had one at this level."""
    tasks = [
        task
        for task in db.tasks_left(today)
        if level(task) >= EVERY and not db.was_notified("task", task.id, f"postponed-{level(task)}", "nudge")
    ]
    return tasks[:MAX_PER_DAY]


def nudge_message(db: Database, task: Task, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    t = TEXT[lang]
    generation = db.get_generation()
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t[choice], callback_data=f"nudge:{choice}:{task.id}:{generation}")
        for choice in ("today", "drop", "someday")
    ]])
    return t["question"].format(title=task.title, count=task.postponed), keyboard


def parse_nudge(data: str) -> tuple[str, int, int] | None:
    """(choice, task id, generation) from a nudge button's data."""
    try:
        prefix, choice, task_id, generation = data.split(":")
        if prefix != "nudge" or choice not in ("today", "drop", "someday"):
            return None
        return choice, int(task_id), int(generation)
    except ValueError:
        return None


def apply_nudge(db: Database, choice: str, task_id: int, today: date, lang: str) -> str | None:
    """Carry out a nudge button. Returns the confirmation, or None if the task is gone or done."""
    t = TEXT[lang]
    task = db.get_task(task_id)
    if task is None or task.done_at is not None:
        return None
    if choice == "today":
        db.reschedule_task(task.id, today, task.due_at if task.due_date == today else None)
        db.reset_postponed(task.id)
        return t["done_today"].format(title=task.title)
    if choice == "drop":
        db.delete_task(task.id)
        return t["done_drop"].format(title=task.title)
    db.add_someday(task.title, t["category"])
    db.delete_task(task.id)
    return t["done_someday"].format(title=task.title)
