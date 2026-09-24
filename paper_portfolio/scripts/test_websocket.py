import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fyers_apiv3.FyersWebsocket import data_ws


# ============================================================
# PATHS
# ============================================================

ROOT_DIR = Path("/home/manish/trading_project")

ENV_FILE = ROOT_DIR / ".env"
ACCESS_FILE = ROOT_DIR / "access.txt"


# ============================================================
# LOAD CREDENTIALS
# ============================================================

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


# ============================================================
# SYMBOLS
# ============================================================

SYMBOLS = [
    "NSE:AEGISVOPAK-EQ",
    "NSE:GOODLUCK-EQ",
]


# ============================================================
# CALLBACKS
# ============================================================

def on_message(message):
    print()
    print("=" * 80)
    print("LIVE TICK")
    print("=" * 80)
    print(message)


def on_error(message):
    print()
    print("WEBSOCKET ERROR:")
    print(message)


def on_close(message):
    print()
    print("WEBSOCKET CLOSED:")
    print(message)


def on_open():
    print()
    print("=" * 80)
    print("WEBSOCKET CONNECTED")
    print("=" * 80)

    print("Subscribing to:")
    for symbol in SYMBOLS:
        print("  ", symbol)

    socket.subscribe(
        symbols=SYMBOLS,
        data_type="SymbolUpdate",
    )


# ============================================================
# CREATE SOCKET
# ============================================================

socket = data_ws.FyersDataSocket(
    access_token=f"{APP_ID}:{ACCESS_TOKEN}",
    log_path="",
    litemode=False,
    write_to_file=False,
    reconnect=True,
    on_connect=on_open,
    on_close=on_close,
    on_error=on_error,
    on_message=on_message,
)


# ============================================================
# CONNECT
# ============================================================

print("=" * 80)
print("FYERS WEBSOCKET TEST")
print("=" * 80)
print("Symbols:", ", ".join(SYMBOLS))
print("Test duration: 20 seconds")
print("=" * 80)

socket.connect()


# ============================================================
# RUN FOR 20 SECONDS
# ============================================================

time.sleep(20)


# ============================================================
# CLOSE
# ============================================================

print()
print("=" * 80)
print("20 SECONDS COMPLETED")
print("Closing WebSocket...")
print("=" * 80)

socket.close_connection()

print("Test finished.")
