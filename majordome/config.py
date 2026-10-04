"""Read settings from environment variables.

Everything personal (tokens, owner, timezone) comes from the environment so the
same code can be deployed by anyone without editing it.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REQUIRED = ("TELEGRAM_BOT_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")


class ConfigError(Exception):
    """Raised when a setting is missing or invalid. The message is shown in the logs."""


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    openai_api_key: str
    anthropic_api_key: str
    owner_telegram_id: int | None
    timezone: ZoneInfo
    database_path: Path
    claude_model: str
    enable_dashboard: bool
    # Running on Railway without a volume: the database is wiped at every redeploy.
    storage_is_temporary: bool = False


def _default_database_path(env: dict[str, str]) -> Path:
    # Railway sets RAILWAY_VOLUME_MOUNT_PATH when a volume is attached, so the
    # database survives redeploys without the user configuring anything.
    volume = env.get("RAILWAY_VOLUME_MOUNT_PATH")
    if volume:
        return Path(volume) / "majordome.db"
    return Path("data") / "majordome.db"


def load_config(env: dict[str, str] | None = None) -> Config:
    """Build a Config from `env` (defaults to the real environment)."""
    if env is None:
        env = dict(os.environ)
    # Treat "VAR=" (empty) the same as unset.
    env = {key: value.strip() for key, value in env.items() if value.strip()}

    missing = [name for name in REQUIRED if name not in env]
    if missing:
        raise ConfigError(
            "Missing required setting(s): " + ", ".join(missing)
            + ". Add them in Railway's Variables tab (or in your .env file)."
        )

    owner = env.get("OWNER_TELEGRAM_ID")
    if owner is not None:
        try:
            owner = int(owner)
        except ValueError:
            raise ConfigError(
                f"OWNER_TELEGRAM_ID must be a number (your Telegram user ID), got {owner!r}."
            ) from None

    tz_name = env.get("TIMEZONE", "Europe/Paris")
    try:
        timezone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ConfigError(
            f"Unknown TIMEZONE {tz_name!r}. Use a name like Europe/Paris or America/New_York."
        ) from None

    database_path = Path(env["DATABASE_PATH"]) if "DATABASE_PATH" in env else _default_database_path(env)

    return Config(
        telegram_bot_token=env["TELEGRAM_BOT_TOKEN"],
        openai_api_key=env["OPENAI_API_KEY"],
        anthropic_api_key=env["ANTHROPIC_API_KEY"],
        owner_telegram_id=owner,
        timezone=timezone,
        database_path=database_path,
        # Railway always sets RAILWAY_PROJECT_ID; it sets RAILWAY_VOLUME_MOUNT_PATH only
        # when a volume (permanent storage) is attached to the service.
        storage_is_temporary="RAILWAY_PROJECT_ID" in env
        and "RAILWAY_VOLUME_MOUNT_PATH" not in env
        and "DATABASE_PATH" not in env,
        claude_model=env.get("CLAUDE_MODEL", "claude-haiku-4-5"),
        enable_dashboard=env.get("ENABLE_DASHBOARD", "false").lower() in ("true", "1", "yes"),
    )
