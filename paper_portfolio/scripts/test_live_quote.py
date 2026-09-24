import os
from pathlib import Path

from dotenv import load_dotenv
from fyers_apiv3 import fyersModel


ROOT_DIR = Path("/home/manish/trading_project")

ENV_FILE = ROOT_DIR / ".env"
ACCESS_FILE = ROOT_DIR / "access.txt"


# ------------------------------------------------------------
# LOAD CREDENTIALS
# ------------------------------------------------------------

load_dotenv(ENV_FILE)

APP_ID = os.getenv("FYERS_APP_ID")

if not APP_ID:
    raise RuntimeError(
        f"FYERS_APP_ID not found in {ENV_FILE}"
    )


if not ACCESS_FILE.exists():
    raise FileNotFoundError(
        f"Access token file not found: {ACCESS_FILE}"
    )


ACCESS_TOKEN = ACCESS_FILE.read_text().strip()

if not ACCESS_TOKEN:
    raise RuntimeError("Access token file is empty.")


# ------------------------------------------------------------
# FYERS CONNECTION
# ------------------------------------------------------------

fyers = fyersModel.FyersModel(
    client_id=APP_ID,
    token=ACCESS_TOKEN,
    log_path=""
)


# ------------------------------------------------------------
# TEST SYMBOL
# ------------------------------------------------------------

symbol = "NSE:AEGISVOPAK-EQ"


# ------------------------------------------------------------
# LIVE QUOTE
# ------------------------------------------------------------

data = {
    "symbols": symbol
}

response = fyers.quotes(data=data)


print("=" * 70)
print("FYERS LIVE QUOTE TEST")
print("=" * 70)

print("Symbol   :", symbol)
print("Response :", response)

print("=" * 70)
