"""Fetch the NIFTY 50 index option chain from the required source:
NSE India (www.nseindia.com).

This script deliberately does NOT fall back to any other exchange or data
provider.  If NSE India is unreachable, it fails loudly instead.

Endpoint: https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY
Output  : data/downloads/nse_nifty50_option_chain.json

The console output shows the underlying's spot value, the list of expiry
dates, the put-call ratio (PCR), and a window of strikes around the money
with each side's last price, open interest and IV.
"""
import json
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

HOST = "www.nseindia.com"
SYMBOL = "NIFTY"
URL = (f"https://{HOST}/api/option-chain-indices?"
       + urllib.parse.urlencode({"symbol": SYMBOL}))
OUT = Path("data/downloads/nse_nifty50_option_chain.json")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"https://{HOST}/",
}


def fetch() -> bytes:
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"unexpected HTTP status {resp.status}")
        return resp.read()


def num(value):
    """Coerce NSE's sometimes-string numbers to float (None if unusable)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt(value, width=8, decimals=2):
    v = num(value)
    return f"{v:>{width},.{decimals}f}" if v is not None else " " * width


def strike_window(records, half_width):
    """Strikes nearest the underlying value, `half_width` on each side."""
    underlying = num(records.get("underlyingValue"))
    if underlying is None:
        return [], None

    strikes = sorted({num(row.get("strikePrice"))
                      for row in records.get("data", [])
                      if num(row.get("strikePrice")) is not None})

    closest = min(strikes, key=lambda s: abs(s - underlying))
    lo, hi = closest - half_width, closest + half_width
    window = [s for s in strikes if lo <= s <= hi]
    return window, underlying


def main() -> None:
    t0 = time.monotonic()
    try:
        raw = fetch()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"FAIL: NSE India blocked the request (HTTP {exc.code}). "
                         "No fallback source is permitted.") from exc
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"FAIL: could not reach NSE India: {exc}") from exc

    # ---- persist FIRST, so raw data survives even if validation fails ----
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(raw)

    elapsed = time.monotonic() - t0
    print(f"OK  fetched {len(raw):,} bytes from {URL} in {elapsed:.2f}s")
    print(f"    saved to {OUT}")

    # ---- validate --------------------------------------------------------
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"FAIL: response is not valid JSON: {exc}") from exc

    if not {"records", "data"} <= set(data.keys()):
        raise SystemExit(f"FAIL: unexpected payload shape, keys={sorted(data.keys())}")

    records = data["records"]
    if str(records.get("underlying", "")).upper() != SYMBOL:
        raise SystemExit("FAIL: payload is not NIFTY option chain data "
                         f"(underlying={records.get('underlying')!r}).")

    print(f"    instrument    : {records.get('underlying')}")
    print(f"    spot          : {records.get('underlyingValue')}")
    print(f"    server time   : {data.get('timestamp')}")

    expiries = records.get("expiryDates") or []
    print(f"    expiries      : {len(expiries)}"
          + (f"  (next: {expiries[0]})" if expiries else ""))

    filtered = data.get("filtered")
    if isinstance(filtered, dict) and filtered.get("data"):
        pcr = num(filtered.get("PCR"))
        if pcr is not None:
            print(f"    PCR (nearest) : {pcr:.2f}")
        nearest_expiry = expiries[0] if expiries else None
        print(f"    contracts in nearest expiry: {len(filtered['data'])}")

    # ---- strike window around the money ----------------------------------
    rows = {num(r.get("strikePrice")): r
            for r in records.get("data", []) if num(r.get("strikePrice")) is not None}
    window, underlying = strike_window(records, half_width=2)
    if not window:
        print("    note: no strike data available")
        return

    print("\n    Strikes around the money "
          f"(spot {underlying:,.2f}):")
    print("    " + "strike   | CE last   CE OI | PE last   PE OI")
    for strike in window:
        row = rows[strike]
        ce, pe = row.get("CE") or {}, row.get("PE") or {}
        print(f"    {strike:7,.0f} | {fmt(ce.get('lastPrice'))} "
              f"{fmt(ce.get('openInterest'), 7, 0)} | "
              f"{fmt(pe.get('lastPrice'))} {fmt(pe.get('openInterest'), 7, 0)}")


if __name__ == "__main__":
    main()
