from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from majordome.actions import execute, format_brief
from majordome.brain import AddTasks, CompleteTasks, ListTasks, NewTask, Reply, SetBriefTime
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
    assert execute(SetBriefTime(time(7, 30), "fr"), db, NOW) == (
        "☀️ C'est noté : ton brief arrivera chaque matin à 07:30."
    )
    assert db.get_brief_time() == time(7, 30)
    execute(SetBriefTime(None, "en"), db, NOW)
    assert db.get_brief_time() is None


def test_brief():
    db = Database(":memory:")
    assert format_brief(db, NOW, "en") == "☀️ Good morning! Nothing planned today. Enjoy 🙂"
    db.add_task("Supplements")
    db.add_task("Gym", due_date=TODAY, due_at=datetime(2026, 10, 4, 18, 0, tzinfo=PARIS))
    db.add_task("Tomorrow's", due_date=TOMORROW)
    assert format_brief(db, NOW, "fr") == "☀️ Bonjour ! Au programme aujourd'hui :\n• Gym (18:00)\n• Supplements"
