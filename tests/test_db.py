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
    assert db.get_daily_time("brief") == time(8, 0)  # default
    db.set_daily_time("brief", time(7, 30))
    assert db.get_daily_time("brief") == time(7, 30)
    db.set_daily_time("brief", None)
    assert db.get_daily_time("brief") is None  # turned off
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
    db.set_daily_time("brief", time(7, 0))
    db.set_language("fr")
    routine = db.add_routine("Gym", [0], time(18, 0))
    db.check_routine(routine.id, date(2026, 10, 5))
    db.add_task("Bank")
    assert db.get_generation() == 0

    db.wipe_history()
    assert db.open_tasks() == [] and db.active_routines() == []
    assert db.conn.execute("SELECT COUNT(*) FROM routine_checks").fetchone()[0] == 0
    assert db.get_owner_id() == 42 and db.get_daily_time("brief") == time(7, 0) and db.get_language() == "fr"
    assert db.get_generation() == 1
    db.wipe_history()
    assert db.get_generation() == 2


def test_someday():
    db = Database(":memory:")
    dune = db.add_someday("Read Dune", "Books")
    guitar = db.add_someday("Learn guitar", "Learning")
    tolkien = db.add_someday("Read Tolkien", "books")  # same category, other spelling
    assert tolkien.category == "Books"
    assert [(i.title, i.category) for i in db.open_someday()] == [
        ("Read Dune", "Books"), ("Read Tolkien", "Books"), ("Learn guitar", "Learning")
    ]
    task = db.add_task("Read Dune")
    assert db.promote_someday(dune.id, task.id) == dune
    assert db.close_someday(guitar.id, done=True) == guitar
    assert db.close_someday(guitar.id, done=False) is None  # already off the list
    assert [i.title for i in db.open_someday()] == ["Read Tolkien"]


def test_lists():
    db = Database(":memory:")
    assert db.add_to_list("Courses", ["lait", "œufs"]) == "Courses"
    assert db.add_to_list("courses", ["pain"]) == "Courses"  # same list, any case
    db.add_to_list("Idées", ["app de recettes"])
    assert db.list_names() == ["Courses", "Idées"]
    assert [i.text for i in db.list_items("COURSES")] == ["lait", "œufs", "pain"]
    milk = db.list_items("Courses")[0]
    assert db.check_list_item(milk.id) == milk
    assert db.check_list_item(milk.id) is None
    assert db.clear_list("courses") == "Courses"
    assert db.list_items("Courses") == [] and [i.text for i in db.list_items()] == ["app de recettes"]
    assert db.clear_list("Nope") is None


def test_wipe_includes_someday_and_lists():
    db = Database(":memory:")
    db.add_someday("Read Dune", "Books")
    db.add_to_list("Courses", ["lait"])
    db.wipe_history()
    assert db.open_someday() == [] and db.list_names() == []


def test_timezone_quiet_hours_and_usage():
    from datetime import datetime, time, timedelta, timezone
    from zoneinfo import ZoneInfo

    db = Database(":memory:")
    paris = ZoneInfo("Europe/Paris")
    assert db.get_timezone(paris) == paris  # default from the TIMEZONE variable
    db.set_timezone(ZoneInfo("America/Montreal"))
    assert db.get_timezone(paris).key == "America/Montreal"

    assert db.get_quiet_hours() is None
    db.set_quiet_hours((time(22, 0), time(7, 0)))
    assert db.get_quiet_hours() == (time(22, 0), time(7, 0))
    db.set_quiet_hours(None)
    assert db.get_quiet_hours() is None

    db.record_usage("claude", "claude-haiku-4-5", input_tokens=4000, output_tokens=100)
    db.record_usage("claude", "claude-haiku-4-5", input_tokens=3000, output_tokens=50)
    db.record_usage("whisper", "whisper-1", seconds=12.5)
    since = datetime.now(timezone.utc) - timedelta(days=1)
    assert db.usage_since(since) == [
        ("claude", "claude-haiku-4-5", 7000, 150, 0.0, 2),
        ("whisper", "whisper-1", 0, 0, 12.5, 1),
    ]
    assert db.usage_since(datetime.now(timezone.utc) + timedelta(days=1)) == []


def test_repeat_patterns():
    from datetime import date, timedelta

    db = Database(":memory:")
    start = date(2026, 10, 2)  # a Friday
    cleaning = db.add_routine("Cleaning", [4], None, unit="week", every=2, start_date=start)
    rent = db.add_routine("Pay rent", [], None, unit="month", month_day=1, start_date=start)
    month_end = db.add_routine("Budget", [], None, unit="month", month_day=31, start_date=start)
    dentist = db.add_routine("Dentist", [], None, unit="month", every=6, month_day=15, start_date=start)

    def days_of(routine, first, last):
        days, day = [], first
        while day <= last:
            if routine.happens_on(day):
                days.append(day.isoformat())
            day += timedelta(days=1)
        return days

    assert days_of(cleaning, date(2026, 9, 25), date(2026, 10, 31)) == ["2026-10-02", "2026-10-16", "2026-10-30"]
    assert days_of(rent, date(2026, 10, 1), date(2027, 1, 1)) == ["2026-11-01", "2026-12-01", "2027-01-01"]  # not before start
    assert days_of(month_end, date(2026, 10, 1), date(2027, 3, 1)) == [
        "2026-10-31", "2026-11-30", "2026-12-31", "2027-01-31", "2027-02-28"  # last day of each month
    ]
    assert days_of(dentist, date(2026, 10, 1), date(2027, 12, 31)) == ["2026-10-15", "2027-04-15", "2027-10-15"]
    assert not rent.daily and not cleaning.daily
    # Said on 2 Oct, "every 6 months on the 1st" starts on 1 Nov, not next April.
    boiler = db.add_routine("Boiler check", [], None, unit="month", every=6, month_day=1, start_date=start)
    assert days_of(boiler, date(2026, 10, 1), date(2027, 6, 1)) == ["2026-11-01", "2027-05-01"]

    # Older routines (no start date) keep repeating every week, as before.
    gym = db.add_routine("Gym", [0, 1])
    assert gym.unit == "week" and gym.every == 1 and gym.happens_on(date(2020, 1, 6))
