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
from zoneinfo import ZoneInfo

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
    # 4: messages the bot sent on its own (reminders, follow-ups), so each is sent once
    # even if the bot restarts. slot says which occurrence: a task's due time, or a
    # routine's day. Changing a task's time gives a new slot, so a new reminder.
    """
    CREATE TABLE notifications (
        kind    TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        slot    TEXT NOT NULL,
        type    TEXT NOT NULL,
        sent_at TEXT NOT NULL,
        PRIMARY KEY (kind, item_id, slot, type)
    );
    """,
    # 5: the Someday list (wishes without a date, grouped by category) and named lists
    # (shopping list, ideas, notes...). A Someday wish leaves the list when it's done,
    # dropped, or promoted to a dated task (task_id says which one).
    """
    CREATE TABLE someday (
        id         INTEGER PRIMARY KEY,
        title      TEXT NOT NULL,
        category   TEXT NOT NULL,
        created_at TEXT NOT NULL,
        done_at    TEXT,
        dropped_at TEXT,
        task_id    INTEGER REFERENCES tasks (id)
    );
    CREATE TABLE lists (
        id         INTEGER PRIMARY KEY,
        name       TEXT NOT NULL UNIQUE COLLATE NOCASE,
        created_at TEXT NOT NULL
    );
    CREATE TABLE list_items (
        id         INTEGER PRIMARY KEY,
        list_id    INTEGER NOT NULL REFERENCES lists (id),
        text       TEXT NOT NULL,
        created_at TEXT NOT NULL,
        done_at    TEXT
    );
    """,
    # 6: AI usage, to tell the owner what the bot costs them (/usage).
    # service: "claude" (tokens) or "whisper" (seconds of audio).
    """
    CREATE TABLE usage (
        id            INTEGER PRIMARY KEY,
        at            TEXT NOT NULL,
        service       TEXT NOT NULL,
        model         TEXT NOT NULL,
        input_tokens  INTEGER NOT NULL DEFAULT 0,
        output_tokens INTEGER NOT NULL DEFAULT 0,
        seconds       REAL NOT NULL DEFAULT 0
    );
    """,
]

OWNER_KEY = "owner_telegram_id"
# Messages sent every day at a time the owner can change ("HH:MM" local time, or "off"),
# with their default time.
DAILY_MESSAGES = {"brief": time(8, 0), "checkin": time(21, 0)}
REMINDER_MINUTES_KEY = "reminder_minutes"  # how long before a timed item to remind; 0 = off
DEFAULT_REMINDER_MINUTES = 30
TIMEZONE_KEY = "timezone"  # e.g. "America/Montreal"; if unset, the TIMEZONE variable is used
QUIET_HOURS_KEY = "quiet_hours"  # "22:00-07:00": no reminders in between; unset = off
LANGUAGE_KEY = "language"  # "fr" or "en": used for messages the bot sends on its own
GENERATION_KEY = "generation"  # goes up by one at each reset (see wipe_history)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Task:
    id: int
    title: str
    due_date: date | None
    due_at: datetime | None  # UTC
    done_at: datetime | None  # UTC
    created_at: datetime | None = None  # UTC

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Task":
        return cls(
            id=row["id"],
            title=row["title"],
            due_date=date.fromisoformat(row["due_date"]) if row["due_date"] else None,
            due_at=datetime.fromisoformat(row["due_at"]) if row["due_at"] else None,
            done_at=datetime.fromisoformat(row["done_at"]) if row["done_at"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
        )


@dataclass(frozen=True)
class Routine:
    id: int
    title: str
    weekdays: tuple[int, ...]  # Monday = 0 ... Sunday = 6
    time: time | None  # local wall-clock time
    active: bool
    created_at: datetime | None = None  # UTC

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
            created_at=datetime.fromisoformat(row["created_at"]),
        )


@dataclass(frozen=True)
class SomedayItem:
    id: int
    title: str
    category: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "SomedayItem":
        return cls(id=row["id"], title=row["title"], category=row["category"])


@dataclass(frozen=True)
class ListItem:
    id: int
    list_name: str
    text: str


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

    def get_daily_time(self, name: str) -> time | None:
        """When the daily message `name` ("brief" or "checkin") is sent, or None if turned off."""
        value = self.get_setting(f"{name}_time")
        if value is None:
            return DAILY_MESSAGES[name]
        if value == "off":
            return None
        return time.fromisoformat(value)

    def set_daily_time(self, name: str, value: time | None) -> None:
        if name not in DAILY_MESSAGES:
            raise ValueError(f"Unknown daily message {name!r}")
        self.set_setting(f"{name}_time", value.strftime("%H:%M") if value else "off")

    def get_reminder_minutes(self) -> int:
        value = self.get_setting(REMINDER_MINUTES_KEY)
        return DEFAULT_REMINDER_MINUTES if value is None else int(value)

    def set_reminder_minutes(self, minutes: int) -> None:
        self.set_setting(REMINDER_MINUTES_KEY, str(max(0, minutes)))

    def get_timezone(self, default: ZoneInfo) -> ZoneInfo:
        value = self.get_setting(TIMEZONE_KEY)
        return ZoneInfo(value) if value else default

    def set_timezone(self, tz: ZoneInfo) -> None:
        self.set_setting(TIMEZONE_KEY, tz.key)

    def get_quiet_hours(self) -> tuple[time, time] | None:
        value = self.get_setting(QUIET_HOURS_KEY)
        if not value or value == "off":
            return None
        start, end = value.split("-")
        return time.fromisoformat(start), time.fromisoformat(end)

    def set_quiet_hours(self, hours: tuple[time, time] | None) -> None:
        self.set_setting(QUIET_HOURS_KEY, f"{hours[0]:%H:%M}-{hours[1]:%H:%M}" if hours else "off")

    def get_language(self) -> str:
        return self.get_setting(LANGUAGE_KEY) or "en"

    def set_language(self, language: str) -> None:
        self.set_setting(LANGUAGE_KEY, language)

    def get_generation(self) -> int:
        return int(self.get_setting(GENERATION_KEY) or 0)

    def wipe_history(self) -> None:
        """Delete all tasks, routines, Someday wishes, lists and history. Owner and settings are kept.

        After this, SQLite starts numbering from 1 again, so a new task can get the
        number of a deleted one. Bumping the generation lets ✅ buttons on older messages
        tell they're out of date instead of ticking off the wrong thing.
        """
        with self.conn:
            self.conn.execute("DELETE FROM list_items")
            self.conn.execute("DELETE FROM lists")
            self.conn.execute("DELETE FROM someday")
            self.conn.execute("DELETE FROM notifications")
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

    def reschedule_task(self, task_id: int, due_date: date | None, due_at: datetime | None) -> Task | None:
        """Give an open task a new day (and time). Returns it, or None if it's done or gone."""
        with self.conn:
            cursor = self.conn.execute(
                "UPDATE tasks SET due_date = ?, due_at = ? WHERE id = ? AND done_at IS NULL",
                (
                    due_date.isoformat() if due_date else None,
                    due_at.astimezone(timezone.utc).isoformat() if due_at else None,
                    task_id,
                ),
            )
        return self.get_task(task_id) if cursor.rowcount else None

    def timed_tasks_between(self, start: datetime, end: datetime) -> list[Task]:
        """Open tasks with a due time from `start` to `end` (both aware datetimes)."""
        rows = self.conn.execute(
            "SELECT * FROM tasks WHERE done_at IS NULL AND due_at BETWEEN ? AND ? ORDER BY due_at",
            (start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat()),
        ).fetchall()
        return [Task.from_row(row) for row in rows]

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

    # --- notifications ----------------------------------------------------

    def mark_notified(self, kind: str, item_id: int, slot: str, type_: str) -> bool:
        """Record that a message was sent. Returns False if it had already been sent."""
        with self.conn:
            cursor = self.conn.execute(
                "INSERT OR IGNORE INTO notifications (kind, item_id, slot, type, sent_at) VALUES (?, ?, ?, ?, ?)",
                (kind, item_id, slot, type_, utc_now().isoformat()),
            )
        return cursor.rowcount == 1

    def was_notified(self, kind: str, item_id: int, slot: str, type_: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM notifications WHERE kind = ? AND item_id = ? AND slot = ? AND type = ?",
            (kind, item_id, slot, type_),
        ).fetchone()
        return row is not None

    # --- someday ----------------------------------------------------------

    def add_someday(self, title: str, category: str) -> SomedayItem:
        # Reuse an existing category's spelling ("books" -> "Books") so groups don't split.
        existing = {c.lower(): c for c in self.someday_categories()}
        category = existing.get(category.strip().lower(), category.strip())
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO someday (title, category, created_at) VALUES (?, ?, ?)",
                (title, category, utc_now().isoformat()),
            )
        return SomedayItem(cursor.lastrowid, title, category)

    def open_someday(self, limit: int = 200) -> list[SomedayItem]:
        rows = self.conn.execute(
            "SELECT * FROM someday WHERE done_at IS NULL AND dropped_at IS NULL AND task_id IS NULL "
            "ORDER BY category COLLATE NOCASE, id LIMIT ?",
            (limit,),
        ).fetchall()
        return [SomedayItem.from_row(row) for row in rows]

    def someday_categories(self) -> list[str]:
        rows = self.conn.execute("SELECT DISTINCT category FROM someday ORDER BY category COLLATE NOCASE").fetchall()
        return [row["category"] for row in rows]

    def close_someday(self, someday_id: int, done: bool) -> SomedayItem | None:
        """Take a wish off the list, as achieved (done) or no longer wanted. None if not open."""
        column = "done_at" if done else "dropped_at"
        return self._close_someday(someday_id, f"{column} = ?", (utc_now().isoformat(),))

    def promote_someday(self, someday_id: int, task_id: int) -> SomedayItem | None:
        """Record that a wish became a dated task. None if it wasn't open."""
        return self._close_someday(someday_id, "task_id = ?", (task_id,))

    def get_someday(self, someday_id: int) -> SomedayItem | None:
        row = self.conn.execute(
            "SELECT * FROM someday WHERE id = ? AND done_at IS NULL AND dropped_at IS NULL AND task_id IS NULL",
            (someday_id,),
        ).fetchone()
        return SomedayItem.from_row(row) if row else None

    def _close_someday(self, someday_id: int, assignment: str, values: tuple) -> SomedayItem | None:
        item = self.get_someday(someday_id)
        if item is None:
            return None
        with self.conn:
            self.conn.execute(f"UPDATE someday SET {assignment} WHERE id = ?", (*values, someday_id))
        return item

    # --- lists ------------------------------------------------------------

    def find_list(self, name: str) -> tuple[int, str] | None:
        """(id, name as saved) of the list called `name`, ignoring case."""
        row = self.conn.execute("SELECT id, name FROM lists WHERE name = ?", (name.strip(),)).fetchone()
        return (row["id"], row["name"]) if row else None

    def add_to_list(self, name: str, texts: list[str]) -> str:
        """Add items to a list, creating it if needed. Returns the list's name as saved."""
        found = self.find_list(name)
        with self.conn:
            if found is None:
                cursor = self.conn.execute(
                    "INSERT INTO lists (name, created_at) VALUES (?, ?)", (name.strip(), utc_now().isoformat())
                )
                found = (cursor.lastrowid, name.strip())
            self.conn.executemany(
                "INSERT INTO list_items (list_id, text, created_at) VALUES (?, ?, ?)",
                [(found[0], text, utc_now().isoformat()) for text in texts],
            )
        return found[1]

    def list_items(self, name: str | None = None, limit: int = 500) -> list[ListItem]:
        """Items not yet ticked off, of one list or of all lists."""
        sql = (
            "SELECT list_items.id, lists.name, list_items.text FROM list_items "
            "JOIN lists ON lists.id = list_items.list_id WHERE list_items.done_at IS NULL"
        )
        params: tuple = ()
        if name is not None:
            sql += " AND lists.name = ?"
            params = (name.strip(),)
        rows = self.conn.execute(sql + " ORDER BY lists.name COLLATE NOCASE, list_items.id LIMIT ?", (*params, limit)).fetchall()
        return [ListItem(row[0], row[1], row[2]) for row in rows]

    def list_names(self) -> list[str]:
        return [row["name"] for row in self.conn.execute("SELECT name FROM lists ORDER BY name COLLATE NOCASE")]

    def check_list_item(self, item_id: int) -> ListItem | None:
        """Tick an item off its list. None if it doesn't exist or was already ticked."""
        found = [item for item in self.list_items() if item.id == item_id]
        if not found:
            return None
        with self.conn:
            self.conn.execute("UPDATE list_items SET done_at = ? WHERE id = ?", (utc_now().isoformat(), item_id))
        return found[0]

    def clear_list(self, name: str) -> str | None:
        """Tick off every item of a list. Returns the list's name, or None if there's no such list."""
        found = self.find_list(name)
        if found is None:
            return None
        with self.conn:
            self.conn.execute(
                "UPDATE list_items SET done_at = ? WHERE list_id = ? AND done_at IS NULL",
                (utc_now().isoformat(), found[0]),
            )
        return found[1]

    # --- usage ------------------------------------------------------------

    def record_usage(
        self, service: str, model: str, input_tokens: int = 0, output_tokens: int = 0, seconds: float = 0
    ) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO usage (at, service, model, input_tokens, output_tokens, seconds) VALUES (?, ?, ?, ?, ?, ?)",
                (utc_now().isoformat(), service, model, input_tokens, output_tokens, seconds),
            )

    def usage_since(self, start: datetime) -> list[tuple[str, str, int, int, float, int]]:
        """Totals per (service, model) since `start`: input tokens, output tokens, seconds, calls."""
        rows = self.conn.execute(
            "SELECT service, model, SUM(input_tokens), SUM(output_tokens), SUM(seconds), COUNT(*) "
            "FROM usage WHERE at >= ? GROUP BY service, model ORDER BY service, model",
            (start.astimezone(timezone.utc).isoformat(),),
        ).fetchall()
        return [tuple(row) for row in rows]
