"""Core task logic for the to-do app.

Tasks are plain dicts so they serialize easily to JSON:

    {"id": 1, "title": "Buy milk", "done": False}

Feature: priority
    Task dicts carry an optional ``"priority"`` field with the value
    ``"high"``, ``"medium"`` or ``"low"``.  When absent, it is treated as
    ``"medium"`` (see :func:`get_priority`).  Task dicts never store a
    ``None`` priority — the key is simply omitted for the default, so old
    data files remain valid and unchanged.
"""

from . import storage

# The single source of truth for supported priorities, listed low → high.
# Use :func:`priority_rank` when a *sort* order is needed.
PRIORITY_ORDER = ["low", "medium", "high"]

DEFAULT_PRIORITY = "medium"

VALID_PRIORITIES = set(PRIORITY_ORDER)

# Tasks marked done always sort after every pending task, regardless of
# priority, so they can never bury actionable work.
_DONE_GROUP_OFFSET = len(PRIORITY_ORDER) * 10


def normalize_priority(value):
    """Return a valid priority for *value*.

    - ``None`` or ``""``        -> DEFAULT_PRIORITY ("medium")
    - ``"high"`` (any casing)   -> ``"high"``
    - anything else             -> ``None`` (caller decides how to report it)
    """
    if value is None:
        return DEFAULT_PRIORITY
    if not isinstance(value, str):
        return None
    cleaned = value.strip().lower()
    return cleaned if cleaned in VALID_PRIORITIES else None


def get_priority(task):
    """Return the task's priority, defaulting to ``"medium"``."""
    value = normalize_priority(task.get("priority"))
    return value if value is not None else DEFAULT_PRIORITY


def priority_rank(task):
    """Return a numeric sort key where higher priority sorts earlier.

    Pending tasks come before done ones; within a group, high priority
    sorts before medium, which sorts before low.
    """
    priority = get_priority(task)
    rank = PRIORITY_ORDER.index(priority)          # low=0, medium=1, high=2
    return _DONE_GROUP_OFFSET if task["done"] else len(PRIORITY_ORDER) - 1 - rank


def add_task(tasks, title, priority=None):
    """Add a new task with the next available id. Returns the new task.

    ``priority`` may be ``"high"``, ``"medium"`` or ``"low"`` (case
    insensitive).  ``None``/empty means the default (``"medium"``).  An
    invalid value raises ``ValueError``.
    """
    title = title.strip()
    if not title:
        raise ValueError("Task title must not be empty.")

    resolved = normalize_priority(priority)
    if resolved is None:
        raise ValueError(
            f"Priority must be one of: {', '.join(PRIORITY_ORDER)} "
            f"(got {priority!r})."
        )

    next_id = max((task["id"] for task in tasks), default=0) + 1
    task = {"id": next_id, "title": title, "done": False}
    if resolved != DEFAULT_PRIORITY:
        task["priority"] = resolved
    tasks.append(task)
    return task


def complete_task(tasks, task_id):
    """Mark the task with the given id as done. Returns the task or None."""
    for task in tasks:
        if task["id"] == task_id:
            task["done"] = True
            return task
    return None


def remove_task(tasks, task_id):
    """Remove the task with the given id. Returns True if something was removed."""
    remaining = [task for task in tasks if task["id"] != task_id]
    removed = len(remaining) != len(tasks)
    tasks[:] = remaining
    return removed


def list_tasks(tasks, order="id"):
    """Return tasks in the requested order.

    ``order``:
        ``"id"``       – sorted by id (default, unchanged behaviour)
        ``"priority"`` – pending tasks first (high priority first), done
                         tasks last
        ``"status"``   – pending tasks first (by id), done tasks last
    """
    if order == "priority":
        return sorted(tasks, key=lambda t: (priority_rank(t), t["id"]))
    if order == "status":
        return sorted(tasks, key=lambda task: (task["done"], task["id"]))
    return sorted(tasks, key=lambda task: task["id"])


def filter_tasks(tasks, priority=None, done=None):
    """Return the tasks that match the given filters.

    ``priority`` – optional priority name (case-insensitive); an invalid
                   value raises ``ValueError``.
    ``done``     – optional True/False status filter; anything else is
                   treated as no filter.
    """
    if priority is None:
        resolved = None
    else:
        resolved = normalize_priority(priority)
        if resolved is None:
            raise ValueError(
                f"Priority must be one of: {', '.join(PRIORITY_ORDER)} "
                f"(got {priority!r})."
            )

    matched = tasks
    if resolved is not None:
        matched = [t for t in matched if get_priority(t) == resolved]
    if done is not None:
        matched = [t for t in matched if t["done"] is done]
    return matched
