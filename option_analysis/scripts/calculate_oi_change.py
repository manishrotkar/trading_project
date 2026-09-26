import sqlite3
from pathlib import Path


# ============================================================
# PATH
# ============================================================

OPTION_PROJECT = Path(__file__).resolve().parents[1]

DATABASE = (
    OPTION_PROJECT
    / "database"
    / "oi_analysis.db"
)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 65)
    print("CALCULATING OI CHANGE")
    print("=" * 65)

    print(f"Database : {DATABASE}")
    print()

    connection = sqlite3.connect(DATABASE)

    try:

        # ----------------------------------------------------
        # Clear previous calculations.
        # ----------------------------------------------------

        connection.execute(
            """
            UPDATE strike_oi_analysis
            SET
                ce_oi_change = NULL,
                pe_oi_change = NULL,
                total_oi_change = NULL
            """
        )

        connection.commit()

        # ----------------------------------------------------
        # Process each index separately.
        # ----------------------------------------------------

        indexes = connection.execute(
            """
            SELECT DISTINCT index_name
            FROM strike_oi_analysis
            ORDER BY index_name
            """
        ).fetchall()

        total_updated = 0

        for (index_name,) in indexes:

            print(f"Processing {index_name}...")

            previous = {}

            rows = connection.execute(
                """
                SELECT
                    id,
                    datetime,
                    strike,
                    ce_oi,
                    pe_oi,
                    total_oi
                FROM strike_oi_analysis
                WHERE index_name = ?
                ORDER BY datetime, strike
                """,
                (index_name,),
            )

            updates = []

            for (
                row_id,
                timestamp,
                strike,
                ce_oi,
                pe_oi,
                total_oi,
            ) in rows:

                # ------------------------------------------------
                # Trading date.
                #
                # This prevents calculating ΔOI across
                # overnight/session gaps.
                # ------------------------------------------------

                trading_date = timestamp[:10]

                key = (
                    trading_date,
                    float(strike),
                )

                if key in previous:

                    (
                        previous_ce_oi,
                        previous_pe_oi,
                        previous_total_oi,
                    ) = previous[key]

                    ce_change = (
                        float(ce_oi)
                        - previous_ce_oi
                    )

                    pe_change = (
                        float(pe_oi)
                        - previous_pe_oi
                    )

                    total_change = (
                        float(total_oi)
                        - previous_total_oi
                    )

                    updates.append(
                        (
                            ce_change,
                            pe_change,
                            total_change,
                            row_id,
                        )
                    )

                # ------------------------------------------------
                # Store current values for next timestamp.
                # ------------------------------------------------

                previous[key] = (
                    float(ce_oi),
                    float(pe_oi),
                    float(total_oi),
                )

                # ------------------------------------------------
                # Batch update.
                # ------------------------------------------------

                if len(updates) >= 5000:

                    connection.executemany(
                        """
                        UPDATE strike_oi_analysis
                        SET
                            ce_oi_change = ?,
                            pe_oi_change = ?,
                            total_oi_change = ?
                        WHERE id = ?
                        """,
                        updates,
                    )

                    total_updated += len(updates)
                    updates.clear()

            # ----------------------------------------------------
            # Remaining rows.
            # ----------------------------------------------------

            if updates:

                connection.executemany(
                    """
                    UPDATE strike_oi_analysis
                    SET
                        ce_oi_change = ?,
                        pe_oi_change = ?,
                        total_oi_change = ?
                    WHERE id = ?
                    """,
                    updates,
                )

                total_updated += len(updates)

            connection.commit()

            print(
                f"{index_name} completed."
            )

    finally:

        connection.close()

    print()
    print("=" * 65)
    print("OI CHANGE CALCULATION COMPLETED")
    print("=" * 65)

    print(
        f"Rows updated : {total_updated:,}"
    )


if __name__ == "__main__":
    main()