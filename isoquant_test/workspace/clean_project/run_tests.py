"""Unit tests + CLI smoke test for todoapp (run from the workspace root)."""

import os
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent


def main() -> int:
    # 1. Unit tests (run from the project dir so imports resolve).
    tests = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests"],
        cwd=PROJECT,
    )
    if tests.returncode != 0:
        return tests.returncode

    # 2. CLI smoke test on a scratch data file (never touches real data).
    scratch = PROJECT / "smoke_tasks.json"
    env = {**os.environ, "PYTHONPATH": str(PROJECT)}
    commands = [
        [sys.executable, "-m", "todoapp.cli", "--file", str(scratch), "add", "smoke item"],
        [sys.executable, "-m", "todoapp.cli", "--file", str(scratch), "list"],
    ]
    try:
        for cmd in commands:
            result = subprocess.run(cmd, env=env)
            if result.returncode != 0:
                return result.returncode
    finally:
        scratch.unlink(missing_ok=True)

    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
