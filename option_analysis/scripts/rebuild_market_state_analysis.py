from pathlib import Path
import sqlite3
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "option_analysis" / "database" / "oi_analysis.db"


def price_state(change):
    if change is None:
        return None
    if change > 0:
        return "UP"
    if change < 0:
        return "DOWN"
    return "FLAT"


def oi_state(change):
    if change is None:
        return None
    if change > 0:
        return "OI_BUILDUP"
    if change < 0:
        return "OI_REDUCTION"
    return "FLAT"


def pcr_state(pcr):
    if pcr is None:
        return None

    if pcr < 0.80:
        return "LOW"

    if pcr <= 1.20:
        return "NORMAL"

    return "HIGH"


def iv_rank_state(iv_rank):
    if iv_rank is None:
        return None

    if iv_rank < 25:
        return "LOW"

    if iv_rank < 50:
        return "MEDIUM"

    if iv_rank < 75:
        return "HIGH"

    return "VERY_HIGH"


def main():
    print("Rebuilding market_state_analysis...")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # ---------------------------------------------------------
        # 1. Clear only market_state_analysis
        # ---------------------------------------------------------
        conn.execute("DELETE FROM market_state_analysis")

        # ---------------------------------------------------------
        # 2. Read corrected combined market analysis
        # ---------------------------------------------------------
        rows = conn.execute(
            """
            SELECT
                index_name,
                expiry,
                datetime,
                futures_price_change_5c,
                futures_price_change_pct_5c,
                ce_activity_balance_pm5,
                pe_activity_balance_pm5,
                total_pcr,
                atm_iv,
                iv_rank,
                iv_percentile
            FROM combined_market_analysis
            ORDER BY index_name, datetime
            """
        ).fetchall()

        inserted = 0

        for row in rows:

            # -----------------------------------------------------
            # Price state
            # -----------------------------------------------------
            p_state = price_state(
                row["futures_price_change_5c"]
            )

            # -----------------------------------------------------
            # OI state
            # -----------------------------------------------------
            ce_state = oi_state(
                row["ce_activity_balance_pm5"]
            )

            pe_state = oi_state(
                row["pe_activity_balance_pm5"]
            )

            # -----------------------------------------------------
            # PCR state
            # -----------------------------------------------------
            pcr_state_value = pcr_state(
                row["total_pcr"]
            )

            # -----------------------------------------------------
            # IV Rank state
            # -----------------------------------------------------
            iv_rank_state_value = iv_rank_state(
                row["iv_rank"]
            )

            # -----------------------------------------------------
            # Insert
            # -----------------------------------------------------
            conn.execute(
                """
                INSERT INTO market_state_analysis (
                    index_name,
                    expiry,
                    datetime,
                    price_state,
                    ce_oi_state,
                    pe_oi_state,
                    ce_activity_balance_pm5,
                    pe_activity_balance_pm5,
                    total_pcr,
                    atm_iv,
                    iv_rank,
                    iv_percentile,
                    pcr_state,
                    iv_rank_state,
                    forward_price_change_5c,
                    forward_price_change_pct_5c
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["index_name"],
                    row["expiry"],
                    row["datetime"],
                    p_state,
                    ce_state,
                    pe_state,
                    row["ce_activity_balance_pm5"],
                    row["pe_activity_balance_pm5"],
                    row["total_pcr"],
                    row["atm_iv"],
                    row["iv_rank"],
                    row["iv_percentile"],
                    pcr_state_value,
                    iv_rank_state_value,
                    None,
                    None,
                ),
            )

            inserted += 1

        conn.commit()

        print(f"Rows inserted: {inserted}")

        # ---------------------------------------------------------
        # 3. Verify latest timestamp
        # ---------------------------------------------------------
        print("\nLatest market states:")

        latest_datetime = conn.execute(
            "SELECT MAX(datetime) FROM market_state_analysis"
        ).fetchone()[0]

        df = pd.read_sql_query(
            """
            SELECT
                index_name,
                datetime,
                price_state,
                ce_oi_state,
                pe_oi_state,
                ce_activity_balance_pm5,
                pe_activity_balance_pm5,
                total_pcr,
                pcr_state,
                atm_iv,
                iv_rank,
                iv_rank_state,
                forward_price_change_5c,
                forward_price_change_pct_5c
            FROM market_state_analysis
            WHERE datetime = ?
            ORDER BY index_name
            """,
            conn,
            params=(latest_datetime,),
        )

        df = df.rename(columns={
            "ce_activity_balance_pm5": "CE_Activity",
            "pe_activity_balance_pm5": "PE_Activity",
            "total_pcr": "PCR",
            "atm_iv": "ATM_IV_%",
            "iv_rank": "IV_Rank",
            "iv_rank_state": "IV_Rank_State",
            "forward_price_change_5c": "Forward_5C_Change",
            "forward_price_change_pct_5c": "Forward_5C_%",
        })

        df["ATM_IV_%"] = df["ATM_IV_%"] * 100

        print()
        print(f"Latest market state: {latest_datetime}")
        print(df.to_string(index=False))

    finally:
        conn.close()


if __name__ == "__main__":
    main()

