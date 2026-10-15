"""Read-only check: list the NAMES of variables defined in .env.

Values are never printed -- only the key names and a redacted shape,
so this is safe to run and show. It also flags any key whose name
mentions fyers (case-insensitive).
"""

import os

ENV_PATH = ".env"

if not os.path.exists(ENV_PATH):
    print(f"{ENV_PATH} does not exist.")
    raise SystemExit(0)

with open(ENV_PATH, "r", encoding="utf-8", errors="replace") as fh:
    lines = fh.readlines()

keys = []
fyers_hits = []
for i, line in enumerate(lines, start=1):
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        continue
    if "=" not in stripped:
        continue
    name, _, value = stripped.partition("=")
    name = name.strip()
    value = value.strip()
    keys.append(name)
    # Redacted preview: show length and first character only, never the value.
    shape = f"<{len(value)} chars, starts with '{value[:1]}'>" if value else "<empty>"
    marker = "  <-- FYERS-RELATED KEY NAME" if "fyers" in name.lower() else ""
    print(f".env:{i}: {name} = {shape}{marker}")
    if "fyers" in name.lower():
        fyers_hits.append(name)

print(f"\nTotal variables defined in {ENV_PATH}: {len(keys)}")
if fyers_hits:
    print(f"Fyers-related variable names found: {fyers_hits}")
else:
    print("No fyers-related variable names found in .env.")
