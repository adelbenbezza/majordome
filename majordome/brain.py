"""Understanding messages with Claude.

Claude never touches the database. It reads the message and answers by calling one
of the "tools" described below (tool use): a structured request like
add_tasks(tasks=[{"title": "Call the bank", "due_date": "2026-10-09", ...}]).
We turn those requests into Action objects; actions.py then does the real work.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import anthropic

from .db import ListItem, Routine, SomedayItem, Task

log = logging.getLogger(__name__)

LANGUAGE = {
    "type": "string",
    "enum": ["fr", "en"],
    "description": "Language the user wrote in (the main one if mixed).",
}

NULLABLE_STRING = {"anyOf": [{"type": "string"}, {"type": "null"}]}

WEEKDAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # index = date.weekday()

# How a routine repeats (add_routine and update_routine).
REPEAT_FIELDS = {
    "unit": {"type": "string", "enum": ["week", "month"]},
    "every": {"type": "integer", "description": "Every N weeks/months; 1 = every week/month."},
    "weekdays": {
        "type": "array",
        "items": {"type": "string", "enum": WEEKDAY_NAMES},
        "description": "unit week: the days (every day = all seven). unit month: empty.",
    },
    "month_day": {
        "anyOf": [{"type": "integer"}, {"type": "null"}],
        "description": "unit month: day of the month (31 = last day). unit week: null.",
    },
    "start_date": {**NULLABLE_STRING, "description": "YYYY-MM-DD if they said when it starts, else null (today)."},
}

TOOLS = [
    {
        "name": "add_tasks",
        "description": "Add one or more tasks the user wants to do or remember.",
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
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title in the user's language, without the days or time."},
                **REPEAT_FIELDS,
                "time": {**NULLABLE_STRING, "description": "Time as HH:MM (24h), or null if none was mentioned."},
                "language": LANGUAGE,
            },
            "required": ["title", *REPEAT_FIELDS, "time", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "update_routine",
        "description": "Change an existing routine's title, days or time. Give the full new version.",
        "input_schema": {
            "type": "object",
            "properties": {
                "routine_id": {"type": "integer", "description": "Number from the routine list (r3 -> 3)."},
                "title": {"type": "string", "description": "Title, unchanged unless they asked to rename it."},
                **REPEAT_FIELDS,
                "time": {**NULLABLE_STRING, "description": "Time as HH:MM (24h), or null for no time."},
                "language": LANGUAGE,
            },
            "required": ["routine_id", "title", *REPEAT_FIELDS, "time", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "remove_routines",
        "description": "Stop routines the user no longer wants.",
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
        "name": "delete_tasks",
        "description": "Delete tasks completely (added by mistake, no longer relevant). Not for tasks they did: use complete_tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_ids": {"type": "array", "items": {"type": "integer"}, "description": "Numbers from the open task list."},
                "language": LANGUAGE,
            },
            "required": ["task_ids", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "rename_task",
        "description": "Change a task's title (e.g. a word was misheard).",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "title": {"type": "string"},
                "language": LANGUAGE,
            },
            "required": ["task_id", "title", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "undo",
        "description": "Undo the bot's last change (\"undo\", \"annule\", \"oops, not that\").",
        "input_schema": {
            "type": "object",
            "properties": {"language": LANGUAGE},
            "required": ["language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "show",
        "description": "Show the user's routines, Someday list, or notes and lists.",
        "input_schema": {
            "type": "object",
            "properties": {
                "what": {"type": "string", "enum": ["routines", "someday", "lists"]},
                "name": {
                    **NULLABLE_STRING,
                    "description": "For lists: the list to show (null = overview of all lists). For someday: a category, or null for all.",
                },
                "language": LANGUAGE,
            },
            "required": ["what", "name", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "add_someday",
        "description": "Add wishes with no date to the Someday list (books to read, things to learn, places to visit...).",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Short, in the user's language."},
                            "category": {"type": "string", "description": "Reuse an existing category if one fits; else a short new one in the user's language."},
                        },
                        "required": ["title", "category"],
                        "additionalProperties": False,
                    },
                },
                "language": LANGUAGE,
            },
            "required": ["items", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "close_someday",
        "description": "Take wishes off the Someday list: achieved (done=true) or no longer wanted (done=false).",
        "input_schema": {
            "type": "object",
            "properties": {
                "someday_ids": {"type": "array", "items": {"type": "integer"}, "description": "Numbers from the Someday list (s4 -> 4)."},
                "done": {"type": "boolean"},
                "language": LANGUAGE,
            },
            "required": ["someday_ids", "done", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "promote_someday",
        "description": "Turn a Someday wish into a dated task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "someday_id": {"type": "integer", "description": "Number from the Someday list (s4 -> 4)."},
                "due_date": {"type": "string", "description": "Day as YYYY-MM-DD."},
                "due_time": {**NULLABLE_STRING, "description": "Time as HH:MM (24h), or null."},
                "language": LANGUAGE,
            },
            "required": ["someday_id", "due_date", "due_time", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "add_to_list",
        "description": "Add items or notes to a named list (shopping list, ideas, notes...). Creates the list if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "list": {"type": "string", "description": "Reuse an existing list name if one fits."},
                "items": {"type": "array", "items": {"type": "string"}},
                "language": LANGUAGE,
            },
            "required": ["list", "items", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "check_list_items",
        "description": "Tick items off their lists (bought, done, no longer needed).",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_ids": {"type": "array", "items": {"type": "integer"}, "description": "Numbers from the lists (l12 -> 12)."},
                "language": LANGUAGE,
            },
            "required": ["item_ids", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "clear_list",
        "description": "Empty a whole list.",
        "input_schema": {
            "type": "object",
            "properties": {"list": {"type": "string"}, "language": LANGUAGE},
            "required": ["list", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "update_settings",
        "description": "Change one of the user's settings. Call it once per setting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "setting": {
                    "type": "string",
                    "enum": ["brief_time", "checkin_time", "review_time", "reminder_minutes", "timezone", "quiet_hours"],
                },
                "value": {
                    **NULLABLE_STRING,
                    "description": (
                        "brief_time / checkin_time / review_time (Sunday weekly review): HH:MM, or null to turn it off. "
                        "reminder_minutes: minutes before timed things, \"0\" = no reminders. "
                        "timezone: IANA name for where they live, e.g. America/Montreal. "
                        "quiet_hours: HH:MM-HH:MM (no reminders in between), or null to turn off."
                    ),
                },
                "language": LANGUAGE,
            },
            "required": ["setting", "value", "language"],
            "additionalProperties": False,
        },
    },
    {
        "name": "reschedule_tasks",
        "description": "Move open tasks to another day and/or time.",
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

# "strict" makes the API guarantee Claude's tool input matches the schema exactly. The API
# compiles all strict schemas into one grammar with a size limit (16 strict tools was too
# many, and 8 once routines got their repeat fields), so only the most used tools are
# strict. parse_tool_call checks every tool's input anyway.
STRICT_TOOLS = {"add_tasks", "complete_tasks", "list_tasks", "reschedule_tasks", "add_routine", "update_routine"}
TOOLS = [{**tool, "strict": tool["name"] in STRICT_TOOLS} for tool in TOOLS]

SYSTEM_PROMPT = """You are Majordome, a personal assistant in Telegram. The user writes in French or English, sometimes mixing both. Work out what they want and call the matching tool. One message can need several tool calls.

- add_tasks: they want to do or remember something. Resolve dates and times relative to the current date and time given with the message. If no day is mentioned, due_date is null, except when a time is given: then use today, or tomorrow if that time has already passed.
- complete_tasks: they say they did something. Match it by meaning to the open tasks and routines listed with the message, and only use numbers from those lists.
- add_routine: something that repeats ("gym every Monday and Tuesday at 6pm", "supplements every day", "tous les mardis", "cleaning every other Friday", "rent on the 1st of each month", "dentist every 6 months"). Never add a repeating thing as tasks.
- update_routine: change an existing routine's days, time or title (keep whatever they didn't mention).
- remove_routines: they want to stop a routine.
- add_someday: the Someday list (called « Un jour » in French) holds wishes with no date or deadline ("I'd like to learn guitar one day", "livre à lire : Dune"). close_someday when one is achieved or dropped, promote_someday to plan it on a day.
- add_to_list: shopping items, ideas, notes to keep ("note : ...", "add milk"). Notes and ideas go in a list such as "Notes" or "Idées". check_list_items when bought or done, clear_list to empty a list.
- show: their routines (with their streaks: use it for any streak question), Someday list, or lists and notes.
- delete_tasks / rename_task: remove a task added by mistake, or fix its title. undo: reverse the bot's last change ("annule", "undo that").
- reschedule_tasks: move existing tasks to another day or time ("move the bank to Friday").
- update_settings: morning brief time (their day's list), evening check-in time (what's left), Sunday weekly review time, how long before timed things to remind them, their timezone (where they live: "I'm in Montreal now"), quiet hours (no reminders at night). In French, « plus de brief / de rappels / d'heures calmes » means turning it off.
- list_tasks: they ask what they have to do on a day or over a period ("what's left today?", "tomorrow?", "this week?").

The recent conversation may come first, for context only: use it to understand follow-ups ("yes", "the second one", "move it to Friday"), but only act on the new <message>.

A message marked as an uncertain voice transcription may contain misheard words. If it doesn't clearly make sense, don't act: say in one sentence what you understood and ask them to confirm or repeat.

Changes only happen through tools: never say you added, changed, deleted or undid something without calling the tool that does it. "Annule" / "undo" always means calling undo.

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
    unit: str = "week"
    every: int = 1
    month_day: int | None = None
    start_date: date | None = None


@dataclass(frozen=True)
class UpdateRoutine:
    routine_id: int
    title: str
    weekdays: list[int]
    time: time | None
    language: str
    unit: str = "week"
    every: int = 1
    month_day: int | None = None
    start_date: date | None = None


@dataclass(frozen=True)
class RemoveRoutines:
    routine_ids: list[int]
    language: str


@dataclass(frozen=True)
class DeleteTasks:
    task_ids: list[int]
    language: str


@dataclass(frozen=True)
class RenameTask:
    task_id: int
    title: str
    language: str


@dataclass(frozen=True)
class Undo:
    language: str


@dataclass(frozen=True)
class Show:
    what: str  # "routines", "someday" or "lists"
    name: str | None  # a list name, or a Someday category
    language: str


@dataclass(frozen=True)
class NewSomeday:
    title: str
    category: str


@dataclass(frozen=True)
class AddSomeday:
    items: list[NewSomeday]
    language: str


@dataclass(frozen=True)
class CloseSomeday:
    someday_ids: list[int]
    done: bool
    language: str


@dataclass(frozen=True)
class PromoteSomeday:
    someday_id: int
    due_date: date
    due_time: time | None
    language: str


@dataclass(frozen=True)
class AddToList:
    list: str
    items: list[str]
    language: str


@dataclass(frozen=True)
class CheckListItems:
    item_ids: list[int]
    language: str


@dataclass(frozen=True)
class ClearList:
    list: str
    language: str


@dataclass(frozen=True)
class ListTasks:
    start: date
    end: date
    language: str


@dataclass(frozen=True)
class UpdateSetting:
    setting: str  # see SETTINGS
    # brief_time / checkin_time: time or None (off); reminder_minutes: int (0 = off);
    # timezone: ZoneInfo; quiet_hours: (start, end) times or None (off)
    value: object
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


Action = AddTasks | CompleteTasks | ListTasks | AddRoutine | UpdateRoutine | RemoveRoutines | DeleteTasks | RenameTask | Undo | Show | AddSomeday | CloseSomeday | PromoteSomeday | AddToList | CheckListItems | ClearList | RescheduleTasks | UpdateSetting | Reply


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


def _list(value) -> list:
    """A list from Claude. Refuses a bare string, which Python would read letter by letter."""
    if not isinstance(value, list):
        raise TypeError(f"expected a list, got {value!r}")
    return value


def _ids(value) -> list[int]:
    """A list of item numbers. Refuses a bare string, which would be read digit by digit."""
    if not isinstance(value, list):
        raise TypeError(f"expected a list of numbers, got {value!r}")
    return [int(i) for i in value]


def _setting_value(setting: str, value: str | None) -> object:
    """Check and convert a settings value sent by Claude (see the update_settings tool)."""
    value = value.strip() if isinstance(value, str) else None
    if setting in ("brief_time", "checkin_time", "review_time"):
        return _parse_time(value)
    if setting == "reminder_minutes":
        return max(0, int(value or 0))
    if setting == "timezone":
        try:
            return ZoneInfo(value or "")
        except (ZoneInfoNotFoundError, ValueError):
            raise BrainError("bad_answer", f"unknown timezone {value!r}") from None
    if setting == "quiet_hours":
        if not value:
            return None
        start, end = value.split("-")
        return _parse_time(start.strip()), _parse_time(end.strip())
    raise BrainError("bad_answer", f"unknown setting {setting!r}")


def _language(data: dict) -> str:
    return "fr" if data.get("language") == "fr" else "en"


def parse_tool_call(name: str, data: dict) -> Action:
    """Turn one tool call from Claude into an Action, checking every field."""
    try:
        return _parse_tool_call(name, data)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        # A missing field or a wrong type (possible on non-strict tools).
        raise BrainError("bad_answer", f"{name}: {error!r}") from None


def _parse_tool_call(name: str, data: dict) -> Action:
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
            task_ids=_ids(data.get("task_ids", [])),
            routine_ids=_ids(data.get("routine_ids", [])),
            language=_language(data),
        )
    if name in ("add_routine", "update_routine"):
        title = str(data.get("title", "")).strip()
        unit = data.get("unit") or "week"
        every = max(1, int(data.get("every") or 1))
        weekdays = sorted({WEEKDAY_NAMES.index(d) for d in data.get("weekdays", []) if d in WEEKDAY_NAMES})
        month_day = data.get("month_day")
        if unit == "month":
            weekdays = []
            if month_day is None or not 1 <= int(month_day) <= 31:
                raise BrainError("bad_answer", f"{name}: monthly without a valid day")
            month_day = int(month_day)
        elif unit == "week":
            month_day = None
            if not weekdays:
                raise BrainError("bad_answer", f"{name}: weekly without days")
        else:
            raise BrainError("bad_answer", f"{name}: unknown unit {unit!r}")
        if not title:
            raise BrainError("bad_answer", f"{name} without a title")
        fields = dict(
            title=title,
            weekdays=weekdays,
            time=_parse_time(data.get("time")),
            language=_language(data),
            unit=unit,
            every=every,
            month_day=month_day,
            start_date=_parse_date(data.get("start_date")),
        )
        if name == "add_routine":
            return AddRoutine(**fields)
        return UpdateRoutine(routine_id=int(data["routine_id"]), **fields)
    if name == "remove_routines":
        return RemoveRoutines(routine_ids=_ids(data.get("routine_ids", [])), language=_language(data))
    if name == "delete_tasks":
        return DeleteTasks(_ids(data.get("task_ids", [])), _language(data))
    if name == "rename_task":
        title = str(data["title"]).strip()
        if not title:
            raise BrainError("bad_answer", "rename_task without a title")
        return RenameTask(int(data["task_id"]), title, _language(data))
    if name == "undo":
        return Undo(_language(data))
    if name == "show":
        if data.get("what") not in ("routines", "someday", "lists"):
            raise BrainError("bad_answer", "show with unknown what")
        return Show(what=data["what"], name=(data.get("name") or "").strip() or None, language=_language(data))
    if name == "add_someday":
        items = [
            NewSomeday(str(i["title"]).strip(), str(i.get("category") or "").strip() or "?")
            for i in _list(data.get("items", []))
            if str(i.get("title", "")).strip()
        ]
        if not items:
            raise BrainError("bad_answer", "add_someday without items")
        return AddSomeday(items=items, language=_language(data))
    if name == "close_someday":
        return CloseSomeday(_ids(data.get("someday_ids", [])), bool(data.get("done")), _language(data))
    if name == "promote_someday":
        due_date = _parse_date(data.get("due_date"))
        if due_date is None:
            raise BrainError("bad_answer", "promote_someday without a day")
        return PromoteSomeday(int(data["someday_id"]), due_date, _parse_time(data.get("due_time")), _language(data))
    if name == "add_to_list":
        list_name = str(data.get("list", "")).strip()
        items = [str(i).strip() for i in _list(data.get("items", [])) if str(i).strip()]
        if not list_name or not items:
            raise BrainError("bad_answer", "add_to_list without list or items")
        return AddToList(list=list_name, items=items, language=_language(data))
    if name == "check_list_items":
        return CheckListItems(_ids(data.get("item_ids", [])), _language(data))
    if name == "clear_list":
        list_name = str(data.get("list", "")).strip()
        if not list_name:
            raise BrainError("bad_answer", "clear_list without a list")
        return ClearList(list=list_name, language=_language(data))
    if name == "list_tasks":
        start, end = _parse_date(data.get("from_date")), _parse_date(data.get("to_date"))
        if not start or not end:
            raise BrainError("bad_answer", "list_tasks without dates")
        return ListTasks(start=min(start, end), end=max(start, end), language=_language(data))
    if name == "update_settings":
        return UpdateSetting(data["setting"], _setting_value(data["setting"], data.get("value")), _language(data))
    if name == "reschedule_tasks":
        due_date = _parse_date(data.get("due_date"))
        if due_date is None:
            raise BrainError("bad_answer", "reschedule_tasks without a day")
        return RescheduleTasks(
            task_ids=_ids(data.get("task_ids", [])),
            due_date=due_date,
            due_time=_parse_time(data.get("due_time")),
            language=_language(data),
        )
    raise BrainError("bad_answer", f"unknown tool {name!r}")


# Every confirmation the bot writes after a change starts with one of these (see actions.py).
# If Claude answers in words but starts like a confirmation, it's imitating one from the
# conversation without having changed anything: we must not pass that on.
CONFIRMATION_MARKS = ("📝", "✅", "✓", "🗑", "↩", "✏", "🔁", "📅", "✨", "🎉", "➡", "🧹", "⏰", "🔕", "🔔", "🌍", "🌙", "☀", "🗓")


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
    if text.startswith(CONFIRMATION_MARKS):
        raise BrainError("fake_confirmation", text[:100])
    return [Reply(text)]


@dataclass
class Snapshot:
    """What Claude needs to see to understand a message: the user's current things.

    Only open items are sent (not history) to keep requests short and cheap.
    """

    open_tasks: list[Task] = field(default_factory=list)
    routines: list[tuple[Routine, bool]] = field(default_factory=list)  # (routine, done today?)
    someday: list[SomedayItem] = field(default_factory=list)
    list_items: list[ListItem] = field(default_factory=list)
    list_names: list[str] = field(default_factory=list)


def describe_repeat(routine: Routine) -> str:
    """The routine's schedule in plain English, for Claude ("every 2 weeks on fri")."""
    since = f" from {routine.start_date}" if routine.start_date and routine.every > 1 else ""
    if routine.unit == "month":
        every = "every month" if routine.every == 1 else f"every {routine.every} months"
        return f"day {routine.month_day} of {every}{since}"
    if routine.daily:
        return "every day"
    days = ", ".join(WEEKDAY_NAMES[d] for d in routine.weekdays)
    return days if routine.every == 1 else f"every {routine.every} weeks on {days}{since}"


def build_context(text: str, now: datetime, snapshot: Snapshot, uncertain: bool = False) -> str:
    """The user turn: current time, the user's open things (to match by number), then the message."""
    lines = [f"Now: {now:%A %Y-%m-%d %H:%M} ({now.tzinfo})", "Open tasks:"]
    for task in snapshot.open_tasks:
        due = f" (due {task.due_date})" if task.due_date else ""
        lines.append(f"#{task.id} {task.title}{due}")
    if not snapshot.open_tasks:
        lines.append("(none)")
    lines.append("Routines:")
    for routine, done_today in snapshot.routines:
        days = describe_repeat(routine)
        at = f" at {routine.time:%H:%M}" if routine.time else ""
        status = "done today" if done_today else "not done today"
        lines.append(f"r{routine.id} {routine.title} ({days}{at}; {status})")
    if not snapshot.routines:
        lines.append("(none)")
    lines.append("Someday list:")
    for item in snapshot.someday:
        lines.append(f"s{item.id} {item.title} [{item.category}]")
    if not snapshot.someday:
        lines.append("(none)")
    lines.append("Lists: " + (", ".join(snapshot.list_names) or "(none)"))
    for item in snapshot.list_items:
        lines.append(f"l{item.id} {item.text} [{item.list_name}]")
    if uncertain:
        lines.append("(Uncertain voice transcription: some words may be misheard.)")
    lines.append(f"<message>\n{text}\n</message>")
    return "\n".join(lines)


def build_messages(
    text: str, now: datetime, snapshot: Snapshot, history: list[tuple[str, str]], uncertain: bool = False
) -> list[dict]:
    """One user message: the recent conversation as a transcript, then the state and new message.

    The history is a labelled transcript rather than earlier assistant turns: given its
    "own" past confirmations, Claude tended to imitate them in words instead of calling tools.
    """
    context = build_context(text, now, snapshot, uncertain)
    if history:
        transcript = "\n".join(f"User: {user}\nBot: {bot}" for user, bot in history)
        context = f"<recent_conversation>\n{transcript}\n</recent_conversation>\n{context}"
    return [{"role": "user", "content": context}]


class Brain:
    def __init__(self, api_key: str, model: str, on_usage=None):
        """`on_usage(model, input_tokens, output_tokens)` is called after each request (for /usage)."""
        # max_retries: the SDK retries rate limits, overloads and network errors itself.
        self.client = anthropic.AsyncAnthropic(api_key=api_key, timeout=30.0, max_retries=2)
        self.model = model
        self.on_usage = on_usage

    async def interpret(
        self,
        text: str,
        now: datetime,
        snapshot: Snapshot,
        history: list[tuple[str, str]] = (),
        uncertain: bool = False,
    ) -> list[Action]:
        """`history`: the recent (user, bot) exchanges, so follow-ups like "yes" make sense.
        `uncertain`: the text is a voice transcription that may contain misheard words."""
        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                # "auto" lets Claude answer in words when no tool fits. It also works on every
                # model: newer ones refuse forced tool use.
                tool_choice={"type": "auto"},
                messages=build_messages(text, now, snapshot, history, uncertain),
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
        if self.on_usage:
            self.on_usage(self.model, message.usage.input_tokens, message.usage.output_tokens)
        return parse_response(message)
