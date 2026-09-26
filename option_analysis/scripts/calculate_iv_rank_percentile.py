import sqlite3
from pathlib import Path
from collections import deque


# ============================================================
# PATHS
# ============================================================

OPTION_PROJECT = Path(__file__).resolve().parents[1]

DATABASE = (
    OPTION_PROJECT
    / "database"
    / "iv_analysis.db"
)

LOOKBACK_DAYS = 25


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 65)
    print("CALCULATING IV RANK + IV PERCENTILE")
    print("=" * 65)

    print(f"Database       : {DATABASE}")
    print(f"Target lookback: {LOOKBACK_DAYS} trading days")
    print()

    connection = sqlite3.connect(DATABASE)

    try:

        # ----------------------------------------------------
        # Clear previous calculated results.
        # ATM IV data remains untouched.
        # ----------------------------------------------------

        connection.execute(
            "DELETE FROM iv_rank_percentile"
        )

        connection.commit()

        print("Previous IV Rank/Percentile results cleared.")
        print()

        cursor = connection.execute(
            """
            SELECT
                index_name,
                datetime,
                atm_iv
            FROM atm_iv
            ORDER BY
                index_name,
                datetime
            """
        )

        current_index = None

        # ----------------------------------------------------
        # Store complete previous trading-day observations.
        #
        # Each item:
        #     (trading_date, iv)
        # ----------------------------------------------------

        history = deque()

        processed = 0
        inserted = 0

        for index_name, timestamp, current_iv in cursor:

            # ------------------------------------------------
            # Extract trading date.
            # Example:
            # 2026-09-25 15:29:00
            # becomes:
            # 2026-09-25
            # ------------------------------------------------

            trading_date = timestamp[:10]

            # ------------------------------------------------
            # New index
            # ------------------------------------------------

            if current_index != index_name:

                current_index = index_name
                history.clear()

            current_iv = float(current_iv)

            # ------------------------------------------------
            # Remove observations older than 25 trading days.
            #
            # We keep complete trading days in history.
            # Current trading day is NOT removed here because
            # it will be handled below.
            # ------------------------------------------------

            unique_days = []

            for day, _ in history:

                if day not in unique_days:
                    unique_days.append(day)

            # ------------------------------------------------
            # Keep maximum 25 previous trading days.
            # ------------------------------------------------

            if len(unique_days) > LOOKBACK_DAYS:

                oldest_allowed_day = unique_days[-LOOKBACK_DAYS]

                while history and history[0][0] != oldest_allowed_day:
                    history.popleft()

            # ------------------------------------------------
            # Historical IV values only.
            # ------------------------------------------------

            historical_values = [
                value
                for _, value in history
            ]

            if historical_values:

                period_low = min(historical_values)
                period_high = max(historical_values)

                # --------------------------------------------
                # IV Rank
                # --------------------------------------------

                if period_high > period_low:

                    iv_rank = (
                        (current_iv - period_low)
                        / (period_high - period_low)
                    ) * 100.0

                    # Safety boundary.
                    iv_rank = max(
                        0.0,
                        min(100.0, iv_rank)
                    )

                else:

                    iv_rank = 0.0

                # --------------------------------------------
                # IV Percentile
                # --------------------------------------------

                count_at_or_below = sum(
                    value <= current_iv
                    for value in historical_values
                )

                iv_percentile = (
                    count_at_or_below
                    / len(historical_values)
                ) * 100.0

                # --------------------------------------------
                # Number of actual trading days represented
                # by the historical window.
                # --------------------------------------------

                actual_lookback_days = len(
                    set(day for day, _ in history)
                )

                # --------------------------------------------
                # Store result
                # --------------------------------------------

                connection.execute(
                    """
                    INSERT INTO iv_rank_percentile (
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
                        current_iv,
                        LOOKBACK_DAYS,
                        period_low,
                        period_high,
                        iv_rank,
                        iv_percentile,
                        actual_lookback_days,
                    ),
                )

                inserted += 1

            processed += 1

            # ------------------------------------------------
            # Add current observation AFTER calculation.
            # ------------------------------------------------

            history.append(
                (trading_date, current_iv)
            )

            # ------------------------------------------------
            # Keep only the latest 25 complete trading days.
            # ------------------------------------------------

            unique_days = []

            for day, _ in history:

                if day not in unique_days:
                    unique_days.append(day)

            while len(unique_days) > LOOKBACK_DAYS:

                oldest_day = unique_days.pop(0)

                while history and history[0][0] == oldest_day:
                    history.popleft()

            # ------------------------------------------------
            # Progress
            # ------------------------------------------------

            if processed % 5000 == 0:

                connection.commit()

                print(
                    f"Processed: {processed:,} | "
                    f"Inserted: {inserted:,}"
                )

        connection.commit()

        print()
        print("=" * 65)
        print("IV RANK + PERCENTILE COMPLETED")
        print("=" * 65)

        print(
            f"ATM observations processed : "
            f"{processed:,}"
        )

        print(
            f"Results inserted            : "
            f"{inserted:,}"
        )

    finally:

        connection.close()


if __name__ == "__main__":
    main()