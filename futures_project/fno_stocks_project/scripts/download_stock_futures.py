import os
import time
import sqlite3
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fyers_apiv3 import fyersModel
from dotenv import load_dotenv


# ============================================================
# CONFIG
# ============================================================

IST = ZoneInfo("Asia/Kolkata")

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_DIR, "database", "fno_stocks.db")

SYMBOL_MASTER_URL = "https://public.fyers.in/sym_details/NSE_FO.csv"

BATCH_DAYS = 30
SLEEP_SECONDS = 1
NEW_CONTRACT_LOOKBACK_DAYS = 180


# ============================================================
# FYERS LOGIN
# ============================================================

load_dotenv(
    os.path.expanduser("~/trading_project/.env")
)

CLIENT_ID = os.getenv("FYERS_CLIENT_ID")

with open(
    os.path.expanduser("~/trading_project/access.txt"),
    "r"
) as f:
    ACCESS_TOKEN = f.read().strip()

fyers = fyersModel.FyersModel(
    client_id=CLIENT_ID,
    token=ACCESS_TOKEN,
    log_path=PROJECT_DIR
)


# ============================================================
# DISCOVER STOCK FUTURES
# ============================================================

def get_stock_contracts():

    print("Downloading FYERS NSE F&O symbol master...")

    df = pd.read_csv(
        SYMBOL_MASTER_URL,
        header=None
    )

    # Instrument type 13 = Stock Futures
    futures = df[df[2] == 13].copy()

    futures["expiry_date"] = pd.to_datetime(
        futures[8],
        unit="s",
        errors="coerce"
    ).dt.date

    today = datetime.now(IST).date()

    futures = futures[
        futures["expiry_date"].notna()
        & (futures["expiry_date"] >= today)
    ].copy()

    futures = futures.sort_values(
        [13, "expiry_date"]
    )

    contracts = []

    for stock, group in futures.groupby(13):

        group = (
            group
            .drop_duplicates(subset=["expiry_date"])
            .sort_values("expiry_date")
            .head(3)
        )

        labels = [
            "CURRENT",
            "NEXT",
            "FAR"
        ]

        for label, (_, row) in zip(
            labels,
            group.iterrows()
        ):

            contracts.append({
                "stock": stock,
                "symbol": row[9],
                "contract": row[1],
                "expiry": row["expiry_date"],
                "lot_size": row[3],
                "position": label
            })

    return contracts


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_last_datetime(symbol, expiry):

    conn = sqlite3.connect(DB_PATH)

    cur = conn.cursor()

    cur.execute(
        """
        SELECT MAX(datetime)
        FROM fno_stocks_data
        WHERE symbol = ?
        AND expiry = ?
        """,
        (symbol, str(expiry))
    )

    result = cur.fetchone()[0]

    conn.close()

    return result


def insert_candles(
    stock,
    symbol,
    contract,
    expiry,
    candles
):

    if not candles:
        return 0

    conn = sqlite3.connect(DB_PATH)

    cur = conn.cursor()

    inserted = 0

    for candle in candles:

        timestamp = candle[0]

        dt = datetime.fromtimestamp(
            timestamp,
            tz=IST
        )

        dt_string = dt.isoformat()

        cur.execute(
            """
            INSERT OR IGNORE INTO fno_stocks_data
            (
                stock,
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stock,
                symbol,
                contract,
                str(expiry),
                dt_string,
                candle[1],
                candle[2],
                candle[3],
                candle[4],
                candle[5],
                candle[6]
            )
        )

        if cur.rowcount == 1:
            inserted += 1

    conn.commit()
    conn.close()

    return inserted


# ============================================================
# DOWNLOAD ONE CONTRACT
# ============================================================

def download_contract(contract):

    stock = contract["stock"]
    symbol = contract["symbol"]
    contract_name = contract["contract"]
    expiry = contract["expiry"]
    position = contract["position"]

    print()
    print(
        f"{stock:<15} "
        f"{position:<8} "
        f"{symbol}"
    )

    last_datetime = get_last_datetime(
        symbol,
        expiry
    )

    if last_datetime:

        last_dt = datetime.fromisoformat(
            last_datetime
        )

        start_date = last_dt.date()

        print(
            f"  Existing data → "
            f"starting from {start_date}"
        )

    else:

        start_date = (
            expiry -
            timedelta(
                days=NEW_CONTRACT_LOOKBACK_DAYS
            )
        )

        print(
            f"  New contract → "
            f"lookback {NEW_CONTRACT_LOOKBACK_DAYS} days"
        )

    end_date = datetime.now(IST).date()

    total_inserted = 0

    current_start = start_date

    while current_start <= end_date:

        current_end = min(
            current_start +
            timedelta(days=BATCH_DAYS - 1),
            end_date
        )

        print(
            f"  Downloading "
            f"{current_start} → {current_end}"
        )

        data = {
            "symbol": symbol,
            "resolution": "1",
            "date_format": "1",
            "range_from": current_start.strftime("%Y-%m-%d"),
            "range_to": current_end.strftime("%Y-%m-%d"),
            "cont_flag": "0",
            "oi_flag": "1"
        }

        try:

            response = fyers.history(
                data=data
            )

            if response.get("s") != "ok":

                print(
                    "  API:",
                    response
                )

            else:

                candles = response.get(
                    "candles",
                    []
                )

                inserted = insert_candles(
                    stock,
                    symbol,
                    contract_name,
                    expiry,
                    candles
                )

                total_inserted += inserted

                print(
                    f"  Candles: {len(candles)} | "
                    f"New rows: {inserted}"
                )

        except Exception as e:

            print(
                f"  ERROR: {e}"
            )

        current_start = (
            current_end +
            timedelta(days=1)
        )

        time.sleep(
            SLEEP_SECONDS
        )

    print(
        f"  Total new rows: {total_inserted}"
    )

    return total_inserted


# ============================================================
# MAIN
# ============================================================

def main():

    contracts = get_stock_contracts()

    print()
    print("=" * 100)
    print(
        f"Found {len(contracts)} stock futures contracts"
    )
    print("=" * 100)

    total_rows = 0

    for contract in contracts:

        total_rows += download_contract(
            contract
        )

    print()
    print("=" * 100)
    print(
        f"TOTAL NEW ROWS INSERTED: {total_rows}"
    )
    print("=" * 100)


if __name__ == "__main__":
    main()
