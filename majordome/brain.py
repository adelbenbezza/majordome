"""Understanding messages with Claude.

Claude never touches the database. It reads the message and answers by calling one
of the "tools" described below (tool use): a structured request like
add_tasks(tasks=[{"title": "Call the bank", "due_date": "2026-10-09", ...}]).
We turn those requests into Action objects; actions.py then does the real work.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time

import anthropic

from .db import Routine, Task

log = logging.getLogger(__name__)

LANGUAGE = {
    "type": "string",
    "enum": ["fr", "en"],
    "description": "Language the user wrote in (the main one if mixed).",
}

NULLABLE_STRING = {"anyOf": [{"type": "string"}, {"type": "null"}]}

WEEKDAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # index = date.weekday()

TOOLS = [
    {
        "name": "add_tasks",
        "description": "Add one or more tasks the user wants to do or remember.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Short task title in the user's language, without the date or time.",
                            },
                            "due_date": {
                                **NULLABLE_STRING,
                                "description": "Day as YYYY-MM-DD, or null if no day was mentioned.",
                            },
                            "due_time": {
                                **NULLABLE_STRING,
                                "description": "Time as HH:MM (24h), or null if no time was mentioned.",
                            },
                        },
                        "required": ["title", "due_date", "due_time"],
                        "additionalProperties": False,
                    },
                },
                "language": LANGUAGE,
            },
            "required": ["tasks", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "complete_tasks",
        "description": "Mark open tasks and/or today's routines as done, when the user says they did them.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "task_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Numbers from the open task list (#12 -> 12).",
                },
                "routine_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Numbers from the routine list (r3 -> 3).",
                },
                "language": LANGUAGE,
            },
            "required": ["task_ids", "routine_ids", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_tasks",
        "description": "Show the tasks for a day or a period (today, tomorrow, Friday, this week...).",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "First day, YYYY-MM-DD."},
                "to_date": {"type": "string", "description": "Last day, YYYY-MM-DD. Same as from_date for a single day."},
                "language": LANGUAGE,
            },
            "required": ["from_date", "to_date", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "add_routine",
        "description": "Add a recurring routine: something done on given weekdays, every week.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title in the user's language, without the days or time."},
                "weekdays": {
                    "type": "array",
                    "items": {"type": "string", "enum": WEEKDAY_NAMES},
                    "description": "Days it happens on. Every day = all seven.",
                },
                "time": {**NULLABLE_STRING, "description": "Time as HH:MM (24h), or null if none was mentioned."},
                "language": LANGUAGE,
            },
            "required": ["title", "weekdays", "time", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "update_routine",
        "description": "Change an existing routine's title, days or time. Give the full new version.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "routine_id": {"type": "integer", "description": "Number from the routine list (r3 -> 3)."},
                "title": {"type": "string", "description": "Title, unchanged unless they asked to rename it."},
                "weekdays": {"type": "array", "items": {"type": "string", "enum": WEEKDAY_NAMES}},
                "time": {**NULLABLE_STRING, "description": "Time as HH:MM (24h), or null for no time."},
                "language": LANGUAGE,
            },
            "required": ["routine_id", "title", "weekdays", "time", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "remove_routines",
        "description": "Stop routines the user no longer wants.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "routine_ids": {"type": "array", "items": {"type": "integer"}, "description": "Numbers from the routine list (r3 -> 3)."},
                "language": LANGUAGE,
            },
            "required": ["routine_ids", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_routines",
        "description": "Show all the user's routines.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"language": LANGUAGE},
            "required": ["language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "set_daily_time",
        "description": "Change the time of a daily message (morning brief or evening check-in), or turn it off.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "enum": ["brief", "checkin"]},
                "time": {**NULLABLE_STRING, "description": "New time as HH:MM (24h), or null to turn it off."},
                "language": LANGUAGE,
            },
            "required": ["message", "time", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "set_reminders",
        "description": "Change how long before a timed task or routine the reminder comes, or turn reminders off.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "minutes_before": {"type": "integer", "description": "Minutes before; 0 turns reminders off."},
                "language": LANGUAGE,
            },
            "required": ["minutes_before", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "reschedule_tasks",
        "description": "Move open tasks to another day and/or time.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "task_ids": {"type": "array", "items": {"type": "integer"}, "description": "Numbers from the open task list."},
                "due_date": {"type": "string", "description": "New day as YYYY-MM-DD."},
                "due_time": {**NULLABLE_STRING, "description": "New time as HH:MM (24h), or null to keep the current time."},
                "language": LANGUAGE,
            },
            "required": ["task_ids", "due_date", "due_time", "language"],
            "additionalProperties": False,
        },
    },
]

SYSTEM_PROMPT = """You are Majordome, a personal assistant in Telegram. The user writes in French or English, sometimes mixing both. Work out what they want and call the matching tool. One message can need several tool calls.

- add_tasks: they want to do or remember something. Resolve dates and times relative to the current date and time given with the message. If no day is mentioned, due_date is null, except when a time is given: then use today, or tomorrow if that time has already passed.
- complete_tasks: they say they did something. Match it by meaning to the open tasks and routines listed with the message, and only use numbers from those lists.
- add_routine: something that repeats every week ("gym every Monday and Tuesday at 6pm", "supplements every day", "tous les mardis"). Never add a repeating thing as tasks.
- update_routine: change an existing routine's days, time or title (keep whatever they didn't mention).
- remove_routines / list_routines: they want to stop a routine, or see their routines.
- reschedule_tasks: move existing tasks to another day or time ("move the bank to Friday").
- set_daily_time: they want the morning brief (their day's list) or the evening check-in (what's left, in the evening) at another time, or not at all.
- set_reminders: they want reminders earlier or later before timed things, or none.
- list_tasks: they ask what they have to do on a day or over a period ("what's left today?", "tomorrow?", "this week?").

If no tool fits, a completion matches no open task, or the request is too unclear, call no tool and reply in one or two short sentences, in the user's language."""


@dataclass(frozen=True)
class NewTask:
    title: str
    due_date: date | None
    due_time: time | None


@dataclass(frozen=True)
class AddTasks:
    tasks: list[NewTask]
    language: str


@dataclass(frozen=True)
class CompleteTasks:
    task_ids: list[int]
    language: str
    routine_ids: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class AddRoutine:
    title: str
    weekdays: list[int]  # Monday = 0
    time: time | None
    language: str


@dataclass(frozen=True)
class UpdateRoutine:
    routine_id: int
    title: str
    weekdays: list[int]
    time: time | None
    language: str


@dataclass(frozen=True)
class RemoveRoutines:
    routine_ids: list[int]
    language: str


@dataclass(frozen=True)
class ListRoutines:
    language: str


@dataclass(frozen=True)
class ListTasks:
    start: date
    end: date
    language: str


@dataclass(frozen=True)
class SetDailyTime:
    message: str  # "brief" or "checkin"
    time: time | None  # None = turned off
    language: str


@dataclass(frozen=True)
class SetReminders:
    minutes_before: int  # 0 = off
    language: str


@dataclass(frozen=True)
class RescheduleTasks:
    task_ids: list[int]
    due_date: date
    due_time: time | None  # None = keep the current time
    language: str


@dataclass(frozen=True)
class Reply:
    """Claude answered in words instead of calling a tool."""

    text: str


Action = AddTasks | CompleteTasks | ListTasks | AddRoutine | UpdateRoutine | RemoveRoutines | ListRoutines | RescheduleTasks | SetDailyTime | SetReminders | Reply


class BrainError(Exception):
    """Claude couldn't be reached or gave an unusable answer. `kind` picks the message shown."""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind = kind


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise BrainError("bad_answer", f"invalid date {value!r}") from None


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        raise BrainError("bad_answer", f"invalid time {value!r}") from None


def _language(data: dict) -> str:
    return "fr" if data.get("language") == "fr" else "en"


def parse_tool_call(name: str, data: dict) -> Action:
    """Turn one tool call from Claude into an Action, checking every field."""
    if name == "add_tasks":
        tasks = [
            NewTask(
                title=str(item["title"]).strip(),
                due_date=_parse_date(item.get("due_date")),
                due_time=_parse_time(item.get("due_time")),
            )
            for item in data.get("tasks", [])
            if str(item.get("title", "")).strip()
        ]
        if not tasks:
            raise BrainError("bad_answer", "add_tasks without tasks")
        return AddTasks(tasks=tasks, language=_language(data))
    if name == "complete_tasks":
        return CompleteTasks(
            task_ids=[int(i) for i in data.get("task_ids", [])],
            routine_ids=[int(i) for i in data.get("routine_ids", [])],
            language=_language(data),
        )
    if name in ("add_routine", "update_routine"):
        title = str(data.get("title", "")).strip()
        weekdays = sorted({WEEKDAY_NAMES.index(d) for d in data.get("weekdays", []) if d in WEEKDAY_NAMES})
        if not title or not weekdays:
            raise BrainError("bad_answer", f"{name} without title or days")
        at, language = _parse_time(data.get("time")), _language(data)
        if name == "add_routine":
            return AddRoutine(title=title, weekdays=weekdays, time=at, language=language)
        return UpdateRoutine(routine_id=int(data["routine_id"]), title=title, weekdays=weekdays, time=at, language=language)
    if name == "remove_routines":
        return RemoveRoutines(routine_ids=[int(i) for i in data.get("routine_ids", [])], language=_language(data))
    if name == "list_routines":
        return ListRoutines(language=_language(data))
    if name == "list_tasks":
        start, end = _parse_date(data.get("from_date")), _parse_date(data.get("to_date"))
        if not start or not end:
            raise BrainError("bad_answer", "list_tasks without dates")
        return ListTasks(start=min(start, end), end=max(start, end), language=_language(data))
    if name == "set_daily_time":
        if data.get("message") not in ("brief", "checkin"):
            raise BrainError("bad_answer", "set_daily_time with unknown message")
        return SetDailyTime(message=data["message"], time=_parse_time(data.get("time")), language=_language(data))
    if name == "set_reminders":
        return SetReminders(minutes_before=max(0, int(data["minutes_before"])), language=_language(data))
    if name == "reschedule_tasks":
        due_date = _parse_date(data.get("due_date"))
        if due_date is None:
            raise BrainError("bad_answer", "reschedule_tasks without a day")
        return RescheduleTasks(
            task_ids=[int(i) for i in data.get("task_ids", [])],
            due_date=due_date,
            due_time=_parse_time(data.get("due_time")),
            language=_language(data),
        )
    raise BrainError("bad_answer", f"unknown tool {name!r}")


def parse_response(message) -> list[Action]:
    """Turn Claude's whole answer into a list of Actions."""
    if message.stop_reason == "refusal":
        raise BrainError("refused")
    if message.stop_reason == "max_tokens":
        raise BrainError("bad_answer", "answer was cut off")
    tool_calls = [block for block in message.content if block.type == "tool_use"]
    if tool_calls:
        # Any text next to tool calls is commentary; our own confirmations replace it.
        return [parse_tool_call(block.name, block.input) for block in tool_calls]
    text = " ".join(block.text for block in message.content if block.type == "text").strip()
    if not text:
        raise BrainError("bad_answer", "empty answer")
    return [Reply(text)]


def build_context(text: str, now: datetime, open_tasks: list[Task], routines: list[tuple[Routine, bool]]) -> str:
    """The user turn: current time, open tasks and routines (to match completions), then the message.

    `routines`: each active routine with whether it's already done today.
    """
    lines = [f"Now: {now:%A %Y-%m-%d %H:%M} ({now.tzinfo})", "Open tasks:"]
    for task in open_tasks:
        due = f" (due {task.due_date})" if task.due_date else ""
        lines.append(f"#{task.id} {task.title}{due}")
    if not open_tasks:
        lines.append("(none)")
    lines.append("Routines:")
    for routine, done_today in routines:
        days = "every day" if routine.daily else ", ".join(WEEKDAY_NAMES[d] for d in routine.weekdays)
        at = f" at {routine.time:%H:%M}" if routine.time else ""
        status = "done today" if done_today else "not done today"
        lines.append(f"r{routine.id} {routine.title} ({days}{at}; {status})")
    if not routines:
        lines.append("(none)")
    lines.append(f"<message>\n{text}\n</message>")
    return "\n".join(lines)


class Brain:
    def __init__(self, api_key: str, model: str):
        # max_retries: the SDK retries rate limits, overloads and network errors itself.
        self.client = anthropic.AsyncAnthropic(api_key=api_key, timeout=30.0, max_retries=2)
        self.model = model

    async def interpret(
        self, text: str, now: datetime, open_tasks: list[Task], routines: list[tuple[Routine, bool]] = ()
    ) -> list[Action]:
        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                # "auto" lets Claude answer in words when no tool fits. It also works on every
                # model: newer ones refuse forced tool use.
                tool_choice={"type": "auto"},
                messages=[{"role": "user", "content": build_context(text, now, open_tasks, list(routines))}],
            )
        except anthropic.AuthenticationError as error:
            raise BrainError("auth", str(error)) from error
        except anthropic.RateLimitError as error:
            raise BrainError("busy", str(error)) from error
        except anthropic.BadRequestError as error:
            # An empty credit balance comes back as a "bad request".
            kind = "no_credit" if "credit balance" in str(error).lower() else "other"
            raise BrainError(kind, str(error)) from error
        except anthropic.APIStatusError as error:
            kind = "busy" if error.status_code >= 500 else "other"
            raise BrainError(kind, str(error)) from error
        except anthropic.APIConnectionError as error:  # includes timeouts
            raise BrainError("network", str(error)) from error
        log.info("Claude usage: %s in / %s out tokens", message.usage.input_tokens, message.usage.output_tokens)
        return parse_response(message)
