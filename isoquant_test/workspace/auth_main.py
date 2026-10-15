"""Authentication cycle CLI.

Usage:
    python auth_main.py refresh          new session: replace the token in access.txt
    python auth_main.py show             print the current token (if any)
    python auth_main.py verify           check the token and report its age
    python auth_main.py cycle            refresh only if expired (ensure_fresh_token)

The file can be overridden with the ACCESS_TOKEN_FILE environment variable.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "auth"))

from token_manager import (  # noqa: E402
    DEFAULT_PATH,
    DEFAULT_TTL_SECONDS,
    TokenError,
    ensure_fresh_token,
    read_token,
    refresh_token,
    token_age,
)

FILE = os.environ.get("ACCESS_TOKEN_FILE", DEFAULT_PATH)


def main(argv):
    if not argv:
        print(__doc__.strip())
        return 2

    cmd = argv[0]

    try:
        if cmd == "refresh":
            token = refresh_token(FILE)
            print(f"access.txt replaced with new token: {token}")
            return 0

        if cmd == "show":
            token = read_token(FILE)
            if token is None:
                print("no token yet - run: python auth_main.py refresh")
                return 1
            print(token)
            return 0

        if cmd == "verify":
            token = read_token(FILE)
            if token is None:
                print("no token yet - run: python auth_main.py refresh")
                return 1
            age = token_age(FILE)
            fresh = "fresh" if age < DEFAULT_TTL_SECONDS else "EXPIRED"
            print(f"token ok, age {age:.0f}s ({fresh})")
            return 0

        if cmd == "cycle":
            token = ensure_fresh_token(FILE)
            age = token_age(FILE)
            print(f"token ready (age {age:.0f}s): {token}")
            return 0

    except (TokenError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"unknown command: {cmd}", file=sys.stderr)
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
