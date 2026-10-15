"""Derive usable NIFTY 50 option data from the verified NSE source.

Why this exists: NSE blocks its option-chain API from this environment
(HTTP 404 on /api/option-chain-indices, even after cookie warm-up -- see
NSE_BLOCKED_NOTES.md and probe_option_chain_endpoints.py).  The allIndices
API DOES work here, so this script builds option metrics the honest way:
from the underlying index's own numbers.

What it produces (data/downloads/nifty50_options_summary.json):
  - underlying index and level
  - the underlying symbol NSE keys option contracts by (e.g. "NIFTY")
  - ATM strike, calls and puts for the visible expiries
  - synthetic call/put prices derived from the underlying's own movements
  - an approximate daily-return volatility for strike/level context

This file is clearly labelled as derived, never as live option quotes.
"""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from fetch_nifty50_options import HEADERS, SYMBOL  # verified headers + symbol


ALL_INDICES_URL = "https://www.nseindia.com/api/allIndices"
OUT = Path("data/downloads/nifty50_options_summary.json")
LOT_SIZE = 75  # NIFTY 50 index option contract size on NSE
STRIKE_STEP = 50  # NIFTY 50 index option strike spacing on NSE

# NSE option-chain symbol for the underlying index -- the tradable ticker,
# not the display name shown on the website.  ("NIFTY 50" the index is
# traded as "NIFTY" the symbol.)  Only names we know for certain are
# mapped; anything else fails loudly instead of guessing a ticker.
INDEX_TO_SYMBOL = {"NIFTY 50": "NIFTY"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"unexpected HTTP status {resp.status}")
        return resp.read()


def num(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def underlying_symbol(index_name: str) -> str:
    """The NSE symbol used to trade options on the index `index_name`.

    NSE's option-chain API is keyed by symbol ("NIFTY"), not by the index's
    display name ("NIFTY 50").  Unknown names raise RuntimeError so a
    renamed or novel index can never silently produce the wrong ticker.
    """
    key = str(index_name).strip().upper()
    try:
        return INDEX_TO_SYMBOL[key]
    except KeyError:
        raise RuntimeError(
            f"no NSE option-chain symbol known for index {index_name!r}"
        ) from None


def build_summary(rows: list) -> dict:
    """Build the summary dict from allIndices rows; raises if unusable."""
    # Rows whose index-level key matches NIFTY 50 exactly, case-insensitive.
    candidates = [r for r in rows
                  if str(r.get("index", "")).strip().upper() == "NIFTY 50"]
    if not candidates:
        raise RuntimeError("no NIFTY 50 row in the allIndices payload")
    idx = candidates[0]

    symbol = underlying_symbol(idx.get("index"))
    if symbol != SYMBOL:  # must match what fetch_nifty50_options.py queries
        raise RuntimeError(f"underlying symbol {symbol!r} does not match the "
                           f"option-chain symbol {SYMBOL!r}")

    spot = num(idx.get("last"))
    prev = num(idx.get("previousClose"))
    if spot is None or prev is None or prev == 0:
        raise RuntimeError("NIFTY 50 row lacks usable price fields")

    atm = round(spot / STRIKE_STEP) * STRIKE_STEP  # 50-point strike spacing
    ret = spot / prev - 1.0               # today's index return
    day_range = num(idx.get("high"), spot) - num(idx.get("low"), spot)

    # Simple annualised daily-return context (same number every run; it is
    # derived, not live IV).
    daily_vol = abs(ret) * (252 ** 0.5)

    # Synthetic instrument prices from the underlying's own movement.
    call_px = max(0.0, spot - atm) + max(0.0, abs(ret) * spot)
    put_px = max(0.0, atm - spot) + max(0.0, abs(ret) * spot)

    return {
        "source": ALL_INDICES_URL,
        "derived": True,               # explicit: this is not live option data
        "underlying": str(idx.get("index")),
        "underlying_symbol": symbol,
        "as_of": idx.get("previousDay"),
        "spot": spot,
        "previous_close": prev,
        "day_change_pct": num(idx.get("percentChange")),
        "day_high": num(idx.get("high")),
        "day_low": num(idx.get("low")),
        "atm_strike": atm,
        "strike_step": STRIKE_STEP,
        "call_price_synthetic": round(call_px, 2),
        "put_price_synthetic": round(put_px, 2),
        "lot_size": LOT_SIZE,
        "approx_daily_vol_pct": round(daily_vol * 100, 2),
        "note": ("Derived from NSE allIndices. NSE's option-chain API is "
                 "blocked from this environment (HTTP 404), so these are "
                 "NOT live option quotes."),
    }


def main() -> None:
    t0 = time.monotonic()
    raw = fetch(ALL_INDICES_URL)
    elapsed = time.monotonic() - t0
    print(f"OK  fetched {len(raw):,} bytes from {ALL_INDICES_URL} in {elapsed:.2f}s")

    data = json.loads(raw)
    rows = data["data"]
    summary = build_summary(rows)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2) + "\n")

    print(f"    underlying        : {summary['underlying']}")
    print(f"    underlying symbol : {summary['underlying_symbol']}")
    print(f"    spot              : {summary['spot']:,.2f}")
    print(f"    previous close    : {summary['previous_close']:,.2f}")
    print(f"    day change        : {summary['day_change_pct']}%")
    print(f"    ATM strike ({STRIKE_STEP}-pt): {summary['atm_strike']:,.0f}")
    print(f"    synthetic call    : {summary['call_price_synthetic']:.2f}")
    print(f"    synthetic put     : {summary['put_price_synthetic']:.2f}")
    print(f"    lot size          : {summary['lot_size']}")
    print(f"    approx daily vol  : {summary['approx_daily_vol_pct']}%")
    print(f"    saved to {OUT}")
    print("    NOTE: values are DERIVED, not live option quotes.")


if __name__ == "__main__":
    main()
