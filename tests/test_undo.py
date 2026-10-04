from datetime import date, time

from majordome.db import Database


def snapshot(db):
    """Everything the owner can see, to compare before and after an undo."""
    tables = ["tasks", "routines", "routine_checks", "someday", "lists", "list_items"]
    return {t: [tuple(r) for r in db.conn.execute(f"SELECT * FROM {t} ORDER BY rowid")] for t in tables}


def test_undo_reverses_adds_changes_and_deletes():
    db = Database(":memory:")
    with db.undo_step():
        bank = db.add_task("Bank", due_date=date(2026, 10, 9))
        db.add_routine("Gym", [0], time(18, 0))
    before = snapshot(db)

    with db.undo_step() as step:
        db.complete_task(bank.id)
        db.rename_task(bank.id, "Call the bank")
        db.add_to_list("Courses", ["lait", "pain"])
        db.add_someday("Read Dune", "Books")
        step.label = "✅ Done: Bank"
    with db.undo_step() as step:
        db.delete_task(bank.id)
        step.label = "🗑️ Deleted: Bank"

    assert db.undo_last() == "🗑️ Deleted: Bank"
    assert db.get_task(bank.id).title == "Call the bank"  # the delete is reversed...
    assert db.undo_last() == "✅ Done: Bank"
    assert snapshot(db) == before  # ...then everything from the step before
    assert db.undo_last() == ""  # the very first step (no label)
    assert db.open_tasks() == [] and db.active_routines() == []
    assert db.undo_last() is None  # nothing left


def test_steps_without_changes_are_not_undo_steps():
    db = Database(":memory:")
    with db.undo_step() as step:
        db.add_task("Bank")
        step.label = "added"
    with db.undo_step():
        db.open_tasks()  # just reading
    assert db.undo_last() == "added"


def test_undo_from_inside_a_step_targets_the_previous_one():
    db = Database(":memory:")
    with db.undo_step() as step:
        db.add_task("Bank")
        step.label = "added"
    with db.undo_step():  # the "undo" message itself
        assert db.undo_last() == "added"
        assert db.open_tasks() == []
    assert db.undo_last() is None  # undoing didn't create something to "redo"


def test_changes_outside_steps_are_not_logged_and_reset_clears_history():
    db = Database(":memory:")
    db.add_task("Added by the scheduler, say")
    assert db.undo_last() is None
    with db.undo_step():
        db.add_task("Bank")
    db.wipe_history()
    assert db.undo_last() is None  # a reset can't be undone


def test_settings_changes_can_be_undone():
    db = Database(":memory:")
    with db.undo_step():
        db.set_daily_time("brief", time(7, 0))
    with db.undo_step():
        db.set_daily_time("brief", time(9, 0))
    db.undo_last()
    assert db.get_daily_time("brief") == time(7, 0)
    db.undo_last()
    assert db.get_daily_time("brief") == time(8, 0)  # back to the default


def test_deleting_a_promoted_task_puts_the_wish_back():
    db = Database(":memory:")
    wish = db.add_someday("Learn guitar", "Learning")
    task = db.add_task("Learn guitar", due_date=date(2026, 10, 10))
    db.promote_someday(wish.id, task.id)
    assert db.open_someday() == []
    db.delete_task(task.id)
    assert [w.title for w in db.open_someday()] == ["Learn guitar"]


def test_only_recent_steps_are_kept():
    from majordome.db import UNDO_KEEP_STEPS

    db = Database(":memory:")
    for i in range(UNDO_KEEP_STEPS + 5):
        with db.undo_step() as step:
            db.add_task(f"T{i}")
            step.label = f"T{i}"
    undone = []
    while (label := db.undo_last()) is not None:
        undone.append(label)
    assert len(undone) == UNDO_KEEP_STEPS
    assert undone[0] == f"T{UNDO_KEEP_STEPS + 4}"
