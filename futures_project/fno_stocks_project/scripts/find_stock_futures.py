import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

URL = "https://public.fyers.in/sym_details/NSE_FO.csv"

IST = ZoneInfo("Asia/Kolkata")
today = datetime.now(IST).date()

print("Downloading FYERS NSE F&O symbol master...")
df = pd.read_csv(URL, header=None)

# Stock FUTURES only
futures = df[df[2] == 13].copy()

# Expiry date
futures["expiry_date"] = pd.to_datetime(
    futures[8],
    unit="s",
    errors="coerce"
).dt.date

# Keep non-expired contracts
futures = futures[
    futures["expiry_date"].notna() &
    (futures["expiry_date"] >= today)
].copy()

# Sort by stock and expiry
futures = futures.sort_values(
    [13, "expiry_date"]
)

print()
print("Today:", today)
print("Active stock futures contracts:", len(futures))

print()
print("=" * 100)
print("CURRENT / NEXT / FAR STOCK FUTURES")
print("=" * 100)

total_stocks = 0

for stock, group in futures.groupby(13):

    group = (
        group
        .drop_duplicates(subset=["expiry_date"])
        .sort_values("expiry_date")
    )

    contracts = group.head(3)

    if len(contracts) == 0:
        continue

    print()
    print(stock)

    labels = ["CURRENT", "NEXT", "FAR"]

    for label, (_, row) in zip(labels, contracts.iterrows()):
        print(
            f"  {label:<8} | "
            f"{row[9]:<35} | "
            f"Expiry {row['expiry_date']} | "
            f"Lot {row[3]}"
        )

    total_stocks += 1

print()
print("=" * 100)
print("Total stocks:", total_stocks)
print("=" * 100)
