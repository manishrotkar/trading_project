"""Fetch NIFTY 50 option-contract market data — including OPEN INTEREST —
from NSE India (the only permitted source).

Two paths, selected automatically:

1. LIVE API (preferred) -- /api/option-chain-indices?symbol=NIFTY on
   www.nseindia.com.  Returns real-time chain data.  Blocked (HTTP 404) from
   this environment as of 01-Oct-2026; see NSE_BLOCKED_NOTES.md and
   probe_option_chain_retest.py.

2. OFFICIAL ARCHIVE bhavcopy (verified working from this environment) --
   the exchange's own daily FO bhavcopy from nsearchives.nseindia.com
   (UDiFF format).  Still NSE India — the required source — just the
   exchange's end-of-day record of the complete option-contract set for
   the session: every listed strike, every expiry, with CE/PE settle
   prices, OPEN INTEREST (OpnIntrst), change in OI (ChngInOpnIntrst),
   volume (TtlTradgVol), premium turnover (TtlTrfVal) and the
   underlying's own level (UndrlygPric).  Tries today first, then steps
   back through recent calendar days.

Output: data/downloads/nse_nifty50_option_contracts.csv
        data/downloads/nifty50_option_chain_status.json

Only nseindia.com hosts are ever contacted; nothing is substituted.
"""
import csv
import datetime as dt
import io
import json
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from fetch_nifty50_options import HEADERS  # verified browser-like headers

API_URL = ("https://www.nseindia.com/api/option-chain-indices?"
           "symbol=NIFTY")
BHAV_URL = ("https://nsearchives.nseindia.com/content/fo/"
            "BhavCopy_NSE_FO_0_0_0_{stamp}_F_0000.csv.zip")
OUT_CSV = Path("data/downloads/nse_nifty50_option_contracts.csv")
OUT_STATUS = Path("data/downloads/nifty50_option_chain_status.json")

LOT_SIZE = 65         # NIFTY 50 index option lot size on NSE (NewBrdLotQty)
STRIKE_STEP = 50      # expected NIFTY 50 index option strike spacing on NSE
SYMBOL_IN_FILE = "NIFTY"   # how the index option appears in the bhavcopy
MAX_BACKFILL_DAYS = 6      # calendar days to step back for the latest file

# UDiFF bhavcopy columns to persist for every contract row.  These are the
# file's own names, verified against a real download (34-column header):
# the option-type column is "OptnTp"; open interest lives in "OpnIntrst".
FIELDS = [
    "TradDt", "BizDt", "Sgmt", "Src", "FinInstrmTp", "FinInstrmId", "ISIN",
    "TckrSymb", "SctySrs", "XpryDt", "FininstrmActlXpryDt", "StrkPric",
    "OptnTp", "FinInstrmNm", "OpnPric", "HghPric", "LwPric", "ClsPric",
    "LastPric", "PrvsClsgPric", "UndrlygPric", "SttlmPric",
    "OpnIntrst", "ChngInOpnIntrst", "TtlTradgVol", "TtlTrfVal",
    "TtlNbOfTxsExctd", "SsnId", "NewBrdLotQty",
]


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        if resp.status != 200:
            raise RuntimeError(f"unexpected HTTP status {resp.status}")
        return resp.read()


def try_live_api():
    """Attempt the live option-chain API.

    Returns (records, None) on success, or (None, reason) if unusable.
    Never raises.
    """
    try:
        raw = http_get(API_URL)
    except Exception as exc:  # noqa: BLE001
        return None, f"live API unavailable: {type(exc).__name__}: {exc}"
    try:
        data = json.loads(raw)
        records = data["records"]
        if not isinstance(records, dict) or not records.get("data"):
            return None, "live API returned an empty payload"
        return records, None
    except Exception as exc:  # noqa: BLE001
        return None, f"live API payload unusable: {exc}"


def find_bhavcopy_for_day(day: dt.date):
    """Return ((url, raw_zip_bytes), None) for `day`'s FO bhavcopy,
    or (None, reason) if there is no file that day.  Never raises."""
    url = BHAV_URL.format(stamp=day.strftime("%Y%m%d"))
    try:
        return (url, http_get(url)), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def open_bhavcopy_csv(zip_bytes: bytes) -> str:
    """Extract the single CSV inside the bhavcopy zip as text."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        csv_name = next((n for n in names if n.lower().endswith(".csv")), None)
        if csv_name is None:
            raise RuntimeError(
                f"no CSV member in bhavcopy zip; members={names[:5]}...")
        return zf.read(csv_name).decode("utf-8", "replace")


def parse_csv(text: str) -> list:
    """Parse the UDiFF bhavcopy CSV into a list of dict rows."""
    return list(csv.DictReader(io.StringIO(text, newline="")))


def rows_for_symbol(rows: list, symbol: str) -> list:
    """All rows whose TckrSymb matches — the whole chain, all expiries."""
    return [r for r in rows
            if r.get("TckrSymb", "").strip().upper() == symbol.upper()]


def to_num(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a


def strike_step(strikes: list) -> int:
    """GCD of the gaps between consecutive strikes — the chain's own
    strike spacing, computed from the data instead of assumed."""
    strikes = sorted({int(round(s)) for s in strikes if s is not None})
    gaps = {b - a for a, b in zip(strikes, strikes[1:])}
    gaps.discard(0)
    step = 0
    for g in gaps:
        step = gcd(step, g)
    return step


def parse_udi_date(value):
    """Parse a UDiFF date (YYYY-MM-DD or DD-MMM-YYYY); None if unparseable."""
    for fmt in ("%Y-%m-%d", "%d-%b-%Y"):
        try:
            return dt.datetime.strptime(str(value).strip(), fmt).date()
        except (TypeError, ValueError):
            continue
    return None


def summarize_chain(rows: list, as_of: dt.date, source_url: str) -> dict:
    """Aggregate the full chain into the status dict."""

    def n(value):
        return to_num(value, 0.0) or 0.0

    expiries = sorted({r.get("XpryDt").strip() for r in rows
                       if r.get("XpryDt") and r.get("XpryDt").strip()})

    # The underlying's own closing level is in UndrlygPric on every row;
    # take it from a row that actually traded.
    spot = next((to_num(r.get("UndrlygPric"))
                 for r in rows
                 if to_num(r.get("UndrlygPric")) is not None
                 and n(r.get("OpnIntrst")) + n(r.get("TtlTradgVol")) > 0),
                None)

    # Nearest expiry = soonest XpryDt on/after the trade date; when every
    # listed expiry is already past, keep the soonest so the file is
    # never treated as empty.
    trade_day = parse_udi_date(rows[0].get("TradDt")) if rows else None
    as_of = trade_day or as_of
    future = [e for e in expiries
              if parse_udi_date(e) and parse_udi_date(e) >= as_of]
    nearest = (min(future, key=parse_udi_date) if future
               else (expiries[0] if expiries else None))

    stats = None
    contracts = None
    chain_step = None
    if nearest:
        near_rows = [r for r in rows if r.get("XpryDt") == nearest]
        contracts = len(near_rows)
        chain_step = strike_step([to_num(r.get("StrkPric")) for r in near_rows])

        calls = [r for r in near_rows
                 if (r.get("OptnTp") or "").strip().upper() == "CE"]
        puts = [r for r in near_rows
                if (r.get("OptnTp") or "").strip().upper() == "PE"]

        def total(rs, field):
            return sum(n(r.get(field)) for r in rs)

        oi_ce = total(calls, "OpnIntrst")
        oi_pe = total(puts, "OpnIntrst")
        stats = {
            "contracts": contracts,
            "ce_oi": oi_ce,
            "pe_oi": oi_pe,
            "pcr_by_oi": round(oi_pe / oi_ce, 3) if oi_ce else None,
            "ce_oi_change": total(calls, "ChngInOpnIntrst"),
            "pe_oi_change": total(puts, "ChngInOpnIntrst"),
            "ce_volume": total(calls, "TtlTradgVol"),
            "pe_volume": total(puts, "TtlTradgVol"),
        }

    return {
        "source": source_url,
        "path": "archive-bhavcopy",
        "as_of": as_of.isoformat(),
        "expiries": expiries,
        "nearest_expiry": nearest,
        "contracts_in_nearest_expiry": contracts,
        "nearest_expiry_stats": stats,
        "underlying_spot_from_file": spot,
        "lot_size": LOT_SIZE,
        "strike_step": chain_step or STRIKE_STEP,
        "derived": False,
        "note": ("Official NSE India FO bhavcopy (UDiFF) — the exchange's own "
                 "end-of-day option-contract market data: every listed strike "
                 "with CE/PE prices, OPEN INTEREST, volume and premium "
                 "turnover for the session."),
    }


def main() -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    # ---- path 1: live option-chain API -----------------------------------
    records, reason = try_live_api()
    if records is not None:
        print("path: live option-chain API")
        print(f"    underlying : {records.get('underlying')}")
        print(f"    spot       : {records.get('underlyingValue')}")
        expiries = records.get("expiryDates") or []
        print(f"    expiries   : {len(expiries)} listed "
              f"(next: {expiries[0] if expiries else '-'})")
        chain_path = OUT_CSV.with_suffix(".json")
        chain_path.write_text(json.dumps(records, indent=2) + "\n")
        status = {
            "path": "live-api",
            "source": API_URL,
            "as_of": records.get("timestamp"),
            "derived": False,
        }
        OUT_STATUS.write_text(json.dumps(status, indent=2) + "\n")
        print(f"    saved raw chain to {chain_path}")
        return

    print(f"live API unavailable: {reason}")

    # ---- path 2: official archive bhavcopy --------------------------------
    for back in range(MAX_BACKFILL_DAYS + 1):
        day = dt.date.today() - dt.timedelta(days=back)
        found, why = find_bhavcopy_for_day(day)
        if found:
            url, raw_zip = found
            print(f"path: official archive bhavcopy for {day} "
                  f"({len(raw_zip):,} bytes)")

            all_rows = parse_csv(open_bhavcopy_csv(raw_zip))
            chain_rows = rows_for_symbol(all_rows, SYMBOL_IN_FILE)
            if not chain_rows:
                raise SystemExit(
                    f"FAIL: no {SYMBOL_IN_FILE} rows in the bhavcopy -- "
                    f"cannot proceed (file has {len(all_rows):,} rows total).")

            # Persist the FULL option-contract market data for NIFTY:
            # every strike, CE and PE, every expiry, with the OI columns.
            available = [f for f in FIELDS if f in chain_rows[0]]
            with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=available,
                                        extrasaction="ignore")
                writer.writeheader()
                writer.writerows(chain_rows)

            status = summarize_chain(chain_rows, dt.date.today(), url)
            OUT_STATUS.write_text(json.dumps(status, indent=2) + "\n")

            stats = status["nearest_expiry_stats"]
            spot = status["underlying_spot_from_file"]
            print(f"    file            : {url.rsplit('/', 1)[-1]}")
            print(f"    as-of           : {status['as_of']}")
            print(f"    spot in file    : "
                  f"{spot:,.2f}" if spot is not None else "    spot in file    : -")
            print(f"    expiries        : {len(status['expiries'])}")
            print(f"    contracts       : {len(chain_rows):,} "
                  f"(nearest expiry: {status['contracts_in_nearest_expiry']:,})")
            if stats:
                print(f"    CE OI / PE OI   : "
                      f"{stats['ce_oi']:,.0f} / {stats['pe_oi']:,.0f}")
                print(f"    PCR by OI       : {stats['pcr_by_oi']}")
            print(f"    saved {len(chain_rows):,} rows to {OUT_CSV}")
            print(f"    saved status    : {OUT_STATUS}")
            return
        print(f"    no file for {day}: {why}")

    raise SystemExit(
        "FAIL: no FO bhavcopy found for the last "
        f"{MAX_BACKFILL_DAYS + 1} calendar days -- giving up.")


if __name__ == "__main__":
    main()
