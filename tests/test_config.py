from pathlib import Path

import pytest

from majordome.config import ConfigError, load_config

BASE = {"TELEGRAM_BOT_TOKEN": "t", "OPENAI_API_KEY": "o", "ANTHROPIC_API_KEY": "a"}


def test_defaults():
    config = load_config(dict(BASE))
    assert config.owner_telegram_id is None
    assert config.timezone.key == "Europe/Paris"
    assert config.database_path == Path("data/majordome.db")
    assert config.claude_model == "claude-haiku-4-5"
    assert config.enable_dashboard is False


def test_missing_required_variables_are_listed():
    with pytest.raises(ConfigError, match="OPENAI_API_KEY, ANTHROPIC_API_KEY"):
        load_config({"TELEGRAM_BOT_TOKEN": "t", "OPENAI_API_KEY": "  "})


def test_empty_optional_values_mean_unset():
    config = load_config({**BASE, "OWNER_TELEGRAM_ID": "", "TIMEZONE": ""})
    assert config.owner_telegram_id is None
    assert config.timezone.key == "Europe/Paris"


def test_owner_id_must_be_a_number():
    with pytest.raises(ConfigError, match="OWNER_TELEGRAM_ID"):
        load_config({**BASE, "OWNER_TELEGRAM_ID": "@adel"})
    assert load_config({**BASE, "OWNER_TELEGRAM_ID": "123"}).owner_telegram_id == 123


def test_invalid_timezone():
    with pytest.raises(ConfigError, match="TIMEZONE"):
        load_config({**BASE, "TIMEZONE": "Mars/Olympus"})


def test_database_path_uses_railway_volume():
    config = load_config({**BASE, "RAILWAY_VOLUME_MOUNT_PATH": "/data"})
    assert config.database_path == Path("/data/majordome.db")


def test_explicit_database_path_wins():
    config = load_config({**BASE, "RAILWAY_VOLUME_MOUNT_PATH": "/data", "DATABASE_PATH": "/x/y.db"})
    assert config.database_path == Path("/x/y.db")


@pytest.mark.parametrize("value, expected", [("true", True), ("TRUE", True), ("1", True), ("false", False), ("no", False)])
def test_enable_dashboard(value, expected):
    assert load_config({**BASE, "ENABLE_DASHBOARD": value}).enable_dashboard is expected
