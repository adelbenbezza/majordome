from datetime import date, time
from types import SimpleNamespace

import pytest

from majordome.brain import AddSomeday, AddToList, CheckListItems, ClearList, CloseSomeday, NewSomeday, PromoteSomeday, Show, Snapshot, build_context, AddRoutine, AddTasks, RemoveRoutines, UpdateRoutine, BrainError, CompleteTasks, ListTasks, NewTask, Reply, RescheduleTasks, SetDailyTime, SetReminders, parse_response


def answer(*blocks, stop_reason="tool_use"):
    """A fake Claude response with the same shape as the SDK's Message."""
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks))


def tool(name, data):
    return SimpleNamespace(type="tool_use", name=name, input=data)


def text(value):
    return SimpleNamespace(type="text", text=value)


def test_add_tasks_with_date_and_time():
    message = answer(
        text("Sure!"),  # commentary next to a tool call is ignored
        tool("add_tasks", {
            "tasks": [
                {"title": "Appeler la banque", "due_date": "2026-10-09", "due_time": "15:00"},
                {"title": "Buy milk", "due_date": None, "due_time": None},
            ],
            "language": "fr",
        }),
    )
    assert parse_response(message) == [
        AddTasks(
            tasks=[
                NewTask("Appeler la banque", date(2026, 10, 9), time(15, 0)),
                NewTask("Buy milk", None, None),
            ],
            language="fr",
        )
    ]


def test_several_tool_calls():
    message = answer(
        tool("complete_tasks", {"task_ids": [3], "language": "en"}),
        tool("list_tasks", {"from_date": "2026-10-05", "to_date": "2026-10-05", "language": "en"}),
    )
    assert parse_response(message) == [CompleteTasks([3], "en"), ListTasks(date(2026, 10, 5), date(2026, 10, 5), "en")]


def test_list_tasks_dates_in_wrong_order_are_swapped():
    message = answer(tool("list_tasks", {"from_date": "2026-10-11", "to_date": "2026-10-05", "language": "fr"}))
    assert parse_response(message) == [ListTasks(date(2026, 10, 5), date(2026, 10, 11), "fr")]


def test_text_only_is_a_reply():
    assert parse_response(answer(text("Bonjour !"), stop_reason="end_turn")) == [Reply("Bonjour !")]


@pytest.mark.parametrize("data", [
    {"tasks": [{"title": "X", "due_date": "next friday", "due_time": None}], "language": "en"},
    {"tasks": [{"title": "X", "due_date": None, "due_time": "3pm"}], "language": "en"},
    {"tasks": [{"title": "  ", "due_date": None, "due_time": None}], "language": "en"},
])
def test_invalid_add_tasks(data):
    with pytest.raises(BrainError):
        parse_response(answer(tool("add_tasks", data)))


@pytest.mark.parametrize("message", [
    answer(stop_reason="end_turn"),  # empty
    answer(tool("delete_everything", {}), stop_reason="tool_use"),  # unknown tool
    answer(text("..."), stop_reason="refusal"),
    answer(tool("list_tasks", {"from_date": "2026-10-05", "to_date": "x", "language": "en"})),  # bad date
    answer(tool("list_tasks", {"from_date": "2026-10-05", "to_date": "2026-10-05", "language": "en"}), stop_reason="max_tokens"),  # cut off
])
def test_unusable_answers(message):
    with pytest.raises(BrainError):
        parse_response(message)


def test_settings_and_reschedule_tools():
    message = answer(
        tool("set_daily_time", {"message": "brief", "time": "07:30", "language": "fr"}),
        tool("set_daily_time", {"message": "checkin", "time": None, "language": "fr"}),
        tool("set_reminders", {"minutes_before": 15, "language": "en"}),
        tool("reschedule_tasks", {"task_ids": [4], "due_date": "2026-10-09", "due_time": None, "language": "en"}),
    )
    assert parse_response(message) == [
        SetDailyTime("brief", time(7, 30), "fr"),
        SetDailyTime("checkin", None, "fr"),
        SetReminders(15, "en"),
        RescheduleTasks([4], date(2026, 10, 9), None, "en"),
    ]


def test_routine_tools():
    message = answer(
        tool("add_routine", {"title": "Gym", "weekdays": ["tue", "mon"], "time": "18:00", "language": "fr"}),
        tool("complete_tasks", {"task_ids": [], "routine_ids": [2], "language": "fr"}),
        tool("update_routine", {"routine_id": 1, "title": "Gym", "weekdays": ["mon"], "time": None, "language": "fr"}),
        tool("remove_routines", {"routine_ids": [4], "language": "fr"}),
        tool("show", {"what": "routines", "name": None, "language": "en"}),
    )
    assert parse_response(message) == [
        AddRoutine("Gym", [0, 1], time(18, 0), "fr"),
        CompleteTasks([], "fr", routine_ids=[2]),
        UpdateRoutine(1, "Gym", [0], None, "fr"),
        RemoveRoutines([4], "fr"),
        Show("routines", None, "en"),
    ]


def test_routine_without_days_is_invalid():
    with pytest.raises(BrainError):
        parse_response(answer(tool("add_routine", {"title": "Gym", "weekdays": [], "time": None, "language": "en"})))


def test_someday_and_list_tools():
    message = answer(
        tool("add_someday", {"items": [{"title": "Lire Dune", "category": "Livres"}], "language": "fr"}),
        tool("close_someday", {"someday_ids": [2], "done": True, "language": "fr"}),
        tool("promote_someday", {"someday_id": 3, "due_date": "2026-10-10", "due_time": None, "language": "fr"}),
        tool("add_to_list", {"list": "Courses", "items": ["lait", " "], "language": "fr"}),
        tool("check_list_items", {"item_ids": [7], "language": "fr"}),
        tool("clear_list", {"list": "Courses", "language": "fr"}),
        tool("show", {"what": "lists", "name": "Courses", "language": "fr"}),
    )
    assert parse_response(message) == [
        AddSomeday([NewSomeday("Lire Dune", "Livres")], "fr"),
        CloseSomeday([2], True, "fr"),
        PromoteSomeday(3, date(2026, 10, 10), None, "fr"),
        AddToList("Courses", ["lait"], "fr"),  # blank items dropped
        CheckListItems([7], "fr"),
        ClearList("Courses", "fr"),
        Show("lists", "Courses", "fr"),
    ]


def test_context_lists_everything_with_numbers():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from majordome.db import ListItem, SomedayItem, Task

    snapshot = Snapshot(
        open_tasks=[Task(1, "Bank", date(2026, 10, 9), None, None)],
        someday=[SomedayItem(4, "Lire Dune", "Livres")],
        list_items=[ListItem(12, "Courses", "lait")],
        list_names=["Courses", "Idées"],
    )
    context = build_context("j'ai acheté le lait", datetime(2026, 10, 4, 18, 0, tzinfo=ZoneInfo("Europe/Paris")), snapshot)
    assert context.splitlines() == [
        "Now: Sunday 2026-10-04 18:00 (Europe/Paris)",
        "Open tasks:",
        "#1 Bank (due 2026-10-09)",
        "Routines:",
        "(none)",
        "Someday list:",
        "s4 Lire Dune [Livres]",
        "Lists: Courses, Idées",
        "l12 lait [Courses]",
        "<message>",
        "j'ai acheté le lait",
        "</message>",
    ]


def test_strict_tools_stay_under_the_api_limit():
    from majordome.brain import TOOLS

    # The API rejected 16 strict tools ("compiled grammar is too large"); 10 worked.
    assert sum(tool["strict"] for tool in TOOLS) <= 8


def test_malformed_tool_input_is_a_brain_error():
    for name, data in [
        ("update_routine", {"title": "Gym", "weekdays": ["mon"], "time": None, "language": "en"}),  # no routine_id
        ("set_reminders", {"minutes_before": "soon", "language": "en"}),
        ("close_someday", {"someday_ids": "4", "done": True, "language": "en"}),
    ]:
        with pytest.raises(BrainError):
            parse_response(answer(tool(name, data)))
