"""Drive the authentication cycle end to end against the real access.txt.

Equivalent to running:
    python auth_main.py refresh
    python auth_main.py verify
    python auth_main.py show
"""

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLI = HERE / "auth_main.py"

# Make the CLI read/write the real access.txt in this workspace.
env = dict(os.environ)
env["ACCESS_TOKEN_FILE"] = str(HERE / "access.txt")


def run(*args):
    result = subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        env=env,
    )
    return result


print("=== 1. verify (before) ===")
r = run("verify")
print(r.stdout or r.stderr, "exit:", r.returncode)

print("=== 2. refresh ===")
r = run("refresh")
print(r.stdout or r.stderr, "exit:", r.returncode)

print("=== 3. verify (after) ===")
r = run("verify")
print(r.stdout or r.stderr, "exit:", r.returncode)

print("=== 4. show ===")
r = run("show")
print(r.stdout or r.stderr, "exit:", r.returncode)

print("=== 5. cycle (token still fresh -> must NOT change it) ===")
before = (HERE / "access.txt").read_text(encoding="utf-8").strip()
r = run("cycle")
print(r.stdout or r.stderr, "exit:", r.returncode)
after = (HERE / "access.txt").read_text(encoding="utf-8").strip()
print("token unchanged:", before == after)

print("=== 6. access.txt contents ===")
print((HERE / "access.txt").read_text(encoding="utf-8").strip())
