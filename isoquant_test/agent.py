import json
import os
import subprocess
import signal
from pathlib import Path

from openai import OpenAI
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path.cwd().resolve()
WORKSPACE = BASE_DIR

API_KEY = os.getenv("ISOQUANT_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "ISOQUANT_API_KEY is not loaded."
    )


client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.isoquant.ai/v1",
)


# ============================================================
# SAFETY
# ============================================================

def safe_path(relative_path: str) -> Path:
    """
    Convert a workspace-relative path into an absolute path.

    The path MUST remain inside workspace/.
    """

    path = (WORKSPACE / relative_path).resolve()

    try:
        path.relative_to(WORKSPACE.resolve())
    except ValueError:
        raise RuntimeError(
            "Security error: path is outside the workspace."
        )

    # Block sensitive files/directories from agent tools.
    sensitive_names = {
        ".env",
        "access.txt",
        "credentials.json",
        "secrets.json",
    }

    if path.name in sensitive_names:
        raise RuntimeError(
            f"Security error: access to sensitive file is blocked: {path.name}"
        )

    if path.name.startswith(".env."):
        raise RuntimeError(
            f"Security error: access to sensitive file is blocked: {path.name}"
        )

    if path.suffix in {".pem", ".key"}:
        raise RuntimeError(
            f"Security error: access to sensitive file is blocked: {path.name}"
        )

    relative_parts = path.relative_to(WORKSPACE.resolve()).parts

    if ".git" in relative_parts:
        raise RuntimeError(
            "Security error: access to .git is blocked."
        )

    return path


# ============================================================
# TOOL FUNCTIONS
# ============================================================

def list_files() -> str:
    """List files inside the workspace."""

    files = []

    sensitive_names = {
        ".env",
        "access.txt",
        "credentials.json",
        "secrets.json",
    }

    for path in WORKSPACE.rglob("*"):
        if not path.is_file():
            continue

        relative_path = path.relative_to(WORKSPACE)
        parts = relative_path.parts

        # Hide protected directories.
        if ".git" in parts:
            continue

        # Hide protected files.
        if path.name in sensitive_names:
            continue

        if path.name.startswith(".env."):
            continue

        if path.suffix in {".pem", ".key"}:
            continue

        files.append(str(relative_path))

    if not files:
        return "Workspace is empty."

    return "\n".join(sorted(files))


def read_file(path: str) -> str:
    """Read a text file from the workspace."""

    file_path = safe_path(path)

    if not file_path.exists():
        return f"File does not exist: {path}"

    if not file_path.is_file():
        return f"Not a file: {path}"

    return file_path.read_text(
        encoding="utf-8"
    )


def write_file(path: str, content: str) -> str:
    """Create or replace a file inside the workspace."""

    file_path = safe_path(path)

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    file_path.write_text(
        content,
        encoding="utf-8"
    )

    return f"File written successfully: {path}"


def run_python(path: str) -> str:
    """
    Run a Python file inside the workspace with controlled cancellation.

    The child process runs in its own process group so timeout or
    Ctrl+C can terminate the child and its descendants.
    """

    file_path = safe_path(path)

    if not file_path.exists():
        return f"File does not exist: {path}"

    if file_path.suffix != ".py":
        return "Only .py files can be executed."

    process = None
    interrupted = False

    def handle_sigint(signum, frame):
        nonlocal interrupted

        interrupted = True

        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    previous_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, handle_sigint)

    try:
        process = subprocess.Popen(
            [os.sys.executable, str(file_path)],
            cwd=WORKSPACE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )

        import time

        start_time = time.monotonic()

        while process.poll() is None:
            if interrupted:
                break

            if time.monotonic() - start_time >= 60:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)

                process.wait()

                return (
                    "ERROR: Program timed out after 60 seconds "
                    "and the child process was terminated."
                )

            time.sleep(0.1)

        stdout, stderr = process.communicate()

        if interrupted:
            return (
                "CANCELLED: Program was stopped by Ctrl+C "
                "and the child process was terminated."
            )

        output = [
            f"RETURN CODE: {process.returncode}"
        ]

        if stdout:
            output.append("\nSTDOUT:\n" + stdout)

        if stderr:
            output.append("\nSTDERR:\n" + stderr)

        return "\n".join(output)

    except OSError as exc:
        return f"ERROR: Could not start Python program: {exc}"

    finally:
        signal.signal(signal.SIGINT, previous_handler)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all non-sensitive files inside the current workspace.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file inside the current workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative file path.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or replace a file inside the current workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative file path.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete text content to write.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Run a Python file inside the current workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative Python file path.",
                    },
                },
                "required": ["path"],
            },
        },
    },
]

def execute_tool(name: str, arguments: dict) -> str:

    if name == "list_files":
        return list_files()

    if name == "read_file":
        return read_file(
            arguments["path"]
        )

    if name == "write_file":
        return write_file(
            arguments["path"],
            arguments["content"],
        )

    if name == "run_python":
        return run_python(
            arguments["path"]
        )

    return f"Unknown tool: {name}"


# ============================================================
# AI AGENT
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
12. NEVER write tool calls as XML, such as <tool_call>...</tool_call>,
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


def run_agent(user_request: str):

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_request,
        },
    ]

    for step in range(20):

        print()
        print("=" * 70)
        print(f"AGENT STEP {step + 1}")
        print("=" * 70)

        response = client.chat.completions.create(
            model="glm-5.3-flash",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=4000,
            extra_headers={
                "Isoquant-ZDR": "required"
            },
        )

        message = response.choices[0].message

        if message.content:
            print()
            print("AI:")
            print(message.content)

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

            print()
            print(
                f"TOOL REQUEST: {name}"
            )

            if arguments:
                print(
                    f"ARGUMENTS: {arguments}"
                )

            try:
                result = execute_tool(
                    name,
                    arguments
                )
            except Exception as exc:
                result = (
                    f"TOOL ERROR: {type(exc).__name__}: {exc}"
                )

            print()
            print("TOOL RESULT:")
            print(result)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )



# ============================================================
# INTERACTIVE INPUT
# ============================================================

def get_user_request():
    """
    Read a multiline request.

    Enter submits the request.
    Shift+Enter inserts a newline.
    Ctrl+C cancels the current request.
    Ctrl+D exits the agent.
    """

    bindings = KeyBindings()

    @bindings.add("enter")
    def _(event):
        event.current_buffer.validate_and_handle()

    @bindings.add("escape", "enter")
    def _(event):
        event.current_buffer.insert_text("\n")

    session = PromptSession(
        message="YOU: ",
        multiline=True,
        key_bindings=bindings,
    )

    try:
        return session.prompt().strip()
    except KeyboardInterrupt:
        print("\nRequest cancelled.")
        return ""
    except EOFError:
        raise

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("ISOQUANT CODING AGENT")
    print("=" * 70)

    print()
    print(f"Workspace: {WORKSPACE}")

    print()
    print("Type your programming request.")
    print("Type 'exit' to quit.")
    while True:

        print()

        try:
            user_request = get_user_request()
        except KeyboardInterrupt:
            print("\nAgent stopped.")
            break
        except EOFError:
            print("\nGoodbye.")
            break

        if user_request.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break

        if not user_request:
            continue

        try:
            run_agent(user_request)
        except KeyboardInterrupt:
            print("\nAgent operation cancelled.")
