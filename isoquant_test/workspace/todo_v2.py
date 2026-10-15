"""Market data scope -- locked to version 1.

Status: LOCKED. This project implements version 1 only.

Version 1 scope (implemented)
-----------------------------
1. Market-data retrieval (fetch from the source over HTTP).
2. Local storage (save the retrieved data to files on disk).

Anything beyond that -- analytics, dashboards, alerts, brokers, trading,
jobs/scheduling -- is out of scope for this version.

Source behaviour (unchanged, by design)
---------------------------------------
- Data comes only from NSE India (www.nseindia.com), which this
  environment can reach at /api/allIndices.
- No fallback to any other exchange or data provider, ever.
- Note: NSE's option-chain API is blocked here (see NSE_BLOCKED_NOTES.md),
  so only allIndices-based retrieval is in scope for version 1.

Run with --check to verify the lock and the implemented scope.
"""
from pathlib import Path

STATUS = "LOCKED"
SCOPE = [
    "1. Market-data retrieval (fetch from the source over HTTP).",
    "2. Local storage (save the retrieved data to files on disk).",
]
OUT_OF_SCOPE = [
    "analytics, dashboards, alerts, brokers, trading, jobs/scheduling",
]
SOURCE = "https://www.nseindia.com/api/allIndices"


def check() -> bool:
    """Verify the locked scope actually exists in the current codebase."""
    ok = True

    def report(condition, message):
        nonlocal ok
        if not condition:
            ok = False
        print(f"  [{'PASS' if condition else 'FAIL'}] {message}")

    print(f"Version 1 status: {STATUS}")
    print("Implemented scope:")
    for line in SCOPE:
        print(f"  {line}")

    print("Checks:")

    # 1. Retrieval + storage entry points exist.
    report(Path("fetch_nse_indices.py").is_file(),
           "retrieval script present (fetch_nse_indices.py)")
    report(Path("data/downloads").is_dir(),
           "local storage directory present (data/downloads/)")

    # 2. Data actually stored locally.
    stored = Path("data/downloads/nse_all_indices.json")
    report(stored.is_file() and stored.stat().st_size > 0,
           "market data stored locally (data/downloads/nse_all_indices.json)")

    print(f"Data source (no fallback permitted): {SOURCE}")
    print("Out of scope for version 1: " + ", ".join(OUT_OF_SCOPE))
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if check() else 1)
