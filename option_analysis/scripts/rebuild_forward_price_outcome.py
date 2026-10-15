from pathlib import Path
import sqlite3
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OI_DB = PROJECT_ROOT / "option_analysis" / "database" / "oi_analysis.db"


def main():
    print("Rebuilding forward 5-candle price outcome...")

    conn = sqlite3.connect(OI_DB)
    conn.row_factory = sqlite3.Row

    try:
        # ---------------------------------------------------------
        # 1. Check required columns
        # ---------------------------------------------------------
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(market_state_analysis)"
            ).fetchall()
        }

        required = {
            "forward_price_change_5c",
            "forward_price_change_pct_5c",
        }

        missing = required - columns

        if missing:
            raise RuntimeError(
                f"Missing columns in market_state_analysis: {missing}"
            )

        # ---------------------------------------------------------
        # 2. Clear previous forward outcomes
        # ---------------------------------------------------------
        conn.execute(
            """
            UPDATE market_state_analysis
            SET
                forward_price_change_5c = NULL,
                forward_price_change_pct_5c = NULL
            """
        )

        # ---------------------------------------------------------
        # 3. Get all market-state timestamps
        # ---------------------------------------------------------
        rows = conn.execute(
            """
            SELECT
                index_name,
                expiry,
                datetime
            FROM market_state_analysis
            ORDER BY index_name, datetime
            """
        ).fetchall()

        processed = 0
        valid = 0
        skipped = 0

        for row in rows:

            index_name = row["index_name"]
            expiry = row["expiry"]
            current_dt = row["datetime"]

            # -----------------------------------------------------
            # 4. Get current futures price
            # -----------------------------------------------------
            current = conn.execute(
                """
                SELECT futures_price
                FROM combined_market_analysis
                WHERE index_name = ?
                  AND expiry = ?
                  AND datetime = ?
                """,
                (
                    index_name,
                    expiry,
                    current_dt,
                ),
            ).fetchone()

            if current is None or current["futures_price"] is None:
                skipped += 1
                continue

            current_price = current["futures_price"]

            # -----------------------------------------------------
            # 5. Find the next 5 candles on the SAME trading day
            #
            # We deliberately use datetime ordering and then verify
            # the calendar date. This prevents overnight movement
            # from entering the forward outcome.
            # -----------------------------------------------------
            current_date = current_dt[:10]

            future_rows = conn.execute(
                """
                SELECT
                    datetime,
                    futures_price
                FROM combined_market_analysis
                WHERE index_name = ?
                  AND expiry = ?
                  AND datetime > ?
                  AND datetime LIKE ?
                  AND futures_price IS NOT NULL
                ORDER BY datetime
                LIMIT 5
                """,
                (
                    index_name,
                    expiry,
                    current_dt,
                    current_date + "%",
                ),
            ).fetchall()

            # Need exactly five future candles.
            if len(future_rows) < 5:
                skipped += 1
                processed += 1
                continue

            future_price = future_rows[-1]["futures_price"]

            # -----------------------------------------------------
            # 6. Calculate forward movement
            # -----------------------------------------------------
            change = future_price - current_price

            if current_price == 0:
                skipped += 1
                processed += 1
                continue

            change_pct = (change / current_price) * 100.0

            # -----------------------------------------------------
            # 7. Update market state
            # -----------------------------------------------------
            conn.execute(
                """
                UPDATE market_state_analysis
                SET
                    forward_price_change_5c = ?,
                    forward_price_change_pct_5c = ?
                WHERE index_name = ?
                  AND expiry = ?
                  AND datetime = ?
                """,
                (
                    change,
                    change_pct,
                    index_name,
                    expiry,
                    current_dt,
                ),
            )

            valid += 1
            processed += 1

        conn.commit()

        # ---------------------------------------------------------
        # 8. Summary
        # ---------------------------------------------------------
        print()
        print(f"Rows processed : {processed}")
        print(f"Valid 5-candle : {valid}")
        print(f"Skipped         : {skipped}")

        # ---------------------------------------------------------
        # 9. Verify latest rows
        # ---------------------------------------------------------
        print()
        print("Latest forward outcomes:")

        latest_datetime = conn.execute(
            """
            SELECT MAX(datetime)
            FROM market_state_analysis
            WHERE forward_price_change_5c IS NOT NULL
            """
        ).fetchone()[0]

        df = pd.read_sql_query(
            """
            SELECT
                index_name,
                datetime,
                forward_price_change_5c,
                forward_price_change_pct_5c
            FROM market_state_analysis
            WHERE datetime = ?
            ORDER BY index_name
            """,
            conn,
            params=(latest_datetime,),
        )

        df = df.rename(columns={
            "forward_price_change_5c": "Forward_5C_Change",
            "forward_price_change_pct_5c": "Forward_5C_%",
        })

        print()
        print(f"Latest valid forward outcome: {latest_datetime}")
        print(df.to_string(index=False))

    finally:
        conn.close()


if __name__ == "__main__":
    main()
