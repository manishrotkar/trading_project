from pathlib import Path
import sqlite3


OPTION_PROJECT = Path(__file__).resolve().parents[1]

DB_PATH = OPTION_PROJECT / "database" / "oi_analysis.db"


def main():
    print("Starting chain summary rebuild...")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Rebuild only chain_summary.
    cur.execute("DELETE FROM chain_summary")
    conn.commit()

    # Use the corrected ATM analysis as the master timestamp/expiry/futures source.
    rows = cur.execute(
        """
        SELECT
            index_name,
            expiry,
            datetime,
            futures_price,
            atm_strike
        FROM atm_oi_analysis
        ORDER BY index_name, datetime
        """
    ).fetchall()

    total_inserted = 0

    for (
        index_name,
        expiry,
        datetime,
        futures_price,
        atm_strike,
    ) in rows:

        # Sum the exact selected strikes present in
        # strike_oi_analysis for this timestamp.
        chain = cur.execute(
            """
            SELECT
                COALESCE(SUM(ce_oi), 0),
                COALESCE(SUM(pe_oi), 0)
            FROM strike_oi_analysis
            WHERE index_name = ?
              AND expiry = ?
              AND datetime = ?
            """,
            (
                index_name,
                expiry,
                datetime,
            ),
        ).fetchone()

        total_ce_oi, total_pe_oi = chain

        # No chain data means we cannot create a valid summary.
        if total_ce_oi == 0 and total_pe_oi == 0:
            continue

        total_oi = total_ce_oi + total_pe_oi

        total_pcr = (
            total_pe_oi / total_ce_oi
            if total_ce_oi != 0
            else None
        )

        cur.execute(
            """
            INSERT INTO chain_summary (
                index_name,
                expiry,
                datetime,
                futures_price,
                atm_strike,
                total_ce_oi,
                total_pe_oi,
                total_oi,
                total_pcr
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                index_name,
                expiry,
                datetime,
                futures_price,
                atm_strike,
                total_ce_oi,
                total_pe_oi,
                total_oi,
                total_pcr,
            ),
        )

        total_inserted += 1

    conn.commit()
    conn.close()

    print("\nChain summary rebuild completed.")
    print(f"Rows inserted: {total_inserted}")


if __name__ == "__main__":
    main()
