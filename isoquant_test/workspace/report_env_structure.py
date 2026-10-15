"""Read-only structural report: .env contents (masked) and file stats.

Never prints .env content -- only line types and counts, so secrets in
comments would be detected but not exposed.
"""

import os

def env_report(path):
    if not os.path.exists(path):
        return f"{path}: MISSING"
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    blank = comment = assignment = other = 0
    for line in lines:
        s = line.strip()
        if not s:
            blank += 1
        elif s.startswith("#"):
            comment += 1
        elif "=" in s:
            assignment += 1
        else:
            other += 1
    return (f"{path}: {len(lines)} line(s) -> "
            f"blank={blank}, comment={comment}, assignment={assignment}, other={other}")

print(env_report(".env"))
print(env_report(".env.example"))

# File stats for the files whose behaviour looked odd.
for p in ("check_env_gitignore.py", "access.txt", ".gitignore"):
    if os.path.exists(p):
        size = os.path.getsize(p)
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            nlines = sum(1 for _ in fh)
        print(f"{p}: exists, {size} bytes, {nlines} line(s)")
    else:
        print(f"{p}: MISSING")
