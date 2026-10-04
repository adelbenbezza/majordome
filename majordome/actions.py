"""Carry out what Claude understood, and write the reply.

Everything here is plain Python on the database: no AI involved, so it's
predictable and easy to test.
"""

from datetime import date, datetime, timedelta

from .brain import Action, AddTasks, CompleteTasks, ListTasks, Reply, SetBriefTime
from .db import Database, Task

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
        "brief_hello": "☀️ Bonjour ! Au programme aujourd'hui :",
        "brief_empty": "☀️ Bonjour ! Rien de prévu aujourd'hui. Profite bien 🙂",
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
        "brief_hello": "☀️ Good morning! Here's your day:",
        "brief_empty": "☀️ Good morning! Nothing planned today. Enjoy 🙂",
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
        done = [task for task in (db.complete_task(i) for i in action.task_ids) if task]
        if not done:
            return t["not_found"]
        return "\n".join([t["done"], *(f"• {task.title}" for task in done)])

    if isinstance(action, ListTasks):
        return format_tasks(db, now, action.start, action.end, lang)

    if isinstance(action, SetBriefTime):
        # The bot reschedules the daily job after this (see bot.py).
        db.set_brief_time(action.time)
        if action.time is None:
            return t["brief_off"]
        return t["brief_set"].format(time=f"{action.time:%H:%M}")

    raise TypeError(f"Unknown action {action!r}")


def format_tasks(db: Database, now: datetime, start: date, end: date, lang: str) -> str:
    """Open tasks from `start` to `end`, grouped by day.

    When the period includes today, today also gets the overdue and undated tasks,
    since those are still waiting to be done.
    """
    t = TEXT[lang]
    today = now.date()
    if start <= today <= end:
        tasks = db.tasks_left(today) + db.tasks_between(today + timedelta(days=1), end)
    else:
        tasks = db.tasks_between(start, end)

    if not tasks:
        if start == end == today:
            return t["nothing_left"]
        when = format_day(start, today, lang) if start == end else t["that_period"]
        return t["nothing_planned"].format(when=when)

    groups: dict[date, list[Task]] = {}
    for task in tasks:
        day = task.due_date if task.due_date and task.due_date >= today else today
        groups.setdefault(day, []).append(task)

    def heading(day: date) -> str:
        if day == today and start == end:
            return t["left"]
        name = format_day(day, today, lang)
        return f"📋 {name[0].upper()}{name[1:]} :" if lang == "fr" else f"📋 {name[0].upper()}{name[1:]}:"

    sections = []
    for day, day_tasks in groups.items():
        lines = [heading(day), *(f"• {format_task(task, now, lang, hide_day=day)}" for task in day_tasks)]
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def format_brief(db: Database, now: datetime, lang: str) -> str:
    """The morning brief: everything waiting for today, overdue and undated tasks included."""
    t = TEXT[lang]
    today = now.date()
    tasks = db.tasks_left(today)
    if not tasks:
        return t["brief_empty"]
    return "\n".join([t["brief_hello"], *(f"• {format_task(task, now, lang, hide_day=today)}" for task in tasks)])
