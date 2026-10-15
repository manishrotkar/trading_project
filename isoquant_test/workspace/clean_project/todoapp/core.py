"""Core task logic for the to-do app.

Tasks are plain dicts so they serialize easily to JSON:

    {"id": 1, "title": "Buy milk", "done": False}

No printing and no file I/O here — these functions are pure and easy to
unit test.
"""

from typing import Any


def add_task(tasks: list[dict[str, Any]], title: str) -> dict[str, Any]:
    """Add a new task with the next available id. Returns the new task."""
    title = title.strip()
    if not title:
        raise ValueError("Task title must not be empty.")

    next_id = max((task["id"] for task in tasks), default=0) + 1
    task = {"id": next_id, "title": title, "done": False}
    tasks.append(task)
    return task


def complete_task(tasks: list[dict[str, Any]], task_id: int) -> dict[str, Any] | None:
    """Mark the task with the given id as done. Returns the task or None."""
    for task in tasks:
        if task["id"] == task_id:
            task["done"] = True
            return task
    return None


def remove_task(tasks: list[dict[str, Any]], task_id: int) -> bool:
    """Remove the task with the given id. Returns True if something was removed."""
    remaining = [task for task in tasks if task["id"] != task_id]
    removed = len(remaining) != len(tasks)
    tasks[:] = remaining
    return removed


def list_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return tasks sorted by id."""
    return sorted(tasks, key=lambda task: task["id"])
