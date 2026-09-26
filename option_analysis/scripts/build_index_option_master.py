import pandas as pd
from pathlib import Path

SYMBOL_MASTER_URL = "https://public.fyers.in/sym_details/NSE_FO.csv"

PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_FILE = PROJECT_DIR / "database" / "index_option_contracts.csv"

INDEXES = [
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "NIFTYNXT50",
    "NIFTYFPI",
]

def main():
    print("Downloading FYERS NSE FO symbol master...")

    df = pd.read_csv(
        SYMBOL_MASTER_URL,
        header=None
    )

    print(f"Total symbol-master rows: {len(df):,}")

    # Option instruments only
    options = df[df[2].isin([14, 15])].copy()

    # Our six index options
    options = options[options[13].isin(INDEXES)].copy()

    # Convert expiry timestamp
    options["expiry"] = pd.to_datetime(
        options[8],
        unit="s"
    ).dt.strftime("%Y-%m-%d")

    # Build clean contract master
    master = pd.DataFrame({
        "index_name": options[13],
        "symbol": options[9],
        "option_type": options[16],
        "strike": options[15],
        "expiry": options["expiry"],
        "lot_size": options[3],
        "instrument_type": options[2],
    })

    # Remove accidental duplicates
    master = master.drop_duplicates()

    # Sort
    master = master.sort_values(
        ["index_name", "expiry", "strike", "option_type"]
    ).reset_index(drop=True)

    # Save
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    master.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print()
    print("Index option contract master created.")
    print(f"File: {OUTPUT_FILE}")
    print(f"Contracts: {len(master):,}")

    print()
    print("Contracts by index:")
    print(
        master.groupby("index_name")
        .size()
        .sort_values(ascending=False)
        .to_string()
    )

    print()
    print("Contracts by expiry:")
    print(
        master.groupby(["index_name", "expiry"])
        .size()
        .to_string()
    )


if __name__ == "__main__":
    main()
