"""web_ui.agent_bridge

Adapter layer between the Streamlit UI and the existing `agent.py`.

The bridge translates a plain-text user message into a call to the
Isoquant agent (via `agent.py`'s tool definitions and tool execution
functions) and returns the agent's final plain-text reply.

Configuration:
    - API key:      ISOQUANT_API_KEY environment variable
    - base URL:     https://api.isoquant.ai/v1
    - model:        glm-5.3-flash
    - ZDR header:   Isoquant-ZDR: required
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

# `agent.py` lives in the project root, one level above this file.
# Make sure the root is importable no matter how the UI is launched.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent import TOOLS, execute_tool  # noqa: E402

from openai import OpenAI  # noqa: E402


# ============================================================
# CONFIGURATION
# ============================================================

API_KEY = os.getenv("ISOQUANT_API_KEY")

BASE_URL = "https://api.isoquant.ai/v1"
MODEL = "glm-5.3-flash"

if not API_KEY:
    raise RuntimeError(
        "ISOQUANT_API_KEY is not loaded."
    )


client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are an AI coding assistant working inside a safe
workspace.

Your workspace is the directory provided by the host program.

IMPORTANT RULES:

1. Work ONLY inside the workspace.
2. Never request or assume access to files outside it.
3. Use list_files before making major changes.
4. Read existing files before modifying them.
5. When creating code, write the complete file using write_file.
6. After creating Python code, run it using run_python.
7. If the program produces an error, analyze the error,
   modify the code, and run it again.
8. Keep the project simple and understandable.
9. Do not expose or request API keys, passwords, or secrets.
10. Explain important actions briefly.
11. IMPORTANT: When you need to use a tool, ALWAYS use the structured
    function tool provided by the API.
12. NEVER write tool calls as XML,
    or as plain text.
13. If a tool is needed, call the corresponding function directly.
14. After receiving a tool result, continue the task and do not stop
    until the user's request is actually completed.

You have these tools:

- list_files
- read_file
- write_file
- run_python

Your goal is to complete the user's programming request
inside the workspace.
"""


# ============================================================
# AGENT BRIDGE
# ============================================================

def run_agent(user_message: str) -> str:
    """Send a user message to the agent and return the agent's reply.

    Runs the same tool-calling loop as `agent.py`: each model response
    may request tool calls; those are executed via `execute_tool` and
    the results are fed back until the model replies without tool
    calls. That final assistant text is returned to the caller.
    """

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]

    final_reply: Optional[str] = None

    for step in range(20):

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=4000,
            extra_headers={
                "Isoquant-ZDR": "required"
            },
        )

        message = response.choices[0].message

        # Remember the latest assistant text; it becomes the reply if
        # this turn carries no tool calls.
        if message.content:
            final_reply = message.content

        # No tool call means the model considers the task finished.
        if not message.tool_calls:
            break

        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in message.tool_calls
                ],
            }
        )

        for tool_call in message.tool_calls:

            name = tool_call.function.name

            try:
                arguments = json.loads(
                    tool_call.function.arguments
                )
            except json.JSONDecodeError:
                arguments = {}

            try:
                result = execute_tool(
                    name,
                    arguments
                )
            except Exception as exc:
                result = (
                    f"TOOL ERROR: {type(exc).__name__}: {exc}"
                )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    return final_reply if final_reply is not None else ""
