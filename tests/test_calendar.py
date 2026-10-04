from datetime import date, time
from zoneinfo import ZoneInfo

import pytest

from majordome.calendar_feed import CalendarError, Event, looks_like_calendar_url, parse_events

PARIS = ZoneInfo("Europe/Paris")

ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:test
BEGIN:VEVENT
UID:1
SUMMARY:Dentist
DTSTART:20261005T080000Z
DTEND:20261005T090000Z
END:VEVENT
BEGIN:VEVENT
UID:2
SUMMARY:Team meeting
DTSTART;TZID=Europe/Paris:20260928T143000
DTEND;TZID=Europe/Paris:20260928T153000
RRULE:FREQ=WEEKLY;BYDAY=MO
END:VEVENT
BEGIN:VEVENT
UID:3
SUMMARY:Mum's birthday
DTSTART;VALUE=DATE:20261005
DTEND;VALUE=DATE:20261006
END:VEVENT
BEGIN:VEVENT
UID:4
SUMMARY:Other day
DTSTART:20261006T080000Z
END:VEVENT
END:VCALENDAR
"""


def test_events_of_the_day_in_local_time():
    assert parse_events(ICS, date(2026, 10, 5), PARIS) == [
        Event("Mum's birthday", None, None),  # all day first
        Event("Dentist", time(10, 0), time(11, 0)),  # 08:00 UTC = 10:00 in Paris
        Event("Team meeting", time(14, 30), time(15, 30)),  # weekly, created a week earlier
    ]
    assert parse_events(ICS, date(2026, 10, 7), PARIS) == []


def test_invalid_calendar():
    with pytest.raises(CalendarError):
        parse_events(b"<html>Sign in</html>", date(2026, 10, 5), PARIS)


def test_recognises_calendar_links():
    assert looks_like_calendar_url("https://calendar.google.com/calendar/ical/abc%40gmail.com/private-123/basic.ics")
    assert looks_like_calendar_url("webcal://p01-caldav.icloud.com/published/2/abc")
    assert not looks_like_calendar_url("https://example.com/page")
    assert not looks_like_calendar_url("call the bank on friday")
