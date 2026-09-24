import sys
import time
from pathlib import Path
from datetime import date, timedelta

# --------------------------------------------------
# Project path
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.fyers_client import get_fyers_client


# --------------------------------------------------
# Test settings
# --------------------------------------------------

SYMBOL = "NSE:NIFTY26SEPFUT"

START_DATE = date(2026, 3, 5)
END_DATE = date(2026, 9, 5)

BATCH_DAYS = 30
SLEEP_SECONDS = 3


# --------------------------------------------------
# Main test
# --------------------------------------------------

def main():

    print("=" * 70)
    print("FYERS CONTRACT-WISE 1-MINUTE HISTORICAL DATA TEST")
    print("=" * 70)

    print(f"Symbol      : {SYMBOL}")
    print(f"Start date  : {START_DATE}")
    print(f"End date    : {END_DATE}")
    print(f"Batch       : {BATCH_DAYS} days")
    print(f"Sleep       : {SLEEP_SECONDS} seconds")
    print()

    fyers = get_fyers_client()

    current = START_DATE
    total_candles = 0
    batch_number = 0

    while current <= END_DATE:

        batch_number += 1

        batch_end = min(
            current + timedelta(days=BATCH_DAYS - 1),
            END_DATE
        )

        print("-" * 70)
        print(
            f"Batch {batch_number}: "
            f"{current} → {batch_end}"
        )

        data = {
            "symbol": SYMBOL,
            "resolution": "1",
            "date_format": "1",
            "range_from": current.isoformat(),
            "range_to": batch_end.isoformat(),
            "cont_flag": "0",
            "oi_flag": "1",
        }

        try:

            response = fyers.history(data=data)

            status = response.get("s")
            code = response.get("code")
            candles = response.get("candles", [])

            print(f"Status      : {status}")
            print(f"Code        : {code}")
            print(f"Candles     : {len(candles):,}")

            if candles:

                print(f"Fields/candle: {len(candles[0])}")

                print("First candle:")
                print(candles[0])

                print("Last candle:")
                print(candles[-1])

                total_candles += len(candles)

            else:
                print("⚠️ No candles returned.")

        except Exception as e:

            print(f"❌ Exception: {e}")

        # --------------------------------------------------
        # Move to next batch
        # --------------------------------------------------

        current = batch_end + timedelta(days=1)

        if current <= END_DATE:

            print()
            print(
                f"Sleeping {SLEEP_SECONDS} seconds "
                "before next API request..."
            )

            time.sleep(SLEEP_SECONDS)

    print()
    print("=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

    print(f"Total candles returned: {total_candles:,}")
    print()


if __name__ == "__main__":
    main()