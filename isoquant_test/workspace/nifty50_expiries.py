"""Add NIFTY 50 option expiry dates to the options summary.

The options summary (data/downloads/nifty50_options_summary.json) is built
by nifty50_options_summary.py from NSE's allIndices endpoint, because the
option-chain API is blocked from this environment (HTTP 404 -- see
NSE_BLOCKED_NOTES.md).  That summary lists the ATM strike and the synthetic
call/put prices, but not *which* expiry dates NIFTY 50 index options have.

This script fills that gap.  NSE lists NIFTY 50 index options with weekly
contracts that expire on **Tuesday** of every week (a trading-holiday
Tuesday rolls the expiry to the previous trading day).  The option-chain
API being blocked means the expiries cannot be read from the chain itself,
so they are derived here from the calendar:

    next_expiry(from_date, offset) = from_date + offset weeks,
        rolled forward to the next Tuesday if needed

  - offset 0: the next upcoming expiry -- today, if today IS a Tuesday
    (that contract expires today), otherwise the nearest Tuesday AFTER
    today.  e.g. from Thursday 01-Oct-2026 the next expiry is 06-Oct-2026.
  - offset 1..n-1: the following weeks' Tuesdays, always exactly 7 days
    apart.

This script does not refetch anything.  It reads the existing summary,
inserts an "expiries" list (nearest first, DD-MMM-YYYY format, matching the
summary's as_of style), and writes it back.  Everything else in the file is
left exactly as it is.  Like the rest of the summary, the result is
DERIVED context, not live option-chain data.
"""
import calendar
import datetime
import json
from pathlib import Path

SUMMARY_PATH = Path("data/downloads/nifty50_options_summary.json")
# NIFTY 50 index options expire on Tuesdays (calendar: 0=Mon .. 6=Sun).
CONTRACT_EXPIRY_WEEKDAY = calendar.TUESDAY
KEY_AFTER = "as_of"  # "expiries" is inserted right after this key, if present


def next_expiry(from_date: datetime.date, offset: int = 0,
                fmt: str = "%d-%b-%Y") -> str:
    """Contract-expiry date at `offset` weeks from `from_date`, as a string.

    Returns the Tuesday of the contract week `offset` weeks from
    `from_date` -- the next Tuesday on or after that day (today itself,
    when today is a Tuesday) -- formatted as DD-MMM-YYYY, e.g. "06-Oct-2026".
    """
    day = from_date + datetime.timedelta(weeks=offset)
    day += datetime.timedelta(days=(CONTRACT_EXPIRY_WEEKDAY - day.weekday()) % 7)
    return day.strftime(fmt)


def expiries_list(n: int = 3) -> list:
    """The nearest `n` NIFTY 50 option expiry dates, nearest first."""
    today = datetime.date.today()
    return [next_expiry(today, offset=k) for k in range(n)]


def add_expiries(summary: dict, n: int = 3) -> dict:
    """Return a copy of `summary` with an "expiries" key added.

    All existing keys and values are kept as they are; "expiries" is placed
    directly after "as_of" when that key exists (otherwise appended).
    """
    out = {}
    inserted = False
    for key, value in summary.items():
        out[key] = value
        if key == KEY_AFTER and not inserted:
            out["expiries"] = expiries_list(n)
            inserted = True
    if not inserted:
        out["expiries"] = expiries_list(n)
    return out


def main() -> None:
    if not SUMMARY_PATH.exists():
        raise SystemExit(f"FAIL: {SUMMARY_PATH} not found -- run "
                         "nifty50_options_summary.py first.")

    try:
        summary = json.loads(SUMMARY_PATH.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"FAIL: {SUMMARY_PATH} is not valid JSON: {exc}") from exc

    if not isinstance(summary, dict) or not summary:
        raise SystemExit(f"FAIL: unexpected summary shape in {SUMMARY_PATH}")

    updated = add_expiries(summary, n=3)

    SUMMARY_PATH.write_text(json.dumps(updated, indent=2) + "\n")

    print(f"OK  expiries added to {SUMMARY_PATH}")
    print(f"    today (local run date): {datetime.date.today():%d-%b-%Y}")
    for offset, expiry in enumerate(updated["expiries"]):
        print(f"    nearest expiry #{offset + 1}: {expiry}")
    print("    everything else in the summary is unchanged.")
    print("    NOTE: expiries are derived from NSE's weekly Tuesday "
          "contract calendar, not read from the (blocked) option-chain API.")


if __name__ == "__main__":
    main()
