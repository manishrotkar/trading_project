
import os
import csv
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fyers_apiv3 import fyersModel


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
ROOT_DIR = PROJECT_DIR.parent

ENV_FILE = ROOT_DIR / ".env"
ACCESS_FILE = ROOT_DIR / "access.txt"

CSV_PATH = (
    PROJECT_DIR
    / "notebooks"
    / "above_price_scanner_results.csv"
)

DB_PATH = BASE_DIR / "database" / "nse_stockdata_hourly.db"

IST = ZoneInfo("Asia/Kolkata")


# ============================================================
# SETTINGS
# ============================================================

RESOLUTION = "60"             # 60-minute candles
HISTORY_DAYS = 730             # Approximately two years
CHUNK_DAYS = 90                # Request history in 90-day chunks
SLEEP_SECONDS = 0.2
RATE_LIMIT_SLEEP = 10
MAX_RETRIES = 10

CONT_FLAG = "1"
OI_FLAG = "0"


# ============================================================
# FYERS CONNECTION
# ============================================================

load_dotenv(ENV_FILE)

APP_ID = os.getenv("FYERS_APP_ID")

if not APP_ID:
    raise RuntimeError(f"FYERS_APP_ID not found in {ENV_FILE}")

if not ACCESS_FILE.exists():
    raise FileNotFoundError(f"Access token not found: {ACCESS_FILE}")

ACCESS_TOKEN = ACCESS_FILE.read_text().strip()

if not ACCESS_TOKEN:
    raise RuntimeError("FYERS access token file is empty.")

fyers = fyersModel.FyersModel(
    client_id=APP_ID,
    token=ACCESS_TOKEN,
    log_path="",
)


# ============================================================
# DATABASE
# ============================================================

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB_PATH)

conn.execute("""
    CREATE TABLE IF NOT EXISTS hourly_stockdata (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock TEXT NOT NULL,
        symbol TEXT NOT NULL,
        datetime TEXT NOT NULL,
        open REAL NOT NULL,
        high REAL NOT NULL,
        low REAL NOT NULL,
        close REAL NOT NULL,
        volume INTEGER
    )
""")

conn.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS
    idx_hourly_stockdata_unique
    ON hourly_stockdata(symbol, datetime)
""")

conn.commit()


# ============================================================
# LOAD SYMBOLS
# ============================================================

if not CSV_PATH.exists():
    raise FileNotFoundError(f"Scanner CSV not found: {CSV_PATH}")

with CSV_PATH.open("r", newline="", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)

    if not reader.fieldnames or "Symbol" not in reader.fieldnames:
        raise ValueError("Scanner CSV must contain a 'Symbol' column.")

    symbols = list(dict.fromkeys(
        row["Symbol"].strip()
        for row in reader
        if row.get("Symbol") and row["Symbol"].strip()
    ))

if not symbols:
    raise RuntimeError("No symbols found in scanner CSV.")


# ============================================================
# DATABASE RANGE
# ============================================================

def get_latest_candle(symbol):
    row = conn.execute(
        """
        SELECT MAX(datetime)
        FROM hourly_stockdata
        WHERE symbol = ?
        """,
        (symbol,),
    ).fetchone()

    return row[0]


# ============================================================
# INSERT COMPLETED HOURLY CANDLES
# ============================================================

def insert_candles(symbol, candles):
    if not candles:
        return 0

    now_ist = datetime.now(IST).replace(tzinfo=None)
    rows = []

    for candle in candles:
        if len(candle) < 6:
            continue

        try:
            candle_dt = datetime.fromtimestamp(
                float(candle[0]), IST
            ).replace(tzinfo=None)

            # Do not store an unfinished 60-minute candle.
            if candle_dt + timedelta(minutes=60) > now_ist:
                continue

            rows.append((
                symbol,
                symbol,
                candle_dt.strftime("%Y-%m-%d %H:%M:%S"),
                float(candle[1]),
                float(candle[2]),
                float(candle[3]),
                float(candle[4]),
                int(candle[5] or 0),
            ))

        except (TypeError, ValueError, OverflowError, OSError):
            continue

    if not rows:
        return 0

    before = conn.total_changes

    conn.executemany(
        """
        INSERT OR IGNORE INTO hourly_stockdata
        (
            stock, symbol, datetime,
            open, high, low, close, volume
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )

    conn.commit()
    return conn.total_changes - before


# ============================================================
# DOWNLOAD A DATE RANGE
# ============================================================

def download_range(symbol, start_date, end_date):
    current_from = start_date
    requests = 0
    received = 0
    inserted = 0

    while current_from < end_date:
        current_to = min(
            current_from + timedelta(days=CHUNK_DAYS),
            end_date,
        )

        from_text = current_from.strftime("%Y-%m-%d")
        to_text = current_to.strftime("%Y-%m-%d")
        retry_count = 0

        while True:
            requests += 1

            print(f"    Request {requests}: {from_text} -> {to_text}")

            request_data = {
                "symbol": symbol,
                "resolution": RESOLUTION,
                "date_format": "1",
                "range_from": from_text,
                "range_to": to_text,
                "cont_flag": CONT_FLAG,
                "oi_flag": OI_FLAG,
            }

            try:
                response = fyers.history(data=request_data)

                if response.get("s") == "ok":
                    candles = response.get("candles", [])
                    new_rows = insert_candles(symbol, candles)

                    received += len(candles)
                    inserted += new_rows

                    print(
                        f"    Received: {len(candles):>4} | "
                        f"New rows: {new_rows:>4}"
                    )

                    current_from = current_to
                    time.sleep(SLEEP_SECONDS)
                    break

                if response.get("code") == 429:
                    retry_count += 1
                    if retry_count > MAX_RETRIES:
                        raise RuntimeError(
                            f"Maximum rate-limit retries exceeded: {symbol}"
                        )

                    print(f"    Rate limit; waiting {RATE_LIMIT_SLEEP}s")
                    time.sleep(RATE_LIMIT_SLEEP)
                    continue

                if response.get("s") == "no_data":
                    print("    No data for this period.")
                    current_from = current_to
                    time.sleep(SLEEP_SECONDS)
                    break

                raise RuntimeError(f"FYERS API error: {response}")

            except RuntimeError:
                raise

            except Exception as exc:
                retry_count += 1

                if retry_count > MAX_RETRIES:
                    raise RuntimeError(
                        f"Request failed for {symbol}: {exc}"
                    ) from exc

                print(f"    Temporary error: {exc}")
                time.sleep(RATE_LIMIT_SLEEP)

    return requests, received, inserted


# ============================================================
# MAIN
# ============================================================

def main():
    now_ist = datetime.now(IST)
    today = now_ist.date()

    target_end = today + timedelta(days=1)
    target_start = today - timedelta(days=HISTORY_DAYS)

    total_requests = 0
    total_received = 0
    total_inserted = 0
    new_stocks = 0
    updated_stocks = 0
    up_to_date = 0
    failed = []

    print("=" * 70)
    print("FYERS HOURLY STOCK DATA DOWNLOADER")
    print("=" * 70)
    print(f"Run time (IST) : {now_ist:%Y-%m-%d %H:%M:%S}")
    print(f"Stocks         : {len(symbols)}")
    print(f"Resolution     : {RESOLUTION} minutes")
    print(f"History        : {target_start} -> {today}")
    print(f"Database       : {DB_PATH}")
    print("=" * 70)

    for index, symbol in enumerate(symbols, start=1):
        print()
        print(f"[{index}/{len(symbols)}] {symbol}")

        try:
            latest = get_latest_candle(symbol)

            if latest is None:
                # New stock: download approximately two years.
                start_date = target_start
                new_stocks += 1
                print("Status: NEW STOCK - initial history download")

            else:
                # Existing stock: resume from its latest stored date.
                # Re-requesting that date is safe because duplicates
                # are ignored by the unique index.
                latest_dt = datetime.strptime(
                    latest, "%Y-%m-%d %H:%M:%S"
                )
                start_date = latest_dt.date()

                if start_date >= today:
                    print(f"Latest stored candle: {latest}")
                else:
                    print(f"Latest stored candle: {latest}")

                updated_stocks += 1

            if start_date >= target_end:
                up_to_date += 1
                print("Already up to date.")
                continue

            requests, received, inserted = download_range(
                symbol,
                start_date,
                target_end,
            )

            total_requests += requests
            total_received += received
            total_inserted += inserted

            print(f"New database rows: {inserted}")

        except Exception as exc:
            failed.append((symbol, str(exc)))
            print(f"ERROR: {exc}")

    total_rows = conn.execute(
        "SELECT COUNT(*) FROM hourly_stockdata"
    ).fetchone()[0]

    unique_symbols = conn.execute(
        "SELECT COUNT(DISTINCT symbol) FROM hourly_stockdata"
    ).fetchone()[0]

    print()
    print("=" * 70)
    print("DOWNLOAD SUMMARY")
    print("=" * 70)
    print(f"Stocks in CSV       : {len(symbols)}")
    print(f"New stocks seen     : {new_stocks}")
    print(f"Existing stocks     : {updated_stocks}")
    print(f"Already up to date  : {up_to_date}")
    print(f"Failed stocks       : {len(failed)}")
    print(f"API requests        : {total_requests}")
    print(f"Candles received    : {total_received:,}")
    print(f"New database rows   : {total_inserted:,}")
    print(f"Total database rows : {total_rows:,}")
    print(f"Unique stocks in DB : {unique_symbols:,}")
    print(f"Database size       : {DB_PATH.stat().st_size / (1024**2):.2f} MB")

    if failed:
        print()
        print("FAILED STOCKS")
        for symbol, error in failed:
            print(f"  {symbol}: {error}")

    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDownload stopped by user.")
    finally:
        conn.close()
