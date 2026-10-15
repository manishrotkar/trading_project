"""Central configuration constants for the Isoquant Agent web UI.

This file contains only UI and application configuration.
No API keys, tokens, passwords, or other secrets are stored here.
"""

from __future__ import annotations

import pathlib


# ============================================================
# PATHS
# ============================================================

# web_ui/ folder that contains this file.
BASE_DIR = pathlib.Path(__file__).resolve().parent

# Persistent data used by the web UI.
DATA_DIR = BASE_DIR / "data"

# Saved conversation files.
CONVERSATIONS_DIR = DATA_DIR / "conversations"


# ============================================================
# PAGE / LAYOUT
# ============================================================

APP_TITLE = "Isoquant Agent — Web UI"

PAGE_ICON = "🤖"

# Streamlit page layout.
LAYOUT = "centered"


# ============================================================
# CHAT
# ============================================================

WELCOME_MESSAGE = (
    "👋 Hello! This is the **Isoquant Agent Web UI**.\n\n"
    "- Chat with the real Isoquant coding agent.\n"
    "- Upload files and ask the agent to inspect or work with them.\n"
    "- Your conversations are saved locally and can be reopened later.\n"
    "- You can rename or delete saved conversations from the sidebar."
)


# Human-friendly label + avatar per role.
ROLE_LABELS = {
    "user": "You",
    "assistant": "Assistant",
    "system": "System",
}

ROLE_AVATARS = {
    "user": "🧑‍💻",
    "assistant": "🤖",
    "system": "⚙️",
}


# Maximum characters accepted by the chat input box.
MAX_INPUT_CHARS = 100000

# Placeholder text inside the chat input box.
CHAT_INPUT_PLACEHOLDER = "Message the agent…"


# ============================================================
# SIDEBAR
# ============================================================

NEW_CHAT_BUTTON_LABEL = "➕ New chat"

AGENT_STATUS_CONNECTED = "🟢 Agent bridge: connected"

HISTORY_NOTICE = (
    "💾 Conversation history is saved locally in "
    "`web_ui/data/conversations/`."
)
