"""SQLite storage.

The schema evolves through numbered migrations: each entry in MIGRATIONS is run
once, in order, and the database remembers how far it got (`PRAGMA user_version`).
To change the schema in a later stage, append a new migration; never edit an old
one, because existing databases have already run it.
"""

import sqlite3
from pathlib import Path

MIGRATIONS: list[str] = [
    # 1: key/value settings (owner, brief time, language...). Shared later with the dashboard.
    """
    CREATE TABLE settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
]

OWNER_KEY = "owner_telegram_id"


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
