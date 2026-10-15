"""Verify that a credential/token exists -- without exposing it.

Read-only check of ``access.txt``.  Reports ONLY non-sensitive facts:

    - whether the file exists
    - whether it contains a non-empty value
    - its length in characters and a coarse "shape" description
      (e.g. "64 hex characters")
    - how old it is (seconds since last write)

The credential value itself is NEVER printed, logged, or echoed.
"""

import os
import re
import sys

TOKEN_PATH = "access.txt"


def shape(token):
    """Return a coarse description of the token format (no content)."""
    if re.fullmatch(r"[0-9a-fA-F]+", token):
        return f"{len(token)} hex characters"
    if re.fullmatch(r"[A-Za-z0-9_-]+", token):
        return f"{len(token)} alphanumeric characters"
    return f"{len(token)} characters (mixed/unrecognized charset)"


def main():
    if not os.path.isfile(TOKEN_PATH):
        print(f"token file: {TOKEN_PATH} -- MISSING")
        return 1

    with open(TOKEN_PATH, "r", encoding="utf-8") as fh:
        token = fh.read().strip()

    if not token:
        print(f"token file: {TOKEN_PATH} -- exists but is EMPTY")
        return 1

    age = None
    try:
        age = max(0.0, os.path.getmtime(TOKEN_PATH))
    except OSError:
        pass

    print(f"token file: {TOKEN_PATH}")
    print(f"  exists:        yes")
    print(f"  non-empty:     yes")
    print(f"  format:        {shape(token)}")
    if age is not None:
        import time
        print(f"  last written:  {int(time.time() - age)}s ago")
    print("value: [REDACTED -- not displayed]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
