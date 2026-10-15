import sqlite3
from pathlib import Path


OPTION_PROJECT = Path(__file__).resolve().parents[1]

SOURCE_DATABASE = OPTION_PROJECT / "database" / "index_options.db"
OUTPUT_DATABASE = OPTION_PROJECT / "database" / "oi_analysis.db"

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


def get_last_processed_timestamp(output, index_name, expiry):
    row = output.execute(
        """
        SELECT MAX(datetime)
        FROM strike_oi_analysis
        WHERE index_name = ?
          AND expiry = ?
        """,
        (index_name, expiry),
    ).fetchone()

    return row[0]


def process_index(source, output, index_name):
    expiry = get_latest_expiry(source, index_name)

    if expiry is None:
        print(f"{index_name}: no expiry found")
        return 0

    last_timestamp = get_last_processed_timestamp(
        output,
        index_name,
        expiry,
    )

    if last_timestamp is None:
        start_condition = ""
        params = (index_name, expiry)
        print(
            f"{index_name}: no existing rows for expiry {expiry}"
        )
    else:
        start_condition = "AND datetime > ?"
        params = (
            index_name,
            expiry,
            last_timestamp,
        )

        print(
            f"{index_name}: expiry={expiry}, "
            f"last_processed={last_timestamp}"
        )

    query = f"""
        SELECT
            datetime,
            strike,

            MAX(
                CASE
                    WHEN option_type = 'CE'
                    THEN open_interest
                    ELSE 0
                END
            ) AS ce_oi,

            MAX(
                CASE
                    WHEN option_type = 'PE'
                    THEN open_interest
                    ELSE 0
                END
            ) AS pe_oi,

            MAX(
                CASE
                    WHEN option_type = 'CE'
                    THEN volume
                    ELSE 0
                END
            ) AS ce_volume,

            MAX(
                CASE
                    WHEN option_type = 'PE'
                    THEN volume
                    ELSE 0
                END
            ) AS pe_volume

        FROM index_options_data

        WHERE index_name = ?
          AND expiry = ?
          AND option_type IN ('CE', 'PE')
          {start_condition}

        GROUP BY datetime, strike

        HAVING
            SUM(
                CASE
                    WHEN option_type = 'CE'
                    THEN 1
                    ELSE 0
                END
            ) > 0

            AND

            SUM(
                CASE
                    WHEN option_type = 'PE'
                    THEN 1
                    ELSE 0
                END
            ) > 0

        ORDER BY datetime, strike
    """

    rows = source.execute(query, params)

    batch = []
    inserted = 0

    for (
        timestamp,
        strike,
        ce_oi,
        pe_oi,
        ce_volume,
        pe_volume,
    ) in rows:

        ce_oi = float(ce_oi or 0)
        pe_oi = float(pe_oi or 0)
        ce_volume = float(ce_volume or 0)
        pe_volume = float(pe_volume or 0)

        total_oi = ce_oi + pe_oi

        pcr = (
            pe_oi / ce_oi
            if ce_oi > 0
            else None
        )

        batch.append(
            (
                index_name,
                expiry,
                timestamp,
                strike,
                ce_oi,
                pe_oi,
                ce_volume,
                pe_volume,
                total_oi,
                pcr,
            )
        )

        if len(batch) >= 5000:
            output.executemany(
                """
                INSERT OR REPLACE INTO strike_oi_analysis (
                    index_name,
                    expiry,
                    datetime,
                    strike,
                    ce_oi,
                    pe_oi,
                    ce_volume,
                    pe_volume,
                    total_oi,
                    pcr
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                batch,
            )

            inserted += len(batch)
            batch.clear()

    if batch:
        output.executemany(
            """
            INSERT OR REPLACE INTO strike_oi_analysis (
                index_name,
                expiry,
                datetime,
                strike,
                ce_oi,
                pe_oi,
                ce_volume,
                pe_volume,
                total_oi,
                pcr
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            batch,
        )

        inserted += len(batch)

    output.commit()

    print(
        f"{index_name}: inserted/updated {inserted:,} rows"
    )

    return inserted


def main():
    print("=" * 70)
    print("INCREMENTAL LIVE STRIKE OI ANALYSIS")
    print("=" * 70)

    print(f"Source : {SOURCE_DATABASE}")
    print(f"Output : {OUTPUT_DATABASE}")
    print()

    source = sqlite3.connect(SOURCE_DATABASE)
    output = sqlite3.connect(OUTPUT_DATABASE)

    try:
        total = 0

        for index_name in INDEXES:
            total += process_index(
                source,
                output,
                index_name,
            )

    finally:
        source.close()
        output.close()

    print()
    print("=" * 70)
    print("INCREMENTAL STRIKE OI ANALYSIS COMPLETED")
    print("=" * 70)
    print(f"Rows inserted/updated : {total:,}")


if __name__ == "__main__":
    main()
