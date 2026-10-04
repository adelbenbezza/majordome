"""The Sunday weekly review."""

import random
from datetime import date, datetime, timedelta

from .actions import format_day
from .db import Database
from .streaks import streak_text

TEXT = {
    "fr": {
        "review": "🗓️ Ta semaine (du {start} au {end})",
        "done": "✅ {count} tâche(s) faite(s)",
        "done_none": "✅ Aucune tâche cochée cette semaine",
        "routines": "🔁 Routines :",
        "routine_line": "• {title} : {done}/{planned}",
        "open": "📋 Encore ouvert : {count} tâche(s), dont {overdue} en retard",
        "open_none": "📋 Rien en attente, bravo !",
        "next_week": "📅 Semaine prochaine : {count} tâche(s) prévue(s)",
        "someday": "✨ Une idée de ta liste « Un jour » : {title}. Tu veux la caser cette semaine ? Dis-moi juste quel jour.",
    },
    "en": {
        "review": "🗓️ Your week ({start} to {end})",
        "done": "✅ {count} task(s) done",
        "done_none": "✅ No tasks ticked off this week",
        "routines": "🔁 Routines:",
        "routine_line": "• {title}: {done}/{planned}",
        "open": "📋 Still open: {count} task(s), {overdue} overdue",
        "open_none": "📋 Nothing waiting, well done!",
        "next_week": "📅 Next week: {count} task(s) planned",
        "someday": "✨ An idea from your Someday list: {title}. Want to fit it in this week? Just tell me which day.",
    },
}

def format_review(db: Database, now: datetime, lang: str, choose=random.choice) -> str:
    """The weekly review for the week (Monday to Sunday) that contains `now`.

    `choose` picks the Someday suggestion (random; tests pass their own).
    """
    t = TEXT[lang]
    today = now.date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    week_start = datetime.combine(monday, datetime.min.time(), tzinfo=now.tzinfo)
    lines = [t["review"].format(start=format_day(monday, today, lang), end=format_day(sunday, today, lang)), ""]

    done = db.tasks_done_between(week_start, now)
    lines.append(t["done"].format(count=len(done)) if done else t["done_none"])

    routine_lines = []
    for routine in db.active_routines():
        created = routine.created_at.astimezone(now.tzinfo).date() if routine.created_at else monday
        planned = [
            monday + timedelta(days=i)
            for i in range(7)
            if monday + timedelta(days=i) <= today
            and monday + timedelta(days=i) >= created
            and routine.happens_on(monday + timedelta(days=i))
        ]
        if not planned:
            continue
        done_days = db.routine_check_days(routine.id)
        line = t["routine_line"].format(title=routine.title, done=sum(d in done_days for d in planned), planned=len(planned))
        routine_lines.append(line + streak_text(db, routine, today, lang))
    if routine_lines:
        lines += ["", t["routines"], *routine_lines]

    lines.append("")
    open_tasks = db.tasks_left(today)
    overdue = sum(1 for task in open_tasks if task.due_date and task.due_date < today)
    lines.append(t["open"].format(count=len(open_tasks), overdue=overdue) if open_tasks else t["open_none"])
    next_week = db.tasks_between(sunday + timedelta(days=1), sunday + timedelta(days=7))
    if next_week:
        lines.append(t["next_week"].format(count=len(next_week)))

    someday = db.open_someday()
    if someday:
        lines += ["", t["someday"].format(title=choose(someday).title)]
    return "\n".join(lines)
