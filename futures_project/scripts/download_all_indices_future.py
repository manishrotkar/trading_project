import io
import sqlite3
import sys
import time
import requests
import pandas as pd

from pathlib import Path
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# PROJECT PATHS
# ============================================================

FUTURES_PROJECT = Path(__file__).resolve().parents[1]
MAIN_PROJECT = FUTURES_PROJECT.parent

sys.path.insert(0, str(MAIN_PROJECT))

from core.fyers_client import get_fyers_client


# ============================================================
# DATABASE
# ============================================================

DATABASE = FUTURES_PROJECT / "database" / "futures.db"


# ============================================================
# FYERS SYMBOL MASTERS
# ============================================================

NSE_SYMBOL_MASTER_URL = "https://public.fyers.in/sym_details/NSE_FO.csv"
BSE_SYMBOL_MASTER_URL = "https://public.fyers.in/sym_details/BSE_FO.csv"


# ============================================================
# SETTINGS
# ============================================================

IST = ZoneInfo("Asia/Kolkata")

BATCH_DAYS = 30
SLEEP_SECONDS = 1

# Used only when a completely new contract has no data
# in the database yet.
NEW_CONTRACT_LOOKBACK_DAYS = 180


# ============================================================
# INDICES WE WANT
# ============================================================

NSE_INDICES = [
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "NIFTYFPI",
    "NIFTYNXT50",
]

BSE_INDICES = [
    "SENSEX",
    "BANKEX",
]


# ============================================================
# CURRENT DATE
# ============================================================

def get_today():

    return datetime.now(IST).date()


# ============================================================
# GET EXISTING LAST DATE FROM DATABASE
# ============================================================

def get_existing_last_date(symbol, contract):

    connection = sqlite3.connect(DATABASE)

    try:

        row = connection.execute(
            """
            SELECT MAX(datetime)
            FROM futures_data
            WHERE symbol = ?
              AND contract = ?
            """,
            (
                symbol,
                contract,
            ),
        ).fetchone()

    finally:

        connection.close()

    if row is None or row[0] is None:
        return None

    try:

        last_datetime = datetime.fromisoformat(row[0])

        return last_datetime.date()

    except ValueError:

        return None


# ============================================================
# GET DOWNLOAD START DATE
# ============================================================

def get_start_date(contract_info):

    symbol = contract_info["symbol"]
    contract = contract_info["contract"]
    expiry = date.fromisoformat(
        contract_info["expiry"]
    )

    existing_last_date = get_existing_last_date(
        symbol,
        contract
    )

    # --------------------------------------------------------
    # Existing contract:
    # Continue from the last stored date.
    #
    # We intentionally start from the same date again so that
    # any missing candles on that date can be recovered.
    # INSERT OR IGNORE prevents duplicates.
    # --------------------------------------------------------

    if existing_last_date is not None:

        return existing_last_date

    # --------------------------------------------------------
    # Completely new contract:
    #
    # Start automatically from 180 days before expiry.
    # No calendar date is hard-coded.
    # --------------------------------------------------------

    start_date = expiry - timedelta(
        days=NEW_CONTRACT_LOOKBACK_DAYS
    )

    return start_date


# ============================================================
# GET CONTRACTS FROM SYMBOL MASTER
# ============================================================

def get_contracts(url, exchange, indices):

    print()
    print("=" * 70)
    print(f"DOWNLOADING {exchange} FUTURES SYMBOL MASTER")
    print("=" * 70)

    response = requests.get(
        url,
        timeout=30
    )

    response.raise_for_status()

    df = pd.read_csv(
        io.BytesIO(response.content),
        header=None,
        low_memory=False
    )

    print(
        f"Total {exchange} symbol-master rows: "
        f"{len(df):,}"
    )

    # --------------------------------------------------------
    # Column 2 = Instrument type
    # 11 = Futures
    #
    # Column 13 = Underlying
    # --------------------------------------------------------

    futures = df[
        (df[2] == 11) &
        (df[13].astype(str).str.upper().isin(indices))
    ].copy()

    # --------------------------------------------------------
    # Column 8 = Expiry timestamp
    # --------------------------------------------------------

    futures["expiry_date"] = futures[8].apply(
        lambda value: datetime.fromtimestamp(
            int(value),
            tz=IST
        ).date()
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Only contracts that have NOT expired.
    #
    # Current date is determined automatically.
    # --------------------------------------------------------

    today = get_today()

    futures = futures[
        futures["expiry_date"] >= today
    ].copy()

    futures = futures.sort_values(
        [13, "expiry_date"]
    ).reset_index(drop=True)

    contracts = []

    print()
    print(
        f"Contracts selected as of {today}:"
    )

    # --------------------------------------------------------
    # Current / Next / Far
    # --------------------------------------------------------

    for index_name in indices:

        index_futures = futures[
            futures[13].astype(str).str.upper()
            == index_name
        ].sort_values(
            "expiry_date"
        )

        selected = index_futures.head(3)

        labels = [
            "CURRENT",
            "NEXT",
            "FAR"
        ]

        for position, (_, row) in enumerate(
            selected.iterrows()
        ):

            contract_info = {
                "exchange": exchange,
                "index": index_name,
                "position": labels[position],
                "symbol": row[9],
                "contract": row[1],
                "expiry": row["expiry_date"].isoformat(),
                "lot_size": row[3],
            }

            contracts.append(
                contract_info
            )

            print(
                f"{index_name:12} | "
                f"{labels[position]:7} | "
                f"{row[9]:30} | "
                f"Expiry: {row['expiry_date']} | "
                f"Lot: {row[3]}"
            )

    return contracts


# ============================================================
# DOWNLOAD ONE BATCH
# ============================================================

def download_batch(
    fyers,
    contract_info,
    start_date,
    end_date
):

    symbol = contract_info["symbol"]
    contract = contract_info["contract"]
    expiry = contract_info["expiry"]

    data = {
        "symbol": symbol,
        "resolution": "1",
        "date_format": "1",
        "range_from": start_date.isoformat(),
        "range_to": end_date.isoformat(),
        "cont_flag": "0",
        "oi_flag": "1",
    }

    try:

        response = fyers.history(
            data=data
        )

    except Exception as error:

        print(
            f"❌ {symbol} | "
            f"{start_date} → {end_date} | "
            f"API error: {error}"
        )

        return 0

    if response.get("s") != "ok":

        print(
            f"⚠️ {symbol} | "
            f"{start_date} → {end_date} | "
            f"{response.get('s')} | "
            f"{response.get('message', '')}"
        )

        return 0

    candles = response.get(
        "candles",
        []
    )

    print(
        f"✅ {symbol} | "
        f"{start_date} → {end_date} | "
        f"{len(candles):,} candles"
    )

    if not candles:
        return 0

    connection = sqlite3.connect(
        DATABASE
    )

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

            dt = datetime.fromtimestamp(
                timestamp,
                tz=IST
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


# ============================================================
# DOWNLOAD ONE CONTRACT
# ============================================================

def download_contract(
    fyers,
    contract_info
):

    print()
    print("=" * 70)
    print(
        f"{contract_info['exchange']} | "
        f"{contract_info['index']} | "
        f"{contract_info['position']}"
    )
    print("=" * 70)

    print(
        f"Symbol   : {contract_info['symbol']}"
    )

    print(
        f"Contract : {contract_info['contract']}"
    )

    print(
        f"Expiry   : {contract_info['expiry']}"
    )

    print(
        f"Lot size : {contract_info['lot_size']}"
    )

    # --------------------------------------------------------
    # AUTOMATIC START DATE
    # --------------------------------------------------------

    start_date = get_start_date(
        contract_info
    )

    # --------------------------------------------------------
    # AUTOMATIC END DATE
    # --------------------------------------------------------

    end_date = get_today()

    print(
        f"From     : {start_date}"
    )

    print(
        f"To       : {end_date}"
    )

    # --------------------------------------------------------
    # If the database already contains data through today,
    # still download today again.
    #
    # INSERT OR IGNORE handles existing candles.
    # --------------------------------------------------------

    current = start_date

    total_inserted = 0

    while current <= end_date:

        batch_end = min(
            current + timedelta(
                days=BATCH_DAYS - 1
            ),
            end_date
        )

        inserted = download_batch(
            fyers,
            contract_info,
            current,
            batch_end
        )

        total_inserted += inserted

        current = batch_end + timedelta(
            days=1
        )

        if current <= end_date:

            print(
                f"Sleeping {SLEEP_SECONDS} seconds..."
            )

            time.sleep(
                SLEEP_SECONDS
            )

    print()
    print(
        f"{contract_info['position']} "
        f"{contract_info['index']} "
        f"total new rows: "
        f"{total_inserted:,}"
    )

    return total_inserted


# ============================================================
# MAIN
# ============================================================

def main():

    today = get_today()

    print("=" * 70)
    print(
        "ALL INDEX FUTURES — "
        "AUTOMATIC CURRENT / NEXT / FAR"
    )
    print("=" * 70)

    print(
        f"Database : {DATABASE}"
    )

    print(
        f"Today    : {today}"
    )

    print(
        "Mode     : Manual update"
    )

    print(
        "Frequency: 1-minute"
    )

    # --------------------------------------------------------
    # Get NSE contracts
    # --------------------------------------------------------

    nse_contracts = get_contracts(
        NSE_SYMBOL_MASTER_URL,
        "NSE",
        NSE_INDICES
    )

    # --------------------------------------------------------
    # Get BSE contracts
    # --------------------------------------------------------

    bse_contracts = get_contracts(
        BSE_SYMBOL_MASTER_URL,
        "BSE",
        BSE_INDICES
    )

    all_contracts = (
        nse_contracts +
        bse_contracts
    )

    print()
    print("=" * 70)
    print(
        f"TOTAL CONTRACTS FOUND: "
        f"{len(all_contracts)}"
    )
    print("=" * 70)

    if not all_contracts:

        print(
            "\n❌ No active futures contracts found."
        )

        return

    # --------------------------------------------------------
    # Fyers client
    # --------------------------------------------------------

    fyers = get_fyers_client()

    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

    total_inserted = 0

    for contract_info in all_contracts:

        inserted = download_contract(
            fyers,
            contract_info
        )

        total_inserted += inserted

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        f"TOTAL NEW ROWS INSERTED: "
        f"{total_inserted:,}"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()