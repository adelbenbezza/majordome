from datetime import date, time
from types import SimpleNamespace

import pytest

from majordome.brain import AddRoutine, AddTasks, ListRoutines, RemoveRoutines, UpdateRoutine, BrainError, CompleteTasks, ListTasks, NewTask, Reply, SetBriefTime, parse_response


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


def test_set_brief_time():
    assert parse_response(answer(tool("set_brief_time", {"time": "07:30", "language": "fr"}))) == [
        SetBriefTime(time(7, 30), "fr")
    ]
    assert parse_response(answer(tool("set_brief_time", {"time": None, "language": "en"}))) == [
        SetBriefTime(None, "en")
    ]


def test_routine_tools():
    message = answer(
        tool("add_routine", {"title": "Gym", "weekdays": ["tue", "mon"], "time": "18:00", "language": "fr"}),
        tool("complete_tasks", {"task_ids": [], "routine_ids": [2], "language": "fr"}),
        tool("update_routine", {"routine_id": 1, "title": "Gym", "weekdays": ["mon"], "time": None, "language": "fr"}),
        tool("remove_routines", {"routine_ids": [4], "language": "fr"}),
        tool("list_routines", {"language": "en"}),
    )
    assert parse_response(message) == [
        AddRoutine("Gym", [0, 1], time(18, 0), "fr"),
        CompleteTasks([], "fr", routine_ids=[2]),
        UpdateRoutine(1, "Gym", [0], None, "fr"),
        RemoveRoutines([4], "fr"),
        ListRoutines("en"),
    ]


def test_routine_without_days_is_invalid():
    with pytest.raises(BrainError):
        parse_response(answer(tool("add_routine", {"title": "Gym", "weekdays": [], "time": None, "language": "en"})))
