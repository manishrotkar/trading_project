from pathlib import Path
import sys


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
# FYERS CLIENT
# ============================================================

fyers = get_fyers_client()


# ============================================================
# TEST SYMBOLS
# ============================================================

OPTION_SYMBOL = "NSE:NIFTY26SEP25000CE"
INDEX_SYMBOL = "NSE:NIFTY50-INDEX"


# ============================================================
# DATE RANGE
# ============================================================

START_DATE = "2026-09-01"
END_DATE = "2026-09-24"


# ============================================================
# HISTORY FUNCTION
# ============================================================

def get_history(symbol):

    data = {
        "symbol": symbol,
        "resolution": "1",
        "date_format": "1",
        "range_from": START_DATE,
        "range_to": END_DATE,
        "cont_flag": "0",
        "oi_flag": "1",
    }

    return fyers.history(data=data)


# ============================================================
# OPTION TEST
# ============================================================

print("=" * 60)
print("OPTION HISTORY TEST")
print("=" * 60)

option_response = get_history(OPTION_SYMBOL)

print("Symbol:", OPTION_SYMBOL)
print("Response:", option_response.get("s"))
print("Message:", option_response.get("message"))

option_candles = option_response.get("candles", [])

print("Candles:", len(option_candles))

if option_candles:
    print("First candle:", option_candles[0])
    print("Last candle:", option_candles[-1])


# ============================================================
# UNDERLYING INDEX TEST
# ============================================================

print()
print("=" * 60)
print("UNDERLYING INDEX HISTORY TEST")
print("=" * 60)

index_response = get_history(INDEX_SYMBOL)

print("Symbol:", INDEX_SYMBOL)
print("Response:", index_response.get("s"))
print("Message:", index_response.get("message"))

index_candles = index_response.get("candles", [])

print("Candles:", len(index_candles))

if index_candles:
    print("First candle:", index_candles[0])
    print("Last candle:", index_candles[-1])
