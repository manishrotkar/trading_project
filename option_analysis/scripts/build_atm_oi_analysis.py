import sqlite3
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

TRADING_PROJECT = Path(__file__).resolve().parents[2]

IV_DATABASE = (
    TRADING_PROJECT
    / "option_analysis"
    / "database"
    / "iv_analysis.db"
)

OI_DATABASE = (
    TRADING_PROJECT
    / "option_analysis"
    / "database"
    / "oi_analysis.db"
)

FUTURES_DATABASE = (
    TRADING_PROJECT
    / "futures_project"
    / "database"
    / "futures.db"
)


# ============================================================
# SETTINGS
# ============================================================

EXPIRY = "2026-09-29"

INDEXES = (
    "NIFTY",
    "BANKNIFTY",
)


# ============================================================
# FUTURES SYMBOLS
# ============================================================

FUTURES_SYMBOL_PREFIX = {
    "NIFTY": "NSE:NIFTY",
    "BANKNIFTY": "NSE:BANKNIFTY",
}


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 65)
    print("BUILDING ATM OI ANALYSIS")
    print("=" * 65)

    print(f"IV database      : {IV_DATABASE}")
    print(f"OI database      : {OI_DATABASE}")
    print(f"Futures database : {FUTURES_DATABASE}")
    print(f"Expiry           : {EXPIRY}")
    print()

    iv_db = sqlite3.connect(IV_DATABASE)
    oi_db = sqlite3.connect(OI_DATABASE)
    futures_db = sqlite3.connect(FUTURES_DATABASE)

    try:

        # ----------------------------------------------------
        # Clear previous ATM analysis.
        # ----------------------------------------------------

        oi_db.execute(
            "DELETE FROM atm_oi_analysis"
        )

        oi_db.commit()

        total_inserted = 0

        for index_name in INDEXES:

            print(f"Processing {index_name}...")

            # ------------------------------------------------
            # Read ATM IV + IV Rank + Percentile.
            # ------------------------------------------------

            iv_rows = iv_db.execute(
                """
                SELECT
                    a.datetime,
                    a.futures_price,
                    a.atm_strike,
                    a.atm_iv,
                    r.iv_rank,
                    r.iv_percentile,
                    r.actual_lookback_days
                FROM atm_iv a

                LEFT JOIN iv_rank_percentile r
                    ON r.index_name = a.index_name
                    AND r.datetime = a.datetime
                    AND r.lookback_days = 25

                WHERE a.index_name = ?

                ORDER BY a.datetime
                """,
                (index_name,),
            ).fetchall()

            batch = []

            for (
                timestamp,
                futures_price,
                atm_strike,
                atm_iv,
                iv_rank,
                iv_percentile,
                actual_lookback_days,
            ) in iv_rows:

                # ------------------------------------------------
                # Find ATM strike data.
                # ------------------------------------------------

                oi_row = oi_db.execute(
                    """
                    SELECT
                        ce_oi,
                        pe_oi,
                        total_oi,
                        pcr,
                        ce_oi_change,
                        pe_oi_change,
                        ce_activity,
                        pe_activity
                    FROM strike_oi_analysis
                    WHERE
                        index_name = ?
                        AND expiry = ?
                        AND datetime = ?
                        AND strike = ?
                    """,
                    (
                        index_name,
                        EXPIRY,
                        timestamp,
                        float(atm_strike),
                    ),
                ).fetchone()

                if oi_row is None:
                    continue

                (
                    ce_oi,
                    pe_oi,
                    total_oi,
                    pcr,
                    ce_oi_change,
                    pe_oi_change,
                    ce_activity,
                    pe_activity,
                ) = oi_row

                batch.append(
                    (
                        index_name,
                        EXPIRY,
                        timestamp,
                        float(futures_price),
                        float(atm_strike),
                        float(ce_oi),
                        float(pe_oi),
                        float(total_oi),
                        pcr,
                        ce_oi_change,
                        pe_oi_change,
                        ce_activity,
                        pe_activity,
                        float(atm_iv),
                        iv_rank,
                        iv_percentile,
                        actual_lookback_days,
                    )
                )

                if len(batch) >= 1000:

                    oi_db.executemany(
                        """
                        INSERT OR REPLACE INTO atm_oi_analysis (
                            index_name,
                            expiry,
                            datetime,
                            futures_price,
                            atm_strike,
                            atm_ce_oi,
                            atm_pe_oi,
                            atm_total_oi,
                            atm_pcr,
                            atm_ce_oi_change,
                            atm_pe_oi_change,
                            atm_ce_activity,
                            atm_pe_activity,
                            atm_iv,
                            iv_rank,
                            iv_percentile,
                            actual_lookback_days
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        batch,
                    )

                    total_inserted += len(batch)
                    batch.clear()

            # ------------------------------------------------
            # Remaining rows.
            # ------------------------------------------------

            if batch:

                oi_db.executemany(
                    """
                    INSERT OR REPLACE INTO atm_oi_analysis (
                        index_name,
                        expiry,
                        datetime,
                        futures_price,
                        atm_strike,
                        atm_ce_oi,
                        atm_pe_oi,
                        atm_total_oi,
                        atm_pcr,
                        atm_ce_oi_change,
                        atm_pe_oi_change,
                        atm_ce_activity,
                        atm_pe_activity,
                        atm_iv,
                        iv_rank,
                        iv_percentile,
                        actual_lookback_days
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    batch,
                )

                total_inserted += len(batch)

            oi_db.commit()

            print(
                f"{index_name} completed."
            )

    finally:

        iv_db.close()
        oi_db.close()
        futures_db.close()

    print()
    print("=" * 65)
    print("ATM OI ANALYSIS COMPLETED")
    print("=" * 65)

    print(
        f"Rows inserted : {total_inserted:,}"
    )


if __name__ == "__main__":
    main()