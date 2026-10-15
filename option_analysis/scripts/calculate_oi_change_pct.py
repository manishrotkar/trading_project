from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "database" / "oi_analysis.db"

RANGES = [1, 2, 5, 10]

# Strike intervals
STRIKE_STEP = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
}


def get_previous_oi(cur, index_name, expiry, datetime, strike):
    row = cur.execute(
        """
        SELECT ce_oi, pe_oi
        FROM strike_oi_analysis
        WHERE index_name = ?
          AND expiry = ?
          AND strike = ?
          AND datetime < ?
          AND date(datetime) = date(?)
        ORDER BY datetime DESC
        LIMIT 1
        """,
        (
            index_name,
            expiry,
            strike,
            datetime,
            datetime,
        ),
    ).fetchone()

    return row


def calculate_range_change(
    cur,
    index_name,
    expiry,
    datetime,
    atm_strike,
    range_n,
):
    step = STRIKE_STEP[index_name]
    distance = range_n * step

    current_rows = cur.execute(
        """
        SELECT strike, ce_oi, pe_oi
        FROM strike_oi_analysis
        WHERE index_name = ?
          AND expiry = ?
          AND datetime = ?
          AND strike BETWEEN ? AND ?
        ORDER BY strike
        """,
        (
            index_name,
            expiry,
            datetime,
            atm_strike - distance,
            atm_strike + distance,
        ),
    ).fetchall()

    # Expected number of strikes:
    # ATM +/- N contains 2N + 1 strikes.
    expected_count = (2 * range_n) + 1

    if len(current_rows) != expected_count:
        return None

    current_ce = 0.0
    current_pe = 0.0
    previous_ce = 0.0
    previous_pe = 0.0

    for strike, ce_oi, pe_oi in current_rows:

        previous = get_previous_oi(
            cur,
            index_name,
            expiry,
            datetime,
            strike,
        )

        if previous is None:
            return None

        prev_ce, prev_pe = previous

        current_ce += ce_oi
        current_pe += pe_oi
        previous_ce += prev_ce
        previous_pe += prev_pe

    ce_change = current_ce - previous_ce
    pe_change = current_pe - previous_pe

    ce_pct = (
        (ce_change / previous_ce) * 100
        if previous_ce != 0
        else None
    )

    pe_pct = (
        (pe_change / previous_pe) * 100
        if previous_pe != 0
        else None
    )

    return (
        current_ce,
        current_pe,
        ce_change,
        pe_change,
        ce_pct,
        pe_pct,
    )


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT
            index_name,
            expiry,
            datetime,
            atm_strike
        FROM atm_oi_analysis
        ORDER BY index_name, datetime
        """
    ).fetchall()

    print(f"Processing {len(rows)} timestamps...")

    complete_counts = {
        n: 0
        for n in RANGES
    }

    processed = 0

    for index_name, expiry, datetime, atm_strike in rows:

        values = {}

        for n in RANGES:

            result = calculate_range_change(
                cur,
                index_name,
                expiry,
                datetime,
                atm_strike,
                n,
            )

            if result is None:
                values[n] = (None,) * 6
                continue

            values[n] = result
            complete_counts[n] += 1

        # Update only the active ranges.
        cur.execute(
            """
            UPDATE atm_oi_concentration
            SET
                ce_oi_change_pm1 = ?,
                pe_oi_change_pm1 = ?,
                ce_oi_change_pct_pm1 = ?,
                pe_oi_change_pct_pm1 = ?,

                ce_oi_change_pm2 = ?,
                pe_oi_change_pm2 = ?,
                ce_oi_change_pct_pm2 = ?,
                pe_oi_change_pct_pm2 = ?,

                ce_oi_change_pm5 = ?,
                pe_oi_change_pm5 = ?,
                ce_oi_change_pct_pm5 = ?,
                pe_oi_change_pct_pm5 = ?,

                ce_oi_change_pm10 = ?,
                pe_oi_change_pm10 = ?,
                ce_oi_change_pct_pm10 = ?,
                pe_oi_change_pct_pm10 = ?

            WHERE index_name = ?
              AND datetime = ?
            """,
            (
                values[1][2],
                values[1][3],
                values[1][4],
                values[1][5],

                values[2][2],
                values[2][3],
                values[2][4],
                values[2][5],

                values[5][2],
                values[5][3],
                values[5][4],
                values[5][5],

                values[10][2],
                values[10][3],
                values[10][4],
                values[10][5],

                index_name,
                datetime,
            ),
        )

        processed += 1

        if processed % 1000 == 0:
            conn.commit()
            print(f"Processed: {processed}")

    conn.commit()

    print("\nCompleted.")
    print(f"Rows processed: {processed}")

    for n in RANGES:
        print(
            f"Complete +/-{n}: "
            f"{complete_counts[n]}"
        )

    print("\nNote:")
    print("±20 OI-change is intentionally not calculated.")

    conn.close()


if __name__ == "__main__":
    main()