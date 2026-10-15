"""CLI for managing local Fyers credentials.

Usage:
    python fyers_main.py verify   load local credentials and report provenance
    python fyers_main.py check    exit 0 if complete, 1 if any are missing
    python fyers_main.py missing  print the names of missing credentials
    python fyers_main.py template print the placeholder block for .env

Credentials are read from the process environment first, then from the
gitignored ``.env`` file.  No command ever prints a credential value — only
which names are set and where they came from.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fyers.credentials import (  # noqa: E402
    CREDENTIAL_NAMES,
    CredentialError,
    find_missing,
    load_credentials,
    load_template,
)


def main(argv):
    if not argv:
        print(__doc__.strip())
        return 2

    cmd = argv[0]

    if cmd == "template":
        print(load_template(), end="")
        return 0

    if cmd == "missing":
        missing = find_missing()
        if missing:
            print("missing: " + ", ".join(missing))
            return 1
        print("no missing Fyers credentials")
        return 0

    try:
        creds = load_credentials()
    except CredentialError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if cmd in ("verify", "check"):
            return 1
        return 2

    if cmd == "verify":
        print(f"loaded {len(CREDENTIAL_NAMES)} local Fyers credential(s):")
        print(creds.summary())
        return 0

    if cmd == "check":
        print("OK: all local Fyers credentials are configured "
              f"({len(CREDENTIAL_NAMES)}/{len(CREDENTIAL_NAMES)}).")
        return 0

    print(f"unknown command: {cmd}", file=sys.stderr)
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
