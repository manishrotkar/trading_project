import os
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from fyers_apiv3 import fyersModel


# ==========================================
# PATHS
# ==========================================

PROJECT_DIR = Path("/home/manish/trading_project/stock_screener")
ROOT_DIR = Path("/home/manish/trading_project")

ENV_FILE = ROOT_DIR / ".env"
ACCESS_FILE = ROOT_DIR / "access.txt"


# ==========================================
# LOAD FYERS CREDENTIALS
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
# TEST PARAMETERS
# ==========================================

SYMBOL = "NSE:SBIN-EQ"
RESOLUTION = "1"

# Small test period
FROM_DATE = "2026-09-01"
TO_DATE = "2026-09-02"


# ==========================================
# FYERS HISTORY REQUEST
# ==========================================

data = {
    "symbol": SYMBOL,
    "resolution": RESOLUTION,
    "date_format": "1",
    "range_from": FROM_DATE,
    "range_to": TO_DATE,
    "cont_flag": "1"
}

response = fyers.history(data=data)


# ==========================================
# DISPLAY RESULT
# ==========================================

print("==========================================")
print("FYERS HISTORY API TEST")
print("==========================================")
print("Symbol    :", SYMBOL)
print("Resolution:", RESOLUTION, "minute")
print("From      :", FROM_DATE)
print("To        :", TO_DATE)
print()

print("Response status:", response.get("s"))

if response.get("s") != "ok":
    print("ERROR:")
    print(response)
else:

    candles = response.get("candles", [])

    print("Candles received:", len(candles))
    print()

    if candles:

        print("First candle:")
        print(candles[0])

        print()
        print("Last candle:")
        print(candles[-1])

        print()
        print("Sample candles:")

        for candle in candles[:5]:
            timestamp = datetime.fromtimestamp(candle[0])
            print(
                timestamp,
                "O:", candle[1],
                "H:", candle[2],
                "L:", candle[3],
                "C:", candle[4],
                "V:", candle[5]
            )
