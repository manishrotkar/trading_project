import pandas as pd

CSV = "/home/manish/trading_project/stock_screener/notebooks/above_price_scanner_results.csv"

df = pd.read_csv(CSV)

print("Columns:", df.columns.tolist())

symbols = df["Symbol"].dropna().astype(str).str.strip().drop_duplicates().tolist()

print(f"\nTotal unique symbols: {len(symbols)}")

for i, symbol in enumerate(symbols, 1):
    print(f"{i:3}. {symbol}")
