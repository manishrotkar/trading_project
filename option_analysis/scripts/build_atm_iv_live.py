import sqlite3
from pathlib import Path

OPTION_PROJECT = Path(__file__).resolve().parents[1]

FYERS_IV_DB = (
    OPTION_PROJECT
    / "database"
    / "fyers_style_iv.db"
)

FUTURES_DB = (
    OPTION_PROJECT.parent
    / "futures_project"
    / "database"
    / "futures.db"
)

ANALYSIS_DB = (
    OPTION_PROJECT
    / "database"
    / "iv_analysis.db"
)

INDEXES = (
    "NIFTY",
    "BANKNIFTY",
)

FUTURES_PREFIX = {
    "NIFTY": "NSE:NIFTY",
    "BANKNIFTY": "NSE:BANKNIFTY",
}


def open_readonly(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Database not found: {path}"
        )

    return sqlite3.connect(
        path.resolve().as_uri() + "?mode=ro",
        uri=True,
    )


def get_futures_price(
    futures_connection,
    index_name,
    timestamp,
):
    prefix = FUTURES_PREFIX[index_name]

    futures_timestamp = (
        timestamp.replace(" ", "T")
        + "+05:30"
    )

    row = futures_connection.execute(
        """
        SELECT
            close,
            expiry,
            symbol
        FROM futures_data
        WHERE symbol LIKE ?
          AND datetime = ?
        ORDER BY expiry ASC
        LIMIT 1
        """,
        (
            prefix + "%FUT",
            futures_timestamp,
        ),
    ).fetchone()

    if row is None:
        return None

    return float(row[0])


def get_latest_atm_timestamp(
    output_connection,
    index_name,
):
    row = output_connection.execute(
        """
        SELECT MAX(datetime)
        FROM atm_iv
        WHERE index_name = ?
        """,
        (index_name,),
    ).fetchone()

    return row[0]


def process_index(
    iv_connection,
    futures_connection,
    output_connection,
    index_name,
):
    last_timestamp = get_latest_atm_timestamp(
        output_connection,
        index_name,
    )

    if last_timestamp is None:
        print(
            f"{index_name}: "
            "no previous ATM-IV timestamp"
        )

        rows = iv_connection.execute(
            """
            SELECT
                datetime,
                strike,
                iv
            FROM option_iv_data
            WHERE index_name = ?
              AND iv IS NOT NULL
            ORDER BY datetime, strike
            """,
            (index_name,),
        ).fetchall()

    else:
        print(
            f"{index_name}: "
            f"last ATM-IV={last_timestamp}"
        )

        rows = iv_connection.execute(
            """
            SELECT
                datetime,
                strike,
                iv
            FROM option_iv_data
            WHERE index_name = ?
              AND datetime > ?
              AND iv IS NOT NULL
            ORDER BY datetime, strike
            """,
            (
                index_name,
                last_timestamp,
            ),
        ).fetchall()

    if not rows:
        print(
            f"{index_name}: "
            "no new IV data"
        )
        return 0

    processed = 0
    skipped = 0

    current_timestamp = None
    strike_rows = []

    def process_timestamp(
        timestamp,
        rows_for_timestamp,
    ):
        nonlocal processed
        nonlocal skipped

        if not rows_for_timestamp:
            return

        futures_price = get_futures_price(
            futures_connection,
            index_name,
            timestamp,
        )

        if futures_price is None:
            skipped += 1
            print(
                f"{index_name}: "
                f"no futures price for {timestamp}"
            )
            return

        atm_strike, atm_iv = min(
            rows_for_timestamp,
            key=lambda item: abs(
                item[0] - futures_price
            ),
        )

        output_connection.execute(
            """
            INSERT OR REPLACE INTO atm_iv (
                index_name,
                datetime,
                futures_price,
                atm_strike,
                atm_iv
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                index_name,
                timestamp,
                futures_price,
                atm_strike,
                atm_iv,
            ),
        )

        processed += 1

    for timestamp, strike, iv in rows:

        if current_timestamp is None:
            current_timestamp = timestamp

        elif timestamp != current_timestamp:

            process_timestamp(
                current_timestamp,
                strike_rows,
            )

            strike_rows = []
            current_timestamp = timestamp

        strike_rows.append(
            (
                float(strike),
                float(iv),
            )
        )

    if current_timestamp is not None:
        process_timestamp(
            current_timestamp,
            strike_rows,
        )

    output_connection.commit()

    print(
        f"{index_name}: "
        f"ATM-IV rows written={processed:,}, "
        f"skipped={skipped:,}"
    )

    return processed


def main():

    print("=" * 70)
    print("INCREMENTAL ATM IV CALCULATION")
    print("=" * 70)

    print(f"FYERS IV DB : {FYERS_IV_DB}")
    print(f"Futures DB  : {FUTURES_DB}")
    print(f"Output DB   : {ANALYSIS_DB}")
    print()

    iv_connection = open_readonly(
        FYERS_IV_DB
    )

    futures_connection = open_readonly(
        FUTURES_DB
    )

    output_connection = sqlite3.connect(
        ANALYSIS_DB
    )

    try:

        total = 0

        for index_name in INDEXES:

            total += process_index(
                iv_connection,
                futures_connection,
                output_connection,
                index_name,
            )

    finally:

        iv_connection.close()
        futures_connection.close()
        output_connection.close()

    print()
    print("=" * 70)
    print("INCREMENTAL ATM IV COMPLETED")
    print("=" * 70)

    print(
        f"Total ATM-IV rows written : {total:,}"
    )


if __name__ == "__main__":
    main()
