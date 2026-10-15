import sqlite3
from pathlib import Path


OPTION_PROJECT = Path(__file__).resolve().parents[1]

SOURCE_DATABASE = OPTION_PROJECT / "database" / "index_options.db"
ANALYSIS_DATABASE = OPTION_PROJECT / "database" / "oi_analysis.db"


INDEXES = ("NIFTY", "BANKNIFTY")


def get_latest_expiry(source, index_name):
    row = source.execute(
        """
        SELECT MAX(expiry)
        FROM index_options_data
        WHERE index_name = ?
        """,
        (index_name,),
    ).fetchone()

    return row[0]


def get_latest_timestamp(analysis, index_name, expiry):
    row = analysis.execute(
        """
        SELECT MAX(datetime)
        FROM strike_oi_analysis
        WHERE index_name = ?
          AND expiry = ?
        """,
        (index_name, expiry),
    ).fetchone()

    return row[0]


def calculate_price_change(
    source,
    analysis,
    index_name,
    expiry,
    timestamp,
    option_type,
    column_name,
):
    rows = source.execute(
        """
        SELECT
            strike,
            close
        FROM index_options_data
        WHERE index_name = ?
          AND expiry = ?
          AND option_type = ?
          AND datetime = ?
        ORDER BY strike
        """,
        (
            index_name,
            expiry,
            option_type,
            timestamp,
        ),
    ).fetchall()

    updates = []

    trading_date = timestamp[:10]

    for strike, close_price in rows:
        previous = source.execute(
            """
            SELECT close
            FROM index_options_data
            WHERE index_name = ?
              AND expiry = ?
              AND option_type = ?
              AND strike = ?
              AND datetime < ?
              AND datetime LIKE ?
            ORDER BY datetime DESC
            LIMIT 1
            """,
            (
                index_name,
                expiry,
                option_type,
                float(strike),
                timestamp,
                f"{trading_date}%",
            ),
        ).fetchone()

        if previous is None:
            price_change = None
        else:
            price_change = (
                float(close_price)
                - float(previous[0])
            )

        updates.append(
            (
                price_change,
                index_name,
                expiry,
                timestamp,
                float(strike),
            )
        )

    if updates:
        analysis.executemany(
            f"""
            UPDATE strike_oi_analysis
            SET {column_name} = ?
            WHERE index_name = ?
              AND expiry = ?
              AND datetime = ?
              AND strike = ?
            """,
            updates,
        )

        analysis.commit()

    return len(updates)


def process_index(source, analysis, index_name):
    expiry = get_latest_expiry(
        source,
        index_name,
    )

    if expiry is None:
        print(f"{index_name}: no expiry found")
        return 0

    timestamp = get_latest_timestamp(
        analysis,
        index_name,
        expiry,
    )

    if timestamp is None:
        print(
            f"{index_name}: no analysis timestamp"
        )
        return 0

    print(
        f"{index_name}: expiry={expiry}, "
        f"timestamp={timestamp}"
    )

    ce_count = calculate_price_change(
        source,
        analysis,
        index_name,
        expiry,
        timestamp,
        "CE",
        "ce_price_change",
    )

    pe_count = calculate_price_change(
        source,
        analysis,
        index_name,
        expiry,
        timestamp,
        "PE",
        "pe_price_change",
    )

    print(
        f"{index_name}: "
        f"CE={ce_count:,}, PE={pe_count:,}"
    )

    return ce_count + pe_count


def main():
    print("=" * 70)
    print("INCREMENTAL LIVE OPTION PRICE CHANGE")
    print("=" * 70)

    print(f"Source   : {SOURCE_DATABASE}")
    print(f"Analysis : {ANALYSIS_DATABASE}")
    print()

    source = sqlite3.connect(SOURCE_DATABASE)
    analysis = sqlite3.connect(ANALYSIS_DATABASE)

    try:
        total = 0

        for index_name in INDEXES:
            total += process_index(
                source,
                analysis,
                index_name,
            )

    finally:
        source.close()
        analysis.close()

    print()
    print("=" * 70)
    print("INCREMENTAL OPTION PRICE CHANGE COMPLETED")
    print("=" * 70)
    print(f"Rows updated : {total:,}")


if __name__ == "__main__":
    main()
