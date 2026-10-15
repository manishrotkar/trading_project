"""JSON file storage for tasks."""

import json
import os
from pathlib import Path

# The data file can be overridden (e.g. by tests) via the TODO_DATA_FILE env var.
DEFAULT_PATH = Path(os.environ.get("TODO_DATA_FILE", "data/tasks.json"))


def load_tasks(path=DEFAULT_PATH):
    """Load tasks from a JSON file.

    Returns [] if the file does not exist or is empty. Malformed JSON
    still raises so that data corruption is not silently ignored.
    """
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        content = f.read()
    if not content.strip():  # empty or whitespace-only file
        return []
    return json.loads(content)


def save_tasks(tasks, path=DEFAULT_PATH):
    """Save tasks to a JSON file, creating parent directories if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)
        f.write("\n")
