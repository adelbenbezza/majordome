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
