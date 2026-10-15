"""Scan the workspace for references to access.txt, tokens, or auth.

Read-only audit, same style as scan_fyers_refs.py.
"""

import os

SKIP_DIRS = {
    "__pycache__", ".git", ".pytest_cache",
    "node_modules", ".venv", "venv",
}
SKIP_SUFFIXES = {".pyc", ".pyo"}

KEYWORDS = ["access.txt", "access_token", "auth", "token"]

hits = []
files_scanned = 0

for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for name in files:
        if os.path.splitext(name)[1].lower() in SKIP_SUFFIXES:
            continue
        path = os.path.join(root, name)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError as exc:
            print(f"[unreadable] {path}: {exc}")
            continue
        files_scanned += 1
        for i, line in enumerate(lines, start=1):
            low = line.lower()
            if any(k in low for k in KEYWORDS):
                hits.append((path, i, line.rstrip()))

print(f"Scanned {files_scanned} files.")
if hits:
    print(f"\n{len(hits)} matching line(s):\n")
    for path, lineno, text in hits:
        print(f"{path}:{lineno}: {text}")
else:
    print("\nNo matches for access.txt / token / auth anywhere.")
