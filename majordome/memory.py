"""Short conversation memory, so follow-ups work: "yes", "move it to Friday", "the first one".

Only the last few exchanges are kept, in memory (a restart forgets them, which is
fine), and they expire after a pause: an old conversation is more likely to confuse
than help. Only the words are kept, not the task lists sent with each message, so
requests stay small.
"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

MAX_EXCHANGES = 3
EXPIRES_AFTER = timedelta(minutes=30)
MAX_CHARS = 1500  # a long reply (a whole week's list) is cut, the start is what matters


@dataclass(frozen=True)
class Exchange:
    user: str
    bot: str
    at: datetime


class Conversation:
    def __init__(self) -> None:
        self.exchanges: deque[Exchange] = deque(maxlen=MAX_EXCHANGES)

    def add(self, user: str, bot: str, at: datetime) -> None:
        self.exchanges.append(Exchange(user[:MAX_CHARS], bot[:MAX_CHARS], at))

    def recent(self, now: datetime) -> list[tuple[str, str]]:
        """(user, bot) pairs from the current conversation, oldest first."""
        if self.exchanges and now - self.exchanges[-1].at > EXPIRES_AFTER:
            self.exchanges.clear()  # the conversation went quiet: start fresh
        return [(e.user, e.bot) for e in self.exchanges]

    def clear(self) -> None:
        self.exchanges.clear()
