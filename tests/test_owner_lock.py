from dataclasses import replace

from majordome.bot import check_owner
from majordome.config import load_config
from majordome.db import Database

CONFIG = load_config({"TELEGRAM_BOT_TOKEN": "t", "OPENAI_API_KEY": "o", "ANTHROPIC_API_KEY": "a"})


def test_env_owner_only():
    config = replace(CONFIG, owner_telegram_id=111)
    db = Database(":memory:")
    assert check_owner(config, db, 111, is_start=False)
    assert not check_owner(config, db, 222, is_start=True)
    assert db.get_owner_id() is None  # env owner is never written to the database


def test_first_start_claims_ownership():
    db = Database(":memory:")
    assert not check_owner(CONFIG, db, 111, is_start=False)  # a plain message doesn't claim
    assert check_owner(CONFIG, db, 111, is_start=True)
    assert check_owner(CONFIG, db, 111, is_start=False)
    assert not check_owner(CONFIG, db, 222, is_start=True)  # too late for strangers
