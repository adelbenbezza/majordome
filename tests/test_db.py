from majordome.db import MIGRATIONS, Database


def test_migrations_run_once(tmp_path):
    path = tmp_path / "sub" / "test.db"  # parent folder is created automatically
    db = Database(path)
    assert db.schema_version == len(MIGRATIONS)
    db.set_setting("brief_time", "08:00")
    db.close()

    # Reopening must not re-run migrations (CREATE TABLE would fail) nor lose data.
    db = Database(path)
    assert db.schema_version == len(MIGRATIONS)
    assert db.get_setting("brief_time") == "08:00"


def test_settings_roundtrip():
    db = Database(":memory:")
    assert db.get_setting("missing") is None
    db.set_setting("language", "fr")
    db.set_setting("language", "en")
    assert db.get_setting("language") == "en"


def test_first_claim_wins():
    db = Database(":memory:")
    assert db.get_owner_id() is None
    assert db.claim_owner(111) is True
    assert db.claim_owner(222) is False
    assert db.get_owner_id() == 111


def test_tasks_left_today():
    from datetime import date, datetime, timezone

    db = Database(":memory:")
    today = date(2026, 10, 4)
    overdue = db.add_task("Overdue", due_date=date(2026, 10, 1))
    undated = db.add_task("Undated")
    timed = db.add_task("Timed", due_date=today, due_at=datetime(2026, 10, 4, 13, 0, tzinfo=timezone.utc))
    db.add_task("Tomorrow", due_date=date(2026, 10, 5))
    done = db.add_task("Done", due_date=today)
    db.complete_task(done.id)

    # Overdue first, then today's, then undated; tomorrow's and done ones are left out.
    assert [t.title for t in db.tasks_left(today)] == ["Overdue", "Timed", "Undated"]
    assert timed.due_at == datetime(2026, 10, 4, 13, 0, tzinfo=timezone.utc)
    assert {t.id for t in db.open_tasks()} == {overdue.id, undated.id, timed.id, 4}


def test_complete_task_only_once():
    db = Database(":memory:")
    task = db.add_task("Supplements")
    assert db.complete_task(task.id).done_at is not None
    assert db.complete_task(task.id) is None  # already done
    assert db.complete_task(999) is None  # doesn't exist


def test_brief_time_and_language_settings():
    from datetime import time

    db = Database(":memory:")
    assert db.get_brief_time() == time(8, 0)  # default
    db.set_brief_time(time(7, 30))
    assert db.get_brief_time() == time(7, 30)
    db.set_brief_time(None)
    assert db.get_brief_time() is None  # turned off
    assert db.get_language() == "en"
    db.set_language("fr")
    assert db.get_language() == "fr"


def test_routines():
    from datetime import date, time

    db = Database(":memory:")
    monday, tuesday, wednesday = date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7)
    gym = db.add_routine("Gym", [1, 0, 1], time(18, 0))  # duplicates and order don't matter
    pills = db.add_routine("Supplements", list(range(7)))
    assert gym.weekdays == (0, 1) and gym.time == time(18, 0) and not gym.daily
    assert pills.daily and pills.time is None

    assert [r.title for r in db.routines_on(monday)] == ["Gym", "Supplements"]  # timed first
    assert [r.title for r in db.routines_on(wednesday)] == ["Supplements"]

    assert db.check_routine(gym.id, monday) == gym
    assert db.check_routine(gym.id, monday) is None  # already done that day
    assert [r.title for r in db.routines_left(monday)] == ["Supplements"]
    assert [r.title for r in db.routines_left(tuesday)] == ["Gym", "Supplements"]  # each day is separate

    assert db.remove_routine(gym.id).title == "Gym"
    assert db.remove_routine(gym.id) is None
    assert [r.title for r in db.active_routines()] == ["Supplements"]
    assert db.check_routine(gym.id, tuesday) is None  # removed routines can't be checked
    assert db.is_routine_done(gym.id, monday)  # history is kept


def test_wipe_history_keeps_owner_and_settings():
    from datetime import date, time

    db = Database(":memory:")
    db.claim_owner(42)
    db.set_brief_time(time(7, 0))
    db.set_language("fr")
    routine = db.add_routine("Gym", [0], time(18, 0))
    db.check_routine(routine.id, date(2026, 10, 5))
    db.add_task("Bank")
    assert db.get_generation() == 0

    db.wipe_history()
    assert db.open_tasks() == [] and db.active_routines() == []
    assert db.conn.execute("SELECT COUNT(*) FROM routine_checks").fetchone()[0] == 0
    assert db.get_owner_id() == 42 and db.get_brief_time() == time(7, 0) and db.get_language() == "fr"
    assert db.get_generation() == 1
    db.wipe_history()
    assert db.get_generation() == 2
