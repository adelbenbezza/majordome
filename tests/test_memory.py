import re
from datetime import datetime, timedelta, timezone

from majordome.brain import Snapshot, build_messages
from majordome.memory import MAX_EXCHANGES, Conversation

T0 = datetime(2026, 10, 4, 18, 0, tzinfo=timezone.utc)


def test_keeps_the_last_exchanges_and_forgets_after_a_pause():
    conversation = Conversation()
    for i in range(MAX_EXCHANGES + 2):
        conversation.add(f"msg {i}", f"reply {i}", T0 + timedelta(minutes=i))
    recent = conversation.recent(T0 + timedelta(minutes=10))
    assert len(recent) == MAX_EXCHANGES and recent[-1] == ("msg 4", "reply 4")
    assert conversation.recent(T0 + timedelta(hours=2)) == []  # went quiet: forgotten


def test_history_comes_before_the_new_message():
    messages = build_messages("le premier", T0, Snapshot(), [("appelle Paul", "Paul Martin ou Paul Durand ?")])
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[1]["content"] == "Paul Martin ou Paul Durand ?"
    assert messages[2]["content"].endswith("<message>\nle premier\n</message>")


def test_command_menu_fits_telegram_rules():
    from majordome.bot import COMMANDS

    for name, english, french in COMMANDS:
        assert re.fullmatch(r"[a-z0-9_]{1,32}", name)
        assert 3 <= len(english) <= 256 and 3 <= len(french) <= 256
