import pandas as pd

from core.fyers_client import get_fyers_client


# ========================================================
# CONFIGURATION
# ========================================================

MASTER_FILE = (
    "option_analysis/database/index_option_contracts.csv"
)

START_DATE = "2026-09-01"
END_DATE = "2026-09-25"

NUMBER_OF_STRIKES = 10


INDEX_SYMBOLS = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
    "FINNIFTY": "NSE:FINNIFTY-INDEX",
    "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
    "NIFTYNXT50": "NSE:NIFTYNXT50-INDEX",
    "NIFTYFPI": "NSE:NIFTYFPI150-INDEX",
}


# ========================================================
# LOAD CONTRACT MASTER
# ========================================================

master = pd.read_csv(MASTER_FILE)

master["expiry"] = pd.to_datetime(
    master["expiry"]
)


# ========================================================
# FYERS CLIENT
# ========================================================

fyers = get_fyers_client()


# ========================================================
# GET DAILY UNDERLYING DATA
# ========================================================

def get_daily_data(symbol):

    data = fyers.history(
        {
            "symbol": symbol,
            "resolution": "1",
            "date_format": "1",
            "range_from": START_DATE,
            "range_to": END_DATE,
            "cont_flag": "1",
        }
    )

    if data.get("s") != "ok":
        print(
            f"ERROR getting {symbol}: "
            f"{data}"
        )
        return pd.DataFrame()

    candles = data.get(
        "candles",
        []
    )

    if not candles:
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
        df["datetime"].dt.normalize()
    )

    daily = (
        df.groupby("date")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
        )
        .reset_index()
    )

    return daily


# ========================================================
# FIND EXPIRY
# ========================================================

def find_expiry(
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


# ========================================================
# FIND ATM
# ========================================================

def find_atm(
    index_name,
    expiry,
    close_price,
):

    contracts = master[
        (master["index_name"] == index_name)
        &
        (master["expiry"] == expiry)
    ]

    if contracts.empty:
        return None, []

    strikes = sorted(
        contracts["strike"]
        .dropna()
        .unique()
    )

    atm = min(
        strikes,
        key=lambda strike:
        abs(strike - close_price)
    )

    atm_position = strikes.index(atm)

    start_position = max(
        0,
        atm_position - NUMBER_OF_STRIKES,
    )

    end_position = min(
        len(strikes),
        atm_position
        + NUMBER_OF_STRIKES
        + 1,
    )

    selected_strikes = strikes[
        start_position:end_position
    ]

    return atm, selected_strikes


# ========================================================
# MAIN TEST
# ========================================================

print()
print("=" * 80)
print("ALL 6 INDEX DAILY SELECTION TEST")
print("=" * 80)


for index_name, symbol in INDEX_SYMBOLS.items():

    print()
    print("=" * 80)
    print(index_name)
    print(symbol)
    print("=" * 80)

    daily = get_daily_data(symbol)

    if daily.empty:
        print("No data.")
        continue

    print(
        f"Trading days: {len(daily)}"
    )

    print()

    for _, row in daily.iterrows():

        trading_date = row["date"]
        close_price = row["close"]

        expiry = find_expiry(
            index_name,
            trading_date,
        )

        if expiry is None:
            print(
                f"{trading_date.date()} "
                f"NO EXPIRY"
            )
            continue

        atm, selected_strikes = find_atm(
            index_name,
            expiry,
            close_price,
        )

        if atm is None:
            print(
                f"{trading_date.date()} "
                f"NO CONTRACTS"
            )
            continue

        contract_count = (
            len(selected_strikes) * 2
        )

        print(
            f"{trading_date.date()} | "
            f"Close: {close_price:,.2f} | "
            f"Expiry: {expiry.date()} | "
            f"ATM: {atm:,.0f} | "
            f"Strikes: {len(selected_strikes)} | "
            f"Contracts: {contract_count}"
        )


print()
print("=" * 80)
print("TEST FINISHED")
print("=" * 80)
