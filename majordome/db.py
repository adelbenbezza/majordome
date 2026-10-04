"""SQLite storage.

The schema evolves through numbered migrations: each entry in MIGRATIONS is run
once, in order, and the database remembers how far it got (`PRAGMA user_version`).
To change the schema in a later stage, append a new migration; never edit an old
one, because existing databases have already run it.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
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
]

OWNER_KEY = "owner_telegram_id"


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
