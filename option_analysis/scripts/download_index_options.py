from pathlib import Path
from datetime import datetime
import sys
import sqlite3
import time

import pandas as pd


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
# PATHS
# ============================================================

OPTION_DIR = PROJECT_ROOT / "option_analysis"

DB_PATH = (
    OPTION_DIR
    / "database"
    / "index_options.db"
)

MASTER_FILE = (
    OPTION_DIR
    / "database"
    / "index_option_contracts.csv"
)


# ============================================================
# SETTINGS
# ============================================================

START_DATE = "2026-09-01"
END_DATE = "2026-09-25"

NUMBER_OF_STRIKES = 10

SLEEP_SECONDS = 1

MAX_RETRIES = 3


# ============================================================
# TEST MODE
# ============================================================
#
# True:
#     Download only a small number of selected contracts.
#
# False:
#     Download all unique contracts selected by the
#     historical ATM ± 10 logic.
#
# ============================================================

TEST_MODE = False

TEST_CONTRACT_LIMIT = 5


# ============================================================
# INDEX SYMBOLS
# ============================================================

INDEX_SYMBOLS = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
}


# ============================================================
# FYERS CLIENT
# ============================================================

fyers = get_fyers_client()


# ============================================================
# LOAD CONTRACT MASTER
# ============================================================

def load_contract_master():

    if not MASTER_FILE.exists():

        raise FileNotFoundError(
            f"Contract master not found:\n{MASTER_FILE}"
        )

    df = pd.read_csv(
        MASTER_FILE
    )

    df["expiry"] = pd.to_datetime(
        df["expiry"]
    )

    return df


# ============================================================
# GET DAILY UNDERLYING DATA
# ============================================================

def get_daily_data(symbol):

    print()
    print(
        f"Getting underlying data: {symbol}"
    )

    response = fyers.history(
        data={
            "symbol": symbol,
            "resolution": "1",
            "date_format": "1",
            "range_from": START_DATE,
            "range_to": END_DATE,
            "cont_flag": "1",
        }
    )

    if response.get("s") != "ok":

        print(
            f"FYERS error for {symbol}:"
        )

        print(response)

        return pd.DataFrame()

    candles = response.get(
        "candles",
        []
    )

    if not candles:

        print(
            f"No candles returned for {symbol}"
        )

        return pd.DataFrame()

    df = pd.DataFrame(
        candles,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
    )

    df["datetime"] = pd.to_datetime(
        df["timestamp"],
        unit="s",
    )

    df["date"] = (
        df["datetime"]
        .dt
        .normalize()
    )

    daily = (
        df.groupby("date")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .reset_index()
    )

    return daily


# ============================================================
# FIND EXPIRY FOR TRADING DATE
# ============================================================

def find_expiry(
    master,
    index_name,
    trading_date,
):

    expiries = (
        master[
            master["index_name"]
            == index_name
        ]["expiry"]
        .drop_duplicates()
        .sort_values()
    )

    future_expiries = expiries[
        expiries >= trading_date
    ]

    if future_expiries.empty:

        return None

    return future_expiries.iloc[0]


# ============================================================
# FIND ATM AND SELECT ATM ± 10 STRIKES
# ============================================================

def select_contracts_for_day(
    master,
    index_name,
    expiry,
    close_price,
):

    contracts = master[
        (master["index_name"] == index_name)
        & (master["expiry"] == expiry)
    ].copy()

    if contracts.empty:

        return pd.DataFrame()

    strikes = sorted(
        contracts["strike"]
        .dropna()
        .unique()
    )

    if not strikes:

        return pd.DataFrame()

    # --------------------------------------------------------
    # Find nearest available strike to underlying close
    # --------------------------------------------------------

    atm = min(
        strikes,
        key=lambda strike: abs(
            strike - close_price
        )
    )

    atm_position = strikes.index(
        atm
    )

    start_position = max(
        0,
        atm_position - NUMBER_OF_STRIKES
    )

    end_position = min(
        len(strikes),
        atm_position
        + NUMBER_OF_STRIKES
        + 1
    )

    selected_strikes = strikes[
        start_position:end_position
    ]

    selected = contracts[
        contracts["strike"].isin(
            selected_strikes
        )
    ].copy()

    return selected


# ============================================================
# BUILD UNIQUE HISTORICAL CONTRACT LIST
# ============================================================

def build_required_contracts(
    master
):

    all_contracts = {}

    print()
    print("=" * 80)
    print("BUILDING HISTORICAL OPTION CONTRACT LIST")
    print("=" * 80)

    for index_name, symbol in INDEX_SYMBOLS.items():

        print()
        print(
            f"Processing {index_name}"
        )

        daily = get_daily_data(
            symbol
        )

        if daily.empty:

            print(
                f"No daily data for {index_name}"
            )

            continue

        index_contracts = {}

        for _, row in daily.iterrows():

            trading_date = row["date"]

            close_price = float(
                row["close"]
            )

            expiry = find_expiry(
                master,
                index_name,
                trading_date,
            )

            if expiry is None:

                print(
                    f"No expiry found for "
                    f"{index_name} "
                    f"{trading_date.date()}"
                )

                continue

            selected = (
                select_contracts_for_day(
                    master,
                    index_name,
                    expiry,
                    close_price,
                )
            )

            if selected.empty:

                continue

            # ------------------------------------------------
            # Save unique symbols
            # ------------------------------------------------

            for _, contract in selected.iterrows():

                symbol_name = contract[
                    "symbol"
                ]

                index_contracts[
                    symbol_name
                ] = contract

        print(
            f"{index_name:<12} "
            f"Trading days: "
            f"{len(daily):2d} | "
            f"Unique contracts: "
            f"{len(index_contracts):3d}"
        )

        all_contracts.update(
            index_contracts
        )

    contracts = list(
        all_contracts.values()
    )

    if not contracts:

        return pd.DataFrame()

    result = pd.DataFrame(
        contracts
    )

    result = (
        result
        .sort_values(
            [
                "index_name",
                "expiry",
                "strike",
                "option_type",
            ]
        )
        .reset_index(drop=True)
    )

    return result


# ============================================================
# GET LAST DOWNLOADED DATETIME
# ============================================================

def get_last_datetime(symbol):

    query = """
        SELECT MAX(datetime)
        FROM index_options_data
        WHERE symbol = ?
    """

    with sqlite3.connect(
        DB_PATH
    ) as conn:

        row = conn.execute(
            query,
            (symbol,)
        ).fetchone()

    return row[0]


# ============================================================
# INSERT CANDLES
# ============================================================

def insert_candles(
    contract,
    candles,
):

    if not candles:

        return 0

    rows = []

    expiry = (
        contract["expiry"]
        .strftime("%Y-%m-%d")
    )

    for candle in candles:

        # ----------------------------------------------------
        # Minimum expected fields:
        #
        # 0 timestamp
        # 1 open
        # 2 high
        # 3 low
        # 4 close
        # 5 volume
        #
        # Optional:
        #
        # 6 open interest
        # ----------------------------------------------------

        if len(candle) < 6:

            print(
                "Skipping malformed candle:"
            )

            print(candle)

            continue

        timestamp = int(
            candle[0]
        )

        dt = datetime.fromtimestamp(
            timestamp
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        volume = (
            float(candle[5])
            if candle[5] is not None
            else None
        )

        # ----------------------------------------------------
        # OI may or may not be present
        # ----------------------------------------------------

        if len(candle) >= 7:

            open_interest = (
                float(candle[6])
                if candle[6] is not None
                else None
            )

        else:

            open_interest = None

        rows.append(
            (
                contract["index_name"],
                contract["symbol"],
                contract["option_type"],
                float(contract["strike"]),
                expiry,
                dt,
                float(candle[1]),
                float(candle[2]),
                float(candle[3]),
                float(candle[4]),
                volume,
                open_interest,
            )
        )

    if not rows:

        return 0

    query = """
        INSERT OR IGNORE INTO index_options_data
        (
            index_name,
            symbol,
            option_type,
            strike,
            expiry,
            datetime,
            open,
            high,
            low,
            close,
            volume,
            open_interest
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    with sqlite3.connect(
        DB_PATH
    ) as conn:

        cursor = conn.executemany(
            query,
            rows
        )

        conn.commit()

        return cursor.rowcount


# ============================================================
# DOWNLOAD ONE CONTRACT
# ============================================================

def download_contract(
    contract
):

    symbol = contract["symbol"]

    expiry = contract["expiry"]

    print()
    print("-" * 80)

    print(
        f"Index      : "
        f"{contract['index_name']}"
    )

    print(
        f"Symbol     : "
        f"{symbol}"
    )

    print(
        f"Option     : "
        f"{contract['option_type']}"
    )

    print(
        f"Strike     : "
        f"{contract['strike']}"
    )

    print(
        f"Expiry     : "
        f"{expiry.date()}"
    )

    # --------------------------------------------------------
    # Resume point
    # --------------------------------------------------------

    last_datetime = get_last_datetime(
        symbol
    )

    if last_datetime:

        start = (
            pd.Timestamp(
                last_datetime
            )
            + pd.Timedelta(
                minutes=1
            )
        )

        print(
            f"Resume from : {start}"
        )

    else:

        start = pd.Timestamp(START_DATE)

        print(
            f"Starting from: {start}"
        )
        
    end = pd.Timestamp(END_DATE) + pd.Timedelta(days=1)

    if start >= end:

        print(
            "Already downloaded."
        )

        return 0

    total_received = 0

    total_inserted = 0

    # --------------------------------------------------------
    # Download in batches
    # --------------------------------------------------------

    while start < end:

        batch_end = min(
            start
            + pd.Timedelta(days=30),
            end,
        )

        range_from = (
            start.strftime(
                "%Y-%m-%d"
            )
        )
        
        request_end = min(
            batch_end,
            pd.Timestamp(END_DATE)
        )

        range_to = (
            request_end.strftime(
                "%Y-%m-%d"
            )
        )

        print()
        print(
            f"Request: "
            f"{range_from} -> {range_to}"
        )

        data = {
            "symbol": symbol,
            "resolution": "1",
            "date_format": "1",
            "range_from": range_from,
            "range_to": range_to,
            "cont_flag": "0",
            "oi_flag": "1",
        }

        response = None

        # ----------------------------------------------------
        # Retry
        # ----------------------------------------------------

        for attempt in range(
            1,
            MAX_RETRIES + 1
        ):

            try:

                response = fyers.history(
                    data=data
                )

            except Exception as exc:

                print(
                    f"API exception "
                    f"(attempt "
                    f"{attempt}/"
                    f"{MAX_RETRIES}): "
                    f"{exc}"
                )

                if attempt < MAX_RETRIES:

                    time.sleep(
                        SLEEP_SECONDS
                    )

                continue

            if response.get(
                "s"
            ) == "ok":

                break

            if response.get(
                "s"
            ) == "no_data":

                print(
                    "FYERS returned no_data."
                )

                return 0

            print(
                f"FYERS error "
                f"(attempt "
                f"{attempt}/"
                f"{MAX_RETRIES})"
            )

            print(response)

            if attempt < MAX_RETRIES:

                time.sleep(
                    SLEEP_SECONDS
                )

        # ----------------------------------------------------
        # Failed completely
        # ----------------------------------------------------

        if response is None:

            print(
                "No response after retries."
            )

            return total_inserted

        if response.get(
            "s"
        ) != "ok":

            print(
                "Contract skipped after "
                "maximum retries."
            )

            return total_inserted

        candles = response.get(
            "candles",
            []
        )

        if not candles:

            print(
                "No candles returned."
            )

            return total_inserted

        inserted = insert_candles(
            contract,
            candles
        )

        total_received += len(
            candles
        )

        total_inserted += inserted

        print(
            f"Candles received : "
            f"{len(candles):,}"
        )

        print(
            f"Rows inserted    : "
            f"{inserted:,}"
        )

        # ----------------------------------------------------
        # Move to next batch
        # ----------------------------------------------------

        start = batch_end

        time.sleep(
            SLEEP_SECONDS
        )

    print()
    print(
        f"Total candles received: "
        f"{total_received:,}"
    )

    print(
        f"Total rows inserted   : "
        f"{total_inserted:,}"
    )

    return total_inserted


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 80)
    print("INDEX OPTIONS DOWNLOADER")
    print("=" * 80)

    print(
        f"Period    : "
        f"{START_DATE} -> {END_DATE}"
    )

    print(
        f"ATM range : "
        f"±{NUMBER_OF_STRIKES} strikes"
    )

    print(
        f"TEST_MODE : "
        f"{TEST_MODE}"
    )

    # --------------------------------------------------------
    # Load master
    # --------------------------------------------------------

    master = load_contract_master()

    print()
    print(
        f"Master contracts: "
        f"{len(master):,}"
    )

    # --------------------------------------------------------
    # Build historical contract list
    # --------------------------------------------------------

    contracts = build_required_contracts(
        master
    )

    if contracts.empty:

        print(
            "No contracts selected."
        )

        return

    print()
    print("=" * 80)
    print(
        f"TOTAL UNIQUE CONTRACTS: "
        f"{len(contracts):,}"
    )
    print("=" * 80)

    # --------------------------------------------------------
    # TEST MODE
    # --------------------------------------------------------

    if TEST_MODE:

        contracts = contracts.head(
            TEST_CONTRACT_LIMIT
        ).copy()

        print()
        print("=" * 80)
        print(
            f"TEST MODE - ONLY "
            f"{len(contracts)} CONTRACTS"
        )
        print("=" * 80)

    # --------------------------------------------------------
    # Display selected contracts
    # --------------------------------------------------------

    print()

    print(
        contracts[
            [
                "index_name",
                "symbol",
                "option_type",
                "strike",
                "expiry",
            ]
        ].to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

    print()
    print("=" * 80)

    print(
        f"Starting download of "
        f"{len(contracts)} contract(s)..."
    )

    print("=" * 80)

    total_inserted = 0

    for position, (_, contract) in enumerate(
        contracts.iterrows(),
        start=1,
    ):

        print()
        print(
            "=" * 80
        )

        print(
            f"PROGRESS: "
            f"{position}/{len(contracts)}"
        )

        print(
            "=" * 80
        )

        inserted = download_contract(
            contract
        )

        total_inserted += inserted

    # --------------------------------------------------------
    # Finished
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("DOWNLOAD FINISHED")
    print("=" * 80)

    print(
        f"Total rows inserted: "
        f"{total_inserted:,}"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()