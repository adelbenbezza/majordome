"""Understanding messages with Claude.

Claude never touches the database. It reads the message and answers by calling one
of the "tools" described below (tool use): a structured request like
add_tasks(tasks=[{"title": "Call the bank", "due_date": "2026-10-09", ...}]).
We turn those requests into Action objects; actions.py then does the real work.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, time

import anthropic

from .db import Task

log = logging.getLogger(__name__)

LANGUAGE = {
    "type": "string",
    "enum": ["fr", "en"],
    "description": "Language the user wrote in (the main one if mixed).",
}

NULLABLE_STRING = {"anyOf": [{"type": "string"}, {"type": "null"}]}

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
        "description": "Mark open tasks as done, when the user says they did them.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "task_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Ids from the open task list.",
                },
                "language": LANGUAGE,
            },
            "required": ["task_ids", "language"],
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
]

SYSTEM_PROMPT = """You are Majordome, a personal assistant in Telegram. The user writes in French or English, sometimes mixing both. Work out what they want and call the matching tool. One message can need several tool calls.

- add_tasks: they want to do or remember something. Resolve dates and times relative to the current date and time given with the message. If no day is mentioned, due_date is null, except when a time is given: then use today, or tomorrow if that time has already passed.
- complete_tasks: they say they did something. Match it by meaning to the open tasks listed with the message, and only use ids from that list.
- list_tasks: they ask what they have to do on a day or over a period ("what's left today?", "tomorrow?", "this week?").

Recurring routines ("every Monday", "daily", "tous les mardis") aren't supported yet: don't add them as tasks, say in one sentence that routines are coming soon. A one-off task is fine ("gym next Monday").

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


@dataclass(frozen=True)
class ListTasks:
    start: date
    end: date
    language: str


@dataclass(frozen=True)
class Reply:
    """Claude answered in words instead of calling a tool."""

    text: str


Action = AddTasks | CompleteTasks | ListTasks | Reply


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
        return CompleteTasks(task_ids=[int(i) for i in data.get("task_ids", [])], language=_language(data))
    if name == "list_tasks":
        start, end = _parse_date(data.get("from_date")), _parse_date(data.get("to_date"))
        if not start or not end:
            raise BrainError("bad_answer", "list_tasks without dates")
        return ListTasks(start=min(start, end), end=max(start, end), language=_language(data))
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


def build_context(text: str, now: datetime, open_tasks: list[Task]) -> str:
    """The user turn: current time, open tasks (for matching completions) and the message."""
    lines = [f"Now: {now:%A %Y-%m-%d %H:%M} ({now.tzinfo})", "Open tasks:"]
    for task in open_tasks:
        due = f" (due {task.due_date})" if task.due_date else ""
        lines.append(f"#{task.id} {task.title}{due}")
    if not open_tasks:
        lines.append("(none)")
    lines.append(f"<message>\n{text}\n</message>")
    return "\n".join(lines)


class Brain:
    def __init__(self, api_key: str, model: str):
        # max_retries: the SDK retries rate limits, overloads and network errors itself.
        self.client = anthropic.AsyncAnthropic(api_key=api_key, timeout=30.0, max_retries=2)
        self.model = model

    async def interpret(self, text: str, now: datetime, open_tasks: list[Task]) -> list[Action]:
        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                # "auto" lets Claude answer in words when no tool fits. It also works on every
                # model: newer ones refuse forced tool use.
                tool_choice={"type": "auto"},
                messages=[{"role": "user", "content": build_context(text, now, open_tasks)}],
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
