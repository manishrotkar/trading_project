"""JSON file storage for tasks."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# The data file can be overridden (e.g. by tests) via the TODOAPP_DATA_FILE
# environment variable. Each CLI invocation can also pass --file <path>.
DEFAULT_DATA_FILE = Path(os.environ.get("TODOAPP_DATA_FILE", "data/tasks.json"))


def load_tasks(path: str | Path = DEFAULT_DATA_FILE) -> list[dict[str, Any]]:
    """Load tasks from a JSON file.

    Returns [] if the file does not exist or is empty. Malformed JSON
    still raises so that data corruption is not silently ignored.
    """
    path = Path(path)
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8")
    if not content.strip():  # empty or whitespace-only file
        return []
    return json.loads(content)


def save_tasks(tasks: list[dict[str, Any]], path: str | Path = DEFAULT_DATA_FILE) -> None:
    """Save tasks to a JSON file, creating parent directories if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)
        f.write("\n")
