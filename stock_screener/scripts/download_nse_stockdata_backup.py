import os
import sqlite3
import time
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
# STOCK LIST
# ==========================================

STOCKS = [
    "NSE:ENIL-EQ",
    "NSE:APCL-EQ",
    "NSE:HRYNSHP-EQ",
    "NSE:DBREALTY-EQ",
    "NSE:ADSL-EQ",
    "NSE:SARLAPOLY-EQ",
    "NSE:PVSL-EQ",
    "NSE:GILLANDERS-EQ",
    "NSE:MAHEPC-EQ",
    "NSE:VASUPRADA-EQ",
    "NSE:EKC-EQ",
    "NSE:ARCHIDPLY-EQ",
    "NSE:VMM-EQ",
    "NSE:CAMLINFINE-EQ",
    "NSE:LEMONTREE-EQ",
    "NSE:CORDELIA-EQ",
    "NSE:BEDMUTHA-EQ",
    "NSE:LUMINO-EQ",
    "NSE:GNRL-EQ",
    "NSE:TGVSL-EQ",
    "NSE:SANSTAR-EQ",
    "NSE:ALEMBICLTD-EQ",
    "NSE:THOMASCOOK-EQ",
    "NSE:NATIONSTD-EQ",
    "NSE:BANARBEADS-EQ",
    "NSE:SBIN-EQ",
    "NSE:DCMSHRIRAM-EQ",
    "NSE:HINDALCO-EQ",
    "NSE:TATACONSUM-EQ",
    "NSE:DHUNINV-EQ",
    "NSE:SIKA-EQ",
    "NSE:JINDALPHOT-EQ",
    "NSE:THACKER-EQ",
    "NSE:YUKEN-EQ",
    "NSE:TINNARUBR-EQ",
    "NSE:SHRIRAMFIN-EQ",
    "NSE:JYOTICNC-EQ",
    "NSE:ABSLAMC-EQ",
    "NSE:JENBURPH-EQ",
    "NSE:GANECOS-EQ",
    "NSE:SPAL-EQ",
    "NSE:DREDGECORP-EQ",
    "NSE:SANDESH-EQ",
    "NSE:MOTILALOFS-EQ",
    "NSE:BAJFINANCE-EQ",
    "NSE:GALAPREC-EQ",
    "NSE:GULFOILLUB-EQ",
    "NSE:MAITHANALL-EQ",
    "NSE:DSSL-EQ",
    "NSE:MANGLMCEM-EQ",
    "NSE:AUBANK-EQ",
    "NSE:MIDWESTLTD-EQ",
    "NSE:DODLA-EQ",
    "NSE:SHYAMMETL-EQ",
    "NSE:INFY-EQ",
    "NSE:CYIENT-EQ",
    "NSE:SYMBIOTEC-EQ",
    "NSE:PUNJABCHEM-EQ",
    "NSE:CARBORUNIV-EQ",
    "NSE:ANTELOPUS-EQ",
]


# ==========================================
# SETTINGS
# ==========================================

RESOLUTION = "1"

# FYERS API request chunk
CHUNK_DAYS = 7

# Small delay between requests
SLEEP_SECONDS = 0.2


# ==========================================
# USER INPUT
# ==========================================

print("=" * 60)
print("NSE STOCK 1-MINUTE HISTORICAL DATA DOWNLOADER")
print("=" * 60)

months_input = input(
    "\nHow many months of historical data do you want? "
    "[12]: "
).strip()

if not months_input:
    months_input = "12"

try:
    MONTHS = int(months_input)

    if MONTHS <= 0:
        raise ValueError

except ValueError:
    raise ValueError("Please enter a positive number of months.")


print(f"\nRequested history: {MONTHS} months")
print(f"Stocks: {len(STOCKS)}")
print("Resolution: 1 minute")


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
# DATABASE
# ==========================================

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()


# ==========================================
# DATE RANGE
# ==========================================

today = datetime.now().date()

# Requested start date
requested_from = today - timedelta(
    days=int(MONTHS * 30.4375)
)

# Don't store today's incomplete candle
requested_to = today


# ==========================================
# DOWNLOAD
# ==========================================

overall_start = time.time()

total_received = 0
total_inserted = 0
total_requests = 0


for stock_number, symbol in enumerate(STOCKS, start=1):

    stock_start = time.time()

    stock_name = symbol.split(":")[1].replace("-EQ", "")

    print("\n" + "=" * 60)
    print(
        f"[{stock_number}/{len(STOCKS)}] {stock_name}"
    )
    print("=" * 60)

    current_from = requested_from

    stock_received = 0
    stock_inserted = 0

    while current_from < requested_to:

        current_to = min(
            current_from + timedelta(days=CHUNK_DAYS),
            requested_to
        )

        range_from = current_from.strftime("%Y-%m-%d")
        range_to = current_to.strftime("%Y-%m-%d")

        request_number = total_requests + 1

        print(
            f"Request {request_number}: "
            f"{range_from} → {range_to}"
        )

        data = {
            "symbol": symbol,
            "resolution": RESOLUTION,
            "date_format": "1",
            "range_from": range_from,
            "range_to": range_to,
            "cont_flag": "1"
        }

        try:

            request_start = time.time()

            response = fyers.history(data=data)

            request_time = time.time() - request_start

            total_requests += 1

            if response.get("s") != "ok":

                print(
                    "  ERROR:",
                    response
                )

                current_from = current_to
                time.sleep(SLEEP_SECONDS)
                continue

            candles = response.get(
                "candles",
                []
            )

            received = len(candles)

            inserted = 0

            for candle in candles:

                candle_timestamp = datetime.fromtimestamp(
                    candle[0]
                )

                # ----------------------------------
                # Ignore today's incomplete candle
                # ----------------------------------

                if candle_timestamp.date() >= today:
                    continue

                timestamp = candle_timestamp.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

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
                        stock_name,
                        symbol,
                        timestamp,
                        candle[1],
                        candle[2],
                        candle[3],
                        candle[4],
                        candle[5]
                    )
                )

                if cursor.rowcount == 1:
                    inserted += 1

            conn.commit()

            stock_received += received
            stock_inserted += inserted

            total_received += received
            total_inserted += inserted

            print(
                f"  Candles: {received:,}"
                f" | New: {inserted:,}"
                f" | {request_time:.2f}s"
            )

        except Exception as e:

            print(
                f"  ERROR: {e}"
            )

        current_from = current_to

        time.sleep(SLEEP_SECONDS)

    stock_time = time.time() - stock_start

    print(
        f"\n{stock_name} COMPLETE"
    )

    print(
        f"Received : {stock_received:,}"
    )

    print(
        f"Inserted : {stock_inserted:,}"
    )

    print(
        f"Time     : {stock_time / 60:.2f} minutes"
    )


# ==========================================
# FINAL SUMMARY
# ==========================================

conn.close()

total_time = time.time() - overall_start

print("\n")
print("=" * 60)
print("DOWNLOAD COMPLETE")
print("=" * 60)

print(
    f"Stocks processed : {len(STOCKS)}"
)

print(
    f"API requests     : {total_requests:,}"
)

print(
    f"Candles received : {total_received:,}"
)

print(
    f"New candles      : {total_inserted:,}"
)

print(
    f"Total time       : {total_time / 60:.2f} minutes"
)

print(
    f"Total time       : {total_time / 3600:.2f} hours"
)

print("\nDatabase:")
print(DB_PATH)
