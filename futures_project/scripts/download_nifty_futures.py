import io
import sqlite3
import sys
import time
import requests
import pandas as pd

from pathlib import Path
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo


# ==================================================
# PROJECT PATHS
# ==================================================

FUTURES_PROJECT = Path(__file__).resolve().parents[1]
MAIN_PROJECT = FUTURES_PROJECT.parent

sys.path.insert(0, str(MAIN_PROJECT))

from core.fyers_client import get_fyers_client


# ==================================================
# SETTINGS
# ==================================================

DATABASE = FUTURES_PROJECT / "database" / "futures.db"

SYMBOL_MASTER_URL = "https://public.fyers.in/sym_details/NSE_FO.csv"

START_DATE = date(2026, 6, 1)
END_DATE = date(2026, 9, 5)

BATCH_DAYS = 30
SLEEP_SECONDS = 3


# ==================================================
# FIND CURRENT / NEXT / FAR NIFTY FUTURES
# ==================================================

def get_nifty_contracts():

    print("\nDownloading FYERS NSE Futures symbol master...")

    response = requests.get(
        SYMBOL_MASTER_URL,
        timeout=30
    )

    response.raise_for_status()

    df = pd.read_csv(
        io.BytesIO(response.content),
        header=None,
        low_memory=False
    )

    print(f"Total symbol-master rows: {len(df):,}")

    # NIFTY index futures only
    nifty_futures = df[
        (df[2] == 11) &
        (df[13].astype(str).str.upper() == "NIFTY")
    ].copy()

    print(
        f"NIFTY index futures found: "
        f"{len(nifty_futures)}"
    )

    # Column 8 = expiry timestamp
    # Column 9 = FYERS symbol

    nifty_futures["expiry_date"] = nifty_futures[8].apply(
        lambda x: datetime.fromtimestamp(
            int(x),
            tz=ZoneInfo("Asia/Kolkata")
        ).date()
    )

    # Sort by actual expiry
    nifty_futures = nifty_futures.sort_values(
        "expiry_date"
    ).reset_index(drop=True)

    labels = [
        "CURRENT",
        "NEXT",
        "FAR"
    ]

    contracts = []

    print("\nContracts selected:")

    for position, label in enumerate(labels):

        if position >= len(nifty_futures):
            break

        row = nifty_futures.iloc[position]

        contract = {
            "position": label,
            "symbol": row[9],
            "contract": row[1],
            "expiry": row["expiry_date"].isoformat(),
        }

        contracts.append(contract)

        print(
            f"{label:7} | "
            f"{row[9]} | "
            f"Expiry: {row['expiry_date']}"
        )

    return contracts


# ==================================================
# DOWNLOAD ONE BATCH
# ==================================================

def download_batch(
    fyers,
    symbol,
    contract,
    expiry,
    start_date,
    end_date
):

    data = {
        "symbol": symbol,
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
            f"❌ {start_date} → {end_date} "
            f"| {response.get('s')}"
        )

        return 0

    candles = response.get("candles", [])

    print(
        f"✅ {start_date} → {end_date} "
        f"| {len(candles):,} candles"
    )

    if not candles:
        return 0

    connection = sqlite3.connect(DATABASE)

    inserted = 0

    try:

        for candle in candles:

            if len(candle) < 7:
                print(
                    "⚠️ Unexpected candle format:",
                    candle
                )
                continue

            timestamp = candle[0]
            open_price = candle[1]
            high_price = candle[2]
            low_price = candle[3]
            close_price = candle[4]
            volume = candle[5]
            open_interest = candle[6]

            # Unix timestamp → IST
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
                    symbol,
                    contract,
                    expiry,
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

    print(
        f"   New rows inserted: {inserted:,}"
    )

    return inserted


# ==================================================
# DOWNLOAD ONE CONTRACT
# ==================================================

def download_contract(fyers, contract_info):

    symbol = contract_info["symbol"]
    contract = contract_info["contract"]
    expiry = contract_info["expiry"]

    print()
    print("=" * 70)
    print(
        f"{contract_info['position']} CONTRACT"
    )
    print("=" * 70)

    print(f"Symbol   : {symbol}")
    print(f"Contract : {contract}")
    print(f"Expiry   : {expiry}")
    print(
        f"From     : {START_DATE}"
    )
    print(
        f"To       : {END_DATE}"
    )

    current = START_DATE
    total_inserted = 0

    while current <= END_DATE:

        batch_end = min(
            current + timedelta(days=BATCH_DAYS - 1),
            END_DATE
        )

        inserted = download_batch(
            fyers,
            symbol,
            contract,
            expiry,
            current,
            batch_end
        )

        total_inserted += inserted

        current = batch_end + timedelta(days=1)

        if current <= END_DATE:

            print(
                f"Sleeping {SLEEP_SECONDS} seconds..."
            )

            time.sleep(SLEEP_SECONDS)

    print(
        f"\n{contract_info['position']} "
        f"total new rows: {total_inserted:,}"
    )

    return total_inserted


# ==================================================
# MAIN
# ==================================================

def main():

    print("=" * 70)
    print("NIFTY FUTURES — CURRENT / NEXT / FAR DOWNLOAD")
    print("=" * 70)

    print(f"Database : {DATABASE}")
    print(f"From     : {START_DATE}")
    print(f"To       : {END_DATE}")

    # --------------------------------------------------
    # Discover contracts
    # --------------------------------------------------

    contracts = get_nifty_contracts()

    if not contracts:

        print("\n❌ No NIFTY futures contracts found.")

        return

    # --------------------------------------------------
    # FYERS client
    # --------------------------------------------------

    fyers = get_fyers_client()

    # --------------------------------------------------
    # Download CURRENT / NEXT / FAR
    # --------------------------------------------------

    total_inserted = 0

    for contract_info in contracts:

        inserted = download_contract(
            fyers,
            contract_info
        )

        total_inserted += inserted

    # --------------------------------------------------
    # Final result
    # --------------------------------------------------

    print()
    print("=" * 70)
    print(
        f"TOTAL NEW ROWS INSERTED: "
        f"{total_inserted:,}"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
