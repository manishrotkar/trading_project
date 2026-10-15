"""Fetch index data from the required source: NSE India (www.nseindia.com).

This script deliberately does NOT fall back to any other exchange or data
provider.  If NSE India is unreachable, it fails loudly instead.

Endpoint: https://www.nseindia.com/api/allIndices
Output  : data/downloads/nse_all_indices.json
"""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

HOST = "www.nseindia.com"
URL = f"https://{HOST}/api/allIndices"
OUT = Path("data/downloads/nse_all_indices.json")

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

    if not {"data", "timestamp"} <= set(data.keys()):
        raise SystemExit(f"FAIL: unexpected payload shape, keys={sorted(data.keys())}")

    indices = data["data"]
    print(f"    indices returned : {len(indices)}")
    print(f"    server timestamp : {data.get('timestamp')}")

    # Source identity check: NSE India uses the 'NIFTY' brand.  Verify by
    # substring so minor label variations ('NIFTY 50', 'NIFTY NEXT 50', ...)
    # still pass, while a different exchange (e.g. BSE 'SENSEX') would fail.
    nifty_count = sum(1 for r in indices if "NIFTY" in str(r.get("index", "")).upper())
    print(f"    NIFTY-branded rows: {nifty_count}")
    if nifty_count == 0:
        raise SystemExit("FAIL: no NIFTY rows -- this is not NSE India data.")

    print("\n    sample rows:")
    for row in indices[:5]:
        print(f"      {str(row.get('index')):<28} last={row.get('last')} "
              f"change={row.get('percentChange')}%")

    exact = next((r for r in indices if str(r.get("index", "")).upper() == "NIFTY 50"), None)
    if exact:
        print(f"\n    NIFTY 50: last={exact.get('last')}  "
              f"change={exact.get('percentChange')}%  "
              f"(open={exact.get('open')}, high={exact.get('high')}, low={exact.get('low')})")
    else:
        print("\n    note: no exact 'NIFTY 50' label; check sample rows above")


if __name__ == "__main__":
    main()
