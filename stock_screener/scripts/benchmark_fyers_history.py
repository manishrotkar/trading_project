import os
import time
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fyers_apiv3 import fyersModel


# ==========================================
# PATHS
# ==========================================

PROJECT_DIR = Path("/home/manish/trading_project/stock_screener")
ROOT_DIR = Path("/home/manish/trading_project")

ENV_FILE = ROOT_DIR / ".env"
ACCESS_FILE = ROOT_DIR / "access.txt"
DB_PATH = PROJECT_DIR / "database" / "nse_stockdata.db"


# ==========================================
# FYERS LOGIN
# ==========================================

load_dotenv(ENV_FILE)

APP_ID = os.getenv("FYERS_APP_ID")

if not APP_ID:
    raise ValueError("FYERS_APP_ID not found in .env")

ACCESS_TOKEN = ACCESS_FILE.read_text().strip()

if not ACCESS_TOKEN:
    raise ValueError("FYERS access token is empty")

fyers = fyersModel.FyersModel(
    client_id=APP_ID,
    token=ACCESS_TOKEN,
    log_path=""
)


# ==========================================
# BENCHMARK SETTINGS
# ==========================================

SYMBOL = "NSE:SBIN-EQ"
STOCK_NAME = "SBIN"

RESOLUTION = "1"

# 30 calendar days
TO_DATE = datetime.now().date()
FROM_DATE = TO_DATE - timedelta(days=30)

# FYERS request chunk
CHUNK_DAYS = 7

# Delay between API requests
SLEEP_SECONDS = 0.2


# ==========================================
# DATABASE
# ==========================================

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()


# ==========================================
# START BENCHMARK
# ==========================================

print("=" * 60)
print("FYERS 1-MINUTE DOWNLOAD BENCHMARK")
print("=" * 60)

print("Stock       :", STOCK_NAME)
print("Symbol      :", SYMBOL)
print("Resolution  :", "1 minute")
print("From        :", FROM_DATE)
print("To          :", TO_DATE)
print("Chunk       :", f"{CHUNK_DAYS} days")
print()


overall_start = time.time()

total_candles = 0
total_requests = 0
total_inserted = 0


current_from = FROM_DATE

while current_from < TO_DATE:

    current_to = min(
        current_from + timedelta(days=CHUNK_DAYS),
        TO_DATE
    )

    range_from = current_from.strftime("%Y-%m-%d")
    range_to = current_to.strftime("%Y-%m-%d")

    print(
        f"Request {total_requests + 1}: "
        f"{range_from} → {range_to}"
    )

    request_start = time.time()

    data = {
        "symbol": SYMBOL,
        "resolution": RESOLUTION,
        "date_format": "1",
        "range_from": range_from,
        "range_to": range_to,
        "cont_flag": "1"
    }

    try:

        response = fyers.history(data=data)

        total_requests += 1

        if response.get("s") != "ok":

            print("  ERROR:", response)
            current_from = current_to
            time.sleep(SLEEP_SECONDS)
            continue

        candles = response.get("candles", [])

        request_time = time.time() - request_start

        total_candles += len(candles)

        inserted = 0

        for candle in candles:

            timestamp = datetime.fromtimestamp(
                candle[0]
            ).strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute(
                """
                INSERT OR IGNORE INTO nse_stockdata
                (
                    stock,
                    symbol,
                    datetime,
                    open,
                    high,
                    low,
                    close,
                    volume
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    STOCK_NAME,
                    SYMBOL,
                    timestamp,
                    candle[1],
                    candle[2],
                    candle[3],
                    candle[4],
                    candle[5]
                )
            )

            inserted += cursor.rowcount

        conn.commit()

        total_inserted += inserted

        print(
            f"  Candles : {len(candles):,}"
            f" | Inserted : {inserted:,}"
            f" | Time : {request_time:.2f}s"
        )

    except Exception as e:

        print("  ERROR:", e)

    current_from = current_to

    time.sleep(SLEEP_SECONDS)


# ==========================================
# FINISH
# ==========================================

conn.close()

total_time = time.time() - overall_start

print()
print("=" * 60)
print("BENCHMARK COMPLETE")
print("=" * 60)

print(f"API requests       : {total_requests:,}")
print(f"Candles received   : {total_candles:,}")
print(f"Candles inserted   : {total_inserted:,}")
print(f"Total time         : {total_time:.2f} seconds")
print(f"Total time         : {total_time / 60:.2f} minutes")

if total_time > 0:

    print(
        f"Download speed     : "
        f"{total_candles / total_time:,.0f} candles/sec"
    )

print()
print("Database:")
print(DB_PATH)
