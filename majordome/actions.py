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
    AddSomeday,
    AddToList,
    CheckListItems,
    ClearList,
    CloseSomeday,
    DeleteTasks,
    ListTasks,
    PromoteSomeday,
    RemoveRoutines,
    RenameTask,
    Reply,
    RescheduleTasks,
    Show,
    Undo,
    UpdateRoutine,
    UpdateSetting,
)
from .db import Database, Routine, Task
from .streaks import streak_text

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
        "someday_added": "✨ Ajouté à « Un jour » :",
        "someday": "✨ Un jour :",
        "no_someday": "Ta liste « Un jour » est vide. Dis par exemple « un jour j'aimerais apprendre la guitare ».",
        "someday_done": "🎉 Bravo ! Retiré de « Un jour » :",
        "someday_dropped": "🗑️ Retiré de « Un jour » :",
        "someday_not_found": "Je n'ai pas trouvé ça dans ta liste « Un jour ».",
        "promoted": "📅 De « Un jour » à tes tâches :",
        "list_added": "📝 Ajouté à « {list} » :",
        "list": "📝 {list} :",
        "list_empty": "Ta liste « {list} » est vide.",
        "no_list": "Je n'ai pas trouvé de liste « {list} ».",
        "lists": "📝 Tes listes :",
        "no_lists": "Tu n'as pas encore de liste. Dis par exemple « ajoute du lait à la liste de courses ».",
        "checked": "✅ Coché :",
        "item_not_found": "Je n'ai pas trouvé ça dans tes listes.",
        "cleared": "🧹 Liste « {list} » vidée.",
        "deleted": "🗑️ Supprimé :",
        "renamed": "✏️ Renommé : {title}",
        "undone": "↩️ Annulé :",
        "nothing_to_undo": "Il n'y a rien à annuler.",
        "timezone_set": "🌍 C'est noté : fuseau horaire {tz} (il y est {time}).",
        "quiet_set": "🌙 Heures calmes : pas de rappels entre {start} et {end}.",
        "quiet_off": "🔔 Heures calmes désactivées.",
        "settings": "⚙️ Tes réglages",
        "s_language": "Langue : je réponds dans la langue de ton message",
        "s_timezone": "Fuseau horaire : {tz}",
        "s_brief": "Brief du matin : {value}",
        "s_checkin": "Point du soir : {value}",
        "s_reminders": "Rappels : {value}",
        "s_quiet": "Heures calmes : {value}",
        "s_model": "Modèle d'IA : {model} (réglé dans Railway)",
        "s_review": "Bilan de la semaine : {value}",
        "s_sundays_at": "le dimanche à {time}",
        "s_calendar": "Agenda : {value}",
        "s_connected": "connecté",
        "s_not_connected": "non connecté (/calendar pour le relier)",
        "review_set": "🗓️ C'est noté : ton bilan arrivera le dimanche à {time}.",
        "review_off": "🔕 C'est noté : plus de bilan de la semaine. Dis-moi quand tu veux le réactiver.",
        "all_day": "toute la journée",
        "calendar_failed": "📅 (je n'ai pas pu lire ton agenda aujourd'hui)",
        "s_off": "désactivé",
        "s_minutes_before": "{minutes} min avant",
        "s_quiet_hours": "de {start} à {end}",
        "settings_help": (
            "Pour changer quelque chose, dis-le simplement :\n"
            "« brief à 7h30 » · « point du soir à 20h » · « rappelle-moi 15 min avant » · "
            "« j'habite à Montréal maintenant » · « pas de rappels entre 22h et 7h » · « plus de brief »"
        ),
        "usage": "💶 Ce mois-ci (depuis le {start})",
        "usage_claude": "Claude ({model}) : {calls} messages, ≈ {cost}",
        "usage_whisper": "Messages vocaux : {minutes} min, ≈ {cost}",
        "usage_unknown": "prix inconnu",
        "usage_total": "Total IA : ≈ {cost}",
        "usage_none": "Aucune utilisation de l'IA ce mois-ci pour l'instant.",
        "usage_note": "Estimation à partir des tarifs publics. L'hébergement Railway (~5 $/mois) est en plus.",
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
        "someday_added": "✨ Added to Someday:",
        "someday": "✨ Someday:",
        "no_someday": "Your Someday list is empty. Try \"one day I'd like to learn guitar\".",
        "someday_done": "🎉 Well done! Off your Someday list:",
        "someday_dropped": "🗑️ Removed from Someday:",
        "someday_not_found": "I couldn't find that in your Someday list.",
        "promoted": "📅 From Someday to your tasks:",
        "list_added": "📝 Added to \"{list}\":",
        "list": "📝 {list}:",
        "list_empty": "Your \"{list}\" list is empty.",
        "no_list": "I couldn't find a list called \"{list}\".",
        "lists": "📝 Your lists:",
        "no_lists": "You don't have any lists yet. Try \"add milk to the shopping list\".",
        "checked": "✅ Ticked off:",
        "item_not_found": "I couldn't find that in your lists.",
        "cleared": "🧹 \"{list}\" list emptied.",
        "deleted": "🗑️ Deleted:",
        "renamed": "✏️ Renamed: {title}",
        "undone": "↩️ Undone:",
        "nothing_to_undo": "There's nothing to undo.",
        "timezone_set": "🌍 Got it: timezone {tz} (it's {time} there).",
        "quiet_set": "🌙 Quiet hours: no reminders between {start} and {end}.",
        "quiet_off": "🔔 Quiet hours turned off.",
        "settings": "⚙️ Your settings",
        "s_language": "Language: I reply in the language you write in",
        "s_timezone": "Timezone: {tz}",
        "s_brief": "Morning brief: {value}",
        "s_checkin": "Evening check-in: {value}",
        "s_reminders": "Reminders: {value}",
        "s_quiet": "Quiet hours: {value}",
        "s_model": "AI model: {model} (set in Railway)",
        "s_review": "Weekly review: {value}",
        "s_sundays_at": "Sundays at {time}",
        "s_calendar": "Calendar: {value}",
        "s_connected": "connected",
        "s_not_connected": "not connected (/calendar to link it)",
        "review_set": "🗓️ Got it: your weekly review will arrive on Sundays at {time}.",
        "review_off": "🔕 Got it: no more weekly review. Tell me when you want it back.",
        "all_day": "all day",
        "calendar_failed": "📅 (I couldn't read your calendar today)",
        "s_off": "off",
        "s_minutes_before": "{minutes} min before",
        "s_quiet_hours": "from {start} to {end}",
        "settings_help": (
            "To change anything, just say it:\n"
            "\"brief at 7:30\" · \"check in at 8pm\" · \"remind me 15 min before\" · "
            "\"I live in Montreal now\" · \"no reminders between 10pm and 7am\" · \"no more brief\""
        ),
        "usage": "💶 This month (since {start})",
        "usage_claude": "Claude ({model}): {calls} messages, ≈ {cost}",
        "usage_whisper": "Voice notes: {minutes} min, ≈ {cost}",
        "usage_unknown": "unknown price",
        "usage_total": "AI total: ≈ {cost}",
        "usage_none": "No AI usage this month yet.",
        "usage_note": "Estimated from public prices. Railway hosting (~$5/month) comes on top.",
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


def ordinal(day: int, lang: str) -> str:
    """1 -> "1st" / "1er", 2 -> "2nd" / "2", 31 -> "last day" / "dernier jour"."""
    if day == 31:
        return "dernier jour" if lang == "fr" else "last day"
    if lang == "fr":
        return "1er" if day == 1 else str(day)
    suffix = "th" if 11 <= day % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def format_repeat(routine: Routine, lang: str) -> str:
    """When a routine happens: "Mon, Tue", "every 2 weeks on Fri", "on the 1st of every month"."""
    t = TEXT[lang]
    fr = lang == "fr"
    if routine.unit == "month":
        day = ordinal(routine.month_day or 1, lang)
        if routine.every == 1:
            return f"le {day} de chaque mois" if fr else f"on the {day} of every month"
        return f"tous les {routine.every} mois, le {day}" if fr else f"every {routine.every} months on the {day}"
    if routine.daily:
        days = t["every_day"]
    elif routine.weekdays == (0, 1, 2, 3, 4):
        days = t["weekdays"]
    elif routine.weekdays == (5, 6):
        days = t["weekend"]
    else:
        days = ", ".join(WEEKDAYS[lang][d] for d in routine.weekdays)
    if routine.every == 1:
        return days
    return f"toutes les {routine.every} semaines, {days}" if fr else f"every {routine.every} weeks, {days}"


def format_routine(routine: Routine, lang: str) -> str:
    """A routine with its schedule, e.g. "Gym — Mon, Tue at 18:00"."""
    at = f" {TEXT[lang]['at']} {routine.time:%H:%M}" if routine.time else ""
    return f"{routine.title} — {format_repeat(routine, lang)}{at}"


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


def repeat_fields(action: AddRoutine | UpdateRoutine, now: datetime, current: Routine | None = None) -> dict:
    """How a new or changed routine repeats.

    Counting starts on the given start date; otherwise a changed routine keeps its own,
    and a new one starts today.
    """
    start = action.start_date or (current.start_date if current else None) or now.date()
    return dict(unit=action.unit, every=action.every, month_day=action.month_day, start_date=start)


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
        done += [
            r.title + streak_text(db, r, now.date(), lang)
            for r in (db.check_routine(i, now.date()) for i in action.routine_ids)
            if r
        ]
        if not done:
            return t["not_found"]
        return "\n".join([t["done"], *(f"• {title}" for title in done)])

    if isinstance(action, AddRoutine):
        routine = db.add_routine(action.title, action.weekdays, action.time, **repeat_fields(action, now))
        return t["routine_added"].format(routine=format_routine(routine, lang))

    if isinstance(action, UpdateRoutine):
        routine = db.update_routine(
            action.routine_id,
            action.title,
            action.weekdays,
            action.time,
            **repeat_fields(action, now, db.get_routine(action.routine_id)),
        )
        if routine is None:
            return t["routine_not_found"]
        return t["routine_updated"].format(routine=format_routine(routine, lang))

    if isinstance(action, RemoveRoutines):
        removed = [r for r in (db.remove_routine(i) for i in action.routine_ids) if r]
        if not removed:
            return t["routine_not_found"]
        return "\n".join([t["routine_removed"], *(f"• {r.title}" for r in removed)])

    if isinstance(action, DeleteTasks):
        deleted = [task for task in (db.delete_task(i) for i in action.task_ids) if task]
        if not deleted:
            return t["not_found"]
        return "\n".join([t["deleted"], *(f"• {task.title}" for task in deleted)])

    if isinstance(action, RenameTask):
        task = db.rename_task(action.task_id, action.title)
        return t["renamed"].format(title=format_task(task, now, lang)) if task else t["not_found"]

    if isinstance(action, Undo):
        return format_undo(db.undo_last(), lang)

    if isinstance(action, Show):
        return format_show(db, action.what, action.name, lang, now)

    if isinstance(action, AddSomeday):
        added = [db.add_someday(item.title, item.category) for item in action.items]
        return "\n".join([t["someday_added"], *(f"• {item.title} ({item.category})" for item in added)])

    if isinstance(action, CloseSomeday):
        closed = [item for item in (db.close_someday(i, action.done) for i in action.someday_ids) if item]
        if not closed:
            return t["someday_not_found"]
        heading = t["someday_done"] if action.done else t["someday_dropped"]
        return "\n".join([heading, *(f"• {item.title}" for item in closed)])

    if isinstance(action, PromoteSomeday):
        wish = db.get_someday(action.someday_id)
        if wish is None:
            return t["someday_not_found"]
        due_at = datetime.combine(action.due_date, action.due_time, tzinfo=now.tzinfo) if action.due_time else None
        task = db.add_task(wish.title, due_date=action.due_date, due_at=due_at)
        db.promote_someday(wish.id, task.id)
        return f"{t['promoted']}\n• {format_task(task, now, lang)}"

    if isinstance(action, AddToList):
        name = db.add_to_list(action.list, action.items)
        return "\n".join([t["list_added"].format(list=name), *(f"• {item}" for item in action.items)])

    if isinstance(action, CheckListItems):
        checked = [item for item in (db.check_list_item(i) for i in action.item_ids) if item]
        if not checked:
            return t["item_not_found"]
        return "\n".join([t["checked"], *(f"• {item.text}" for item in checked)])

    if isinstance(action, ClearList):
        name = db.clear_list(action.list)
        return t["cleared"].format(list=name) if name else t["no_list"].format(list=action.list)

    if isinstance(action, ListTasks):
        return format_tasks(db, now, action.start, action.end, lang)

    if isinstance(action, UpdateSetting):
        # The bot reschedules the daily jobs after this when needed (see bot.py).
        return apply_setting(db, action.setting, action.value, lang)

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


def format_event(event, lang: str) -> str:
    """A calendar event line: "📅 10:00–11:00 Dentist" or "📅 Mum's birthday (all day)"."""
    if event.start is None:
        return f"📅 {event.title} ({TEXT[lang]['all_day']})"
    hours = f"{event.start:%H:%M}" + (f"–{event.end:%H:%M}" if event.end and event.end != event.start else "")
    return f"📅 {hours} {event.title}"


def format_brief(db: Database, now: datetime, lang: str, events: list | None = None, calendar_failed: bool = False) -> str:
    """The morning brief: today's calendar events, then everything waiting for today
    (routines and overdue tasks included)."""
    t = TEXT[lang]
    items = day_items(db, now.date(), now, lang)
    events = events or []
    lines = [format_event(event, lang) for event in events]
    if calendar_failed:
        lines.append(t["calendar_failed"])
    lines += [f"• {item.text}" for item in items]
    if not items and not events:
        return "\n".join([t["brief_empty"], *lines])
    return "\n".join([t["brief_hello"], *lines])


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


def format_show(db: Database, what: str, name: str | None, lang: str, now: datetime) -> str:
    """Routines, the Someday list (optionally one category), or lists (one, or an overview)."""
    t = TEXT[lang]
    if what == "routines":
        routines = db.active_routines()
        if not routines:
            return t["no_routines"]
        lines = [f"• {format_routine(r, lang)}{streak_text(db, r, now.date(), lang, minimum=1)}" for r in routines]
        return "\n".join([t["routines"], *lines])

    if what == "someday":
        items = [i for i in db.open_someday() if name is None or i.category.lower() == name.lower()]
        if not items:
            return t["no_someday"]
        sections, category = [t["someday"]], None
        for item in items:  # already sorted by category
            if item.category != category:
                category = item.category
                sections.append(f"\n▸ {category}")
            sections.append(f"• {item.title}")
        return "\n".join(sections)

    if name is None:  # overview of all lists
        names = db.list_names()
        if not names:
            return t["no_lists"]
        counts = {n: 0 for n in names}
        for item in db.list_items():
            counts[item.list_name] += 1
        return "\n".join([t["lists"], *(f"• {n} ({count})" for n, count in counts.items())])
    found = db.find_list(name)
    if found is None:
        return t["no_list"].format(list=name)
    items = db.list_items(found[1])
    if not items:
        return t["list_empty"].format(list=found[1])
    return "\n".join([t["list"].format(list=found[1]), *(f"• {item.text}" for item in items)])


def apply_setting(db: Database, setting: str, value, lang: str) -> str:
    """Save one setting (already checked by brain.py) and confirm it."""
    t = TEXT[lang]
    if setting in ("brief_time", "checkin_time", "review_time"):
        name = setting.removesuffix("_time")
        db.set_daily_time(name, value)
        return t[f"{name}_off"] if value is None else t[f"{name}_set"].format(time=f"{value:%H:%M}")
    if setting == "reminder_minutes":
        db.set_reminder_minutes(value)
        return t["reminders_off"] if value == 0 else t["reminders_set"].format(minutes=value)
    if setting == "timezone":
        db.set_timezone(value)
        return t["timezone_set"].format(tz=value.key, time=f"{datetime.now(value):%H:%M}")
    if setting == "quiet_hours":
        db.set_quiet_hours(value)
        if value is None:
            return t["quiet_off"]
        return t["quiet_set"].format(start=f"{value[0]:%H:%M}", end=f"{value[1]:%H:%M}")
    raise ValueError(f"Unknown setting {setting!r}")


def format_settings(db: Database, tz_name: str, model: str, lang: str) -> str:
    t = TEXT[lang]

    def daily(name: str) -> str:
        at = db.get_daily_time(name)
        return f"{at:%H:%M}" if at else t["s_off"]

    minutes = db.get_reminder_minutes()
    quiet = db.get_quiet_hours()
    reminders = t["s_minutes_before"].format(minutes=minutes) if minutes else t["s_off"]
    quiet_text = t["s_quiet_hours"].format(start=f"{quiet[0]:%H:%M}", end=f"{quiet[1]:%H:%M}") if quiet else t["s_off"]
    calendar = t["s_connected"] if db.get_calendar_url() else t["s_not_connected"]
    review_time = db.get_daily_time("review")
    review = t["s_sundays_at"].format(time=f"{review_time:%H:%M}") if review_time else t["s_off"]
    lines = [
        t["settings"],
        "",
        f"• {t['s_language']}",
        f"• {t['s_timezone'].format(tz=tz_name)}",
        f"• {t['s_brief'].format(value=daily('brief'))}",
        f"• {t['s_checkin'].format(value=daily('checkin'))}",
        f"• {t['s_review'].format(value=review)}",
        f"• {t['s_reminders'].format(value=reminders)}",
        f"• {t['s_quiet'].format(value=quiet_text)}",
        f"• {t['s_calendar'].format(value=calendar)}",
        f"• {t['s_model'].format(model=model)}",
        "",
        t["settings_help"],
    ]
    return "\n".join(lines)


# Public prices in US dollars (what the APIs bill in): per million tokens (input, output),
# and per minute of audio for Whisper. Update when prices change.
CLAUDE_PRICES = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
}
WHISPER_PRICE_PER_MINUTE = 0.006


def format_usage(db: Database, now: datetime, lang: str) -> str:
    """AI cost since the start of the month (in the owner's timezone)."""
    t = TEXT[lang]
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    lines = [t["usage"].format(start=format_day(month_start.date(), now.date(), lang)), ""]
    total, any_usage = 0.0, False
    for service, model, input_tokens, output_tokens, seconds, calls in db.usage_since(month_start):
        any_usage = True
        if service == "whisper":
            cost = seconds / 60 * WHISPER_PRICE_PER_MINUTE
            total += cost
            lines.append(f"• {t['usage_whisper'].format(minutes=round(seconds / 60, 1), cost=f'${cost:.2f}')}")
            continue
        price = CLAUDE_PRICES.get(model)
        if price:
            cost = (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000
            total += cost
            cost_text = f"${cost:.2f}"
        else:
            cost_text = t["usage_unknown"]
        lines.append(f"• {t['usage_claude'].format(model=model, calls=calls, cost=cost_text)}")
    if not any_usage:
        return t["usage_none"]
    lines += ["", t["usage_total"].format(cost=f"${total:.2f}"), t["usage_note"]]
    return "\n".join(lines)


def format_undo(label: str | None, lang: str) -> str:
    """Reply to an undo: what was undone (the label is the reply that step had given)."""
    t = TEXT[lang]
    if label is None:
        return t["nothing_to_undo"]
    return f"{t['undone']}\n{label}" if label else t["undone"].rstrip(" :")
