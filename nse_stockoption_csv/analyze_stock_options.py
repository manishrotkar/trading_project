
import sqlite3
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import re

PROJECT_DIR = Path(__file__).resolve().parent
DB_FILE = PROJECT_DIR / "database" / "stock_option_chain.db"
OUTPUT_DIR = PROJECT_DIR / "output"


def fmt(value, digits=2):
    if value is None:
        return "N/A"
    return f"{value:,.{digits}f}"


def ratio(numerator, denominator):
    if denominator in (None, 0):
        return None
    return numerator / denominator


def safe_name(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value))


def table_exists(conn, table):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def load_snapshots(conn, symbol):
    return conn.execute("""
        SELECT snapshot_id, symbol, expiry_date, captured_at, source,
               underlying_price, aggregate_call_oi, aggregate_put_oi,
               contract_count
        FROM snapshots
        WHERE UPPER(symbol) = ?
        ORDER BY captured_at DESC, snapshot_id DESC
    """, (symbol.upper(),)).fetchall()


def load_contracts(conn, snapshot_id):
    return conn.execute("""
        SELECT *
        FROM option_contracts
        WHERE snapshot_id = ?
        ORDER BY strike_price, option_type
    """, (snapshot_id,)).fetchall()


def load_cash_futures(conn, symbol):
    if not table_exists(conn, "cash_futures_snapshots"):
        return None, None

    rows = conn.execute("""
        SELECT *
        FROM cash_futures_snapshots
        WHERE UPPER(symbol) = ?
        ORDER BY captured_at DESC, id DESC
        LIMIT 2
    """, (symbol.upper(),)).fetchall()

    if not rows:
        return None, None

    return rows[0], rows[1] if len(rows) > 1 else None


def calculate_max_pain(contracts):
    strikes = sorted({
        row["strike_price"]
        for row in contracts
        if row["strike_price"] is not None
    })

    if not strikes:
        return None

    call_oi = defaultdict(float)
    put_oi = defaultdict(float)

    for row in contracts:
        strike = row["strike_price"]
        oi = row["oi"] or 0

        if row["option_type"] == "CE":
            call_oi[strike] += oi
        elif row["option_type"] == "PE":
            put_oi[strike] += oi

    payouts = {}

    for settlement in strikes:
        call_payout = sum(
            max(settlement - strike, 0) * oi
            for strike, oi in call_oi.items()
        )
        put_payout = sum(
            max(strike - settlement, 0) * oi
            for strike, oi in put_oi.items()
        )
        payouts[settlement] = call_payout + put_payout

    return min(payouts, key=payouts.get)


def summarize_contracts(contracts):
    totals = {
        "CE": {"oi": 0, "volume": 0, "oi_change": 0},
        "PE": {"oi": 0, "volume": 0, "oi_change": 0},
    }

    strikes = defaultdict(lambda: {
        "CE_OI": 0,
        "PE_OI": 0,
        "CE_CHANGE": 0,
        "PE_CHANGE": 0,
    })

    for row in contracts:
        side = row["option_type"]
        strike = row["strike_price"]

        if side not in ("CE", "PE") or strike is None:
            continue

        oi = row["oi"] or 0
        volume = row["volume"] or 0
        oi_change = row["oi_change"] or 0

        totals[side]["oi"] += oi
        totals[side]["volume"] += volume
        totals[side]["oi_change"] += oi_change

        strikes[strike][f"{side}_OI"] += oi
        strikes[strike][f"{side}_CHANGE"] += oi_change

    return totals, strikes


def weighted_average(contracts, side, field):
    values = [
        (row[field], row["oi"] or 0)
        for row in contracts
        if row["option_type"] == side
        and row[field] is not None
        and (row["oi"] or 0) > 0
    ]

    total_weight = sum(weight for _, weight in values)

    if not total_weight:
        return None

    return sum(value * weight for value, weight in values) / total_weight


def aggregate_greeks(contracts, side):
    return {
        greek: weighted_average(contracts, side, greek)
        for greek in ("delta", "gamma", "theta", "vega")
    }


def compare_option_snapshots(current_contracts, previous_contracts):
    if previous_contracts is None:
        return []

    previous_map = {
        (row["strike_price"], row["option_type"]): row
        for row in previous_contracts
    }

    changes = []

    for row in current_contracts:
        key = (row["strike_price"], row["option_type"])
        old = previous_map.get(key)

        if old is None:
            continue

        old_oi = old["oi"] or 0
        new_oi = row["oi"] or 0

        changes.append({
            "strike": row["strike_price"],
            "side": row["option_type"],
            "old_oi": old_oi,
            "new_oi": new_oi,
            "change": new_oi - old_oi,
        })

    return changes


def build_probability_estimate(totals):
    """
    Transparent heuristic weights, not calibrated probabilities.
    Limited strike coverage can distort PCR and these estimates.
    """
    ce_oi = totals["CE"]["oi"]
    pe_oi = totals["PE"]["oi"]
    ce_vol = totals["CE"]["volume"]
    pe_vol = totals["PE"]["volume"]

    pcr_oi = ratio(pe_oi, ce_oi)
    pcr_vol = ratio(pe_vol, ce_vol)

    bull = 1.0
    bear = 1.0
    sideways = 1.0

    if pcr_oi is not None:
        if pcr_oi >= 1.15:
            bull += 2
        elif pcr_oi >= 1.00:
            bull += 1
        elif pcr_oi <= 0.85:
            bear += 2
        elif pcr_oi < 1.00:
            bear += 1
        else:
            sideways += 0.5

    if pcr_vol is not None:
        if pcr_vol >= 1.15:
            bull += 1
        elif pcr_vol <= 0.85:
            bear += 1
        else:
            sideways += 0.5

    ce_change = totals["CE"]["oi_change"]
    pe_change = totals["PE"]["oi_change"]

    if pe_change > ce_change:
        bull += 1
    elif ce_change > pe_change:
        bear += 1
    else:
        sideways += 0.5

    total = bull + bear + sideways

    return {
        "Bullish": 100 * bull / total,
        "Bearish": 100 * bear / total,
        "Sideways": 100 * sideways / total,
    }


def futures_interpretation(current, previous):
    if previous is None:
        return (
            "Not available: need at least two cash/futures snapshots "
            "for comparison."
        )

    current_future = current["future_symbol"]
    previous_future = previous["future_symbol"]

    if not current_future or current_future != previous_future:
        return (
            "Not calculated: the futures contract changed between "
            "snapshots. Compare the same expiry contract only."
        )

    old_price = previous["future_ltp"]
    new_price = current["future_ltp"]
    old_oi = previous["future_oi"]
    new_oi = current["future_oi"]

    if old_price is None or new_price is None:
        return "Not calculated: futures price is missing."

    if old_oi is None or new_oi is None:
        return "Not calculated: futures OI is missing."

    price_change = new_price - old_price
    oi_change = new_oi - old_oi

    if price_change > 0 and oi_change > 0:
        label = "Possible long buildup"
    elif price_change < 0 and oi_change > 0:
        label = "Possible short buildup"
    elif price_change > 0 and oi_change < 0:
        label = "Possible short covering"
    elif price_change < 0 and oi_change < 0:
        label = "Possible long unwinding"
    else:
        label = "Mixed or unchanged movement"

    return (
        f"{label}; futures price change {price_change:+,.2f}, "
        f"futures OI change {oi_change:+,.0f}."
    )


def write_report(lines, symbol, expiry, captured_at):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = (
        f"{safe_name(symbol)}_{safe_name(expiry)}_"
        f"{timestamp}_analysis.txt"
    )
    report_file = OUTPUT_DIR / filename
    report_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return report_file


def analyze(symbol):
    if not DB_FILE.exists():
        raise SystemExit(f"Database not found: {DB_FILE}")

    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row

        snapshots = load_snapshots(conn, symbol)

        if not snapshots:
            raise SystemExit(f"No option snapshots found for {symbol}.")

        current = snapshots[0]
        snapshot_id = current["snapshot_id"]
        expiry = current["expiry_date"]
        captured_at = current["captured_at"]

        contracts = load_contracts(conn, snapshot_id)

        totals, strike_summary = summarize_contracts(contracts)

        previous = conn.execute("""
            SELECT snapshot_id, captured_at
            FROM snapshots
            WHERE UPPER(symbol) = ?
              AND expiry_date = ?
              AND snapshot_id < ?
            ORDER BY captured_at DESC, snapshot_id DESC
            LIMIT 1
        """, (symbol.upper(), expiry, snapshot_id)).fetchone()

        previous_contracts = (
            load_contracts(conn, previous["snapshot_id"])
            if previous else None
        )

        cash_current, cash_previous = load_cash_futures(conn, symbol)

    ce_oi = totals["CE"]["oi"]
    pe_oi = totals["PE"]["oi"]
    ce_volume = totals["CE"]["volume"]
    pe_volume = totals["PE"]["volume"]

    pcr_oi = ratio(pe_oi, ce_oi)
    pcr_volume = ratio(pe_volume, ce_volume)

    max_pain = calculate_max_pain(contracts)

    ce_wall = max(
        strike_summary,
        key=lambda strike: strike_summary[strike]["CE_OI"],
        default=None,
    )
    pe_wall = max(
        strike_summary,
        key=lambda strike: strike_summary[strike]["PE_OI"],
        default=None,
    )

    probabilities = build_probability_estimate(totals)
    changes = compare_option_snapshots(contracts, previous_contracts)

    lines = []

    def out(text=""):
        lines.append(str(text))

    out("=" * 76)
    out(f"STOCK OPTION + CASH/FUTURES ANALYSIS: {symbol.upper()}")
    out("=" * 76)
    out(f"Option snapshot ID : {snapshot_id}")
    out(f"Captured at        : {captured_at}")
    out(f"Source             : {current['source']}")
    out(f"Expiry             : {expiry}")
    out(f"Underlying price   : {fmt(current['underlying_price'])}")
    out(f"Contracts saved    : {current['contract_count']}")
    out(
        "Previous option snapshot: "
        + (previous["captured_at"] if previous else "Not available")
    )

    out()
    out("IMPORTANT DATA COVERAGE WARNING")
    out(
        "PCR, OI walls and Max Pain below use only the contracts saved "
        "in this snapshot."
    )
    out(
        "If FYERS returned only a subset of strikes, these are "
        "limited-range estimates, not full-chain values."
    )
    out(
        "API aggregate OI may cover a different range and must not be "
        "compared as if the ranges were identical."
    )

    out()
    out("--- CASH AND FUTURES ---")

    if cash_current is None:
        out("No cash/futures snapshots found for this symbol.")
        out("Run collect_cash_futures.py to start collecting them.")
    else:
        c = cash_current
        out(f"Cash/futures captured: {c['captured_at']}")
        out(f"Cash LTP             : {fmt(c['cash_ltp'])}")
        out(f"Cash change           : {fmt(c['cash_change'])}")
        out(f"Cash change %         : {fmt(c['cash_change_pct'])}%")
        out(f"Cash volume           : {fmt(c['cash_volume'], 0)}")
        out(f"Futures symbol        : {c['future_symbol']}")
        out(f"Futures expiry        : {c['future_expiry']}")
        out(f"Futures LTP           : {fmt(c['future_ltp'])}")
        out(f"Futures change        : {fmt(c['future_change'])}")
        out(f"Futures change %      : {fmt(c['future_change_pct'])}%")
        out(f"Futures volume        : {fmt(c['future_volume'], 0)}")
        out(f"Futures OI             : {fmt(c['future_oi'], 0)}")
        out(f"Futures average price : {fmt(c['future_avg_price'])}")
        out(f"Futures premium       : {fmt(c['future_premium'])}")
        out(f"Futures premium %     : {fmt(c['future_premium_pct'], 4)}%")

        if cash_previous is not None:
            out()
            out(f"Previous cash/futures snapshot: {cash_previous['captured_at']}")

            if c["cash_ltp"] is not None and cash_previous["cash_ltp"] is not None:
                out(
                    "Cash LTP change since snapshot: "
                    f"{c['cash_ltp'] - cash_previous['cash_ltp']:+,.2f}"
                )

            same_future = (
                c["future_symbol"]
                and c["future_symbol"] == cash_previous["future_symbol"]
            )

            if same_future:
                if c["future_ltp"] is not None and cash_previous["future_ltp"] is not None:
                    out(
                        "Futures LTP change since snapshot: "
                        f"{c['future_ltp'] - cash_previous['future_ltp']:+,.2f}"
                    )

                if c["future_oi"] is not None and cash_previous["future_oi"] is not None:
                    out(
                        "Futures OI change since snapshot: "
                        f"{c['future_oi'] - cash_previous['future_oi']:+,.0f}"
                    )
            else:
                out(
                    "Futures OI comparison skipped: futures contract "
                    "changed between snapshots."
                )

        out()
        out("Futures positioning interpretation:")
        out(futures_interpretation(c, cash_previous))
        out(
            "This is a price/OI heuristic, not proof of the positions "
            "taken by individual traders."
        )

    out()
    out("--- OPTION OPEN INTEREST AND PCR ---")
    out(f"CE total OI          : {ce_oi:,.0f}")
    out(f"PE total OI          : {pe_oi:,.0f}")
    out(f"PCR by OI            : {fmt(pcr_oi, 3)}")
    out(f"CE total volume      : {ce_volume:,.0f}")
    out(f"PE total volume      : {pe_volume:,.0f}")
    out(f"PCR by volume        : {fmt(pcr_volume, 3)}")
    out(
        "API aggregate CE OI  : "
        + (fmt(current["aggregate_call_oi"], 0)
           if current["aggregate_call_oi"] is not None else "N/A")
    )
    out(
        "API aggregate PE OI  : "
        + (fmt(current["aggregate_put_oi"], 0)
           if current["aggregate_put_oi"] is not None else "N/A")
    )

    out()
    out("--- OI WALLS AND MAX PAIN (AVAILABLE STRIKES ONLY) ---")
    out(f"Highest CE OI strike : {fmt(ce_wall)}")
    out(f"Highest PE OI strike : {fmt(pe_wall)}")
    out(f"Estimated Max Pain   : {fmt(max_pain)}")

    out()
    out("--- FYERS-REPORTED OI CHANGE ---")
    out(f"CE net reported OI change: {totals['CE']['oi_change']:+,.0f}")
    out(f"PE net reported OI change: {totals['PE']['oi_change']:+,.0f}")
    out(
        "Note: these are API-reported changes; they are not the same "
        "as changes calculated between your saved snapshots."
    )

    for side in ("CE", "PE"):
        rows = sorted(
            [
                (strike, values[f"{side}_CHANGE"], values[f"{side}_OI"])
                for strike, values in strike_summary.items()
            ],
            key=lambda item: item[1],
            reverse=True,
        )

        out()
        out(f"Top {side} strikes by FYERS-reported OI change:")
        for strike, change, oi in rows[:5]:
            out(
                f"  Strike {strike:>9,.2f} | "
                f"reported change {change:+,.0f} | current OI {oi:,.0f}"
            )

    out()
    out("--- IV AND GREEKS (OI-WEIGHTED AVERAGES) ---")
    for side in ("CE", "PE"):
        out(f"{side}:")
        out(f"  Weighted IV: {fmt(weighted_average(contracts, side, 'iv'))}%")
        greeks = aggregate_greeks(contracts, side)

        for greek, value in greeks.items():
            out(f"  Weighted {greek.title():<5}: {fmt(value, 4)}")

    out()
    out("--- CHANGE SINCE PREVIOUS OPTION SNAPSHOT ---")

    if not previous or previous_contracts is None:
        out("Not available. Run the option collector again later.")
    elif not changes:
        out("No matching strikes/contracts found for comparison.")
    else:
        out(f"Previous snapshot time: {previous['captured_at']}")

        for side in ("CE", "PE"):
            side_changes = [item for item in changes if item["side"] == side]

            out()
            out(f"{side} largest OI increases:")
            increases = sorted(
                side_changes, key=lambda item: item["change"], reverse=True
            )

            positive = [item for item in increases if item["change"] > 0]
            if not positive:
                out("  No OI increases in matching contracts.")
            for item in positive[:5]:
                out(
                    f"  Strike {item['strike']:>9,.2f} | "
                    f"OI change {item['change']:+,.0f} | "
                    f"old {item['old_oi']:,.0f} -> "
                    f"new {item['new_oi']:,.0f}"
                )

            out(f"{side} largest OI decreases:")
            decreases = sorted(
                side_changes, key=lambda item: item["change"]
            )
            negative = [item for item in decreases if item["change"] < 0]
            if not negative:
                out("  No OI decreases in matching contracts.")
            for item in negative[:5]:
                out(
                    f"  Strike {item['strike']:>9,.2f} | "
                    f"OI change {item['change']:+,.0f} | "
                    f"old {item['old_oi']:,.0f} -> "
                    f"new {item['new_oi']:,.0f}"
                )

    out()
    out("--- HEURISTIC SCENARIO WEIGHTS ---")
    for label, value in probabilities.items():
        out(f"{label:<10}: {value:5.1f}%")

    out(
        "WARNING: These are simple rule-based scenario weights, "
        "not statistically calibrated probabilities. They are not "
        "a forecast or a recommendation to trade."
    )

    out()
    out("--- INTERPRETATION NOTES ---")
    out(
        "Rising OI means contracts are being added; OI alone does not "
        "tell whether buyers or sellers initiated the positions."
    )
    out(
        "A high CE OI strike may act as resistance and a high PE OI "
        "strike may act as support, but neither level is guaranteed."
    )
    out(
        "IV and Greeks describe the available option data; they do "
        "not independently establish market direction."
    )
    out(
        "Compare snapshots for the same expiry and matching strikes. "
        "Changes in the available strike range can distort totals."
    )
    out()
    out("Database was not modified by this analysis.")
    out("=" * 76)

    report_file = write_report(lines, symbol, expiry, captured_at)

    print("\n".join(lines))
    print(f"\nReport saved to: {report_file}")


def main():
    symbol = input("Stock symbol to analyze [RELIANCE]: ").strip().upper()
    analyze(symbol or "RELIANCE")


if __name__ == "__main__":
    main()
