import sys
import sqlite3
from pathlib import Path
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from datetime import datetime

# --------------------------------------------------
# Project paths
# --------------------------------------------------

FUTURES_PROJECT = Path(__file__).resolve().parents[1]
MAIN_PROJECT = FUTURES_PROJECT.parent

sys.path.insert(0, str(MAIN_PROJECT))

from core.fyers_client import get_fyers_client


DATABASE = FUTURES_PROJECT / "database" / "futures.db"

SYMBOL = "NSE:NIFTY26SEPFUT"
CONTRACT = "NIFTY26SEPFUT"
EXPIRY = "2026-09-29"

START_DATE = date(2026, 3, 5)
END_DATE = date(2026, 9, 5)


# --------------------------------------------------
# Download one batch
# --------------------------------------------------

def download_batch(fyers, start_date, end_date):

    data = {
        "symbol": SYMBOL,
        "resolution": "1",
        "date_format": "1",
        "range_from": start_date.isoformat(),
        "range_to": end_date.isoformat(),
        "cont_flag": "0",
        "oi_flag": "1",
    }

    response = fyers.history(data=data)

    if response.get("s") != "ok":
        print(
            f"❌ API error for "
            f"{start_date} → {end_date}: "
            f"{response}"
        )
        return 0

    candles = response.get("candles", [])

    print(
        f"✅ {start_date} → {end_date} "
        f"| {len(candles):,} candles"
    )

    connection = sqlite3.connect(DATABASE)

    inserted = 0

    try:
        for candle in candles:

            timestamp = candle[0]
            open_price = candle[1]
            high_price = candle[2]
            low_price = candle[3]
            close_price = candle[4]
            volume = candle[5]
            open_interest = candle[6]

            dt = datetime.fromtimestamp(
                timestamp,
                tz=ZoneInfo("Asia/Kolkata")
            ).isoformat()

            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO futures_data
                (
                    symbol,
                    contract,
                    expiry,
                    datetime,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    open_interest
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    SYMBOL,
                    CONTRACT,
                    EXPIRY,
                    dt,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                    open_interest,
                ),
            )

            inserted += cursor.rowcount

        connection.commit()

    finally:
        connection.close()

    print(f"   New rows inserted: {inserted:,}")

    return inserted


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print("=" * 60)
    print("NIFTY SEPTEMBER 2026 FUTURES DOWNLOAD")
    print("=" * 60)

    print(f"Symbol : {SYMBOL}")
    print(f"From   : {START_DATE}")
    print(f"To     : {END_DATE}")
    print()

    fyers = get_fyers_client()

    current = START_DATE
    total_inserted = 0

    while current < END_DATE:

        batch_end = min(
            current + timedelta(days=30),
            END_DATE
        )

        inserted = download_batch(
            fyers,
            current,
            batch_end
        )

        total_inserted += inserted

        current = batch_end + timedelta(days=1)

    print()
    print("=" * 60)
    print(f"TOTAL NEW ROWS INSERTED: {total_inserted:,}")
    print("=" * 60)


if __name__ == "__main__":
    main()
