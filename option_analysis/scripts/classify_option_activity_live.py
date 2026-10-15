import sqlite3
from pathlib import Path

OPTION_PROJECT = Path(__file__).resolve().parents[1]

DATABASE = OPTION_PROJECT / "database" / "oi_analysis.db"

INDEXES = ("NIFTY", "BANKNIFTY")


def classify_activity(price_change, oi_change):
    """Classify option activity using premium change and OI change."""

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


def get_latest_expiry(connection, index_name):
    row = connection.execute(
        """
        SELECT MAX(expiry)
        FROM strike_oi_analysis
        WHERE index_name = ?
        """,
        (index_name,),
    ).fetchone()

    return row[0]


def get_latest_timestamp(connection, index_name, expiry):
    row = connection.execute(
        """
        SELECT MAX(datetime)
        FROM strike_oi_analysis
        WHERE index_name = ?
          AND expiry = ?
        """,
        (index_name, expiry),
    ).fetchone()

    return row[0]


def process_index(connection, index_name):

    expiry = get_latest_expiry(connection, index_name)

    if expiry is None:
        print(f"{index_name}: no expiry found")
        return 0

    timestamp = get_latest_timestamp(
        connection,
        index_name,
        expiry,
    )

    if timestamp is None:
        print(f"{index_name}: no timestamp found")
        return 0

    print(
        f"{index_name}: "
        f"expiry={expiry}, "
        f"timestamp={timestamp}"
    )

    rows = connection.execute(
        """
        SELECT
            id,
            ce_price_change,
            ce_oi_change,
            pe_price_change,
            pe_oi_change
        FROM strike_oi_analysis
        WHERE index_name = ?
          AND expiry = ?
          AND datetime = ?
        ORDER BY strike
        """,
        (
            index_name,
            expiry,
            timestamp,
        ),
    ).fetchall()

    updates = []

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
        f"{index_name}: "
        f"rows updated={len(updates):,}"
    )

    return len(updates)


def main():

    print("=" * 70)
    print("INCREMENTAL LIVE OPTION ACTIVITY CLASSIFICATION")
    print("=" * 70)

    print(f"Database : {DATABASE}")
    print()

    connection = sqlite3.connect(DATABASE)

    try:

        total = 0

        for index_name in INDEXES:

            total += process_index(
                connection,
                index_name,
            )

    finally:

        connection.close()

    print()
    print("=" * 70)
    print("INCREMENTAL OPTION ACTIVITY CLASSIFICATION COMPLETED")
    print("=" * 70)

    print(
        f"Rows updated : {total:,}"
    )


if __name__ == "__main__":
    main()
