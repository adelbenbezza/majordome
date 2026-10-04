"""Today's events from the owner's calendar, for the morning brief.

We read the calendar's secret iCal address (Google Calendar: Settings > your calendar >
"Secret address in iCal format"). It's a read-only link, so there's no Google Cloud
project or sign-in screen to set up: the owner just pastes it with /calendar. It works
with any calendar app that offers an iCal link (Apple, Outlook, Proton...).
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
import icalendar
import recurring_ical_events

log = logging.getLogger(__name__)


class CalendarError(Exception):
    """The calendar couldn't be downloaded or read."""


@dataclass(frozen=True)
class Event:
    title: str
    start: time | None  # None = all-day event
    end: time | None


def looks_like_calendar_url(text: str) -> bool:
    text = text.strip()
    if " " in text:
        return False
    return text.startswith("webcal://") or (text.startswith("https://") and (".ics" in text or "/ical/" in text))


def parse_events(ics: bytes, day: date, tz: ZoneInfo) -> list[Event]:
    """Events happening on `day` (in timezone `tz`), recurring ones included, sorted by time."""
    try:
        calendar = icalendar.Calendar.from_ical(ics)
    except ValueError as error:
        raise CalendarError(f"not a valid calendar: {error}") from error
    start = datetime.combine(day, time.min, tzinfo=tz)
    events = []
    for component in recurring_ical_events.of(calendar).between(start, start + timedelta(days=1)):
        title = str(component.get("SUMMARY", "")).strip() or "?"
        begin = component.decoded("DTSTART")
        finish = component.decoded("DTEND") if "DTEND" in component else None
        if isinstance(begin, datetime):
            begin_local = begin.astimezone(tz) if begin.tzinfo else begin.replace(tzinfo=tz)
            end_local = None
            if isinstance(finish, datetime):
                end_local = (finish.astimezone(tz) if finish.tzinfo else finish.replace(tzinfo=tz)).time()
            events.append(Event(title, begin_local.time(), end_local))
        else:
            events.append(Event(title, None, None))  # a date without time: all day
    return sorted(events, key=lambda e: (e.start is not None, e.start or time.min))


async def fetch_events(url: str, day: date, tz: ZoneInfo) -> list[Event]:
    url = "https://" + url.removeprefix("webcal://") if url.startswith("webcal://") else url
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise CalendarError(f"download failed: {error.__class__.__name__}") from error
    return parse_events(response.content, day, tz)
