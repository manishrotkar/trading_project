"""Fetch the LTP (Last Traded Price) of a NSE India index.

The required source is NSE India (www.nseindia.com).  NSE blocks the
option-chain API from this environment (see NSE_BLOCKED_NOTES.md), but the
official /api/allIndices endpoint works and carries each index's latest
traded level ("last") -- the LTP -- together with the previous close and the
day's change, high and low.

Endpoint: https://www.nseindia.com/api/allIndices
Output  : data/downloads/ltp.json  (one LTP record for the chosen index)

Usage:
    python ltp.py                 # LTP of NIFTY 50 (the default)
    python ltp.py "NIFTY BANK"    # LTP of any index in the payload

This script deliberately does NOT fall back to any other exchange or data
provider.  If NSE India is unreachable, it fails loudly instead.  The
matching is an exact, case-insensitive match on NSE's own index name --
nothing is guessed or substituted.
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from fetch_nifty50_options import HEADERS  # reuse the verified headers

HOST = "www.nseindia.com"
URL = f"https://{HOST}/api/allIndices"
OUT = Path("data/downloads/ltp.json")

DEFAULT_INDEX = "NIFTY 50"


def fetch(url: str = URL) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"unexpected HTTP status {resp.status}")
        return resp.read()


def num(value, default=None):
    """Coerce NSE's sometimes-string numbers to float (default if unusable)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def find_index(rows, index_name: str) -> dict:
    """Return the row for `index_name` (exact, case-insensitive).

    Raises RuntimeError when the name is absent -- a renamed index must fail
    loudly rather than silently return another index's price.
    """
    wanted = str(index_name).strip().upper()
    for row in rows:
        if str(row.get("index", "")).strip().upper() == wanted:
            return row
    nifty_names = [str(r.get("index")) for r in rows
                   if "NIFTY" in str(r.get("index", "")).upper()]
    hint = (f"  Available NIFTY-branded names: {nifty_names[:6]}"
            if nifty_names else "")
    raise RuntimeError(f"index {index_name!r} not found in the payload.{hint}")


def build_ltp(row: dict) -> dict:
    """Build the LTP record from one allIndices row; raises if unusable."""
    ltp = num(row.get("last"))
    if ltp is None or ltp <= 0:
        raise RuntimeError(
            f"row for {row.get('index')!r} has no usable 'last' price "
            f"(got {row.get('last')!r})")

    prev = num(row.get("previousClose"))
    return {
        "index": str(row.get("index")),
        "ltp": ltp,
        "previous_close": prev,
        "change": round(ltp - prev, 2) if prev is not None else None,
        "change_pct": num(row.get("percentChange")),
        "day_high": num(row.get("high")),
        "day_low": num(row.get("low")),
        "previous_day": row.get("previousDay"),
    }


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) > 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    index_name = argv[0] if argv else DEFAULT_INDEX

    t0 = time.monotonic()
    try:
        raw = fetch()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"FAIL: NSE India blocked the request (HTTP {exc.code}). "
                         "No fallback source is permitted.") from exc
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"FAIL: could not reach NSE India: {exc}") from exc

    elapsed = time.monotonic() - t0
    print(f"OK  fetched {len(raw):,} bytes from {URL} in {elapsed:.2f}s")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"FAIL: response is not valid JSON: {exc}") from exc

    rows = data.get("data")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("FAIL: unexpected payload shape (no 'data' rows).")

    if not any("NIFTY" in str(r.get("index", "")).upper() for r in rows):
        raise SystemExit("FAIL: no NIFTY rows -- this is not NSE India data.")

    try:
        record = build_ltp(find_index(rows, index_name))
    except RuntimeError as exc:
        raise SystemExit(f"FAIL: {exc}") from exc

    record.update({
        "source": URL,
        "server_timestamp": data.get("timestamp"),
        "field": "last (NSE allIndices) -- the index's latest traded level",
        # allIndices carries the real level, unlike the option-chain metrics,
        # which this repo has to derive because that API is blocked (404).
        "live": True,
        "fetched_bytes": len(raw),
        "elapsed_seconds": round(elapsed, 2),
    })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2) + "\n")

    chg = record["change"]
    chg_s = f"{chg:+,.2f} pts" if chg is not None else "n/a"
    pct = record["change_pct"]
    pct_s = f"{pct:+.2f}%" if pct is not None else "n/a"
    prev_s = record["previous_close"]
    prev_s = f"{prev_s:,.2f}" if prev_s is not None else "n/a"
    print(f"    index           : {record['index']}")
    print(f"    LTP             : {record['ltp']:,.2f}")
    print(f"    previous close  : {prev_s}")
    print(f"    change          : {chg_s}  ({pct_s})")
    print(f"    day range       : {record['day_low']} - {record['day_high']}")
    print(f"    server timestamp: {record['server_timestamp']}")
    print(f"    saved to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
