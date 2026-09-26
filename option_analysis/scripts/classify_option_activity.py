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
# CLASSIFICATION
# ============================================================

def classify_activity(price_change, oi_change):
    """
    Classify option activity using premium change and OI change.
    """

    if price_change is None or oi_change is None:
        return None

    price_change = float(price_change)
    oi_change = float(oi_change)

    if price_change > 0 and oi_change > 0:
        return "LONG_BUILDUP"

    if price_change < 0 and oi_change > 0:
        return "SHORT_BUILDUP"

    if price_change > 0 and oi_change < 0:
        return "SHORT_COVERING"

    if price_change < 0 and oi_change < 0:
        return "LONG_UNWINDING"

    return "NEUTRAL"


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 65)
    print("CLASSIFYING OPTION ACTIVITY")
    print("=" * 65)

    print(f"Database : {DATABASE}")
    print()

    connection = sqlite3.connect(DATABASE)

    try:

        # ----------------------------------------------------
        # Clear previous classifications.
        # ----------------------------------------------------

        connection.execute(
            """
            UPDATE strike_oi_analysis
            SET
                ce_activity = NULL,
                pe_activity = NULL
            """
        )

        connection.commit()

        # ----------------------------------------------------
        # Read required columns.
        # ----------------------------------------------------

        rows = connection.execute(
            """
            SELECT
                id,
                ce_price_change,
                ce_oi_change,
                pe_price_change,
                pe_oi_change
            FROM strike_oi_analysis
            """
        )

        updates = []

        processed = 0

        for (
            row_id,
            ce_price_change,
            ce_oi_change,
            pe_price_change,
            pe_oi_change,
        ) in rows:

            ce_activity = classify_activity(
                ce_price_change,
                ce_oi_change,
            )

            pe_activity = classify_activity(
                pe_price_change,
                pe_oi_change,
            )

            updates.append(
                (
                    ce_activity,
                    pe_activity,
                    row_id,
                )
            )

            processed += 1

            # ------------------------------------------------
            # Batch update.
            # ------------------------------------------------

            if len(updates) >= 5000:

                connection.executemany(
                    """
                    UPDATE strike_oi_analysis
                    SET
                        ce_activity = ?,
                        pe_activity = ?
                    WHERE id = ?
                    """,
                    updates,
                )

                connection.commit()
                updates.clear()

        # ----------------------------------------------------
        # Remaining rows.
        # ----------------------------------------------------

        if updates:

            connection.executemany(
                """
                UPDATE strike_oi_analysis
                SET
                    ce_activity = ?,
                    pe_activity = ?
                WHERE id = ?
                """,
                updates,
            )

            connection.commit()

        print(
            f"Rows processed : {processed:,}"
        )

    finally:

        connection.close()

    print()
    print("=" * 65)
    print("OPTION ACTIVITY CLASSIFICATION COMPLETED")
    print("=" * 65)


if __name__ == "__main__":
    main()