"""A tiny to-do application package."""

from .core import (
    DEFAULT_PRIORITY,
    PRIORITY_ORDER,
    add_task,
    complete_task,
    filter_tasks,
    list_tasks,
    remove_task,
)

__all__ = [
    "DEFAULT_PRIORITY",
    "PRIORITY_ORDER",
    "add_task",
    "complete_task",
    "filter_tasks",
    "list_tasks",
    "remove_task",
]
