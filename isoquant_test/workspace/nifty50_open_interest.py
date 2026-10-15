"""Report NIFTY 50 option OPEN INTEREST by strike for the nearest expiry.

Reads the official NSE India FO bhavcopy already saved by
fetch_nifty50_option_contracts.py (data/downloads/nse_nifty50_option_contracts.csv)
and prints the chain's open-interest structure around the money:

  - spot is taken from the file's own UndrlygPric column (no other source)
  - per strike: CE OI, PE OI, change in OI since the previous session
  - aggregate totals and the put-call ratio by OI
  - the strikes where the most open interest sits (support/resistance
    context: big call OI above spot acts as resistance, big put OI below
    spot acts as support)

This is a reporting layer over the same NSE data — nothing is refetched,
and nothing from any other provider is used.  Re-run the fetcher first
for a fresh session's numbers.
"""
import csv
import json
from pathlib import Path

CSV_PATH = Path("data/downloads/nse_nifty50_option_contracts.csv")
STATUS_PATH = Path("data/downloads/nifty50_option_chain_status.json")
TOP_N = 5          # strikes to list in the top-OI ranking
WINDOW = 10        # strikes shown on each side of the money


def to_num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_rows():
    if not CSV_PATH.exists():
        raise SystemExit(f"FAIL: {CSV_PATH} not found -- run "
                         "fetch_nifty50_option_contracts.py first.")
    with CSV_PATH.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_status():
    try:
        return json.loads(STATUS_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> None:
    status = load_status()
    rows = load_rows()
    for r in rows:                      # normalise the option-type column
        r["OptnTp"] = (r.get("OptnTp") or "").strip().upper()

    nearest = status.get("nearest_expiry")
    if not nearest:                     # derive it if the status file is gone
        dates = sorted({r.get("XpryDt", "").strip() for r in rows
                        if r.get("XpryDt", "").strip()})
        nearest = dates[0] if dates else None
    if not nearest:
        raise SystemExit("FAIL: no expiry dates in the contract data.")

    near = [r for r in rows if (r.get("XpryDt") or "").strip() == nearest]
    if not near:
        raise SystemExit(f"FAIL: no rows for nearest expiry {nearest}.")

    spot = next((to_num(r.get("UndrlygPric"), None) for r in near
                 if to_num(r.get("UndrlygPric"), None) is not None
                 and (to_num(r.get("OpnIntrst")) + to_num(r.get("TtlTradgVol"))) > 0),
                None)
    if spot is None:
        raise SystemExit("FAIL: no usable UndrlygPric in the contract data.")

    # ---- per-strike aggregation ------------------------------------------
    strikes = {}
    for r in near:
        s = round(to_num(r.get("StrkPric")))
        side = r["OptnTp"]
        if side not in ("CE", "PE"):
            continue
        slot = strikes.setdefault(s, {"CE": {"oi": 0.0, "chg": 0.0, "vol": 0.0},
                                      "PE": {"oi": 0.0, "chg": 0.0, "vol": 0.0}})
        slot[side]["oi"] += to_num(r.get("OpnIntrst"))
        slot[side]["chg"] += to_num(r.get("ChngInOpnIntrst"))
        slot[side]["vol"] += to_num(r.get("TtlTradgVol"))

    ce_oi = sum(v["CE"]["oi"] for v in strikes.values())
    pe_oi = sum(v["PE"]["oi"] for v in strikes.values())
    pcr = pe_oi / ce_oi if ce_oi else None

    print(f"NIFTY 50 option open interest -- nearest expiry {nearest}"
          f"  (as of {status.get('as_of', '?')})")
    print(f"source: official NSE India FO bhavcopy "
          f"({Path(status.get('source', '')).name or 'nsearchives.nseindia.com'})")
    print(f"spot (from file, UndrlygPric): {spot:,.2f}"
          f"    contracts in expiry: {len(near):,}")

    # ---- strikes around the money -----------------------------------------
    listed = sorted(strikes)
    closest = min(listed, key=lambda s: abs(s - spot))
    lo = [s for s in listed if s <= closest][-WINDOW:]
    hi = [s for s in listed if s > closest][:WINDOW]
    window = lo + hi

    print("\n strike  |    CE OI   chg OI |    PE OI   chg OI")
    for s in window:
        ce, pe = strikes[s]["CE"], strikes[s]["PE"]
        tag = "  <- ATM" if s == closest else ""
        print(f" {s:>7,} | {ce['oi']:>9,.0f} {ce['chg']:>9,.0f} | "
              f"{pe['oi']:>9,.0f} {pe['chg']:>9,.0f}{tag}")

    # ---- top open interest by side ----------------------------------------
    def top(side):
        ranked = sorted(strikes.items(),
                        key=lambda kv: kv[1][side]["oi"], reverse=True)[:TOP_N]
        return ", ".join(f"{s:,} ({kv[side]['oi']:,.0f})" for s, kv in ranked)

    print(f"\ntop {TOP_N} call-OI strikes (resistance context): {top('CE')}")
    print(f"top {TOP_N} put-OI strikes  (support context)    : {top('PE')}")

    print(f"\ntotals: CE OI {ce_oi:,.0f}   PE OI {pe_oi:,.0f}   "
          f"PCR by OI {pcr:.3f}" if pcr else "\ntotals: no call OI")
    print("NOTE: end-of-session exchange data for the shown trade date, "
          "not live quotes.")


if __name__ == "__main__":
    main()
