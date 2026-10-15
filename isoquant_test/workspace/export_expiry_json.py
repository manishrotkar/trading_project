"""Export one expiry of the NIFTY 50 option chain to a dated JSON file.

Reads the NSE India option-contract data already on disk
(data/downloads/nse_nifty50_option_contracts.csv, written by
fetch_nifty50_option_contracts.py from the official FO bhavcopy) and writes
one JSON file per expiry:

    data/downloads/nifty50_options_<YYYY-MM-DD>.json

    e.g.  nifty50_options_2026-10-06.json   (the nearest expiry)

The file contains:
  * metadata   -- symbol, expiry, as-of trade date, spot, source URL,
                  provenance flags (nothing is derived or invented)
  * chain      -- one record per strike, sorted by strike, each with the
                  CE and PE legs: close / last / settle prices, open
                  interest, change in OI, volume and premium turnover,
                  exactly as the exchange reported them.

No network access happens here: if the CSV is missing the script exits
loudly instead of contacting any other provider.

Usage:
    python export_expiry_json.py                 # nearest expiry
    python export_expiry_json.py 2026-10-06      # a specific expiry
"""
import csv
import datetime as dt
import json
import sys
from pathlib import Path

CSV_PATH = Path("data/downloads/nse_nifty50_option_contracts.csv")
STATUS_PATH = Path("data/downloads/nifty50_option_chain_status.json")
OUT_DIR = Path("data/downloads")

# UDiFF bhavcopy columns this exporter consumes (see fetch_nifty50_option_contracts.py)
REQUIRED_COLUMNS = {"TckrSymb", "XpryDt", "StrkPric", "OptnTp"}
PRICE_COLUMNS = ["OpnPric", "HghPric", "LwPric", "ClsPric",
                 "LastPric", "SttlmPric", "PrvsClsgPric"]
OI_COLUMNS = ["OpnIntrst", "ChngInOpnIntrst",
              "TtlTradgVol", "TtlTrfVal", "TtlNbOfTxsExctd"]
UNDERLYING_COLUMN = "UndrlygPric"
LOT_COLUMN = "NewBrdLotQty"
SYMBOL = "NIFTY"


def fail(message: str):
    raise SystemExit(f"FAIL: {message}")


def to_num(value, default=None):
    """Bhavcopy numbers may be blank or unparsable; coerce safely."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_date(value: str):
    """Parse a UDiFF date (YYYY-MM-DD or DD-MMM-YYYY); None if unusable."""
    for fmt in ("%Y-%m-%d", "%d-%b-%Y"):
        try:
            return dt.datetime.strptime(str(value).strip(), fmt).date()
        except (TypeError, ValueError):
            continue
    return None


def load_status() -> dict:
    if not STATUS_PATH.exists():
        return {}
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{STATUS_PATH} is not valid JSON: {exc}")


def load_rows() -> list:
    if not CSV_PATH.exists():
        fail(f"{CSV_PATH} not found. Run "
             "'python fetch_nifty50_option_contracts.py' or "
             "'python download_nifty_options.py' first -- "
             "no other data source is permitted.")
    with CSV_PATH.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    if not rows:
        fail(f"{CSV_PATH} is empty.")
    missing = REQUIRED_COLUMNS - set(rows[0])
    if missing:
        fail(f"{CSV_PATH} is missing columns {sorted(missing)} -- "
             "not a recognised NSE FO bhavcopy export.")
    return rows


def pick_expiry(rows: list, status: dict) -> str:
    """Resolve the requested expiry date string (already validated)."""
    expiries = sorted({r["XpryDt"].strip() for r in rows
                       if r["XpryDt"].strip()})
    requested = sys.argv[1] if len(sys.argv) > 1 else None
    if requested:
        # accept 2026-10-06 or 06-Oct-2026, compare on the parsed date
        want = parse_date(requested)
        if want is None:
            fail(f"could not parse expiry {requested!r} as a date")
        for exp in expiries:
            if parse_date(exp) == want:
                return exp
        fail(f"expiry {requested} not in the data; "
             f"available: {', '.join(expiries)}")
    nearest = status.get("nearest_expiry")
    if nearest and nearest in expiries:
        return nearest
    # fall back to the soonest expiry that is on/after the trade date
    trade_day = parse_date(rows[0].get("TradDt", "")) or dt.date.today()
    future = [e for e in expiries
              if (d := parse_date(e)) and d >= trade_day]
    if future:
        return min(future, key=parse_date)
    fail("could not determine an expiry to export; pass one explicitly, "
         f"e.g. 'python export_expiry_json.py {expiries[0]}'")


def build_leg(row: dict) -> dict:
    """One CE or PE leg exactly as the exchange reported it."""
    leg = {}
    for column in PRICE_COLUMNS + OI_COLUMNS:
        if column in row:
            leg[column] = to_num(row[column])
    return leg


def main() -> None:
    status = load_status()
    rows = load_rows()

    chain_rows = [r for r in rows if r["TckrSymb"].strip().upper() == SYMBOL]
    if not chain_rows:
        fail(f"no {SYMBOL} rows in {CSV_PATH}.")

    expiry = pick_expiry(chain_rows, status)
    expiry_date = parse_date(expiry)
    selected = [r for r in chain_rows
                if r["XpryDt"].strip() == expiry
                and (r.get("OptnTp") or "").strip().upper() in ("CE", "PE")]
    if not selected:
        fail(f"no CE/PE contracts for expiry {expiry} in {CSV_PATH}.")

    # ---- group into per-strike records ------------------------------------
    strikes = {}
    for row in selected:
        strike = to_num(row["StrkPric"])
        if strike is None:
            fail(f"unparsable strike price {row['StrkPric']!r}")
        leg_type = row["OptnTp"].strip().upper()
        strikes.setdefault(strike, {})[leg_type] = build_leg(row)

    trade_day = parse_date(selected[0].get("TradDt", ""))
    lot_size = next((int(to_num(r.get(LOT_COLUMN)))
                     for r in selected
                     if to_num(r.get(LOT_COLUMN))), None)
    spot = next((to_num(r.get(UNDERLYING_COLUMN)) for r in selected
                 if to_num(r.get(UNDERLYING_COLUMN)) is not None), None)

    chain = []
    for strike in sorted(strikes):
        entry = {"strike": strike,
                 "call": strikes[strike].get("CE"),
                 "put": strikes[strike].get("PE")}
        ce, pe = entry["call"], entry["put"]
        ce_oi = (ce or {}).get("OpnIntrst") or 0.0
        pe_oi = (pe or {}).get("OpnIntrst") or 0.0
        entry["pcr_at_strike"] = round(pe_oi / ce_oi, 3) if ce_oi else None
        chain.append(entry)

    totals = {
        "contracts": len(selected),
        "strikes": len(chain),
        "ce_open_interest": sum((e["call"] or {}).get("OpnIntrst") or 0.0
                                for e in chain),
        "pe_open_interest": sum((e["put"] or {}).get("OpnIntrst") or 0.0
                                for e in chain),
        "ce_volume": sum((e["call"] or {}).get("TtlTradgVol") or 0.0
                         for e in chain),
        "pe_volume": sum((e["put"] or {}).get("TtlTradgVol") or 0.0
                         for e in chain),
        "max_call_oi_strike": max(chain,
                                  key=lambda e: (e["call"] or {})
                                  .get("OpnIntrst") or 0.0)["strike"],
        "max_put_oi_strike": max(chain,
                                 key=lambda e: (e["put"] or {})
                                 .get("OpnIntrst") or 0.0)["strike"],
    }
    if totals["ce_open_interest"]:
        totals["pcr_by_oi"] = round(
            totals["pe_open_interest"] / totals["ce_open_interest"], 3)
    else:
        totals["pcr_by_oi"] = None

    document = {
        "symbol": SYMBOL,
        "expiry": expiry_date.isoformat() if expiry_date else expiry,
        "as_of": trade_day.isoformat() if trade_day else None,
        "spot": spot,
        "lot_size": lot_size,
        "source": status.get("source", str(CSV_PATH)),
        "source_path": "archive-bhavcopy",
        "derived": False,
        "totals": totals,
        "chain": chain,
        "note": ("NSE India FO bhavcopy (UDiFF) for the shown trade date -- "
                 "end-of-session official exchange data, not live quotes. "
                 "Prices and open interest are as reported by the exchange."),
    }

    out_path = OUT_DIR / f"nifty50_options_{document['expiry']}.json"
    out_path.write_text(json.dumps(document, indent=2) + "\n",
                        encoding="utf-8")

    # ---- console summary ----------------------------------------------------
    print(f"OK  wrote {out_path}")
    print(f"    expiry          : {document['expiry']}")
    print(f"    as-of           : {document['as_of']}")
    print(f"    spot            : {spot:,.2f}" if spot is not None
          else "    spot            : -")
    print(f"    strikes         : {totals['strikes']:,} "
          f"({totals['contracts']:,} contracts)")
    print(f"    CE OI / PE OI   : {totals['ce_open_interest']:,.0f} / "
          f"{totals['pe_open_interest']:,.0f}")
    print(f"    PCR by OI       : {totals['pcr_by_oi']}")
    print(f"    max CE OI strike: {totals['max_call_oi_strike']:,.0f}")
    print(f"    max PE OI strike: {totals['max_put_oi_strike']:,.0f}")


if __name__ == "__main__":
    main()
