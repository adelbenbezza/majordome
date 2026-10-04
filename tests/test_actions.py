from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from majordome.actions import execute
from majordome.brain import AddTasks, CompleteTasks, ListToday, NewTask, Reply
from majordome.db import Database

PARIS = ZoneInfo("Europe/Paris")
NOW = datetime(2026, 10, 4, 16, 20, tzinfo=PARIS)  # a Sunday


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
    assert execute(ListToday("fr"), db, NOW) == "📋 Il te reste :\n• Late (ven. 2 oct.)\n• Gym (18:00)"


def test_nothing_left_and_reply():
    db = Database(":memory:")
    assert execute(ListToday("en"), db, NOW) == "🎉 Nothing left for today!"
    assert execute(Reply("Salut !"), db, NOW) == "Salut !"
