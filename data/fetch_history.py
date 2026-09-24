import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from core.fyers_client import get_fyers_client


SYMBOL = "NSE:NIFTY50-INDEX"
RESOLUTION = "1"
BATCH_DAYS = 30

OUTPUT_FILE = "data/index/raw/nifty50_1m.parquet"
IST = ZoneInfo("Asia/Kolkata")


def fetch_batch(fyers, start_date, end_date):
    data = {
        "symbol": SYMBOL,
        "resolution": RESOLUTION,
        "date_format": "1",
        "range_from": start_date,
        "range_to": end_date,
        "cont_flag": "1",
    }

    max_retries = 5
    wait_seconds = 30

    for attempt in range(1, max_retries + 1):

        response = fyers.history(data=data)

        if response.get("s") == "ok":
            return response

        if response.get("code") == 429:
            print(
                f"  ⚠️ Rate limit reached. "
                f"Waiting {wait_seconds} seconds "
                f"(attempt {attempt}/{max_retries})..."
            )

            time.sleep(wait_seconds)
            wait_seconds *= 2
            continue

        return response

    return {
        "s": "error",
        "code": 429,
        "message": "Maximum retry attempts reached"
    }

def save_to_parquet(candles):
    rows = []

    for candle in candles:
        timestamp, open_price, high, low, close, volume = candle

        rows.append({
            "datetime": datetime.fromtimestamp(
                timestamp, tz=IST
            ),
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        })

    if not rows:
        return

    new_df = pd.DataFrame(rows)

    try:
        existing_df = pd.read_parquet(OUTPUT_FILE)
        df = pd.concat([existing_df, new_df], ignore_index=True)
    except FileNotFoundError:
        df = new_df

    df = (
        df.drop_duplicates(subset=["datetime"])
          .sort_values("datetime")
          .reset_index(drop=True)
    )

    df.to_parquet(OUTPUT_FILE, index=False)

    print(f"  💾 Stored: {len(df)} total candles")


def main():
    if len(sys.argv) != 3:
        print("Usage:")
        print(
            "PYTHONPATH=. python data/fetch_history.py "
            "YYYY-MM-DD YYYY-MM-DD"
        )
        sys.exit(1)

    start_date = datetime.strptime(
        sys.argv[1], "%Y-%m-%d"
    ).date()

    end_date = datetime.strptime(
        sys.argv[2], "%Y-%m-%d"
    ).date()

    fyers = get_fyers_client()

    current_date = start_date

    while current_date <= end_date:
        batch_end = min(
            current_date + timedelta(days=BATCH_DAYS - 1),
            end_date,
        )

        start_str = current_date.strftime("%Y-%m-%d")
        end_str = batch_end.strftime("%Y-%m-%d")

        print(f"\nFetching {start_str} → {end_str}...")

        response = fetch_batch(
            fyers,
            start_str,
            end_str,
        )

        if response.get("s") != "ok":
            print(f"  ❌ API Error: {response}")
        else:
            candles = response.get("candles", [])

            print(f"  ✅ {len(candles)} candles received")

            save_to_parquet(candles)

        current_date = batch_end + timedelta(days=1)

    print("\n✅ Historical data fetch completed.")
    print(f"📁 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
