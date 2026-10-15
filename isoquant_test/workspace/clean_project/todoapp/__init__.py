"""A tiny command-line to-do application package."""

from .core import add_task, complete_task, list_tasks, remove_task

__all__ = ["add_task", "complete_task", "list_tasks", "remove_task"]
