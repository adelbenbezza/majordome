"""Carry out what Claude understood, and write the reply.

Everything here is plain Python on the database: no AI involved, so it's
predictable and easy to test.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from .brain import (
    Action,
    AddRoutine,
    AddTasks,
    CompleteTasks,
    ListRoutines,
    ListTasks,
    RemoveRoutines,
    Reply,
    RescheduleTasks,
    SetDailyTime,
    SetReminders,
    UpdateRoutine,
)
from .db import Database, Routine, Task

MAX_LIST_DAYS = 31  # longest period listed at once

WEEKDAYS = {
    "fr": ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}
MONTHS = {
    "fr": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}
TEXT = {
    "fr": {
        "added": "📝 Ajouté :",
        "done": "✅ Fait :",
        "not_found": "Je n'ai pas trouvé cette tâche dans ta liste.",
        "left": "📋 Il te reste :",
        "nothing_left": "🎉 Rien à faire aujourd'hui !",
        "nothing_planned": "Rien de prévu pour {when}.",
        "that_period": "cette période",
        "brief_set": "☀️ C'est noté : ton brief arrivera chaque matin à {time}.",
        "brief_off": "🔕 C'est noté : plus de brief du matin. Dis-moi quand tu veux le réactiver.",
        "checkin_set": "🌙 C'est noté : je ferai le point chaque soir à {time}.",
        "checkin_off": "🔕 C'est noté : plus de point du soir. Dis-moi quand tu veux le réactiver.",
        "checkin_hello": "🌙 Petit point du soir. Il te reste :",
        "checkin_empty": "🌙 Tout est fait pour aujourd'hui, bravo ! 🎉",
        "move_button": "➡️ Tout reporter à demain",
        "moved": "➡️ Reporté à demain :",
        "rescheduled": "📅 Déplacé :",
        "reminders_set": "⏰ C'est noté : je te préviendrai {minutes} min avant.",
        "reminders_off": "🔕 C'est noté : plus de rappels. Dis-moi quand tu veux les réactiver.",
        "reminder_in": "⏰ Dans {minutes} min : {item}",
        "reminder_now": "⏰ C'est l'heure : {item}",
        "followup": "🔁 Tu as fait « {title} » ?",
        "done_button": "✅ Fait",
        "brief_hello": "☀️ Bonjour ! Au programme aujourd'hui :",
        "brief_empty": "☀️ Bonjour ! Rien de prévu aujourd'hui. Profite bien 🙂",
        "routine_added": "🔁 Routine ajoutée : {routine}",
        "routine_updated": "🔁 Routine modifiée : {routine}",
        "routine_removed": "🗑️ Routine arrêtée :",
        "routine_not_found": "Je n'ai pas trouvé cette routine.",
        "routines": "🔁 Tes routines :",
        "no_routines": "Tu n'as pas encore de routine. Dis par exemple « salle de sport le lundi et le mardi à 18h ».",
        "every_day": "tous les jours",
        "weekdays": "en semaine",
        "weekend": "le week-end",
        "at": "à",
        "today": "aujourd'hui",
        "tomorrow": "demain",
    },
    "en": {
        "added": "📝 Added:",
        "done": "✅ Done:",
        "not_found": "I couldn't find that task in your list.",
        "left": "📋 Still to do:",
        "nothing_left": "🎉 Nothing left for today!",
        "nothing_planned": "Nothing planned for {when}.",
        "that_period": "that period",
        "brief_set": "☀️ Got it: your brief will arrive every morning at {time}.",
        "brief_off": "🔕 Got it: no more morning brief. Tell me when you want it back.",
        "checkin_set": "🌙 Got it: I'll check in every evening at {time}.",
        "checkin_off": "🔕 Got it: no more evening check-in. Tell me when you want it back.",
        "checkin_hello": "🌙 Evening check-in. Still to do:",
        "checkin_empty": "🌙 All done for today, well done! 🎉",
        "move_button": "➡️ Move all to tomorrow",
        "moved": "➡️ Moved to tomorrow:",
        "rescheduled": "📅 Moved:",
        "reminders_set": "⏰ Got it: I'll remind you {minutes} min before.",
        "reminders_off": "🔕 Got it: no more reminders. Tell me when you want them back.",
        "reminder_in": "⏰ In {minutes} min: {item}",
        "reminder_now": "⏰ Time for: {item}",
        "followup": "🔁 Did you do \"{title}\"?",
        "done_button": "✅ Done",
        "brief_hello": "☀️ Good morning! Here's your day:",
        "brief_empty": "☀️ Good morning! Nothing planned today. Enjoy 🙂",
        "routine_added": "🔁 Routine added: {routine}",
        "routine_updated": "🔁 Routine updated: {routine}",
        "routine_removed": "🗑️ Routine stopped:",
        "routine_not_found": "I couldn't find that routine.",
        "routines": "🔁 Your routines:",
        "no_routines": "You don't have any routines yet. Try \"gym on Mondays and Tuesdays at 6pm\".",
        "every_day": "every day",
        "weekdays": "on weekdays",
        "weekend": "at weekends",
        "at": "at",
        "today": "today",
        "tomorrow": "tomorrow",
    },
}


def format_day(day: date, today: date, lang: str) -> str:
    if day == today:
        return TEXT[lang]["today"]
    if day == today + timedelta(days=1):
        return TEXT[lang]["tomorrow"]
    weekday = WEEKDAYS[lang][day.weekday()]
    month = MONTHS[lang][day.month - 1]
    return f"{weekday} {day.day} {month}" if lang == "fr" else f"{weekday} {month} {day.day}"


def format_task(task: Task, now: datetime, lang: str, hide_day: date | None = None) -> str:
    """One task as a line, e.g. "Call the bank (Fri Oct 9, 15:00)".

    `hide_day`: leave the day out when it's this one (the list is already headed by it).
    """
    today = now.date()
    parts = []
    if task.due_date and task.due_date != hide_day:
        parts.append(format_day(task.due_date, today, lang))
    if task.due_at:
        parts.append(f"{task.due_at.astimezone(now.tzinfo):%H:%M}")
    return f"{task.title} ({', '.join(parts)})" if parts else task.title


def format_routine(routine: Routine, lang: str) -> str:
    """A routine with its schedule, e.g. "Gym — Mon, Tue at 18:00"."""
    t = TEXT[lang]
    if routine.daily:
        days = t["every_day"]
    elif routine.weekdays == (0, 1, 2, 3, 4):
        days = t["weekdays"]
    elif routine.weekdays == (5, 6):
        days = t["weekend"]
    else:
        days = ", ".join(WEEKDAYS[lang][d] for d in routine.weekdays)
    at = f" {t['at']} {routine.time:%H:%M}" if routine.time else ""
    return f"{routine.title} — {days}{at}"


@dataclass(frozen=True)
class Item:
    """One line of a day's list: a task or a routine. kind and id let buttons find it again."""

    kind: str  # "task" or "routine"
    id: int
    text: str
    sort_key: tuple


def day_items(db: Database, day: date, now: datetime, lang: str, include_daily: bool = True) -> list[Item]:
    """What's still to do on `day`, tasks and routines mixed, sorted by time.

    For today this includes overdue and undated tasks. `include_daily=False` leaves out
    everyday routines, which would only repeat on every day of a longer period.
    """
    today = now.date()
    items = []
    tasks = db.tasks_left(today) if day == today else db.tasks_between(day, day)
    for task in tasks:
        at = f"{task.due_at.astimezone(now.tzinfo):%H:%M}" if task.due_at else ""
        if task.due_date and task.due_date < day:
            key = (0, task.due_date.isoformat(), at)  # overdue first
        elif at:
            key = (1, at)
        elif task.due_date:
            key = (2, "")
        else:
            key = (3, "")  # undated last
        items.append(Item("task", task.id, format_task(task, now, lang, hide_day=day), key))

    routines = db.routines_left(day) if day == today else db.routines_on(day)
    for routine in routines:
        if routine.daily and not include_daily:
            continue
        at = f"{routine.time:%H:%M}" if routine.time else ""
        text = f"🔁 {routine.title} ({at})" if at else f"🔁 {routine.title}"
        items.append(Item("routine", routine.id, text, (1, at) if at else (2, "")))

    return sorted(items, key=lambda item: item.sort_key)  # sorted() keeps ties in order


def execute(action: Action, db: Database, now: datetime) -> str:
    """Run one action and return the reply text. `now` is in the owner's timezone."""
    if isinstance(action, Reply):
        return action.text

    lang = action.language
    t = TEXT[lang]

    if isinstance(action, AddTasks):
        lines = [t["added"]]
        for new in action.tasks:
            due_date = new.due_date
            if new.due_time and not due_date:
                due_date = now.date()
            due_at = None
            if new.due_time:
                # Local day + time in the owner's timezone; db.add_task stores it in UTC.
                due_at = datetime.combine(due_date, new.due_time, tzinfo=now.tzinfo)
            task = db.add_task(new.title, due_date=due_date, due_at=due_at)
            lines.append(f"• {format_task(task, now, lang)}")
        return "\n".join(lines)

    if isinstance(action, CompleteTasks):
        done = [task.title for task in (db.complete_task(i) for i in action.task_ids) if task]
        done += [r.title for r in (db.check_routine(i, now.date()) for i in action.routine_ids) if r]
        if not done:
            return t["not_found"]
        return "\n".join([t["done"], *(f"• {title}" for title in done)])

    if isinstance(action, AddRoutine):
        routine = db.add_routine(action.title, action.weekdays, action.time)
        return t["routine_added"].format(routine=format_routine(routine, lang))

    if isinstance(action, UpdateRoutine):
        routine = db.update_routine(action.routine_id, action.title, action.weekdays, action.time)
        if routine is None:
            return t["routine_not_found"]
        return t["routine_updated"].format(routine=format_routine(routine, lang))

    if isinstance(action, RemoveRoutines):
        removed = [r for r in (db.remove_routine(i) for i in action.routine_ids) if r]
        if not removed:
            return t["routine_not_found"]
        return "\n".join([t["routine_removed"], *(f"• {r.title}" for r in removed)])

    if isinstance(action, ListRoutines):
        routines = db.active_routines()
        if not routines:
            return t["no_routines"]
        return "\n".join([t["routines"], *(f"• {format_routine(r, lang)}" for r in routines)])

    if isinstance(action, ListTasks):
        return format_tasks(db, now, action.start, action.end, lang)

    if isinstance(action, SetDailyTime):
        # The bot reschedules the daily job after this (see bot.py).
        db.set_daily_time(action.message, action.time)
        if action.time is None:
            return t[f"{action.message}_off"]
        return t[f"{action.message}_set"].format(time=f"{action.time:%H:%M}")

    if isinstance(action, SetReminders):
        db.set_reminder_minutes(action.minutes_before)
        if action.minutes_before == 0:
            return t["reminders_off"]
        return t["reminders_set"].format(minutes=action.minutes_before)

    if isinstance(action, RescheduleTasks):
        moved = []
        for task_id in action.task_ids:
            task = db.get_task(task_id)
            if task and task.done_at is None:
                moved.append(move_task(db, task, action.due_date, now, action.due_time))
        if not moved:
            return t["not_found"]
        return "\n".join([t["rescheduled"], *(f"• {format_task(task, now, lang)}" for task in moved)])

    raise TypeError(f"Unknown action {action!r}")


def format_tasks(db: Database, now: datetime, start: date, end: date, lang: str) -> str:
    """Tasks and routines from `start` to `end`, grouped by day.

    When the period includes today, today also gets the overdue and undated tasks,
    since those are still waiting to be done.
    """
    t = TEXT[lang]
    today = now.date()
    if start <= today <= end:
        start = today  # earlier days' leftovers already show up today, as overdue
    end = min(end, start + timedelta(days=MAX_LIST_DAYS - 1))
    single_day = start == end

    sections = []
    day = start
    while day <= end:
        items = day_items(db, day, now, lang, include_daily=single_day)
        if items:
            if day == today and single_day:
                heading = t["left"]
            else:
                name = format_day(day, today, lang)
                heading = f"📋 {name[0].upper()}{name[1:]}" + (" :" if lang == "fr" else ":")
            sections.append("\n".join([heading, *(f"• {item.text}" for item in items)]))
        day += timedelta(days=1)

    if not sections:
        if single_day and start == today:
            return t["nothing_left"]
        when = format_day(start, today, lang) if single_day else t["that_period"]
        return t["nothing_planned"].format(when=when)
    return "\n\n".join(sections)


def format_brief(db: Database, now: datetime, lang: str) -> str:
    """The morning brief: everything waiting for today, routines and overdue tasks included."""
    t = TEXT[lang]
    items = day_items(db, now.date(), now, lang)
    if not items:
        return t["brief_empty"]
    return "\n".join([t["brief_hello"], *(f"• {item.text}" for item in items)])


def move_task(db: Database, task: Task, day: date, now: datetime, at: time | None = None) -> Task:
    """Move a task to `day`, at time `at`, or at the same local time as before if `at` is None."""
    if at is None and task.due_at:
        at = task.due_at.astimezone(now.tzinfo).time()
    due_at = datetime.combine(day, at, tzinfo=now.tzinfo) if at else None
    return db.reschedule_task(task.id, day, due_at)


def move_to_tomorrow(db: Database, day: date, now: datetime) -> list[Task]:
    """Move `day`'s unfinished dated tasks (and older overdue ones) to the next day.

    Undated tasks stay as they are (they show up every day anyway), and so do
    routines (they come back on their own days).
    """
    tomorrow = day + timedelta(days=1)
    return [move_task(db, task, tomorrow, now) for task in db.tasks_left(day) if task.due_date]


def format_checkin(db: Database, now: datetime, lang: str) -> str:
    """The evening check-in: what's still left today."""
    t = TEXT[lang]
    items = day_items(db, now.date(), now, lang)
    if not items:
        return t["checkin_empty"]
    return "\n".join([t["checkin_hello"], *(f"• {item.text}" for item in items)])
