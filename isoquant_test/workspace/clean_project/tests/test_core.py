"""Unit tests for todoapp.core."""

import pytest

from todoapp.core import (
    add_task,
    complete_task,
    list_tasks,
    remove_task,
)


def test_add_assigns_sequential_ids():
    tasks = []
    assert add_task(tasks, "first")["id"] == 1
    assert add_task(tasks, "second")["id"] == 2


def test_add_strips_whitespace():
    task = add_task([], "  buy milk  ")
    assert task["title"] == "buy milk"


def test_add_rejects_blank_title():
    with pytest.raises(ValueError):
        add_task([], "   ")


def test_complete_task():
    tasks = [add_task([], "buy milk")]
    task = complete_task(tasks, 1)
    assert task["done"] is True


def test_complete_unknown_returns_none():
    assert complete_task([], 99) is None


def test_remove_task():
    tasks = [add_task([], "buy milk")]
    assert remove_task(tasks, 1) is True
    assert tasks == []


def test_remove_unknown_returns_false():
    tasks = [add_task([], "buy milk")]
    assert remove_task(tasks, 42) is False
    assert len(tasks) == 1


def test_list_tasks_sorted_by_id():
    tasks = []
    add_task(tasks, "b")
    add_task(tasks, "a")
    add_task(tasks, "c")
    assert [t["title"] for t in list_tasks(tasks)] == ["b", "a", "c"]
