"""Verify rule 4: no credentials or access tokens appear in source code.

Reads access.txt only at runtime to learn what the secret looks like, then
scans every other workspace text file for that value. Matches are reported
as file:line with the matched text REDACTED, so the secret is never printed
into tool output either.

Exit code 0 = clean, 1 = at least one embedded secret found.
"""

import os

SECRET_FILE = "access.txt"
SKIP_DIRS = {
    "__pycache__", ".git", ".pytest_cache",
    "node_modules", ".venv", "venv",
}
SKIP_SUFFIXES = {".pyc", ".pyo"}
MIN_LEN = 8  # ignore trivially short strings that cannot be real secrets


def load_secrets():
    """Return the candidate secret strings found in access.txt."""
    with open(SECRET_FILE, "r", encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    secrets = set()
    whole = raw.strip()
    if len(whole) >= MIN_LEN:
        secrets.add(whole)
    for line in raw.splitlines():
        s = line.strip()
        if len(s) >= MIN_LEN:
            secrets.add(s)
    return secrets


def iter_files():
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if os.path.splitext(name)[1].lower() in SKIP_SUFFIXES:
                continue
            yield os.path.join(root, name)


def redact(text, secrets):
    """Replace any embedded secret with a fixed placeholder."""
    out = text
    for s in secrets:
        out = out.replace(s, "[REDACTED]")
    return out.rstrip()


def main():
    secrets = load_secrets()
    print(f"Loaded {len(secrets)} candidate secret value(s) from {SECRET_FILE} "
          f"(values hidden).")

    matches = []
    scanned = 0
    for path in iter_files():
        if os.path.abspath(path) == os.path.abspath(SECRET_FILE):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError as exc:
            print(f"[unreadable] {path}: {exc}")
            continue
        scanned += 1
        for i, line in enumerate(lines, start=1):
            if any(s in line for s in secrets):
                matches.append((path, i, redact(line, secrets)))

    print(f"Scanned {scanned} file(s).")
    if matches:
        print(f"\nFAIL: {len(matches)} line(s) contain an embedded secret:\n")
        for path, lineno, text in matches:
            print(f"  {path}:{lineno}: {text}")
        raise SystemExit(1)
    print("\nPASS: no credentials or access tokens embedded in any source file.")


if __name__ == "__main__":
    main()
