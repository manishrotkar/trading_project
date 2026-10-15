import sqlite3
from collections import deque
from pathlib import Path

OPTION_PROJECT = Path(__file__).resolve().parents[1]

DATABASE = OPTION_PROJECT / "database" / "iv_analysis.db"

LOOKBACK_DAYS = 25

INDEXES = (
    "NIFTY",
    "BANKNIFTY",
)


def load_history(connection, index_name, current_timestamp):
    rows = connection.execute(
        """
        SELECT
            datetime,
            atm_iv
        FROM atm_iv
        WHERE index_name = ?
          AND datetime < ?
        ORDER BY datetime
        """,
        (
            index_name,
            current_timestamp,
        ),
    ).fetchall()

    history = deque()

    for timestamp, atm_iv in rows:

        history.append(
            (
                timestamp[:10],
                float(atm_iv),
            )
        )

    unique_days = []

    for day, _ in history:

        if day not in unique_days:
            unique_days.append(day)

    while len(unique_days) > LOOKBACK_DAYS:

        oldest_day = unique_days.pop(0)

        while history and history[0][0] == oldest_day:
            history.popleft()

    return history


def calculate_rank_percentile(
    current_iv,
    history,
):
    historical_values = [
        value
        for _, value in history
    ]

    if not historical_values:
        return None

    period_low = min(
        historical_values
    )

    period_high = max(
        historical_values
    )

    if period_high > period_low:

        iv_rank = (
            (current_iv - period_low)
            / (period_high - period_low)
        ) * 100.0

        iv_rank = max(
            0.0,
            min(100.0, iv_rank),
        )

    else:
        iv_rank = 0.0

    count_at_or_below = sum(
        value <= current_iv
        for value in historical_values
    )

    iv_percentile = (
        count_at_or_below
        / len(historical_values)
    ) * 100.0

    actual_lookback_days = len(
        set(
            day
            for day, _ in history
        )
    )

    return (
        period_low,
        period_high,
        iv_rank,
        iv_percentile,
        actual_lookback_days,
    )


def process_index(connection, index_name):

    latest_row = connection.execute(
        """
        SELECT MAX(datetime)
        FROM atm_iv
        WHERE index_name = ?
        """,
        (index_name,),
    ).fetchone()

    latest_timestamp = latest_row[0]

    if latest_timestamp is None:
        print(
            f"{index_name}: no ATM IV data"
        )
        return 0

    previous_result = connection.execute(
        """
        SELECT MAX(datetime)
        FROM iv_rank_percentile
        WHERE index_name = ?
          AND lookback_days = ?
        """,
        (
            index_name,
            LOOKBACK_DAYS,
        ),
    ).fetchone()[0]

    if previous_result is None:

        first_new_timestamp = None

        print(
            f"{index_name}: "
            "no previous rank/percentile result"
        )

    else:

        first_new_timestamp = previous_result

        print(
            f"{index_name}: "
            f"last result={previous_result}"
        )

    if first_new_timestamp is None:

        rows = connection.execute(
            """
            SELECT
                datetime,
                atm_iv
            FROM atm_iv
            WHERE index_name = ?
            ORDER BY datetime
            """,
            (index_name,),
        ).fetchall()

    else:

        rows = connection.execute(
            """
            SELECT
                datetime,
                atm_iv
            FROM atm_iv
            WHERE index_name = ?
              AND datetime > ?
            ORDER BY datetime
            """,
            (
                index_name,
                first_new_timestamp,
            ),
        ).fetchall()

    if not rows:

        print(
            f"{index_name}: "
            "no new observations"
        )

        return 0

    total_inserted = 0

    for timestamp, current_iv in rows:

        history = load_history(
            connection,
            index_name,
            timestamp,
        )

        result = calculate_rank_percentile(
            float(current_iv),
            history,
        )

        if result is None:
            continue

        (
            period_low,
            period_high,
            iv_rank,
            iv_percentile,
            actual_lookback_days,
        ) = result

        connection.execute(
            """
            INSERT OR REPLACE INTO iv_rank_percentile (
                index_name,
                datetime,
                current_iv,
                lookback_days,
                period_low,
                period_high,
                iv_rank,
                iv_percentile,
                actual_lookback_days
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                index_name,
                timestamp,
                float(current_iv),
                LOOKBACK_DAYS,
                period_low,
                period_high,
                iv_rank,
                iv_percentile,
                actual_lookback_days,
            ),
        )

        total_inserted += 1

    connection.commit()

    print(
        f"{index_name}: "
        f"results written={total_inserted:,}"
    )

    return total_inserted


def main():

    print("=" * 70)
    print("INCREMENTAL IV RANK + PERCENTILE")
    print("=" * 70)

    print(f"Database : {DATABASE}")
    print(
        f"Lookback : "
        f"{LOOKBACK_DAYS} trading days"
    )
    print()

    connection = sqlite3.connect(
        DATABASE
    )

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
    print("INCREMENTAL IV RANK + PERCENTILE COMPLETED")
    print("=" * 70)

    print(
        f"Total results written : "
        f"{total:,}"
    )


if __name__ == "__main__":
    main()
