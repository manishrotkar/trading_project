"""web_ui.renderer

Step 5: display and formatting helpers for the visual chat UI.

Purpose:
    - Render chat messages as ChatGPT-like bubbles inside Streamlit:
      an avatar, a role header ("You" / "Assistant") and markdown
      content.
    - Keep all rendering details in one place so `app.py` stays a
      simple page flow.

Scope note:
    - Visual only. No agent connection, no persistence.
    - `st.chat_message` is used because it handles bubble layout,
      avatars and long-message wrapping correctly as a transcript
      grows.
"""

from __future__ import annotations

import streamlit as st

import config


def render_message(role: str, content: str) -> None:
    """Render a single chat message in the UI.

    Args:
        role: "user", "assistant" or "system".
        content: Message text (rendered as markdown).
    """
    avatar = config.ROLE_AVATARS.get(role, config.ROLE_AVATARS["system"])
    label = config.ROLE_LABELS.get(role, "System")

    with st.chat_message(role, avatar=avatar):
        st.markdown(f"**{label}**")
        st.markdown(content)


def render_notice(text: str) -> None:
    """Render a small informational notice under the chat transcript."""
    st.caption(text)
