import sqlite3
from pathlib import Path


OPTION_PROJECT = Path(__file__).resolve().parents[1]
DATABASE = OPTION_PROJECT / "database" / "oi_analysis.db"


def get_last_processed_timestamp(conn, index_name):
    row = conn.execute(
        """
        SELECT MAX(datetime)
        FROM strike_oi_analysis
        WHERE index_name = ?
        """,
        (index_name,),
    ).fetchone()

    return row[0]


def calculate_for_index(conn, index_name):
    last_timestamp = get_last_processed_timestamp(
        conn,
        index_name,
    )

    if last_timestamp is None:
        print(f"{index_name}: no data")
        return 0

    # Find rows at the latest timestamp.
    # The live strike-OI processor inserts new timestamps here.
    rows = conn.execute(
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
          AND datetime = ?
        ORDER BY strike
        """,
        (index_name, last_timestamp),
    ).fetchall()

    if not rows:
        print(
            f"{index_name}: no rows at {last_timestamp}"
        )
        return 0

    updates = []

    for (
        row_id,
        timestamp,
        strike,
        ce_oi,
        pe_oi,
        total_oi,
    ) in rows:

        trading_date = timestamp[:10]

        previous = conn.execute(
            """
            SELECT
                ce_oi,
                pe_oi,
                total_oi
            FROM strike_oi_analysis
            WHERE index_name = ?
              AND datetime < ?
              AND datetime LIKE ?
              AND strike = ?
            ORDER BY datetime DESC
            LIMIT 1
            """,
            (
                index_name,
                timestamp,
                f"{trading_date}%",
                float(strike),
            ),
        ).fetchone()

        if previous is None:
            updates.append(
                (
                    None,
                    None,
                    None,
                    row_id,
                )
            )
            continue

        previous_ce, previous_pe, previous_total = previous

        updates.append(
            (
                float(ce_oi) - float(previous_ce),
                float(pe_oi) - float(previous_pe),
                float(total_oi) - float(previous_total),
                row_id,
            )
        )

    conn.executemany(
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

    conn.commit()

    print(
        f"{index_name}: updated {len(updates):,} rows "
        f"for {last_timestamp}"
    )

    return len(updates)


def main():
    print("=" * 70)
    print("INCREMENTAL LIVE OI CHANGE")
    print("=" * 70)

    print(f"Database : {DATABASE}")
    print()

    conn = sqlite3.connect(DATABASE)

    try:
        total = 0

        for index_name in ("NIFTY", "BANKNIFTY"):
            total += calculate_for_index(
                conn,
                index_name,
            )

    finally:
        conn.close()

    print()
    print("=" * 70)
    print("INCREMENTAL OI CHANGE COMPLETED")
    print("=" * 70)
    print(f"Rows updated : {total:,}")


if __name__ == "__main__":
    main()
