import os
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
from dotenv import load_dotenv
from fyers_apiv3 import fyersModel


# ============================================================
# PATHS
# ============================================================

PROJECT_DIR = Path("/home/manish/trading_project/stock_screener")
ROOT_DIR = Path("/home/manish/trading_project")

ENV_FILE = ROOT_DIR / ".env"
ACCESS_FILE = ROOT_DIR / "access.txt"

CSV_PATH = PROJECT_DIR / "notebooks" / "above_price_scanner_results.csv"
DB_PATH = PROJECT_DIR / "database" / "nse_stockdata.db"


# ============================================================
# SETTINGS
# ============================================================

# FYERS resolution
RESOLUTION = "1"

# ------------------------------------------------------------
# Initial history for a NEW stock
# ------------------------------------------------------------
INITIAL_HISTORY_MONTHS = 60

# ------------------------------------------------------------
# FYERS API chunk size
#
# 30 days greatly reduces number of API requests compared
# with the previous 7-day chunks.
# ------------------------------------------------------------
CHUNK_DAYS = 30

# ------------------------------------------------------------
# Delay between successful API requests
#
# 0.2 sec = maximum theoretical 5 requests/sec,
# below the known 10 requests/sec limit.
# ------------------------------------------------------------
SLEEP_SECONDS = 0.2

# ------------------------------------------------------------
# Wait after rate-limit / temporary error
# ------------------------------------------------------------
RATE_LIMIT_SLEEP = 60

# ------------------------------------------------------------
# Maximum retries
# ------------------------------------------------------------
MAX_RETRIES = 10

# ------------------------------------------------------------
# FYERS History API
# ------------------------------------------------------------
CONT_FLAG = "1"

# Stock DB stores OHLCV only, so OI is unnecessary.
OI_FLAG = "0"


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv(ENV_FILE)

APP_ID = os.getenv("FYERS_APP_ID")

if not APP_ID:
    raise RuntimeError(
        f"FYERS_APP_ID not found in environment file:\n{ENV_FILE}"
    )


# ============================================================
# ACCESS TOKEN
# ============================================================

if not ACCESS_FILE.exists():
    raise FileNotFoundError(
        f"Access token file not found:\n{ACCESS_FILE}"
    )

ACCESS_TOKEN = ACCESS_FILE.read_text().strip()

if not ACCESS_TOKEN:
    raise RuntimeError("Access token file is empty.")


# ============================================================
# FYERS CONNECTION
# ============================================================

fyers = fyersModel.FyersModel(
    client_id=APP_ID,
    token=ACCESS_TOKEN,
    log_path=""
)


# ============================================================
# DATABASE
# ============================================================

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB_PATH)

conn.execute("""
    CREATE TABLE IF NOT EXISTS nse_stockdata (
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
    CREATE UNIQUE INDEX IF NOT EXISTS idx_nse_stockdata_unique
    ON nse_stockdata(symbol, datetime)
""")

conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_nse_stockdata_symbol_datetime
    ON nse_stockdata(symbol, datetime)
""")

conn.commit()


# ============================================================
# LOAD STOCKS FROM SCANNER CSV
# ============================================================

if not CSV_PATH.exists():
    raise FileNotFoundError(
        f"Scanner CSV not found:\n{CSV_PATH}"
    )

scanner_df = pd.read_csv(CSV_PATH)

if "Symbol" not in scanner_df.columns:
    raise ValueError(
        "Scanner CSV must contain a 'Symbol' column."
    )

symbols = (
    scanner_df["Symbol"]
    .dropna()
    .astype(str)
    .str.strip()
)

# Remove blank symbols and duplicates
symbols = [
    symbol
    for symbol in symbols.unique()
    if symbol
]

if not symbols:
    raise RuntimeError(
        "No symbols found in scanner CSV."
    )


# ============================================================
# DATABASE RANGE
# ============================================================

def get_db_range(symbol):
    """
    Return earliest and latest stored candle for a symbol.
    """

    row = conn.execute(
        """
        SELECT
            MIN(datetime),
            MAX(datetime)
        FROM nse_stockdata
        WHERE symbol = ?
        """,
        (symbol,),
    ).fetchone()

    return row[0], row[1]


# ============================================================
# INSERT CANDLES
# ============================================================

def insert_candles(symbol, stock_name, candles):
    """
    Insert candles safely.

    Important:
    - Today's candles are NEVER stored.
    - Duplicate candles are ignored.
    - Existing database rows are never modified.
    """

    if not candles:
        return 0

    rows = []

    # Today's date
    today = datetime.now().date()

    for candle in candles:

        # Expected:
        # [timestamp, open, high, low, close, volume]

        if len(candle) < 6:
            continue

        timestamp = candle[0]

        try:
            candle_dt = datetime.fromtimestamp(timestamp)

        except Exception:
            continue

        # ----------------------------------------------------
        # SAFETY:
        # Never store today's data.
        # ----------------------------------------------------

        if candle_dt.date() >= today:
            continue

        try:
            open_price = float(candle[1])
            high_price = float(candle[2])
            low_price = float(candle[3])
            close_price = float(candle[4])

            volume = (
                int(candle[5])
                if candle[5] is not None
                else 0
            )

        except (TypeError, ValueError):
            continue

        rows.append(
            (
                stock_name,
                symbol,
                candle_dt.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
            )
        )

    if not rows:
        return 0

    before_changes = conn.total_changes

    conn.executemany(
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
        rows,
    )

    conn.commit()

    return conn.total_changes - before_changes


# ============================================================
# DOWNLOAD RANGE
# ============================================================

def download_range(
    symbol,
    start_date,
    end_date,
    stock_name
):
    """
    Download a specific historical range.

    start_date : inclusive
    end_date   : exclusive

    Uses 30-day chunks.

    Handles:
        OK       -> save candles
        no_data  -> skip chunk
        429      -> wait and retry same chunk
        Exception -> retry
        Other API error -> stop

    Returns:
        {
            "requests": number of API requests,
            "candles": total candles returned,
            "inserted": new DB rows,
            "seconds": total time
        }
    """

    current_from = start_date

    request_count = 0
    total_candles = 0
    total_inserted = 0

    download_start_time = time.time()

    while current_from < end_date:

        current_to = min(
            current_from + timedelta(days=CHUNK_DAYS),
            end_date,
        )

        range_from_text = current_from.strftime(
            "%Y-%m-%d"
        )

        range_to_text = current_to.strftime(
            "%Y-%m-%d"
        )

        retry_count = 0

        while True:

            request_count += 1

            print(
                f"      Request {request_count}: "
                f"{range_from_text} → {range_to_text}"
            )

            data = {
                "symbol": symbol,
                "resolution": RESOLUTION,
                "date_format": "1",
                "range_from": range_from_text,
                "range_to": range_to_text,
                "cont_flag": CONT_FLAG,
                "oi_flag": OI_FLAG,
            }

            try:

                request_start = time.time()

                response = fyers.history(
                    data=data
                )

                request_time = (
                    time.time() - request_start
                )

                status = response.get("s")

                # ==================================================
                # SUCCESS
                # ==================================================

                if status == "ok":

                    candles = response.get(
                        "candles",
                        []
                    )

                    new_rows = insert_candles(
                        symbol,
                        stock_name,
                        candles,
                    )

                    total_candles += len(candles)
                    total_inserted += new_rows

                    print(
                        f"         Candles: {len(candles):>5} | "
                        f"New: {new_rows:>5} | "
                        f"API: {request_time:.2f}s"
                    )

                    current_from = current_to

                    # Small throttle
                    time.sleep(
                        SLEEP_SECONDS
                    )

                    break

                # ==================================================
                # NO DATA
                # ==================================================

                elif status == "no_data":

                    print(
                        "         No data for this period."
                    )

                    current_from = current_to

                    time.sleep(
                        SLEEP_SECONDS
                    )

                    break

                # ==================================================
                # RATE LIMIT
                # ==================================================

                elif response.get("code") == 429:

                    retry_count += 1

                    if retry_count > MAX_RETRIES:

                        raise RuntimeError(
                            f"Maximum 429 retries exceeded "
                            f"for {symbol}: "
                            f"{range_from_text} → "
                            f"{range_to_text}"
                        )

                    print(
                        f"         429 RATE LIMIT."
                    )

                    print(
                        f"         Waiting "
                        f"{RATE_LIMIT_SLEEP}s "
                        f"before retry "
                        f"{retry_count}/"
                        f"{MAX_RETRIES}..."
                    )

                    time.sleep(
                        RATE_LIMIT_SLEEP
                    )

                    # Same chunk is retried.
                    continue

                # ==================================================
                # OTHER API ERROR
                # ==================================================

                else:

                    raise RuntimeError(
                        f"FYERS API error for {symbol}: "
                        f"{range_from_text} → "
                        f"{range_to_text}\n"
                        f"{response}"
                    )

            # ======================================================
            # TEMPORARY NETWORK / PYTHON ERROR
            # ======================================================

            except RuntimeError:
                raise

            except Exception as e:

                retry_count += 1

                if retry_count > MAX_RETRIES:

                    raise RuntimeError(
                        f"Maximum retries exceeded "
                        f"for {symbol}: "
                        f"{range_from_text} → "
                        f"{range_to_text}\n"
                        f"{e}"
                    )

                print(
                    f"         Temporary error: {e}"
                )

                print(
                    f"         Waiting "
                    f"{RATE_LIMIT_SLEEP}s "
                    f"before retry "
                    f"{retry_count}/"
                    f"{MAX_RETRIES}..."
                )

                time.sleep(
                    RATE_LIMIT_SLEEP
                )

    total_time = (
        time.time() - download_start_time
    )

    return {
        "requests": request_count,
        "candles": total_candles,
        "inserted": total_inserted,
        "seconds": total_time,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    overall_start_time = time.time()

    print()
    print("=" * 75)
    print("NSE STOCK 1-MINUTE INCREMENTAL DATA DOWNLOADER")
    print("=" * 75)

    print()
    print(f"Scanner CSV       : {CSV_PATH}")
    print(f"Database          : {DB_PATH}")
    print(f"Stocks in CSV     : {len(symbols)}")
    print(f"Resolution        : {RESOLUTION} minute")
    print(
        f"New stock history : "
        f"{INITIAL_HISTORY_MONTHS} months"
    )
    print(
        f"Chunk size        : "
        f"{CHUNK_DAYS} days"
    )
    print(
        f"Request delay     : "
        f"{SLEEP_SECONDS} sec"
    )
    print(
        f"429 wait          : "
        f"{RATE_LIMIT_SLEEP} sec"
    )
    print(
        f"Max retries       : "
        f"{MAX_RETRIES}"
    )

    # ========================================================
    # TODAY / COMPLETED DATA
    # ========================================================

    today = datetime.now().replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    yesterday = today - timedelta(days=1)

    # Approximate month calculation,
    # same approach as previous downloader.
    history_days = int(
        INITIAL_HISTORY_MONTHS * 30.4375
    )

    target_start = today - timedelta(
        days=history_days
    )

    # TODAY is exclusive.
    target_end = today

    print()
    print(
        f"Target history     : "
        f"{target_start.date()} → "
        f"{yesterday.date()}"
    )

    print(
        f"Today's data       : NOT STORED "
        f"({today.date()})"
    )

    # ========================================================
    # SUMMARY COUNTERS
    # ========================================================

    new_stocks = []
    existing_stocks = []
    up_to_date_stocks = []
    failed_stocks = []

    total_requests = 0
    total_api_candles = 0
    total_inserted = 0

    # ========================================================
    # PROCESS EACH STOCK
    # ========================================================

    for index, symbol in enumerate(
        symbols,
        start=1
    ):

        stock_name = symbol

        print()
        print("=" * 75)
        print(
            f"STOCK {index}/{len(symbols)} : "
            f"{symbol}"
        )
        print("=" * 75)

        stock_start_time = time.time()

        try:

            db_min, db_max = get_db_range(
                symbol
            )

            # ==================================================
            # NEW STOCK
            # ==================================================

            if db_min is None or db_max is None:

                print(
                    "Status            : NEW STOCK"
                )

                print(
                    "Database range    : EMPTY"
                )

                print(
                    f"Action            : "
                    f"FULL {INITIAL_HISTORY_MONTHS}-MONTH "
                    f"DOWNLOAD"
                )

                print(
                    f"Download range    : "
                    f"{target_start.date()} → "
                    f"{yesterday.date()}"
                )

                new_stocks.append(symbol)

                result = download_range(
                    symbol=symbol,
                    start_date=target_start,
                    end_date=target_end,
                    stock_name=stock_name,
                )

                total_requests += result[
                    "requests"
                ]

                total_api_candles += result[
                    "candles"
                ]

                total_inserted += result[
                    "inserted"
                ]

            # ==================================================
            # EXISTING STOCK
            # ==================================================

            else:

                existing_stocks.append(symbol)

                db_min_dt = datetime.strptime(
                    db_min,
                    "%Y-%m-%d %H:%M:%S",
                )

                db_max_dt = datetime.strptime(
                    db_max,
                    "%Y-%m-%d %H:%M:%S",
                )

                print(
                    "Status            : EXISTING STOCK"
                )

                print(
                    f"Database range    : "
                    f"{db_min_dt} → "
                    f"{db_max_dt}"
                )

                stock_had_download = False

                # ==================================================
                # OLDER HISTORY
                # ==================================================

                if db_min_dt > target_start:

                    print()
                    print(
                        "Older history     : MISSING"
                    )

                    print(
                        f"Downloading       : "
                        f"{target_start.date()} → "
                        f"{db_min_dt.date()}"
                    )

                    stock_had_download = True

                    result = download_range(
                        symbol=symbol,
                        start_date=target_start,
                        end_date=db_min_dt,
                        stock_name=stock_name,
                    )

                    total_requests += result[
                        "requests"
                    ]

                    total_api_candles += result[
                        "candles"
                    ]

                    total_inserted += result[
                        "inserted"
                    ]

                else:

                    print(
                        "Older history     : OK"
                    )

                # ==================================================
                # NEWER HISTORY
                # ==================================================

                if db_max_dt < target_end:

                    print()
                    print(
                        "Newer history     : MISSING"
                    )

                    # Start one minute after the last
                    # stored candle.
                    #
                    # This prevents repeatedly requesting
                    # the already-complete final candle.
                    newer_start = (
                        db_max_dt
                        + timedelta(minutes=1)
                    )

                    if newer_start < target_end:

                        print(
                            f"Downloading       : "
                            f"{newer_start.date()} → "
                            f"{yesterday.date()}"
                        )

                        stock_had_download = True

                        result = download_range(
                            symbol=symbol,
                            start_date=newer_start,
                            end_date=target_end,
                            stock_name=stock_name,
                        )

                        total_requests += result[
                            "requests"
                        ]

                        total_api_candles += result[
                            "candles"
                        ]

                        total_inserted += result[
                            "inserted"
                        ]

                    else:

                        print(
                            "Newer history     : "
                            "Already complete"
                        )

                else:

                    print(
                        "Newer history     : OK"
                    )

                # ==================================================
                # COMPLETELY UP TO DATE
                # ==================================================

                if not stock_had_download:

                    up_to_date_stocks.append(
                        symbol
                    )

                    print()
                    print(
                        "ACTION            : "
                        "NO API REQUEST NEEDED"
                    )

        except Exception as e:

            failed_stocks.append(
                (symbol, str(e))
            )

            print()
            print(
                f"ERROR for {symbol}:"
            )

            print(e)

        # ==================================================
        # STOCK TIMING
        # ==================================================

        stock_time = (
            time.time()
            - stock_start_time
        )

        print()
        print(
            f"Stock completed in "
            f"{stock_time:.2f} sec"
        )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    overall_time = (
        time.time()
        - overall_start_time
    )

    print()
    print()
    print("=" * 75)
    print("DOWNLOAD SUMMARY")
    print("=" * 75)

    print()
    print(
        f"Stocks in today's CSV : "
        f"{len(symbols)}"
    )

    print(
        f"New stocks            : "
        f"{len(new_stocks)}"
    )

    print(
        f"Existing stocks       : "
        f"{len(existing_stocks)}"
    )

    print(
        f"Already up-to-date    : "
        f"{len(up_to_date_stocks)}"
    )

    print(
        f"Failed stocks         : "
        f"{len(failed_stocks)}"
    )

    print()
    print(
        f"API requests          : "
        f"{total_requests}"
    )

    print(
        f"API candles received  : "
        f"{total_api_candles:,}"
    )

    print(
        f"New DB candles        : "
        f"{total_inserted:,}"
    )

    print(
        f"Total execution time  : "
        f"{overall_time:.2f} sec"
    )

    # ========================================================
    # NEW STOCK LIST
    # ========================================================

    if new_stocks:

        print()
        print("-" * 75)
        print("NEW STOCKS — FULL 60 MONTH DOWNLOAD")
        print("-" * 75)

        for symbol in new_stocks:
            print(
                f"  + {symbol}"
            )

    # ========================================================
    # UP-TO-DATE LIST
    # ========================================================

    if up_to_date_stocks:

        print()
        print("-" * 75)
        print("ALREADY UP-TO-DATE — NO API REQUEST")
        print("-" * 75)

        for symbol in up_to_date_stocks:
            print(
                f"  = {symbol}"
            )

    # ========================================================
    # FAILED LIST
    # ========================================================

    if failed_stocks:

        print()
        print("-" * 75)
        print("FAILED STOCKS")
        print("-" * 75)

        for symbol, error in failed_stocks:

            print(
                f"  X {symbol}"
            )

            print(
                f"    {error}"
            )

    # ========================================================
    # FINAL DATABASE CHECK
    # ========================================================

    print()
    print("-" * 75)
    print("FINAL DATABASE STATUS")
    print("-" * 75)

    total_rows = conn.execute(
        """
        SELECT COUNT(*)
        FROM nse_stockdata
        """
    ).fetchone()[0]

    total_symbols = conn.execute(
        """
        SELECT COUNT(DISTINCT symbol)
        FROM nse_stockdata
        """
    ).fetchone()[0]

    print(
        f"Total DB rows       : "
        f"{total_rows:,}"
    )

    print(
        f"Unique stocks       : "
        f"{total_symbols:,}"
    )

    print()
    print("=" * 75)
    print("DOWNLOAD COMPLETED")
    print("=" * 75)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()
        print(
            "Download stopped by user."
        )

    finally:

        conn.close()