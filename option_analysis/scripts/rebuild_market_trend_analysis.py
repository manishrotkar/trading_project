from pathlib import Path
import sqlite3


OPTION_PROJECT = Path(__file__).resolve().parents[1]
TRADING_PROJECT = OPTION_PROJECT.parent

OI_DB = OPTION_PROJECT / "database" / "oi_analysis.db"
FUTURES_DB = TRADING_PROJECT / "futures_project" / "database" / "futures.db"

INDEXES = {
    "NIFTY": "NSE:NIFTY%FUT",
    "BANKNIFTY": "NSE:BANKNIFTY%FUT",
}


def load_required_timestamps(oi_cur, index_name):
    rows = oi_cur.execute(
        """
        SELECT datetime
        FROM atm_oi_analysis
        WHERE index_name = ?
        ORDER BY datetime
        """,
        (index_name,),
    ).fetchall()

    return [row[0] for row in rows]


def load_futures_series(
    futures_conn,
    index_name,
    required_timestamps,
):
    symbol_pattern = INDEXES[index_name]

    required_dates = sorted(
        {timestamp[:10] for timestamp in required_timestamps}
    )

    if not required_dates:
        return {}

    # Fetch by calendar date only.
    # Timestamp normalization is handled in Python.
    date_conditions = " OR ".join(
        ["datetime LIKE ?" for _ in required_dates]
    )

    query = f"""
        SELECT
            datetime,
            close,
            expiry,
            symbol
        FROM futures_data
        WHERE symbol LIKE ?
          AND ({date_conditions})
        ORDER BY datetime, expiry
    """

    params = [symbol_pattern]

    for date in required_dates:
        params.append(f"{date}%")

    rows = futures_conn.execute(
        query,
        params,
    ).fetchall()

    required_set = set(required_timestamps)

    selected = {}

    for raw_datetime, close, expiry, symbol in rows:

        # Convert:
        # 2026-09-25T15:39:00+05:30
        #
        # to:
        # 2026-09-25 15:39:00
        normalized_datetime = (
            raw_datetime[:19].replace("T", " ")
        )

        if normalized_datetime not in required_set:
            continue

        # First row for each timestamp is the nearest expiry
        # because results are ordered by datetime, expiry.
        if normalized_datetime not in selected:
            selected[normalized_datetime] = {
                "datetime": normalized_datetime,
                "close": close,
                "expiry": expiry,
                "symbol": symbol,
            }

    return selected


def main():

    print("Starting market trend rebuild...")

    oi_conn = sqlite3.connect(OI_DB)

    # Futures DB is strictly READ ONLY.
    futures_conn = sqlite3.connect(
        f"file:{FUTURES_DB}?mode=ro",
        uri=True,
    )

    oi_cur = oi_conn.cursor()

    # Rebuild only market_trend_analysis.
    oi_cur.execute(
        "DELETE FROM market_trend_analysis"
    )
    oi_conn.commit()

    total_inserted = 0

    for index_name in INDEXES:

        print(f"\nProcessing {index_name}...")

        required_timestamps = (
            load_required_timestamps(
                oi_cur,
                index_name,
            )
        )

        print(
            f"Required timestamps: "
            f"{len(required_timestamps)}"
        )

        futures = load_futures_series(
            futures_conn,
            index_name,
            required_timestamps,
        )

        print(
            f"Matching futures timestamps: "
            f"{len(futures)}"
        )

        series = sorted(
            futures.values(),
            key=lambda x: x["datetime"],
        )

        # Group by trading day.
        trading_days = {}

        for row in series:

            day = row["datetime"][:10]

            trading_days.setdefault(
                day,
                [],
            ).append(row)

        inserted = 0

        for day, day_rows in trading_days.items():

            for i, row in enumerate(day_rows):

                datetime = row["datetime"]
                futures_price = row["close"]
                expiry = row["expiry"]

                # 1-candle same-day change.
                if i >= 1:

                    previous_price = (
                        day_rows[i - 1]["close"]
                    )

                    price_change = (
                        futures_price
                        - previous_price
                    )

                    price_change_pct = (
                        price_change
                        / previous_price
                        * 100
                        if previous_price != 0
                        else None
                    )

                else:

                    price_change = None
                    price_change_pct = None

                # 5-candle same-day change.
                if i >= 5:

                    previous_5c_price = (
                        day_rows[i - 5]["close"]
                    )

                    price_change_5c = (
                        futures_price
                        - previous_5c_price
                    )

                    price_change_pct_5c = (
                        price_change_5c
                        / previous_5c_price
                        * 100
                        if previous_5c_price != 0
                        else None
                    )

                else:

                    price_change_5c = None
                    price_change_pct_5c = None

                oi_cur.execute(
                    """
                    INSERT INTO market_trend_analysis (
                        index_name,
                        expiry,
                        datetime,
                        futures_price,
                        futures_price_change,
                        futures_price_change_pct,
                        futures_price_change_5c,
                        futures_price_change_pct_5c
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        index_name,
                        expiry,
                        datetime,
                        futures_price,
                        price_change,
                        price_change_pct,
                        price_change_5c,
                        price_change_pct_5c,
                    ),
                )

                inserted += 1

        oi_conn.commit()

        print(
            f"Rows inserted: {inserted}"
        )

        total_inserted += inserted

    futures_conn.close()
    oi_conn.close()

    print("\nRebuild completed.")

    print(
        f"Total rows inserted: "
        f"{total_inserted}"
    )


if __name__ == "__main__":
    main()