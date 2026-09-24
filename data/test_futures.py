from core.fyers_client import get_fyers_client


fyers = get_fyers_client()

data = {
    "symbol": "NSE:NIFTY26SEPFUT",
    "resolution": "1",
    "date_format": "1",
    "range_from": "2026-09-01",
    "range_to": "2026-09-02",
    "cont_flag": "1",
}

response = fyers.history(data=data)

print("Status:", response.get("s"))
print("Code:", response.get("code"))

candles = response.get("candles", [])

print("Candles:", len(candles))

if candles:
    print("\nFirst candle:")
    print(candles[0])

    print("\nLast candle:")
    print(candles[-1])