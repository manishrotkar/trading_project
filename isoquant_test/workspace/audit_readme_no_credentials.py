"""Verify rule 6: README.md files must not contain credentials or tokens.

Scans every README.md in the workspace (any directory) for:
  1. The exact secret value stored in access.txt (never printed — output is
     redacted, the same way audit_no_secrets.py does it).
  2. Credential-shaped content: key/value assignments, Bearer tokens, JWTs,
     private-key blocks, and long hex/base64-looking strings.

Placeholder-style example values (your-password-here, <TOKEN>, xxxx, ...)
are allowed, so documented setup examples do not cause false alarms.

Exit code 0 = clean, 1 = at least one problem found.
"""

import os
import re

SECRET_FILE = "access.txt"
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", "node_modules",
             ".venv", "venv"}

# key = value / "key": value   (assignment-style credentials)
KEY_VALUE = re.compile(
    r"""(?:api[_-]?key|apikey|secret(?:[_-]?key)?|password|passwd|pwd|
        access[_-]?token|auth[_-]?token|refresh[_-]?token|client[_-]?secret|
        token)\s*[:=]\s*(?P<value>\S+)""",
    re.IGNORECASE | re.VERBOSE,
)
BEARER = re.compile(r"[Bb]earer\s+(?P<value>[A-Za-z0-9._~+/=-]{8,})")
JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
HEX64 = re.compile(r"\b[A-Fa-f0-9]{48,}\b")   # >= 48 hex chars: real key,
                                              # not a git SHA (40) or short id
B64 = re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b")

# Values that are clearly examples, not real credentials.
PLACEHOLDER_HINTS = ("<", ">", "your", "xxx", "xxxx", "example", "changeme",
                     "placeholder", "****", "••••", "…", "$(", "${", "{{")

# Documentation lines that mention the words but never show a value.
DOC_HINTS = ("never commit", "no credentials", "gitignored", "gitignore",
             "redacted", "placeholder", "rule 6")


def load_secret():
    with open(SECRET_FILE, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read().strip()


def redact(text):
    """Replace the known secret with a fixed placeholder before printing."""
    return text.replace(secret, "[REDACTED]").rstrip()


def is_placeholder(value):
    low = value.lower()
    return any(h in low for h in PLACEHOLDER_HINTS)


def check_line(path, lineno, line):
    """Return a reason string if the line looks like it embeds credentials."""
    if any(h in line.lower() for h in DOC_HINTS):
        return None
    if secret and secret in line:
        return "known secret value from access.txt"

    m = KEY_VALUE.search(line)
    if m and not is_placeholder(m.group("value")):
        return f"credential assignment (value '{m.group('value')}')"
    if PRIVATE_KEY.search(line):
        return "private key block"
    if JWT.search(line):
        return "JWT token"
    m = BEARER.search(line)
    if m and not is_placeholder(m.group("value")):
        return f"bearer token (value '{m.group('value')}')"
    if HEX64.search(line):
        return "long hex string (possible key/hash)"
    m = B64.search(line)
    if m and not is_placeholder(m.group("value")) and "=" not in line:
        return f"long base64-like string (value '{m.group('value')}')"
    return None


def iter_readmes():
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.upper() == "README.MD":
                yield os.path.join(root, name)


def main():
    global secret
    secret = load_secret()
    print("Loaded the known secret from access.txt (value hidden).")

    findings = []
    scanned = 0
    for path in iter_readmes():
        scanned += 1
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, start=1):
                reason = check_line(path, lineno, line)
                if reason:
                    findings.append((path, lineno, reason, redact(line)))

    print(f"Scanned {scanned} README.md file(s).")
    if findings:
        print(f"\nFAIL: {len(findings)} credential/tokens finding(s):\n")
        for path, lineno, reason, text in findings:
            print(f"  {path}:{lineno}: {reason}")
            print(f"      {text}")
        raise SystemExit(1)
    print("\nPASS: no credentials or tokens found in any README.md.")


if __name__ == "__main__":
    main()
