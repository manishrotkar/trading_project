import io
import zipfile
import requests
import pandas as pd


SYMBOL_MASTER_URL = (
    "https://public.fyers.in/sym_details/NSE_FO.csv"
)


def main():
    print("Downloading FYERS NSE Futures symbol master...")

    response = requests.get(SYMBOL_MASTER_URL, timeout=30)
    response.raise_for_status()

    df = pd.read_csv(
        io.BytesIO(response.content),
        header=None,
        low_memory=False,
    )

    print(f"Rows downloaded: {len(df):,}")

    # Display column names so we can inspect FYERS's current format
    print("\nColumns:")
    for i, column in enumerate(df.columns):
        print(f"{i}: {column}")

    # Search every column for NIFTY
    mask = df.astype(str).apply(
        lambda column: column.str.contains(
            "NIFTY",
            case=False,
            na=False,
        )
    ).any(axis=1)

    nifty = df[mask].copy()

    print(f"\nNIFTY-related rows found: {len(nifty):,}")

    print("\nFirst 30 NIFTY rows:")
    print(nifty.head(30).to_string(index=False))


if __name__ == "__main__":
    main()