from pathlib import Path
import sqlite3
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OI_DB = PROJECT_ROOT / "option_analysis" / "database" / "oi_analysis.db"


def activity_balance(activity: str | None) -> int:
    """
    Convert option activity into a signed activity balance.

    Positive:
        LONG_BUILDUP
        SHORT_COVERING

    Negative:
        SHORT_BUILDUP
        LONG_UNWINDING

    Neutral:
        NEUTRAL / NULL
    """
    if activity in ("LONG_BUILDUP", "SHORT_COVERING"):
        return 1

    if activity in ("SHORT_BUILDUP", "LONG_UNWINDING"):
        return -1

    return 0


def main():
    print("Rebuilding combined_market_analysis...")

    conn = sqlite3.connect(OI_DB)
    conn.row_factory = sqlite3.Row

    try:
        # ---------------------------------------------------------
        # 1. Rebuild only combined_market_analysis
        # ---------------------------------------------------------
        conn.execute("DELETE FROM combined_market_analysis")

        # ---------------------------------------------------------
        # 2. Get all ATM analysis timestamps
        # ---------------------------------------------------------
        atm_rows = conn.execute(
            """
            SELECT
                index_name,
                expiry,
                datetime,
                futures_price,
                atm_strike,
                atm_iv,
                iv_rank,
                iv_percentile
            FROM atm_oi_analysis
            ORDER BY index_name, datetime
            """
        ).fetchall()

        inserted = 0

        for atm in atm_rows:
            index_name = atm["index_name"]
            expiry = atm["expiry"]
            dt = atm["datetime"]
            futures_price = atm["futures_price"]
            atm_strike = atm["atm_strike"]

            # -----------------------------------------------------
            # 3. Get 5-candle futures price change
            # -----------------------------------------------------
            trend = conn.execute(
                """
                SELECT
                    futures_price_change_5c,
                    futures_price_change_pct_5c
                FROM market_trend_analysis
                WHERE index_name = ?
                  AND expiry = ?
                  AND datetime = ?
                """,
                (index_name, expiry, dt),
            ).fetchone()

            if trend is None:
                price_change_5c = None
                price_change_pct_5c = None
            else:
                price_change_5c = trend["futures_price_change_5c"]
                price_change_pct_5c = trend["futures_price_change_pct_5c"]

            # -----------------------------------------------------
            # 4. Get chain summary
            # -----------------------------------------------------
            chain = conn.execute(
                """
                SELECT
                    total_ce_oi,
                    total_pe_oi,
                    total_pcr
                FROM chain_summary
                WHERE index_name = ?
                  AND expiry = ?
                  AND datetime = ?
                """,
                (index_name, expiry, dt),
            ).fetchone()

            if chain is None:
                total_ce_oi = None
                total_pe_oi = None
                total_pcr = None
            else:
                total_ce_oi = chain["total_ce_oi"]
                total_pe_oi = chain["total_pe_oi"]
                total_pcr = chain["total_pcr"]

            # -----------------------------------------------------
            # 5. Determine ATM ±5 range
            #
            # NIFTY:
            #     strike step = 50
            #     ±5 = ±250
            #
            # BANKNIFTY:
            #     strike step = 100
            #     ±5 = ±500
            # -----------------------------------------------------
            if index_name == "NIFTY":
                range_points = 250
            elif index_name == "BANKNIFTY":
                range_points = 500
            else:
                continue

            lower_strike = atm_strike - range_points
            upper_strike = atm_strike + range_points

            # -----------------------------------------------------
            # 6. Read current ATM ±5 activity
            # -----------------------------------------------------
            activity_rows = conn.execute(
                """
                SELECT
                    ce_activity,
                    pe_activity
                FROM strike_oi_analysis
                WHERE index_name = ?
                  AND expiry = ?
                  AND datetime = ?
                  AND strike BETWEEN ? AND ?
                ORDER BY strike
                """,
                (
                    index_name,
                    expiry,
                    dt,
                    lower_strike,
                    upper_strike,
                ),
            ).fetchall()

            ce_activity_balance = 0
            pe_activity_balance = 0

            for row in activity_rows:
                ce_activity_balance += activity_balance(
                    row["ce_activity"]
                )

                pe_activity_balance += activity_balance(
                    row["pe_activity"]
                )

            # -----------------------------------------------------
            # 7. Get ATM IV information
            # -----------------------------------------------------
            atm_iv = atm["atm_iv"]
            iv_rank = atm["iv_rank"]
            iv_percentile = atm["iv_percentile"]

            # -----------------------------------------------------
            # 8. Insert combined row
            # -----------------------------------------------------
            conn.execute(
                """
                INSERT INTO combined_market_analysis (
                    index_name,
                    expiry,
                    datetime,
                    futures_price,
                    futures_price_change_5c,
                    futures_price_change_pct_5c,
                    atm_strike,
                    total_ce_oi,
                    total_pe_oi,
                    total_pcr,
                    ce_oi_change_pm5,
                    pe_oi_change_pm5,
                    ce_oi_change_pct_pm5,
                    pe_oi_change_pct_pm5,
                    ce_activity_balance_pm5,
                    pe_activity_balance_pm5,
                    atm_iv,
                    iv_rank,
                    iv_percentile
                )
                SELECT
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    c.ce_oi_change_pm5,
                    c.pe_oi_change_pm5,
                    c.ce_oi_change_pct_pm5,
                    c.pe_oi_change_pct_pm5,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?
                FROM atm_oi_concentration c
                WHERE c.index_name = ?
                  AND c.expiry = ?
                  AND c.datetime = ?
                """,
                (
                    index_name,
                    expiry,
                    dt,
                    futures_price,
                    price_change_5c,
                    price_change_pct_5c,
                    atm_strike,
                    total_ce_oi,
                    total_pe_oi,
                    total_pcr,

                    ce_activity_balance,
                    pe_activity_balance,

                    atm_iv,
                    iv_rank,
                    iv_percentile,

                    index_name,
                    expiry,
                    dt,
                ),
            )

            inserted += 1

        conn.commit()

        # ---------------------------------------------------------
        # 9. Verification
        # ---------------------------------------------------------
        print(f"Rows inserted: {inserted}")

        latest_datetime = conn.execute(
            "SELECT MAX(datetime) FROM combined_market_analysis"
        ).fetchone()[0]

        df = pd.read_sql_query(
            """
            SELECT
                index_name,
                datetime,
                futures_price,
                futures_price_change_5c,
                futures_price_change_pct_5c,
                atm_strike,
                total_ce_oi,
                total_pe_oi,
                total_pcr,
                ce_oi_change_pm5,
                pe_oi_change_pm5,
                ce_oi_change_pct_pm5,
                pe_oi_change_pct_pm5,
                ce_activity_balance_pm5,
                pe_activity_balance_pm5,
                atm_iv,
                iv_rank,
                iv_percentile
            FROM combined_market_analysis
            WHERE datetime = ?
            ORDER BY index_name
            """,
            conn,
            params=(latest_datetime,),
        )

        df = df.rename(columns={
            "futures_price_change_5c": "Fut_5C_Change",
            "futures_price_change_pct_5c": "Fut_5C_%",
            "total_ce_oi": "CE_OI",
            "total_pe_oi": "PE_OI",
            "total_pcr": "PCR",
            "ce_oi_change_pm5": "CE_DeltaOI_±5",
            "pe_oi_change_pm5": "PE_DeltaOI_±5",
            "ce_oi_change_pct_pm5": "CE_DeltaOI_±5_%",
            "pe_oi_change_pct_pm5": "PE_DeltaOI_±5_%",
            "ce_activity_balance_pm5": "CE_Activity",
            "pe_activity_balance_pm5": "PE_Activity",
            "atm_iv": "ATM_IV_%",
            "iv_rank": "IV_Rank",
            "iv_percentile": "IV_Percentile",
        })

        df["ATM_IV_%"] = df["ATM_IV_%"] * 100

        print()
        print(f"Latest market state: {latest_datetime}")
        print(df.to_string(index=False))

    finally:
        conn.close()


if __name__ == "__main__":
    main()
