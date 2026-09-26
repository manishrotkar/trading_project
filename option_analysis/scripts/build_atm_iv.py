import sqlite3
from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

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


# ============================================================
# INDEX / FUTURES MAPPING
# ============================================================

FUTURES_PREFIX = {
    "NIFTY": "NSE:NIFTY",
    "BANKNIFTY": "NSE:BANKNIFTY",
}


# ============================================================
# READ-ONLY DATABASE
# ============================================================

def open_readonly(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Database not found: {path}"
        )

    return sqlite3.connect(
        path.resolve().as_uri() + "?mode=ro",
        uri=True,
    )


# ============================================================
# GET FUTURES PRICE
# ============================================================

def get_futures_price(
    futures_connection,
    index_name,
    timestamp,
):
    """
    Get the nearest available futures contract
    for the given timestamp.

    The futures database contains:
        - current/near expiry
        - next expiry
        - far expiry

    We select the contract with the earliest
    expiry available at that timestamp.
    """

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


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 65)
    print("BUILDING ATM IV")
    print("=" * 65)

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

        cursor = iv_connection.execute(
            """
            SELECT
                index_name,
                datetime,
                strike,
                iv
            FROM option_iv_data
            WHERE iv IS NOT NULL
              AND index_name IN (
                  'NIFTY',
                  'BANKNIFTY'
              )
            GROUP BY
                index_name,
                datetime,
                strike
            ORDER BY
                index_name,
                datetime,
                strike
            """
        )

        # ----------------------------------------------------
        # Collect IV by timestamp.
        # We need all strikes at a timestamp to determine
        # which strike is closest to the futures price.
        # ----------------------------------------------------

        current_index = None
        current_datetime = None
        strikes = []

        processed_timestamps = 0
        inserted_rows = 0
        skipped_rows = 0

        def process_timestamp(
            index_name,
            timestamp,
            strike_rows,
        ):

            nonlocal processed_timestamps
            nonlocal inserted_rows
            nonlocal skipped_rows

            if not strike_rows:
                return

            futures_price = get_futures_price(
                futures_connection,
                index_name,
                timestamp,
            )

            if futures_price is None:
                skipped_rows += 1
                return

            # ------------------------------------------------
            # Find strike closest to futures price.
            # ------------------------------------------------

            atm_strike, atm_iv = min(
                strike_rows,
                key=lambda item: abs(
                    item[0] - futures_price
                )
            )

            # ------------------------------------------------
            # Replace existing row.
            #
            # Important:
            # We corrected futures-contract selection,
            # therefore old ATM-IV rows must be replaced.
            # ------------------------------------------------

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

            inserted_rows += 1
            processed_timestamps += 1

            if processed_timestamps % 5000 == 0:

                output_connection.commit()

                print(
                    f"Timestamps processed: "
                    f"{processed_timestamps:,} | "
                    f"Rows written: "
                    f"{inserted_rows:,}"
                )

        # ----------------------------------------------------
        # Read IV rows grouped by index + timestamp.
        # ----------------------------------------------------

        for index_name, timestamp, strike, iv in cursor:

            key = (
                index_name,
                timestamp,
            )

            current_key = (
                current_index,
                current_datetime,
            )

            if current_index is None:

                current_index = index_name
                current_datetime = timestamp

            elif key != current_key:

                process_timestamp(
                    current_index,
                    current_datetime,
                    strikes,
                )

                strikes = []

                current_index = index_name
                current_datetime = timestamp

            strikes.append(
                (
                    float(strike),
                    float(iv),
                )
            )

        # ----------------------------------------------------
        # Process final timestamp.
        # ----------------------------------------------------

        if current_index is not None:

            process_timestamp(
                current_index,
                current_datetime,
                strikes,
            )

        output_connection.commit()

        print()
        print("=" * 65)
        print("ATM IV COMPLETED")
        print("=" * 65)

        print(
            f"Timestamps processed : "
            f"{processed_timestamps:,}"
        )

        print(
            f"Rows written         : "
            f"{inserted_rows:,}"
        )

        print(
            f"Timestamps skipped   : "
            f"{skipped_rows:,}"
        )

    finally:

        iv_connection.close()
        futures_connection.close()
        output_connection.close()


if __name__ == "__main__":
    main()
