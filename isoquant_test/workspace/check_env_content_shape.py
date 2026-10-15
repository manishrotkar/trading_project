"""Read-only: count content lines in .env without revealing any of them."""

from pathlib import Path

p = Path(".env")
if not p.exists():
    print(".env does not exist.")
else:
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    total = len(lines)
    content = [l for l in lines if l.strip() and not l.strip().startswith("#")]
    blank = sum(1 for l in lines if not l.strip())
    comments = total - len(content) - blank
    print(f".env: {total} line(s) -> {content and 'KEY=value' or 'no'} "
          f"content lines: {len(content)}, comments: {comments}, blank: {blank}")
    print("All content lines are comments/placeholders." if not content
          else "There are KEY=value lines; names would be listed by inspect_env_keys.py.")
