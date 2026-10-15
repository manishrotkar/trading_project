"""Conversation storage for the Streamlit web UI."""

from __future__ import annotations

import json
import re
from pathlib import Path

try:
    import config
except ModuleNotFoundError:
    from web_ui import config

# ============================================================
# STORAGE PATH
# ============================================================

CONVERSATIONS_DIR = config.CONVERSATIONS_DIR
CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def _validate_conversation_id(conversation_id: str) -> str:
    """Validate and return a safe conversation ID."""

    if not isinstance(conversation_id, str):
        raise TypeError("conversation_id must be a string.")

    if not conversation_id:
        raise ValueError("conversation_id cannot be empty.")

    if not re.fullmatch(
        r"[A-Za-z0-9_-]+",
        conversation_id,
    ):
        raise ValueError(
            "Invalid conversation_id. "
            "Only letters, numbers, '-' and '_' are allowed."
        )

    return conversation_id


def _conversation_path(conversation_id: str) -> Path:
    """Return the JSON path for a conversation."""

    conversation_id = _validate_conversation_id(
        conversation_id
    )

    return CONVERSATIONS_DIR / f"{conversation_id}.json"


# ============================================================
# SAVE
# ============================================================

def save_conversation(
    conversation_id: str,
    payload: dict,
) -> None:
    """Save one conversation as UTF-8 JSON."""

    if not isinstance(payload, dict):
        raise TypeError("payload must be a dictionary.")

    path = _conversation_path(conversation_id)

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            payload,
            file,
            indent=2,
            ensure_ascii=False,
        )


# ============================================================
# LOAD
# ============================================================

def load_conversation(
    conversation_id: str,
) -> dict | None:
    """Load one conversation, or return None if it does not exist."""

    path = _conversation_path(conversation_id)

    if not path.exists():
        return None

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise ValueError(
            f"Conversation file is not a JSON object: {path}"
        )

    return payload


# ============================================================
# LIST
# ============================================================

def list_conversations() -> list[str]:
    """Return saved conversation IDs."""

    if not CONVERSATIONS_DIR.exists():
        return []

    conversation_ids = []

    for path in CONVERSATIONS_DIR.glob("*.json"):
        conversation_ids.append(path.stem)

    return sorted(conversation_ids)


# ============================================================
# DELETE
# ============================================================

def delete_conversation(
    conversation_id: str,
) -> None:
    """Delete a conversation if it exists."""

    path = _conversation_path(conversation_id)

    if path.exists():
        path.unlink()
