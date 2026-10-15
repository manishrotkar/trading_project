"""Fetch the closest thing to bid/ask for NIFTY 50 from the required source:
NSE India (www.nseindia.com).

Bid and ask are market maker / depth quotes.  NSE's option-chain API is
blocked from this environment (HTTP 404 -- see NSE_BLOCKED_NOTES.md), and a
verified probe of every working source shows the exchange publishes NO
bid/ask fields anywhere in them:

    /api/allIndices            -> no BID/ASK/OFFER keys (indices are
                                  not quoted instruments at all)
    FO bhavcopy CSV            -> no BID/ASK/OFFER columns in its 34 columns

Rather than invent quotes, this script reports bid/ask explicitly as
unavailable (``bid`` / ``ask`` / ``spread`` = null) alongside the real
fields that bound it -- all from the verified NSE source, never a fallback:

  From /api/allIndices (live):
    LTP, previous close, day high, day low -- the day range brackets
    every executable price the session produced.

  From the official FO bhavcopy (end-of-session):
    the two-sided picture per strike for the ATM row -- call open interest
    vs put open interest, volumes, PCR -- and the closest listed strike.

Output  : data/downloads/nifty50_bid_ask.json
Usage   : python bid_ask.py                 # NIFTY 50 (the default)

Fails loudly if NSE is unreachable or the payload/CSV shape changes.
"""
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from fetch_nifty50_options import HEADERS  # reuse the verified headers
from nifty50_options_summary import ALL_INDICES_URL, LOT_SIZE, STRIKE_STEP

OUT = Path("data/downloads/nifty50_bid_ask.json")
CONTRACTS = Path("data/downloads/nse_nifty50_option_contracts.csv")
DEFAULT_INDEX = "NIFTY 50"
WINDOW = 2  # strikes on each side of the ATM row in the console table

NO_BID_ASK_NOTE = (
    "NSE publishes no bid/ask fields: allIndices has none (indices are not "
    "quoted instruments) and the FO bhavcopy carries no BID/ASK columns. "
    "NSE's live option-chain API, which does show CE/PE bidQty/askQty, is "
    "blocked from this environment (HTTP 404)."
)


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


def find_nifty_row(rows) -> dict:
    """The allIndices row for NIFTY 50 -- exact, case-insensitive."""
    for row in rows:
        if str(row.get("index", "")).strip().upper() == DEFAULT_INDEX:
            return row
    nifty_names = sorted({str(r.get("index")) for r in rows
                          if "NIFTY" in str(r.get("index", "")).upper()})
    raise RuntimeError(f"no {DEFAULT_INDEX!r} row in the payload.  "
                       f"NIFTY-branded names present: {nifty_names[:6]}")


def load_chain_rows() -> list:
    """NIFTY option rows from the verified FO bhavcopy CSV; fails loudly."""
    if not CONTRACTS.exists():
        raise SystemExit(
            f"FAIL: {CONTRACTS} is missing.  Run fetch_nifty50_option_contracts.py "
            "first -- this script never substitutes another source.")
    with CONTRACTS.open(newline="") as f:
        rows = [r for r in csv.DictReader(f)
                if str(r.get("TckrSymb", "")).strip().upper() == "NIFTY"
                and r.get("OptnTp") in ("CE", "PE")]
    if not rows:
        raise SystemExit(f"FAIL: {CONTRACTS} has no NIFTY CE/PE rows.")
    for row in rows:
        row["_strike"] = num(row.get("StrkPric"))
        row["_expiry"] = str(row.get("XpryDt", ""))
        if row["_strike"] is None or not row["_expiry"]:
            raise SystemExit("FAIL: bhavcopy row with unusable strike/expiry -- "
                             "the file's shape may have changed.")
    return rows


def build_record(idx_row: dict, chain_rows: list) -> dict:
    """Assemble the bid/ask record; raises when the data is unusable."""
    ltp = num(idx_row.get("last"))
    if ltp is None or ltp <= 0:
        raise RuntimeError("allIndices row has no usable 'last' price")

    nearest_expiry = min(r["_expiry"] for r in chain_rows)
    chain = [r for r in chain_rows if r["_expiry"] == nearest_expiry]

    oi_by_strike, ce_oi_sum, pe_oi_sum = {}, 0, 0
    for row in chain:
        oi = int(num(row.get("OpnIntrst"), 0))
        vol = int(num(row.get("TtlTradgVol"), 0))
        strike, side = row["_strike"], row["OptnTp"]
        slot = oi_by_strike.setdefault(strike, {"CE": {}, "PE": {}})
        slot[side] = {"open_interest": oi, "volume": vol}
        if side == "CE":
            ce_oi_sum += oi
        else:
            pe_oi_sum += oi
    pcr = round(pe_oi_sum / ce_oi_sum, 4) if ce_oi_sum else None

    listed = sorted(oi_by_strike)
    closest = min(listed, key=lambda s: abs(s - ltp))
    atm = round(ltp / STRIKE_STEP) * STRIKE_STEP
    window = [s for s in listed if abs(s - atm) <= WINDOW * STRIKE_STEP]
    return {
        "index": str(idx_row.get("index")),
        "bid": None,
        "ask": None,
        "spread": None,
        "bid_ask_available": False,
        "reason": NO_BID_ASK_NOTE,
        # the live fields that DO exist -- the day range brackets every
        # price this instrument actually traded at, so any real bid/ask
        # must lie inside it
        "ltp": ltp,
        "previous_close": num(idx_row.get("previousClose")),
        "day_high": num(idx_row.get("high")),
        "day_low": num(idx_row.get("low")),
        "percent_change": num(idx_row.get("percentChange")),
        "server_timestamp": None,  # filled by main()
        "atm_strike": atm,
        "nearest_listed_strike": closest,
        "nearest_expiry": nearest_expiry,
        "strike_step": STRIKE_STEP,
        "strike_window": window,
        "chain": {str(s): oi_by_strike[s] for s in listed},
        "ce_open_interest": ce_oi_sum,
        "pe_open_interest": pe_oi_sum,
        "put_call_ratio_oi": pcr,
        "lot_size": LOT_SIZE,
        "live_source": ALL_INDICES_URL,
        "chain_source": "FO bhavcopy (end-of-session official exchange data)",
        "fetched_bytes": None,
        "elapsed_seconds": None,
        "live": True,
        "bid_ask_note": ("Day high/low above bracket every executable price; "
                         "OI columns below are real end-of-session depth "
                         "context, not quotes."),
    }


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) > 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if argv and argv[0].upper() != DEFAULT_INDEX:
        raise SystemExit(f"FAIL: {argv[0]!r} -- this script reports "
                         f"{DEFAULT_INDEX!r} only.")

    t0 = time.monotonic()
    try:
        raw = fetch(ALL_INDICES_URL)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"FAIL: NSE India blocked the request (HTTP {exc.code}). "
                         "No fallback source is permitted.") from exc
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"FAIL: could not reach NSE India: {exc}") from exc

    elapsed = time.monotonic() - t0
    print(f"OK  fetched {len(raw):,} bytes from {ALL_INDICES_URL} in {elapsed:.2f}s")

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
        record = build_record(find_nifty_row(rows), load_chain_rows())
    except RuntimeError as exc:
        raise SystemExit(f"FAIL: {exc}") from exc

    record.update({
        "server_timestamp": data.get("timestamp"),
        "fetched_bytes": len(raw),
        "elapsed_seconds": round(elapsed, 2),
    })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2) + "\n")

    lo, hi = record["day_low"], record["day_high"]
    print(f"    index            : {record['index']}")
    print(f"    LTP              : {record['ltp']:,.2f}")
    print(f"    bid / ask        : unavailable -- see 'reason' in {OUT}")
    if lo is not None and hi is not None:
        print(f"    day range        : {lo:,.2f} - {hi:,.2f} "
              "(brackets every traded price)")
    pcr = record["put_call_ratio_oi"]
    if pcr is not None:
        print(f"    nearest expiry   : {record['nearest_expiry']}  "
              f"PCR by OI: {pcr:.3f}")
    else:
        print(f"    nearest expiry   : {record['nearest_expiry']}")
    print(f"    nearest strike   : {record['nearest_listed_strike']:,.0f}")
    print(f"    saved to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
