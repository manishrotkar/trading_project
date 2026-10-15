"""Quick smoke check for the new project (run from workspace root)."""

import json
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent

print("== CLI on sample.txt (text mode) ==")
result = subprocess.run(
    [sys.executable, "-m", "textstats.cli", "sample.txt"],
    capture_output=True,
    text=True,
    cwd=PROJECT,
)
print(result.stdout, end="")
if result.returncode != 0:
    sys.exit(result.stderr)

print("== CLI on sample.txt (JSON mode) ==")
result = subprocess.run(
    [sys.executable, "-m", "textstats.cli", "sample.txt", "--json"],
    capture_output=True,
    text=True,
    cwd=PROJECT,
)
print(json.dumps(json.loads(result.stdout), indent=2))
if result.returncode != 0:
    sys.exit(result.stderr)

print("== Import check ==")
sys.path.insert(0, str(PROJECT))
from textstats import analyze  # noqa: E402

sample = analyze("the quick brown fox\nthe lazy dog")
assert sample["top_word"] == "the" and sample["top_word_count"] == 2
print("analyze() OK:", sample)
print("\nAll smoke checks passed.")
