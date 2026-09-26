import sqlite3
from pathlib import Path


# ============================================================
# PATH
# ============================================================

OPTION_PROJECT = Path(__file__).resolve().parents[1]

DB = (
    OPTION_PROJECT
    / "database"
    / "oi_analysis.db"
)


# ============================================================
# SNAPSHOT QUERY
# ============================================================

QUERY = """
SELECT
    c.index_name,
    c.datetime,

    -- Market
    c.futures_price,
    c.futures_price_change_5c,
    c.futures_price_change_pct_5c,
    c.atm_strike,

    -- Selected chain
    c.total_ce_oi,
    c.total_pe_oi,
    c.total_pcr,

    -- OI change
    c.ce_oi_change_pm5,
    c.pe_oi_change_pm5,
    c.ce_oi_change_pct_pm5,
    c.pe_oi_change_pct_pm5,

    -- Activity
    c.ce_activity_balance_pm5,
    c.pe_activity_balance_pm5,

    -- Volatility
    c.atm_iv,
    c.iv_rank,
    c.iv_percentile,

    -- OI concentration
    oc.ce_concentration_pm1,
    oc.pe_concentration_pm1,
    oc.ce_concentration_pm2,
    oc.pe_concentration_pm2,
    oc.ce_concentration_pm5,
    oc.pe_concentration_pm5,
    oc.ce_concentration_pm10,
    oc.pe_concentration_pm10

FROM combined_market_analysis c

LEFT JOIN atm_oi_concentration oc
    ON oc.index_name = c.index_name
    AND oc.datetime = c.datetime
    AND oc.expiry = c.expiry

WHERE c.datetime = (
    SELECT MAX(datetime)
    FROM combined_market_analysis
    WHERE index_name = c.index_name
)

ORDER BY c.index_name
"""


# ============================================================
# MAIN
# ============================================================

def main():

    if not DB.exists():
        raise FileNotFoundError(
            f"Database not found: {DB}"
        )

    con = sqlite3.connect(DB)

    try:

        rows = con.execute(QUERY).fetchall()

        if not rows:
            print("No snapshot data found.")
            return

        columns = [
            description[0]
            for description in con.execute(QUERY).description
        ]

        print()
        print("=" * 100)
        print("CURRENT OPTION ANALYSIS SNAPSHOT")
        print("=" * 100)

        for row in rows:

            data = dict(zip(columns, row))

            print()
            print(f"INDEX          : {data['index_name']}")
            print(f"TIME           : {data['datetime']}")

            print()
            print("--- MARKET ---")
            print(f"Futures        : {data['futures_price']:.2f}")
            print(
                f"5C Change      : "
                f"{data['futures_price_change_5c']:.2f}"
            )
            print(
                f"5C Change %    : "
                f"{data['futures_price_change_pct_5c']:.4f}%"
            )
            print(
                f"ATM Strike     : "
                f"{data['atm_strike']:.0f}"
            )

            print()
            print("--- SELECTED CHAIN ---")
            print(
                f"CE OI          : "
                f"{data['total_ce_oi']:,.0f}"
            )
            print(
                f"PE OI          : "
                f"{data['total_pe_oi']:,.0f}"
            )
            print(
                f"Total PCR      : "
                f"{data['total_pcr']:.4f}"
            )

            print()
            print("--- OI CHANGE ±5 ---")
            print(
                f"CE ΔOI         : "
                f"{data['ce_oi_change_pm5']:,.0f}"
            )
            print(
                f"PE ΔOI         : "
                f"{data['pe_oi_change_pm5']:,.0f}"
            )
            print(
                f"CE ΔOI %       : "
                f"{data['ce_oi_change_pct_pm5']:.4f}%"
            )
            print(
                f"PE ΔOI %       : "
                f"{data['pe_oi_change_pct_pm5']:.4f}%"
            )

            print()
            print("--- ACTIVITY ±5 ---")
            print(
                f"CE Balance     : "
                f"{data['ce_activity_balance_pm5']}"
            )
            print(
                f"PE Balance     : "
                f"{data['pe_activity_balance_pm5']}"
            )

            print()
            print("--- VOLATILITY ---")
            print(
                f"ATM IV         : "
                f"{data['atm_iv'] * 100:.4f}%"
            )
            print(
                f"IV Rank        : "
                f"{data['iv_rank']:.2f}"
            )
            print(
                f"IV Percentile  : "
                f"{data['iv_percentile']:.2f}"
            )

            print()
            print("--- OI CONCENTRATION ---")
            print(
                f"±1  CE / PE    : "
                f"{data['ce_concentration_pm1']:.2f}% / "
                f"{data['pe_concentration_pm1']:.2f}%"
            )
            print(
                f"±2  CE / PE    : "
                f"{data['ce_concentration_pm2']:.2f}% / "
                f"{data['pe_concentration_pm2']:.2f}%"
            )
            print(
                f"±5  CE / PE    : "
                f"{data['ce_concentration_pm5']:.2f}% / "
                f"{data['pe_concentration_pm5']:.2f}%"
            )
            print(
                f"±10 CE / PE    : "
                f"{data['ce_concentration_pm10']:.2f}% / "
                f"{data['pe_concentration_pm10']:.2f}%"
            )
            print(
                "±20 CE / PE    : "
                "100.00% / 100.00%"
            )

        print()
        print("=" * 100)

    finally:
        con.close()


if __name__ == "__main__":
    main()
