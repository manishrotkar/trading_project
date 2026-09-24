import io
import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo


# --------------------------------------------------
# FYERS symbol master
# --------------------------------------------------

SYMBOL_MASTER_URL = "https://public.fyers.in/sym_details/NSE_FO.csv"


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print("=" * 70)
    print("NIFTY FUTURES — CURRENT / NEXT / FAR")
    print("=" * 70)

    print("\nDownloading FYERS NSE Futures symbol master...")

    response = requests.get(
        SYMBOL_MASTER_URL,
        timeout=30
    )

    response.raise_for_status()

    df = pd.read_csv(
        io.BytesIO(response.content),
        header=None,
        low_memory=False
    )

    print(f"Total symbol-master rows: {len(df):,}")

    # --------------------------------------------------
    # NIFTY INDEX FUTURES ONLY
    #
    # Column 2  = Instrument type
    #             11 = Futures
    #
    # Column 13 = Underlying
    #             NIFTY
    # --------------------------------------------------

    nifty_futures = df[
        (df[2] == 11) &
        (df[13].astype(str).str.upper() == "NIFTY")
    ].copy()

    print(
        f"NIFTY index futures found: "
        f"{len(nifty_futures)}"
    )

    # --------------------------------------------------
    # Convert expiry timestamp to IST date
    #
    # Column 8 = expiry timestamp
    # Column 9 = FYERS trading symbol
    # --------------------------------------------------

    nifty_futures["expiry_date"] = nifty_futures[8].apply(
        lambda x: datetime.fromtimestamp(
            int(x),
            tz=ZoneInfo("Asia/Kolkata")
        ).date()
    )

    # --------------------------------------------------
    # Sort by actual expiry
    # --------------------------------------------------

    nifty_futures = nifty_futures.sort_values(
        "expiry_date"
    ).reset_index(drop=True)

    # --------------------------------------------------
    # CURRENT / NEXT / FAR
    # --------------------------------------------------

    labels = [
        "CURRENT",
        "NEXT",
        "FAR"
    ]

    print()

    for position, label in enumerate(labels):

        if position >= len(nifty_futures):
            break

        row = nifty_futures.iloc[position]

        print(label)
        print(f"  Contract : {row[1]}")
        print(f"  Symbol   : {row[9]}")
        print(f"  Expiry   : {row['expiry_date']}")
        print(f"  Lot size : {row[3]}")
        print()


if __name__ == "__main__":
    main()