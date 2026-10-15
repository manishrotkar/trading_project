from __future__ import annotations

import re
import uuid
from pathlib import Path

import streamlit as st

import config
from agent_bridge import run_agent
from renderer import render_message, render_notice
from storage import (
    delete_conversation,
    list_conversations,
    load_conversation,
    save_conversation,
)

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon=config.PAGE_ICON,
    layout=config.LAYOUT,
)

# ============================================================
# PATHS
# ============================================================

UPLOAD_DIR = config.DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = uuid.uuid4().hex

if "delete_confirmation" not in st.session_state:
    st.session_state.delete_confirmation = None

if "rename_conversation" not in st.session_state:
    st.session_state.rename_conversation = None

# ============================================================
# HELPERS
# ============================================================

def safe_filename(filename: str) -> str:
    """Return a safe filename for the uploads directory."""
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    name = name.lstrip(".")
    return name[:200] or "uploaded_file"


def unique_upload_path(filename: str) -> Path:
    """Return a non-existing path without overwriting an existing file."""
    safe_name = safe_filename(filename)
    path = UPLOAD_DIR / safe_name

    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    counter = 1

    while True:
        candidate = UPLOAD_DIR / f"{stem} ({counter}){suffix}"

        if not candidate.exists():
            return candidate

        counter += 1


def save_uploaded_files(uploaded_files) -> list[Path]:
    """Save selected Streamlit uploads and return their paths."""
    saved_paths = []

    for uploaded_file in uploaded_files or []:
        path = unique_upload_path(uploaded_file.name)
        path.write_bytes(uploaded_file.getvalue())
        saved_paths.append(path)

    return saved_paths


def build_agent_request(
    user_message: str,
    saved_paths: list[Path],
) -> str:
    """
    Build the message sent to the agent.

    If files were uploaded, explicitly tell the agent which files
    were attached.
    """
    if not saved_paths:
        return user_message

    attachments = "\n".join(
        f"- {path.relative_to(config.BASE_DIR.parent)}"
        for path in saved_paths
    )

    return (
        "Attached files:\n"
        f"{attachments}\n\n"
        "User request:\n"
        f"{user_message}"
    )


def conversation_title(messages: list[dict]) -> str:
    """Return a human-friendly title from the first user message."""
    for message in messages:
        if message.get("role") == "user":
            content = str(message.get("content", "")).strip()

            if content:
                if len(content) > 60:
                    return content[:57].rstrip() + "..."

                return content

    return "New conversation"


def save_current_conversation() -> None:
    """Save the current conversation to JSON storage."""
    save_conversation(
        st.session_state.conversation_id,
        {
            "conversation_id": st.session_state.conversation_id,
            "title": conversation_title(
                st.session_state.messages
            ),
            "messages": st.session_state.messages,
        },
    )


def load_selected_conversation(conversation_id: str) -> None:
    """Load a saved conversation into the current Streamlit session."""
    conversation = load_conversation(conversation_id)

    if conversation is None:
        st.error("The selected conversation could not be found.")
        return

    messages = conversation.get("messages", [])

    if not isinstance(messages, list):
        st.error("The saved conversation has an invalid message format.")
        return

    st.session_state.conversation_id = conversation_id
    st.session_state.messages = messages


def start_new_chat() -> None:
    """Reset the current session to a new empty conversation."""
    st.session_state.messages = []
    st.session_state.conversation_id = uuid.uuid4().hex
    st.session_state.delete_confirmation = None
    st.session_state.rename_conversation = None


def request_delete_conversation(conversation_id: str) -> None:
    """Ask for confirmation before deleting a conversation."""
    st.session_state.delete_confirmation = conversation_id
    st.session_state.rename_conversation = None


def confirm_delete_conversation(conversation_id: str) -> None:
    """Delete a conversation and reset the current chat if necessary."""
    delete_conversation(conversation_id)

    if st.session_state.conversation_id == conversation_id:
        start_new_chat()
    else:
        st.session_state.delete_confirmation = None


def request_rename_conversation(conversation_id: str) -> None:
    """Open the rename controls for a conversation."""
    st.session_state.rename_conversation = conversation_id
    st.session_state.delete_confirmation = None


def rename_conversation(
    conversation_id: str,
    new_title: str,
) -> bool:
    """Save a new title for an existing conversation."""
    new_title = new_title.strip()

    if not new_title:
        return False

    conversation = load_conversation(conversation_id)

    if conversation is None:
        return False

    conversation["title"] = new_title[:100]

    save_conversation(
        conversation_id,
        conversation,
    )

    return True


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.title("Isoquant Agent")

    # --------------------------------------------------------
    # New Chat
    # --------------------------------------------------------

    if st.button(
        config.NEW_CHAT_BUTTON_LABEL,
        use_container_width=True,
    ):
        start_new_chat()
        st.rerun()

    st.divider()

    # --------------------------------------------------------
    # Conversations
    # --------------------------------------------------------

    st.subheader("Conversations")

    saved_conversations = list_conversations()

    if saved_conversations:
        for conversation_id in saved_conversations:
            conversation = load_conversation(conversation_id)

            if conversation is None:
                continue

            title = conversation.get("title")

            if not title:
                title = conversation_title(
                    conversation.get("messages", [])
                )

            col1, col2, col3 = st.columns(
                [6, 1, 1],
                gap="small",
            )

            with col1:
                if st.button(
                    "Chat: " + title,
                    key=f"conversation_{conversation_id}",
                    use_container_width=True,
                ):
                    load_selected_conversation(conversation_id)
                    st.rerun()

            with col2:
                if st.button(
                    "R",
                    key=f"rename_{conversation_id}",
                    help="Rename conversation",
                    use_container_width=True,
                ):
                    request_rename_conversation(conversation_id)
                    st.rerun()

            with col3:
                if st.button(
                    "X",
                    key=f"delete_{conversation_id}",
                    help="Delete conversation",
                    use_container_width=True,
                ):
                    request_delete_conversation(conversation_id)
                    st.rerun()

    else:
        st.caption("No saved conversations yet.")

    # --------------------------------------------------------
    # Rename
    # --------------------------------------------------------

    rename_id = st.session_state.rename_conversation

    if rename_id:
        rename_data = load_conversation(rename_id)

        if rename_data is not None:
            current_title = rename_data.get("title")

            if not current_title:
                current_title = conversation_title(
                    rename_data.get("messages", [])
                )

            st.divider()
            st.caption("Rename conversation")

            new_title = st.text_input(
                "Conversation title",
                value=current_title,
                max_chars=100,
                key=f"rename_input_{rename_id}",
            )

            save_col, cancel_col = st.columns(2)

            with save_col:
                if st.button(
                    "Save",
                    key="save_rename",
                    use_container_width=True,
                ):
                    if rename_conversation(
                        rename_id,
                        new_title,
                    ):
                        st.session_state.rename_conversation = None
                        st.rerun()
                    else:
                        st.error("Title cannot be empty.")

            with cancel_col:
                if st.button(
                    "Cancel",
                    key="cancel_rename",
                    use_container_width=True,
                ):
                    st.session_state.rename_conversation = None
                    st.rerun()

        else:
            st.session_state.rename_conversation = None

    # --------------------------------------------------------
    # Delete Confirmation
    # --------------------------------------------------------

    delete_id = st.session_state.delete_confirmation

    if delete_id:
        delete_data = load_conversation(delete_id)

        if delete_data is not None:
            delete_title = delete_data.get("title")

            if not delete_title:
                delete_title = conversation_title(
                    delete_data.get("messages", [])
                )

            st.divider()
            st.warning(
                f"Delete conversation?\n\n"
                f"{delete_title}"
            )

            confirm_col, cancel_col = st.columns(2)

            with confirm_col:
                if st.button(
                    "Delete",
                    key="confirm_delete",
                    use_container_width=True,
                ):
                    confirm_delete_conversation(delete_id)
                    st.rerun()

            with cancel_col:
                if st.button(
                    "Cancel",
                    key="cancel_delete",
                    use_container_width=True,
                ):
                    st.session_state.delete_confirmation = None
                    st.rerun()

        else:
            st.session_state.delete_confirmation = None

    st.divider()

    # --------------------------------------------------------
    # Files
    # --------------------------------------------------------

    st.subheader("Files")

    uploaded_files = st.file_uploader(
        "Upload files",
        accept_multiple_files=True,
        help="Files are saved inside web_ui/data/uploads/.",
    )

    if uploaded_files:
        st.caption(
            f"{len(uploaded_files)} file(s) selected."
        )

    st.divider()

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    st.caption("Agent bridge: connected")

    render_notice(
        "History is saved to disk in "
        "web_ui/data/conversations/."
    )


# ============================================================
# MAIN CHAT
# ============================================================

st.title(config.APP_TITLE)

if not st.session_state.messages:
    render_message(
        "assistant",
        config.WELCOME_MESSAGE,
    )

for message in st.session_state.messages:
    render_message(
        message["role"],
        message["content"],
    )


# ============================================================
# CHAT INPUT
# ============================================================

user_message = st.chat_input(
    config.CHAT_INPUT_PLACEHOLDER
)

if user_message:
    user_message = user_message.strip()

    if not user_message:
        st.stop()

    if len(user_message) > config.MAX_INPUT_CHARS:
        st.error(
            f"Message is too long. Maximum length is "
            f"{config.MAX_INPUT_CHARS} characters."
        )
        st.stop()

    # --------------------------------------------------------
    # Save uploaded files
    # --------------------------------------------------------

    saved_paths = save_uploaded_files(
        uploaded_files
    )

    # --------------------------------------------------------
    # Save and display user message
    # --------------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_message,
        }
    )

    render_message(
        "user",
        user_message,
    )

    # --------------------------------------------------------
    # Build request for the agent
    # --------------------------------------------------------

    agent_request = build_agent_request(
        user_message,
        saved_paths,
    )

    # --------------------------------------------------------
    # Call real Isoquant agent
    # --------------------------------------------------------

    try:
        with st.chat_message(
            "assistant",
            avatar=config.ROLE_AVATARS["assistant"],
        ):
            st.markdown("**Assistant**")

            with st.spinner(
                "Agent is working..."
            ):
                response = run_agent(
                    agent_request
                )

            st.markdown(response)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        # ----------------------------------------------------
        # Save conversation
        # ----------------------------------------------------

        save_current_conversation()

        # ----------------------------------------------------
        # Show saved attachment paths
        # ----------------------------------------------------

        if saved_paths:
            st.caption(
                "Attached files saved: "
                + ", ".join(
                    str(path)
                    for path in saved_paths
                )
            )

    except Exception as exc:
        error_message = (
            f"Agent error: "
            f"{type(exc).__name__}: {exc}"
        )

        st.error(error_message)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": error_message,
            }
        )
