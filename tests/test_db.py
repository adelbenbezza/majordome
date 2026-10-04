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
