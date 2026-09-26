from pathlib import Path
from datetime import datetime
import sys
import sqlite3
import time

import pandas as pd

# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================
# EXISTING FYERS CLIENT
# ============================================================

from core.fyers_client import get_fyers_client

# ============================================================
# PATHS
# ============================================================

OPTION_DIR = PROJECT_ROOT / "option_analysis"

DB_PATH = (
    OPTION_DIR
    / "database"
    / "underlying_data.db"
)

# ============================================================
# SETTINGS
# ============================================================

# NIFTY + BANKNIFTY option period
UNDERLYING_START_DATE = "2026-09-01"
UNDERLYING_END_DATE = "2026-09-25"

# India VIX historical period
VIX_START_DATE = "2021-01-01"
VIX_END_DATE = "2026-09-25"

# FYERS historical API batch size
BATCH_DAYS = 30

# Sleep between API requests
SLEEP_SECONDS = 1

# Maximum API retries
MAX_RETRIES = 3

# ============================================================
# SYMBOLS
# ============================================================

INDEX_SYMBOLS = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
}

VIX_SYMBOL = "NSE:INDIAVIX-INDEX"

# ============================================================
# FYERS CLIENT
# ============================================================

fyers = get_fyers_client()

# ============================================================
# CREATE DATABASE
# ============================================================


def create_database():

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with sqlite3.connect(DB_PATH) as conn:

        # ----------------------------------------------------
        # NIFTY + BANKNIFTY
        # ----------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS underlying_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                index_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                datetime TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL
            )
            """
        )

        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_underlying_unique
            ON underlying_data(
                index_name,
                symbol,
                datetime
            )
            """
        )

        # ----------------------------------------------------
        # INDIA VIX
        # ----------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vix_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                index_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                datetime TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL
            )
            """
        )

        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_vix_unique
            ON vix_data(
                index_name,
                symbol,
                datetime
            )
            """
        )

        conn.commit()


# ============================================================
# GET LAST DOWNLOADED DATETIME
# ============================================================


def get_last_datetime(
    table_name,
    symbol,
):

    query = f"""
        SELECT MAX(datetime)
        FROM {table_name}
        WHERE symbol = ?
    """

    with sqlite3.connect(DB_PATH) as conn:

        row = conn.execute(
            query,
            (symbol,),
        ).fetchone()

    return row[0]


# ============================================================
# INSERT CANDLES
# ============================================================


def insert_candles(
    table_name,
    index_name,
    symbol,
    candles,
):

    if not candles:
        return 0

    rows = []

    for candle in candles:

        if len(candle) < 6:
            continue

        timestamp = int(candle[0])

        dt = datetime.fromtimestamp(
            timestamp
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        rows.append(
            (
                index_name,
                symbol,
                dt,
                float(candle[1]),
                float(candle[2]),
                float(candle[3]),
                float(candle[4]),
                float(candle[5]),
            )
        )

    if not rows:
        return 0

    query = f"""
        INSERT OR IGNORE INTO {table_name}
        (
            index_name,
            symbol,
            datetime,
            open,
            high,
            low,
            close,
            volume
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.executemany(
            query,
            rows,
        )

        conn.commit()

        return cursor.rowcount


# ============================================================
# DOWNLOAD ONE SYMBOL
# ============================================================


def download_symbol(
    table_name,
    index_name,
    symbol,
    start_date,
    end_date,
):

    print()
    print("=" * 80)
    print(f"Index      : {index_name}")
    print(f"Symbol     : {symbol}")
    print(f"Period     : {start_date} -> {end_date}")
    print("=" * 80)

    # --------------------------------------------------------
    # Resume point
    # --------------------------------------------------------

    last_datetime = get_last_datetime(
        table_name,
        symbol,
    )

    if last_datetime:

        start = (
            pd.Timestamp(last_datetime)
            + pd.Timedelta(minutes=1)
        )

        print(
            f"Resume from: {start}"
        )

    else:

        start = pd.Timestamp(
            start_date
        )

        print(
            f"Starting from: {start}"
        )

    end = (
        pd.Timestamp(end_date)
        + pd.Timedelta(days=1)
    )

    if start >= end:

        print(
            "Already downloaded."
        )

        return 0

    total_received = 0
    total_inserted = 0

    # --------------------------------------------------------
    # Batch download
    # --------------------------------------------------------

    while start < end:

        batch_end = min(
            start
            + pd.Timedelta(
                days=BATCH_DAYS
            ),
            end,
        )

        range_from = start.strftime(
            "%Y-%m-%d"
        )

        request_end = min(
            batch_end,
            pd.Timestamp(end_date),
        )

        range_to = request_end.strftime(
            "%Y-%m-%d"
        )

        print()
        print(
            f"Request: "
            f"{range_from} -> {range_to}"
        )

        data = {
            "symbol": symbol,
            "resolution": "1",
            "date_format": "1",
            "range_from": range_from,
            "range_to": range_to,
            "cont_flag": "1",
        }

        response = None

        # ----------------------------------------------------
        # Retry
        # ----------------------------------------------------

        for attempt in range(
            1,
            MAX_RETRIES + 1,
        ):

            try:

                response = fyers.history(
                    data=data
                )

            except Exception as exc:

                print(
                    f"API exception "
                    f"(attempt "
                    f"{attempt}/"
                    f"{MAX_RETRIES}): "
                    f"{exc}"
                )

                if attempt < MAX_RETRIES:

                    time.sleep(
                        SLEEP_SECONDS
                    )

                continue

            status = response.get("s")

            if status == "ok":
                break

            if status == "no_data":

                print(
                    "FYERS returned no_data."
                )

                response = None
                break

            print(
                f"FYERS error "
                f"(attempt "
                f"{attempt}/"
                f"{MAX_RETRIES})"
            )

            print(response)

            if attempt < MAX_RETRIES:

                time.sleep(
                    SLEEP_SECONDS
                )

        # ----------------------------------------------------
        # Failed completely
        # ----------------------------------------------------

        if response is None:

            print(
                "No usable response for this batch."
            )

            # Move forward so one bad batch
            # does not stop the entire download.

            start = batch_end

            time.sleep(
                SLEEP_SECONDS
            )

            continue

        if response.get("s") != "ok":

            print(
                "Batch skipped after "
                "maximum retries."
            )

            start = batch_end

            time.sleep(
                SLEEP_SECONDS
            )

            continue

        candles = response.get(
            "candles",
            [],
        )

        if not candles:

            print(
                "No candles returned."
            )

            start = batch_end

            time.sleep(
                SLEEP_SECONDS
            )

            continue

        inserted = insert_candles(
            table_name,
            index_name,
            symbol,
            candles,
        )

        total_received += len(candles)
        total_inserted += inserted

        print(
            f"Candles received : "
            f"{len(candles):,}"
        )

        print(
            f"Rows inserted    : "
            f"{inserted:,}"
        )

        # ----------------------------------------------------
        # Move to next batch
        # ----------------------------------------------------

        start = batch_end

        time.sleep(
            SLEEP_SECONDS
        )

    print()
    print(
        f"Total candles received: "
        f"{total_received:,}"
    )

    print(
        f"Total rows inserted   : "
        f"{total_inserted:,}"
    )

    return total_inserted


# ============================================================
# MAIN
# ============================================================


def main():

    print()
    print("=" * 80)
    print("UNDERLYING + INDIA VIX DOWNLOADER")
    print("=" * 80)

    print()
    print(
        f"NIFTY/BANKNIFTY period : "
        f"{UNDERLYING_START_DATE} -> "
        f"{UNDERLYING_END_DATE}"
    )

    print(
        f"India VIX period       : "
        f"{VIX_START_DATE} -> "
        f"{VIX_END_DATE}"
    )

    print(
        f"Batch size             : "
        f"{BATCH_DAYS} days"
    )

    print(
        f"Sleep                  : "
        f"{SLEEP_SECONDS} second"
    )

    # --------------------------------------------------------
    # Create database/tables
    # --------------------------------------------------------

    create_database()

    total_inserted = 0

    # --------------------------------------------------------
    # NIFTY + BANKNIFTY
    # --------------------------------------------------------

    for index_name, symbol in INDEX_SYMBOLS.items():

        inserted = download_symbol(
            table_name="underlying_data",
            index_name=index_name,
            symbol=symbol,
            start_date=UNDERLYING_START_DATE,
            end_date=UNDERLYING_END_DATE,
        )

        total_inserted += inserted

    # --------------------------------------------------------
    # INDIA VIX
    # --------------------------------------------------------

    inserted = download_symbol(
        table_name="vix_data",
        index_name="INDIA_VIX",
        symbol=VIX_SYMBOL,
        start_date=VIX_START_DATE,
        end_date=VIX_END_DATE,
    )

    total_inserted += inserted

    # --------------------------------------------------------
    # Finished
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("DOWNLOAD FINISHED")
    print("=" * 80)

    print(
        f"Total rows inserted: "
        f"{total_inserted:,}"
    )

    print(
        f"Database: {DB_PATH}"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()