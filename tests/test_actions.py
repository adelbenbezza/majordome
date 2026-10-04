from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from majordome.actions import execute, format_brief, format_checkin, format_settings, format_usage, move_to_tomorrow
from majordome.brain import DeleteTasks, RenameTask, Undo, AddSomeday, AddToList, CheckListItems, ClearList, CloseSomeday, NewSomeday, PromoteSomeday, Show, AddRoutine, AddTasks, RemoveRoutines, UpdateRoutine, CompleteTasks, ListTasks, NewTask, Reply, RescheduleTasks, UpdateSetting
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
    assert execute(UpdateSetting("brief_time", time(7, 30), "fr"), db, NOW) == (
        "☀️ C'est noté : ton brief arrivera chaque matin à 07:30."
    )
    assert db.get_daily_time("brief") == time(7, 30)
    execute(UpdateSetting("brief_time", None, "en"), db, NOW)
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
    assert execute(Show("routines", None, "en"), db, NOW) == (
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
    assert execute(UpdateSetting("checkin_time", time(20, 30), "en"), db, NOW) == "🌙 Got it: I'll check in every evening at 20:30."
    assert db.get_daily_time("checkin") == time(20, 30)
    assert execute(UpdateSetting("reminder_minutes", 15, "fr"), db, NOW) == "⏰ C'est noté : je te préviendrai 15 min avant."
    assert db.get_reminder_minutes() == 15
    execute(UpdateSetting("reminder_minutes", 0, "en"), db, NOW)
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


def test_someday_flow():
    db = Database(":memory:")
    assert execute(Show("someday", None, "en"), db, NOW).startswith("Your Someday list is empty.")
    reply = execute(AddSomeday([NewSomeday("Read Dune", "Books"), NewSomeday("Learn guitar", "Learning")], "en"), db, NOW)
    assert reply == "✨ Added to Someday:\n• Read Dune (Books)\n• Learn guitar (Learning)"
    execute(AddSomeday([NewSomeday("Read Tolkien", "books")], "en"), db, NOW)
    assert execute(Show("someday", None, "en"), db, NOW) == (
        "✨ Someday:\n\n▸ Books\n• Read Dune\n• Read Tolkien\n\n▸ Learning\n• Learn guitar"
    )
    assert execute(Show("someday", "learning", "en"), db, NOW) == "✨ Someday:\n\n▸ Learning\n• Learn guitar"

    saturday = date(2026, 10, 10)
    assert execute(PromoteSomeday(2, saturday, time(10, 0), "en"), db, NOW) == (
        "📅 From Someday to your tasks:\n• Learn guitar (Sat Oct 10, 10:00)"
    )
    assert [t.title for t in db.tasks_between(saturday, saturday)] == ["Learn guitar"]
    assert execute(PromoteSomeday(2, saturday, None, "en"), db, NOW) == "I couldn't find that in your Someday list."
    assert execute(CloseSomeday([1], True, "fr"), db, NOW) == "🎉 Bravo ! Retiré de « Un jour » :\n• Read Dune"
    assert [i.title for i in db.open_someday()] == ["Read Tolkien"]


def test_lists_flow():
    db = Database(":memory:")
    assert execute(Show("lists", None, "fr"), db, NOW).startswith("Tu n'as pas encore de liste.")
    assert execute(AddToList("Courses", ["lait", "œufs"], "fr"), db, NOW) == "📝 Ajouté à « Courses » :\n• lait\n• œufs"
    execute(AddToList("Idées", ["app de recettes"], "fr"), db, NOW)
    assert execute(Show("lists", None, "fr"), db, NOW) == "📝 Tes listes :\n• Courses (2)\n• Idées (1)"
    assert execute(Show("lists", "courses", "fr"), db, NOW) == "📝 Courses :\n• lait\n• œufs"
    milk = db.list_items("Courses")[0]
    assert execute(CheckListItems([milk.id], "en"), db, NOW) == "✅ Ticked off:\n• lait"
    assert execute(CheckListItems([milk.id], "en"), db, NOW) == "I couldn't find that in your lists."
    assert execute(ClearList("courses", "en"), db, NOW) == '🧹 "Courses" list emptied.'
    assert execute(Show("lists", "Courses", "en"), db, NOW) == 'Your "Courses" list is empty.'
    assert execute(ClearList("Nope", "en"), db, NOW) == 'I couldn\'t find a list called "Nope".'


def test_timezone_and_quiet_hours_settings():
    from zoneinfo import ZoneInfo

    db = Database(":memory:")
    reply = execute(UpdateSetting("timezone", ZoneInfo("America/Montreal"), "en"), db, NOW)
    assert reply.startswith("🌍 Got it: timezone America/Montreal (it's ")
    assert db.get_timezone(PARIS).key == "America/Montreal"
    assert execute(UpdateSetting("quiet_hours", (time(22, 0), time(7, 0)), "fr"), db, NOW) == (
        "🌙 Heures calmes : pas de rappels entre 22:00 et 07:00."
    )
    assert execute(UpdateSetting("quiet_hours", None, "en"), db, NOW) == "🔔 Quiet hours turned off."


def test_settings_overview():
    db = Database(":memory:")
    db.set_daily_time("checkin", None)
    db.set_quiet_hours((time(22, 0), time(7, 0)))
    lines = format_settings(db, "Europe/Paris", "claude-haiku-4-5", "en").splitlines()
    assert lines[:11] == [
        "⚙️ Your settings",
        "",
        "• Language: I reply in the language you write in",
        "• Timezone: Europe/Paris",
        "• Morning brief: 08:00",
        "• Evening check-in: off",
        "• Weekly review: Sundays at 19:00",
        "• Reminders: 30 min before",
        "• Quiet hours: from 22:00 to 07:00",
        "• Calendar: not connected (/calendar to link it)",
        "• AI model: claude-haiku-4-5 (set in Railway)",
    ]


def test_usage_report():
    db = Database(":memory:")
    now = datetime.now(PARIS)
    assert format_usage(db, now, "en") == "No AI usage this month yet."
    for _ in range(100):
        db.record_usage("claude", "claude-haiku-4-5", input_tokens=4000, output_tokens=100)
    db.record_usage("whisper", "whisper-1", seconds=600)
    db.record_usage("claude", "some-future-model", input_tokens=10, output_tokens=10)
    lines = format_usage(db, now, "en").splitlines()
    # 100 × (4000 × $1 + 100 × $5) / 1M = $0.45; 10 min × $0.006 = $0.06
    assert "• Claude (claude-haiku-4-5): 100 messages, ≈ $0.45" in lines
    assert "• Claude (some-future-model): 1 messages, ≈ unknown price" in lines
    assert "• Voice notes: 10.0 min, ≈ $0.06" in lines
    assert "AI total: ≈ $0.51" in lines


def test_brief_with_calendar_events():
    from majordome.calendar_feed import Event

    db = Database(":memory:")
    db.add_task("Gym", due_date=TODAY, due_at=datetime(2026, 10, 4, 18, 0, tzinfo=PARIS))
    events = [Event("Mum's birthday", None, None), Event("Dentist", time(10, 0), time(11, 0))]
    assert format_brief(db, NOW, "en", events) == (
        "☀️ Good morning! Here's your day:\n"
        "📅 Mum's birthday (all day)\n"
        "📅 10:00–11:00 Dentist\n"
        "• Gym (18:00)"
    )
    # A calendar problem never stops the brief.
    assert format_brief(db, NOW, "fr", calendar_failed=True) == (
        "☀️ Bonjour ! Au programme aujourd'hui :\n📅 (je n'ai pas pu lire ton agenda aujourd'hui)\n• Gym (18:00)"
    )


def test_ticking_off_a_routine_shows_the_streak():
    db = Database(":memory:")
    pills = db.add_routine("Supplements", list(range(7)))
    db.check_routine(pills.id, TODAY - timedelta(days=1))
    db.check_routine(pills.id, TODAY - timedelta(days=2))
    assert execute(CompleteTasks([], "fr", routine_ids=[pills.id]), db, NOW) == "✅ Fait :\n• Supplements 🔥 3 d'affilée"
    assert execute(Show("routines", None, "en"), db, NOW) == "🔁 Your routines:\n• Supplements — every day 🔥 3 in a row"


def test_delete_rename_and_undo():
    db = Database(":memory:")
    with db.undo_step() as step:
        step.label = execute(AddTasks([NewTask("Appeler Blanche", TOMORROW, None)], "fr"), db, NOW)
    task = db.open_tasks()[0]
    with db.undo_step() as step:
        step.label = execute(RenameTask(task.id, "Appeler la banque", "fr"), db, NOW)
    assert step.label == "✏️ Renommé : Appeler la banque (demain)"
    with db.undo_step():
        assert execute(Undo("fr"), db, NOW) == "↩️ Annulé :\n✏️ Renommé : Appeler la banque (demain)"
    assert db.get_task(task.id).title == "Appeler Blanche"
    assert execute(DeleteTasks([task.id], "en"), db, NOW) == "🗑️ Deleted:\n• Appeler Blanche"
    assert execute(DeleteTasks([task.id], "en"), db, NOW) == "I couldn't find that task in your list."
    assert execute(Undo("en"), db, NOW).startswith("↩️ Undone:\n📝 Ajouté :")  # the add itself
    assert execute(Undo("en"), db, NOW) == "There's nothing to undo."


def test_repeat_wording():
    db = Database(":memory:")
    execute(AddRoutine("Ménage", [4], None, "fr", every=2), db, NOW)
    execute(AddRoutine("Loyer", [], None, "fr", unit="month", month_day=1), db, NOW)
    execute(AddRoutine("Budget", [], time(20, 0), "en", unit="month", month_day=31), db, NOW)
    execute(AddRoutine("Dentist", [], None, "en", unit="month", every=6, month_day=22), db, NOW)
    assert execute(Show("routines", None, "fr"), db, NOW).splitlines()[1:] == [
        "• Budget — le dernier jour de chaque mois à 20:00",
        "• Ménage — toutes les 2 semaines, ven.",
        "• Loyer — le 1er de chaque mois",
        "• Dentist — tous les 6 mois, le 22",
    ]
    assert execute(Show("routines", None, "en"), db, NOW).splitlines()[1:] == [
        "• Budget — on the last day of every month at 20:00",
        "• Ménage — every 2 weeks, Fri",
        "• Loyer — on the 1st of every month",
        "• Dentist — every 6 months on the 22nd",
    ]
    # Counting starts today (Sunday 4 Oct): the cleaning is on Fri 9 Oct, then two weeks later.
    cleaning = db.active_routines()[1]
    assert cleaning.start_date == TODAY
    assert [cleaning.happens_on(date(2026, 10, d)) for d in (9, 16, 23)] == [True, False, True]


def test_updating_a_routine_keeps_its_start_date():
    db = Database(":memory:")
    next_friday = date(2026, 10, 9)
    execute(AddRoutine("Ménage", [4], None, "fr", every=2, start_date=next_friday), db, NOW)
    execute(UpdateRoutine(1, "Ménage", [5], None, "fr", every=2), db, NOW)  # Saturday instead
    assert db.get_routine(1).start_date == next_friday
