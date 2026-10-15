"""Classify NIFTY 50 option strikes by PRICE vs OPEN-INTEREST BUILDUP.

Reads the same official NSE India FO bhavcopy already saved by
fetch_nifty50_option_contracts.py (data/downloads/nse_nifty50_option_contracts.csv)
-- the file nifty50_open_interest.py reports on -- and adds the classic
price/OI reading per strike, for calls and puts separately:

    price up   + OI up    -> Long Buildup    (fresh longs, bullish)
    price down + OI up    -> Short Buildup   (fresh shorts, bearish)
    price up   + OI down  -> Short Covering  (shorts exiting, bullish)
    price down + OI down  -> Long Unwinding  (longs exiting, bearish)
    flat-ish moves        -> Flat / Quiet, reported as such instead of
                             being forced into a quadrant

"Price" here is the option's own premium change (close vs previous close,
volume-weighted when several contracts share a strike); "OI" is the change
in open interest (ChngInOpnIntrst) versus the previous session.

Nothing is refetched and no other provider is used.  Re-run the fetcher
first for a fresh session's numbers.  All heavy lifting lives in pure
functions so tests can cover the classification without any data file.
"""
import csv
import json
from pathlib import Path

CSV_PATH = Path("data/downloads/nse_nifty50_option_contracts.csv")
STATUS_PATH = Path("data/downloads/nifty50_option_chain_status.json")
OUT_PATH = Path("data/downloads/nifty50_price_oi_buildup.json")

WINDOW = 10        # strikes shown on each side of the money (matches OI report)
TOP_N = 5          # strikes listed per classification bucket
PRICE_EPS = 0.01   # premium change up to this % is "flat"
OI_EPS = 0.01      # OI change up to this % is "flat"
MIN_OI = 1.0       # ignore sides with less OI than this entirely


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


# ---------------------------------------------------------------------------
# pure classification helpers (no I/O -- unit-testable on their own)
# ---------------------------------------------------------------------------

def flat(move: float, eps: float) -> bool:
    """True when `move` is within +/- `eps` of zero."""
    return abs(move) <= eps


def classify(price_chg: float, oi_chg: float,
             price_eps: float = PRICE_EPS,
             oi_eps: float = OI_EPS) -> dict:
    """Map a premium change and an OI change onto the classic quadrants.

    Both inputs are relative (fractions).  When either leg is flat the
    result is reported as such instead of being forced into a quadrant.
    """
    p_flat, o_flat = flat(price_chg, price_eps), flat(oi_chg, oi_eps)
    if p_flat and o_flat:
        label, bias = "No activity", "neutral"
    elif o_flat:
        label, bias = "Price-only move (flat OI)", "uncertain"
    elif p_flat:
        label, bias = "OI-only change (flat price)", "uncertain"
    elif price_chg > 0:
        label = ("Long buildup" if oi_chg > 0 else "Short covering")
        bias = "bullish"
    else:
        label = ("Short buildup" if oi_chg > 0 else "Long unwinding")
        bias = "bearish"
    return {
        "price_chg_pct": round(price_chg * 100, 2),
        "oi_chg_pct": round(oi_chg * 100, 2),
        "classification": label,
        "bias": bias,
    }


def merge_side(rows: list, side: str) -> dict:
    """Volume-weighted premium change and summed OI change for one side.

    `rows` are the raw CSV dicts for ONE strike and ONE option type; the
    volume weights keep a tiny illiquid contract from dominating a strike
    where a liquid contract also trades.
    """
    vol = sum(to_num(r.get("TtlTradgVol")) for r in rows)
    prev_px = sum(to_num(r.get("PrvsClsgPric")) * to_num(r.get("TtlTradgVol"))
                  for r in rows)
    last_px = sum(to_num(r.get("ClsPric")) * to_num(r.get("TtlTradgVol"))
                  for r in rows)

    if vol > 0 and prev_px > 0:
        price_chg = (last_px / prev_px) - 1.0
    else:
        # fall back to the settlement-mark change of the biggest contract
        best = max(rows, key=lambda r: to_num(r.get("OpnIntrst")))
        prev = to_num(best.get("PrvsClsgPric"))
        last = to_num(best.get("ClsPric"))
        price_chg = (last / prev - 1.0) if prev > 0 else 0.0

    return {
        "oi": sum(to_num(r.get("OpnIntrst")) for r in rows),
        "oi_change": sum(to_num(r.get("ChngInOpnIntrst")) for r in rows),
        "volume": vol,
        "price_change": price_chg,
        "contracts": len(rows),
    }


def classify_strike(sides: dict) -> dict:
    """Attach a classification to each option side of one strike.

    `sides` maps "CE"/"PE" to the dict produced by merge_side.  A side with
    negligible open interest is reported as "Inactive" rather than being
    classified, so a quiet strike is never dressed up as a buildup.
    """
    out = {}
    for side, data in sides.items():
        if data["oi"] < MIN_OI:
            out[side] = {
                "oi": data["oi"],
                "oi_change": data["oi_change"],
                "premium_change_pct": round(data["price_change"] * 100, 2),
                "classification": "Inactive",
                "bias": "neutral",
            }
            continue
        prev_oi = data["oi"] - data["oi_change"]
        oi_chg = (data["oi_change"] / prev_oi) if prev_oi > 0 else 0.0
        verdict = classify(data["price_change"], oi_chg)
        out[side] = {
            "oi": data["oi"],
            "oi_change": data["oi_change"],
            "premium_change_pct": verdict.pop("price_chg_pct"),
            "oi_change_pct": verdict.pop("oi_chg_pct"),
            **verdict,
        }
    return out


def build_report(rows: list, nearest: str, spot: float) -> dict:
    """Full report dict for one expiry: every strike, both sides classified."""
    strikes = {}
    for r in rows:
        if (r.get("XpryDt") or "").strip() != nearest:
            continue
        side = (r.get("OptnTp") or "").strip().upper()
        if side not in ("CE", "PE"):
            continue
        strike = round(to_num(r.get("StrkPric")))
        slot = strikes.setdefault(strike, {"CE": [], "PE": []})
        slot[side].append(r)

    per_strike = {s: classify_strike(
        {k: merge_side(v, k) for k, v in sides.items() if v})
        for s, sides in sorted(strikes.items())}

    return {
        "source": "official NSE India FO bhavcopy",
        "as_of": nearest,
        "spot": spot,
        "definitions": {
            "Long buildup": "premium up, OI up -- fresh longs (bullish)",
            "Short buildup": "premium down, OI up -- fresh shorts (bearish)",
            "Short covering": "premium up, OI down -- shorts exiting (bullish)",
            "Long unwinding": "premium down, OI down -- longs exiting (bearish)",
        },
        "note": ("End-of-session exchange data for the shown trade date, "
                 "not live quotes. Premium = the option's own price, not "
                 "the underlying."),
        "strikes": per_strike,
    }


# ---------------------------------------------------------------------------
# console report
# ---------------------------------------------------------------------------

def strike_window(strikes: list, spot: float) -> list:
    """The `WINDOW` strikes on each side of the money, sorted."""
    listed = sorted(strikes)
    closest = min(listed, key=lambda s: abs(s - spot))
    lo = [s for s in listed if s <= closest][-WINDOW:]
    hi = [s for s in listed if s > closest][:WINDOW]
    return lo + hi


def print_report(report: dict) -> None:
    spot, strikes = report["spot"], report["strikes"]
    print(f"NIFTY 50 price/OI buildup -- expiry {report['as_of']}")
    print(f"source: {report['source']}    spot: {spot:,.2f}")
    print("\n strike | calls                                "
          "| puts")
    print("        |  prem%   chgOI%  classification      "
          "|  prem%   chgOI%  classification")
    for s in strike_window(list(strikes), spot):
        ce, pe = strikes[s]["CE"], strikes[s]["PE"]
        tag = " <-ATM" if abs(s - spot) == min(abs(x - spot) for x in strikes) else ""
        print(f" {s:>7,} | {ce['premium_change_pct']:>6.1f} "
              f"{ce.get('oi_change_pct', 0):>8.1f}  {ce['classification']:<18} "
              f"| {pe['premium_change_pct']:>6.1f} "
              f"{pe.get('oi_change_pct', 0):>8.1f}  {pe['classification']:<18}{tag}")

    # ---- the strikes with the strongest reading per bucket ----------------
    print("\nstrongest readings per classification (by OI):")
    buckets = {}
    for s, sides in strikes.items():
        for side, info in sides.items():
            if info["classification"] in ("Inactive", "No activity"):
                continue
            buckets.setdefault(info["classification"], []).append(
                (info["oi"], s, side))
    for label in ("Long buildup", "Short buildup",
                  "Short covering", "Long unwinding"):
        rows = sorted(buckets.get(label, []), reverse=True)[:TOP_N]
        text = ", ".join(f"{s:,} {side} (OI {oi:,.0f})" for oi, s, side in rows)
        print(f"  {label:<16}: {text or '-'}")

    print(f"\nNOTE: {report['note']}")


def main() -> None:
    status = load_status()
    rows = load_rows()
    for r in rows:
        r["OptnTp"] = (r.get("OptnTp") or "").strip().upper()

    nearest = status.get("nearest_expiry")
    if not nearest:
        dates = sorted({r.get("XpryDt", "").strip() for r in rows
                        if r.get("XpryDt", "").strip()})
        nearest = dates[0] if dates else None
    if not nearest:
        raise SystemExit("FAIL: no expiry dates in the contract data.")

    spot = next((to_num(r.get("UndrlygPric"), None) for r in rows
                 if to_num(r.get("UndrlygPric"), None) is not None
                 and (to_num(r.get("OpnIntrst")) + to_num(r.get("TtlTradgVol"))) > 0),
                None)
    if spot is None:
        raise SystemExit("FAIL: no usable UndrlygPric in the contract data.")

    report = build_report(rows, nearest, spot)
    print_report(report)

    OUT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nsaved to {OUT_PATH}")


if __name__ == "__main__":
    main()
