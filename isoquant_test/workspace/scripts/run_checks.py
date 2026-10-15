"""Runs the unit tests plus a quick CLI smoke test.

Usage (from anywhere):

    python scripts/run_checks.py

Also runs `pip check`, which verifies that the installed environment
matches the requirements in requirements.txt (non-zero exit if any
dependency is broken or conflicting).

The unit tests run with the network blocked (tests/_offline.py), so they
can never require a live Fyers API request -- an attempted request fails
loudly instead of passing.

The smoke test points TODO_DATA_FILE at a scratch file so the real
data/tasks.json is never touched.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Project root, so "todo" is importable and paths resolve regardless of cwd.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Block network before anything else so even a test that connects during
# IMPORT time fails, not just one that connects inside a test method.
from tests._offline import block_network  # noqa: E402

block_network()

# 0. Environment consistency: the lock file must be satisfied.
print("--- pip check (dependency consistency) ---")
pip_check = subprocess.run(
    [sys.executable, "-m", "pip", "check"],
    capture_output=True, text=True,
)
print(pip_check.stdout.rstrip())
if pip_check.returncode != 0:
    sys.exit("pip check failed: the environment does not satisfy requirements.txt")

# 1. Unit tests (network is blocked -- no live Fyers API requests possible)
suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
result = unittest.TextTestRunner(verbosity=2).run(suite)

# 2. CLI smoke test against a scratch data file
# The child process is separate, so the socket block above does not apply to
# it; the smoke test only talks to a local JSON file, never the network.
print("\n--- CLI smoke test ---")
with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
    scratch = tmp.name

env = dict(os.environ, TODO_DATA_FILE=scratch)
commands = (
    ["add", "Buy milk"],
    ["add", "--priority", "high", "Ship the release"],
    ["add", "-p", "low", "Tidy the downloads folder"],
    ["list"],
    ["list", "--order", "priority"],
    ["list", "--priority", "high"],
    ["done", "1"],
    ["list", "--pending"],
    ["list", "--done"],
    ["remove", "2"],
    ["list"],
    ["add", "--priority", "urgent", "This should fail"],  # exit code 2
)

try:
    ok = result.wasSuccessful()
    entry = str(ROOT / "main.py")
    for args in commands:
        proc = subprocess.run([sys.executable, entry, *args],
                              capture_output=True, text=True, env=env)
        print(f"$ python main.py {' '.join(args)}")
        if proc.stdout:
            print(proc.stdout.rstrip())
        if proc.returncode != 0:
            ok = args[0] == "add" and "--priority" in args  # the deliberate failure
            print("STDERR:", proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "")

    print("\nScratch data file contents:")
    print(Path(scratch).read_text(encoding="utf-8").strip())
finally:
    os.unlink(scratch)

sys.exit(0 if ok else 1)
