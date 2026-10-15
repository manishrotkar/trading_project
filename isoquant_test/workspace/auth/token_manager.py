"""Token manager: store, load, and refresh the access token in access.txt.

The token lives in a plain text file (default ``access.txt``), one token per
file.  Every new session writes a fresh token, so the file always holds the
token of the most recent authentication cycle — in other words, the token in
``access.txt`` is replaced on every refresh, not appended.

No network, no external dependencies: ``new_token()`` generates a token
locally so the cycle is testable end to end.
"""

import os
import secrets
import time
from pathlib import Path

DEFAULT_PATH = "access.txt"

# Token size in random bytes (renders as 64 hex characters).
TOKEN_BYTES = 32

# Optional TTL, in seconds.  Tokens are still replaced on every refresh,
# but the file also records when the token was last written so callers
# can decide whether the token is still fresh enough to use.
DEFAULT_TTL_SECONDS = 60 * 60  # one hour


class TokenError(Exception):
    """Raised when the token file is unreadable or malformed."""


def new_token():
    """Return a new, cryptographically random token string."""
    return secrets.token_hex(TOKEN_BYTES)


def write_token(token, path=DEFAULT_PATH):
    """Atomically replace the token file with ``token``.

    Returns the token.  Uses a temp file + os.replace so a crash can never
    leave a half-written (or partially old) token behind.
    """
    path = Path(path)
    parent = path.parent if str(path.parent) else Path(".")
    parent.mkdir(parents=True, exist_ok=True)

    token = str(token).strip()
    if not token:
        raise ValueError("token must not be empty")

    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(token + "\n")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                os.remove(tmp)
            except OSError:
                pass
    return token


def read_token(path=DEFAULT_PATH):
    """Return the current token, or None if there is none yet."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            token = fh.read().strip()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise TokenError(f"cannot read {path}: {exc}") from exc

    if not token:
        raise TokenError(f"{path} exists but is empty")
    if len(token.splitlines()) > 1:
        raise TokenError(f"{path} contains multiple lines - corrupt token file")
    return token


def token_age(path=DEFAULT_PATH):
    """Seconds since the token file was last written (0.0 if just written)."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    return max(0.0, time.time() - mtime)


def refresh_token(path=DEFAULT_PATH):
    """Generate a new token and replace the one in ``path`` with it.

    Returns the new token.  This is the heart of the authentication cycle:
    every call retires the old token and persists the new one.
    """
    return write_token(new_token(), path)


def is_expired(path=DEFAULT_PATH, ttl=DEFAULT_TTL_SECONDS):
    """True if the token is missing or older than ``ttl`` seconds."""
    token = read_token(path)
    if token is None:
        return True
    age = token_age(path)
    return age is None or age >= ttl


def ensure_fresh_token(path=DEFAULT_PATH, ttl=DEFAULT_TTL_SECONDS):
    """Return a valid token, refreshing (replacing) it only if needed.

    - no token yet  -> create one
    - token expired -> replace it with a new one
    - token valid   -> keep it
    """
    if is_expired(path, ttl):
        return refresh_token(path)
    return read_token(path)
