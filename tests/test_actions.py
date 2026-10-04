from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from majordome.actions import execute, format_brief, format_checkin, move_to_tomorrow
from majordome.brain import AddRoutine, AddTasks, ListRoutines, RemoveRoutines, UpdateRoutine, CompleteTasks, ListTasks, NewTask, Reply, RescheduleTasks, SetDailyTime, SetReminders
from majordome.db import Database

PARIS = ZoneInfo("Europe/Paris")
NOW = datetime(2026, 10, 4, 16, 20, tzinfo=PARIS)  # a Sunday
TODAY = NOW.date()
TOMORROW = TODAY + timedelta(days=1)


def list_tasks(start, end, lang="en"):
    return ListTasks(start, end, lang)


def test_add_task_stores_time_in_utc():
    db = Database(":memory:")
    reply = execute(AddTasks([NewTask("Call the bank", date(2026, 10, 9), time(15, 0))], "en"), db, NOW)
    assert reply == "📝 Added:\n• Call the bank (Fri Oct 9, 15:00)"
    task = db.open_tasks()[0]
    assert task.due_date == date(2026, 10, 9)
    assert task.due_at == datetime(2026, 10, 9, 13, 0, tzinfo=timezone.utc)  # Paris is UTC+2 in October


def test_time_without_day_means_today():
    db = Database(":memory:")
    reply = execute(AddTasks([NewTask("Gym", None, time(18, 30))], "fr"), db, NOW)
    assert reply == "📝 Ajouté :\n• Gym (aujourd'hui, 18:30)"
    assert db.open_tasks()[0].due_date == NOW.date()


def test_complete_and_list_today():
    db = Database(":memory:")
    supplements = db.add_task("Supplements")
    db.add_task("Gym", due_date=NOW.date(), due_at=datetime(2026, 10, 4, 18, 0, tzinfo=PARIS))
    db.add_task("Late", due_date=date(2026, 10, 2))

    assert execute(CompleteTasks([supplements.id], "en"), db, NOW) == "✅ Done:\n• Supplements"
    assert execute(CompleteTasks([supplements.id], "en"), db, NOW) == "I couldn't find that task in your list."
    assert execute(list_tasks(TODAY, TODAY, "fr"), db, NOW) == "📋 Il te reste :\n• Late (ven. 2 oct.)\n• Gym (18:00)"


def test_nothing_left_and_reply():
    db = Database(":memory:")
    assert execute(list_tasks(TODAY, TODAY), db, NOW) == "🎉 Nothing left for today!"
    assert execute(list_tasks(TOMORROW, TOMORROW, "fr"), db, NOW) == "Rien de prévu pour demain."
    assert execute(Reply("Salut !"), db, NOW) == "Salut !"


def test_list_tomorrow_and_week():
    db = Database(":memory:")
    db.add_task("Undated")
    db.add_task("Milk", due_date=TOMORROW)
    db.add_task("Gym", due_date=TOMORROW, due_at=datetime(2026, 10, 5, 19, 0, tzinfo=PARIS))
    db.add_task("Bank", due_date=date(2026, 10, 9), due_at=datetime(2026, 10, 9, 15, 0, tzinfo=PARIS))
    db.add_task("Next month", due_date=date(2026, 11, 2))

    # A single future day: only that day's tasks, timed ones first.
    assert execute(list_tasks(TOMORROW, TOMORROW), db, NOW) == "📋 Tomorrow:\n• Gym (19:00)\n• Milk"

    # A week including today: today gets the undated task, then one section per day.
    assert execute(list_tasks(TODAY, date(2026, 10, 10), "fr"), db, NOW) == (
        "📋 Aujourd'hui :\n• Undated\n\n"
        "📋 Demain :\n• Gym (19:00)\n• Milk\n\n"
        "📋 Ven. 9 oct. :\n• Bank (15:00)"
    )


def test_set_brief_time():
    db = Database(":memory:")
    assert execute(SetDailyTime("brief", time(7, 30), "fr"), db, NOW) == (
        "☀️ C'est noté : ton brief arrivera chaque matin à 07:30."
    )
    assert db.get_daily_time("brief") == time(7, 30)
    execute(SetDailyTime("brief", None, "en"), db, NOW)
    assert db.get_daily_time("brief") is None


def test_brief():
    db = Database(":memory:")
    assert format_brief(db, NOW, "en") == "☀️ Good morning! Nothing planned today. Enjoy 🙂"
    db.add_task("Supplements")
    db.add_task("Gym", due_date=TODAY, due_at=datetime(2026, 10, 4, 18, 0, tzinfo=PARIS))
    db.add_task("Tomorrow's", due_date=TOMORROW)
    assert format_brief(db, NOW, "fr") == "☀️ Bonjour ! Au programme aujourd'hui :\n• Gym (18:00)\n• Supplements"


MONDAY = date(2026, 10, 5)


def test_routines_lifecycle():
    db = Database(":memory:")
    assert execute(AddRoutine("Gym", [0, 1], time(18, 0), "fr"), db, NOW) == (
        "🔁 Routine ajoutée : Gym — lun., mar. à 18:00"
    )
    execute(AddRoutine("Supplements", list(range(7)), None, "en"), db, NOW)
    execute(AddRoutine("Run", [5, 6], None, "en"), db, NOW)
    assert execute(ListRoutines("en"), db, NOW) == (
        "🔁 Your routines:\n• Gym — Mon, Tue at 18:00\n• Supplements — every day\n• Run — at weekends"
    )
    db.check_routine(1, MONDAY)
    assert execute(UpdateRoutine(1, "Gym", [0, 1], time(19, 0), "en"), db, NOW) == (
        "🔁 Routine updated: Gym — Mon, Tue at 19:00"
    )
    assert db.is_routine_done(1, MONDAY)  # history survives the change
    assert execute(RemoveRoutines([3], "en"), db, NOW) == "🗑️ Routine stopped:\n• Run"
    assert execute(RemoveRoutines([3], "en"), db, NOW) == "I couldn't find that routine."
    assert execute(UpdateRoutine(3, "Run", [5], None, "en"), db, NOW) == "I couldn't find that routine."


def test_routines_in_lists():
    db = Database(":memory:")
    gym = db.add_routine("Gym", [0, 1], time(18, 0))
    pills = db.add_routine("Supplements", list(range(7)))
    db.add_task("Bank", due_date=MONDAY, due_at=datetime(2026, 10, 5, 9, 0, tzinfo=PARIS))
    monday_morning = datetime(2026, 10, 5, 7, 0, tzinfo=PARIS)

    # Today: tasks and routines mixed, sorted by time.
    assert execute(list_tasks(MONDAY, MONDAY), db, monday_morning) == (
        "📋 Still to do:\n• Bank (09:00)\n• 🔁 Gym (18:00)\n• 🔁 Supplements"
    )
    # Ticking off a routine counts for today only.
    assert execute(CompleteTasks([], "en", routine_ids=[gym.id, pills.id]), db, monday_morning) == (
        "✅ Done:\n• Gym\n• Supplements"
    )
    assert format_brief(db, monday_morning, "en") == "☀️ Good morning! Here's your day:\n• Bank (09:00)"
    # Tomorrow they're back. A week view leaves out everyday routines, which would repeat on every line.
    assert execute(list_tasks(MONDAY, date(2026, 10, 8)), db, monday_morning) == (
        "📋 Today:\n• Bank (09:00)\n\n📋 Tomorrow:\n• 🔁 Gym (18:00)"
    )


def test_settings_by_conversation():
    db = Database(":memory:")
    assert execute(SetDailyTime("checkin", time(20, 30), "en"), db, NOW) == "🌙 Got it: I'll check in every evening at 20:30."
    assert db.get_daily_time("checkin") == time(20, 30)
    assert execute(SetReminders(15, "fr"), db, NOW) == "⏰ C'est noté : je te préviendrai 15 min avant."
    assert db.get_reminder_minutes() == 15
    execute(SetReminders(0, "en"), db, NOW)
    assert db.get_reminder_minutes() == 0


def test_reschedule_keeps_time_unless_given():
    db = Database(":memory:")
    bank = db.add_task("Bank", due_date=TODAY, due_at=datetime(2026, 10, 4, 15, 0, tzinfo=PARIS))
    friday = date(2026, 10, 9)
    assert execute(RescheduleTasks([bank.id], friday, None, "en"), db, NOW) == "📅 Moved:\n• Bank (Fri Oct 9, 15:00)"
    assert execute(RescheduleTasks([bank.id], friday, time(9, 0), "en"), db, NOW) == "📅 Moved:\n• Bank (Fri Oct 9, 09:00)"
    assert db.get_task(bank.id).due_at == datetime(2026, 10, 9, 7, 0, tzinfo=timezone.utc)
    assert execute(RescheduleTasks([999], friday, None, "en"), db, NOW) == "I couldn't find that task in your list."


def test_evening_check_in_and_move_to_tomorrow():
    db = Database(":memory:")
    evening = datetime(2026, 10, 4, 21, 0, tzinfo=PARIS)
    assert format_checkin(db, evening, "en") == "🌙 All done for today, well done! 🎉"
    db.add_task("Bank", due_date=TODAY, due_at=datetime(2026, 10, 4, 15, 0, tzinfo=PARIS))
    db.add_task("Late", due_date=date(2026, 10, 1))
    db.add_task("Someday-ish")  # undated: stays undated
    db.add_routine("Stretch", [6])  # routines aren't moved
    assert format_checkin(db, evening, "en") == (
        "🌙 Evening check-in. Still to do:\n• Late (Thu Oct 1)\n• Bank (15:00)\n• 🔁 Stretch\n• Someday-ish"
    )
    moved = move_to_tomorrow(db, TODAY, evening)
    assert [(t.title, t.due_date) for t in moved] == [("Late", TOMORROW), ("Bank", TOMORROW)]
    assert db.get_task(moved[1].id).due_at == datetime(2026, 10, 5, 13, 0, tzinfo=timezone.utc)  # same 15:00
    assert format_checkin(db, evening, "en") == "🌙 Evening check-in. Still to do:\n• 🔁 Stretch\n• Someday-ish"
