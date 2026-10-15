
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path.home() / "trading_project"
load_dotenv(PROJECT_ROOT / ".env")

APP_ID = os.getenv("FYERS_APP_ID", "").strip()
TOKEN_FILE = PROJECT_ROOT / "access.txt"

if not APP_ID:
    raise SystemExit("FYERS_APP_ID is missing from .env")

if not TOKEN_FILE.is_file():
    raise SystemExit(f"Token file not found: {TOKEN_FILE}")

ACCESS_TOKEN = TOKEN_FILE.read_text().strip()

if not ACCESS_TOKEN:
    raise SystemExit("access.txt is empty")

# FYERS v3 option-chain endpoint
url = "https://api-t1.fyers.in/data/options-chain-v3"

headers = {
    "Authorization": f"{APP_ID}:{ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

params = {
    "symbol": "NSE:RELIANCE-EQ",
    "strikecount": 10,
    "timestamp": "",
}

print("Testing FYERS stock option-chain API...")
print("Symbol: NSE:RELIANCE-EQ")

try:
    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30,
    )

    print("HTTP status:", response.status_code)

    try:
        data = response.json()
    except ValueError:
        print("Response is not JSON.")
        print("Response preview:", response.text[:500])
        raise SystemExit(1)

    print("FYERS API status:", data.get("s", "not provided"))
    print("FYERS message:", data.get("message", "not provided"))

    if response.status_code != 200 or data.get("s") != "ok":
        print("Option-chain request was not successful.")
        print("Response keys:", list(data.keys()))
        raise SystemExit(1)

    chain = data.get("data", {})
    if not isinstance(chain, dict):
        print("Unexpected data structure:", type(chain).__name__)
        raise SystemExit(1)

    options = chain.get("optionsChain", [])
    print("Response data keys:", list(chain.keys()))
    print("Returned option records:", len(options))

    if options:
        print("First record keys:", list(options[0].keys()))
        print("Sample record (selected fields only):")
        first = options[0]
        for key in (
            "symbol", "strike_price", "option_type",
            "ltp", "oi", "volume", "iv", "fp"
        ):
            if key in first:
                print(f"  {key}: {first[key]}")

        print("\nSUCCESS: FYERS returned option-chain records.")
    else:
        print("No option records found. Check the response structure.")

except requests.RequestException as exc:
    print("Network/request error:", type(exc).__name__, str(exc))
