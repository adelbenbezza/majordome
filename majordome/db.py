"""SQLite storage.

The schema evolves through numbered migrations: each entry in MIGRATIONS is run
once, in order, and the database remembers how far it got (`PRAGMA user_version`).
To change the schema in a later stage, append a new migration; never edit an old
one, because existing databases have already run it.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path

MIGRATIONS: list[str] = [
    # 1: key/value settings (owner, brief time, language...). Shared later with the dashboard.
    """
    CREATE TABLE settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    # 2: tasks. due_date is the owner's local calendar day (a date alone isn't a moment
    # in time, so it has no timezone); due_at is the exact UTC moment, only when a time
    # was given. done_at is NULL until the task is completed.
    """
    CREATE TABLE tasks (
        id         INTEGER PRIMARY KEY,
        title      TEXT NOT NULL,
        due_date   TEXT,
        due_at     TEXT,
        done_at    TEXT,
        created_at TEXT NOT NULL
    );
    CREATE INDEX tasks_open ON tasks (done_at, due_date);
    """,
    # 3: routines. Each routine is a rule (which weekdays, what time), not a copy per day;
    # routine_checks records each day it was done, which is what streaks and charts need.
    # weekdays: "0,1" = Monday and Tuesday (Monday = 0, like Python's date.weekday()).
    # time is the local wall-clock time ("18:00" in the owner's timezone), not UTC: it must
    # stay 18:00 through daylight saving changes, which a fixed UTC time wouldn't.
    # Removing a routine only sets active = 0, so its history is kept.
    """
    CREATE TABLE routines (
        id         INTEGER PRIMARY KEY,
        title      TEXT NOT NULL,
        weekdays   TEXT NOT NULL,
        time       TEXT,
        active     INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    CREATE TABLE routine_checks (
        routine_id INTEGER NOT NULL REFERENCES routines (id),
        day        TEXT NOT NULL,
        done_at    TEXT NOT NULL,
        PRIMARY KEY (routine_id, day)
    );
    """,
]

OWNER_KEY = "owner_telegram_id"
BRIEF_TIME_KEY = "brief_time"  # "HH:MM" in the owner's timezone, or "off"
LANGUAGE_KEY = "language"  # "fr" or "en": used for messages the bot sends on its own
GENERATION_KEY = "generation"  # goes up by one at each reset (see wipe_history)
DEFAULT_BRIEF_TIME = time(8, 0)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Task:
    id: int
    title: str
    due_date: date | None
    due_at: datetime | None  # UTC
    done_at: datetime | None  # UTC

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Task":
        return cls(
            id=row["id"],
            title=row["title"],
            due_date=date.fromisoformat(row["due_date"]) if row["due_date"] else None,
            due_at=datetime.fromisoformat(row["due_at"]) if row["due_at"] else None,
            done_at=datetime.fromisoformat(row["done_at"]) if row["done_at"] else None,
        )


@dataclass(frozen=True)
class Routine:
    id: int
    title: str
    weekdays: tuple[int, ...]  # Monday = 0 ... Sunday = 6
    time: time | None  # local wall-clock time
    active: bool

    @property
    def daily(self) -> bool:
        return len(self.weekdays) == 7

    def happens_on(self, day: date) -> bool:
        return day.weekday() in self.weekdays

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Routine":
        return cls(
            id=row["id"],
            title=row["title"],
            weekdays=tuple(int(d) for d in row["weekdays"].split(",")),
            time=time.fromisoformat(row["time"]) if row["time"] else None,
            active=bool(row["active"]),
        )


class Database:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        # WAL lets the future dashboard read while the bot writes.
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.migrate()

    def migrate(self) -> None:
        current = self.conn.execute("PRAGMA user_version").fetchone()[0]
        for version, sql in enumerate(MIGRATIONS[current:], start=current + 1):
            # One transaction per migration: it either fully applies or not at all.
            try:
                self.conn.executescript(f"BEGIN; {sql} PRAGMA user_version = {version}; COMMIT;")
            except sqlite3.Error:
                self.conn.rollback()
                raise

    @property
    def schema_version(self) -> int:
        return self.conn.execute("PRAGMA user_version").fetchone()[0]

    def close(self) -> None:
        self.conn.close()

    # --- settings ---------------------------------------------------------

    def get_setting(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    # --- owner ------------------------------------------------------------

    def get_owner_id(self) -> int | None:
        value = self.get_setting(OWNER_KEY)
        return int(value) if value is not None else None

    def claim_owner(self, user_id: int) -> bool:
        """Make `user_id` the owner if nobody is yet. Returns True if they are now the owner."""
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (OWNER_KEY, str(user_id)),
            )
        return self.get_owner_id() == user_id

    def get_brief_time(self) -> time | None:
        """The morning brief time, or None if the owner turned it off."""
        value = self.get_setting(BRIEF_TIME_KEY)
        if value is None:
            return DEFAULT_BRIEF_TIME
        if value == "off":
            return None
        return time.fromisoformat(value)

    def set_brief_time(self, value: time | None) -> None:
        self.set_setting(BRIEF_TIME_KEY, value.strftime("%H:%M") if value else "off")

    def get_language(self) -> str:
        return self.get_setting(LANGUAGE_KEY) or "en"

    def set_language(self, language: str) -> None:
        self.set_setting(LANGUAGE_KEY, language)

    def get_generation(self) -> int:
        return int(self.get_setting(GENERATION_KEY) or 0)

    def wipe_history(self) -> None:
        """Delete all tasks, routines and their history. The owner and settings are kept.

        After this, SQLite starts numbering from 1 again, so a new task can get the
        number of a deleted one. Bumping the generation lets ✅ buttons on older messages
        tell they're out of date instead of ticking off the wrong thing.
        """
        with self.conn:
            self.conn.execute("DELETE FROM routine_checks")
            self.conn.execute("DELETE FROM routines")
            self.conn.execute("DELETE FROM tasks")
            self.conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, '1') "
                "ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + 1",
                (GENERATION_KEY,),
            )

    # --- tasks ------------------------------------------------------------

    def add_task(self, title: str, due_date: date | None = None, due_at: datetime | None = None) -> Task:
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO tasks (title, due_date, due_at, created_at) VALUES (?, ?, ?, ?)",
                (
                    title,
                    due_date.isoformat() if due_date else None,
                    due_at.astimezone(timezone.utc).isoformat() if due_at else None,
                    utc_now().isoformat(),
                ),
            )
        return self.get_task(cursor.lastrowid)

    def get_task(self, task_id: int) -> Task | None:
        row = self.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return Task.from_row(row) if row else None

    def complete_task(self, task_id: int) -> Task | None:
        """Mark a task done. Returns it, or None if it doesn't exist or was already done."""
        with self.conn:
            cursor = self.conn.execute(
                "UPDATE tasks SET done_at = ? WHERE id = ? AND done_at IS NULL",
                (utc_now().isoformat(), task_id),
            )
        return self.get_task(task_id) if cursor.rowcount else None

    def open_tasks(self, limit: int = 100) -> list[Task]:
        """Undone tasks, soonest first (undated ones last)."""
        rows = self.conn.execute(
            "SELECT * FROM tasks WHERE done_at IS NULL "
            "ORDER BY due_date IS NULL, due_date, due_at IS NULL, due_at, id LIMIT ?",
            (limit,),
        ).fetchall()
        return [Task.from_row(row) for row in rows]

    def tasks_left(self, today: date) -> list[Task]:
        """What's left today: undone tasks due today, overdue, or without a date."""
        rows = self.conn.execute(
            "SELECT * FROM tasks WHERE done_at IS NULL AND (due_date IS NULL OR due_date <= ?) "
            "ORDER BY due_date IS NULL, due_date, due_at IS NULL, due_at, id",
            (today.isoformat(),),
        ).fetchall()
        return [Task.from_row(row) for row in rows]

    def tasks_between(self, start: date, end: date) -> list[Task]:
        """Undone tasks due from `start` to `end` (both included)."""
        rows = self.conn.execute(
            "SELECT * FROM tasks WHERE done_at IS NULL AND due_date BETWEEN ? AND ? "
            "ORDER BY due_date, due_at IS NULL, due_at, id",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [Task.from_row(row) for row in rows]

    # --- routines ---------------------------------------------------------

    def add_routine(self, title: str, weekdays: list[int], at: time | None = None) -> Routine:
        days = ",".join(str(d) for d in sorted(set(weekdays)))
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO routines (title, weekdays, time, created_at) VALUES (?, ?, ?, ?)",
                (title, days, at.strftime("%H:%M") if at else None, utc_now().isoformat()),
            )
        return self.get_routine(cursor.lastrowid)

    def get_routine(self, routine_id: int) -> Routine | None:
        row = self.conn.execute("SELECT * FROM routines WHERE id = ?", (routine_id,)).fetchone()
        return Routine.from_row(row) if row else None

    def active_routines(self) -> list[Routine]:
        rows = self.conn.execute(
            "SELECT * FROM routines WHERE active = 1 ORDER BY time IS NULL, time, id"
        ).fetchall()
        return [Routine.from_row(row) for row in rows]

    def update_routine(self, routine_id: int, title: str, weekdays: list[int], at: time | None) -> Routine | None:
        """Change an active routine in place, so its history (and future streak) is kept."""
        days = ",".join(str(d) for d in sorted(set(weekdays)))
        with self.conn:
            cursor = self.conn.execute(
                "UPDATE routines SET title = ?, weekdays = ?, time = ? WHERE id = ? AND active = 1",
                (title, days, at.strftime("%H:%M") if at else None, routine_id),
            )
        return self.get_routine(routine_id) if cursor.rowcount else None

    def remove_routine(self, routine_id: int) -> Routine | None:
        """Stop a routine (its history is kept). Returns it, or None if it wasn't active."""
        with self.conn:
            cursor = self.conn.execute(
                "UPDATE routines SET active = 0 WHERE id = ? AND active = 1", (routine_id,)
            )
        return self.get_routine(routine_id) if cursor.rowcount else None

    def check_routine(self, routine_id: int, day: date) -> Routine | None:
        """Mark a routine done for `day`. Returns it, or None if inactive or already done that day."""
        routine = self.get_routine(routine_id)
        if routine is None or not routine.active:
            return None
        with self.conn:
            cursor = self.conn.execute(
                "INSERT OR IGNORE INTO routine_checks (routine_id, day, done_at) VALUES (?, ?, ?)",
                (routine_id, day.isoformat(), utc_now().isoformat()),
            )
        return routine if cursor.rowcount else None

    def is_routine_done(self, routine_id: int, day: date) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM routine_checks WHERE routine_id = ? AND day = ?", (routine_id, day.isoformat())
        ).fetchone()
        return row is not None

    def routines_on(self, day: date) -> list[Routine]:
        """Active routines that happen on `day`."""
        return [r for r in self.active_routines() if r.happens_on(day)]

    def routines_left(self, day: date) -> list[Routine]:
        """Routines that happen on `day` and aren't done yet."""
        return [r for r in self.routines_on(day) if not self.is_routine_done(r.id, day)]
