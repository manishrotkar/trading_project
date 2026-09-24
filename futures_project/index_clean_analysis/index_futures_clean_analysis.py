# ============================================================
# INDEX FUTURES CLEAN ANALYSIS
# ============================================================
#
# Database:
#   ../database/futures.db
#
# Features:
#   - Automatic index selection
#   - Current / Next / Far contract selection
#   - Current + Next + Far cumulative analysis
#   - Interactive timeframe selection
#   - OHLC resampling
#   - Volume analysis
#   - Open Interest analysis
#   - Price/OI buildup classification
#   - Next-period historical probability analysis
#
# No chart / dashboard.
# Raw database is NOT modified.
# ============================================================


# ============================================================
# IMPORTS
# ============================================================

import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_DIR / "database" / "futures.db"


# ============================================================
# SETTINGS
# ============================================================

TIMEFRAMES = [
    "5min",
    "15min",
    "30min",
    "1h",
    "4h",
    "1D",
    "1W",
]

TIMEFRAME_NAMES = {
    "5min": "5 Minute",
    "15min": "15 Minute",
    "30min": "30 Minute",
    "1h": "1 Hour",
    "4h": "4 Hour",
    "1D": "Daily",
    "1W": "Weekly",
}

CONTRACT_OPTIONS = [
    "CURRENT",
    "NEXT",
    "FAR",
    "CURRENT + NEXT + FAR",
]

AVAILABLE_INDEX_ORDER = [
    "BANKEX",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "NIFTY",
    "NIFTYFPI",
    "NIFTYNXT50",
    "SENSEX",
]

PROBABILITY_THRESHOLDS = {
    "5min": 0.15,
    "15min": 0.25,
    "30min": 0.35,
    "1h": 0.50,
    "4h": 0.75,
    "1D": 0.50,
    "1W": 1.00,
}

IST = ZoneInfo("Asia/Kolkata")


# ============================================================
# DATABASE CHECK
# ============================================================

if not DB_PATH.exists():
    raise FileNotFoundError(
        f"Database not found:\n{DB_PATH}"
    )


print("=" * 70)
print("INDEX FUTURES CLEAN ANALYSIS")
print("=" * 70)

print(
    f"Database : {DB_PATH}"
)

print(
    f"Database size : "
    f"{DB_PATH.stat().st_size / (1024 ** 2):.2f} MB"
)


# ============================================================
# LOAD DATABASE
# ============================================================

print()
print("Loading database...")

query = """
SELECT
    symbol,
    contract,
    expiry,
    datetime,
    open,
    high,
    low,
    close,
    volume,
    open_interest
FROM futures_data
"""

with sqlite3.connect(DB_PATH) as conn:
    df = pd.read_sql_query(query, conn)

print(
    f"Rows loaded : {len(df):,}"
)


# ============================================================
# BASIC DATA PREPARATION
# ============================================================

df["datetime"] = pd.to_datetime(
    df["datetime"]
)

df["expiry"] = pd.to_datetime(
    df["expiry"]
).dt.date

df = (
    df
    .drop_duplicates(
        subset=[
            "symbol",
            "contract",
            "expiry",
            "datetime",
        ]
    )
    .sort_values(
        [
            "symbol",
            "contract",
            "datetime",
        ]
    )
    .reset_index(drop=True)
)


# ============================================================
# DATABASE SUMMARY
# ============================================================

print()
print("=" * 70)
print("DATABASE SUMMARY")
print("=" * 70)

print(
    f"Total rows     : "
    f"{len(df):,}"
)

print(
    f"Total contracts: "
    f"{df['symbol'].nunique()}"
)

print(
    f"Total indices  : "
    f"{len(AVAILABLE_INDEX_ORDER)}"
)

print()
print("Date range:")

print(
    f"From : {df['datetime'].min()}"
)

print(
    f"To   : {df['datetime'].max()}"
)


# ============================================================
# INDEX SELECTION
# ============================================================

available_indices = [
    index_name
    for index_name in AVAILABLE_INDEX_ORDER
    if df["contract"]
    .astype(str)
    .str.upper()
    .str.startswith(index_name + " ")
    .any()
]

if not available_indices:
    raise ValueError(
        "No valid index futures found in database."
    )

print()
print("=" * 70)
print("AVAILABLE INDICES")
print("=" * 70)

for number, index_name in enumerate(
    available_indices,
    start=1,
):
    print(
        f"{number}. {index_name}"
    )

while True:
    index_input = input(
        "\nSelect index (1-"
        f"{len(available_indices)}"
        "): "
    ).strip()

    try:
        index_number = int(index_input)

        if 1 <= index_number <= len(available_indices):
            break

    except ValueError:
        pass

    print("Invalid selection.")

INDEX = available_indices[index_number - 1]


# ============================================================
# TIMEFRAME SELECTION
# ============================================================

print()
print("=" * 70)
print("TIMEFRAME")
print("=" * 70)

for number, timeframe in enumerate(
    TIMEFRAMES,
    start=1,
):
    print(
        f"{number}. "
        f"{timeframe} "
        f"({TIMEFRAME_NAMES[timeframe]})"
    )

while True:
    timeframe_input = input(
        "\nSelect timeframe (1-7): "
    ).strip()

    try:
        timeframe_number = int(timeframe_input)

        if 1 <= timeframe_number <= len(TIMEFRAMES):
            break

    except ValueError:
        pass

    print("Invalid timeframe.")

TIMEFRAME = TIMEFRAMES[timeframe_number - 1]


# ============================================================
# CONTRACT SELECTION
# ============================================================

print()
print("=" * 70)
print("CONTRACT")
print("=" * 70)

for number, option in enumerate(
    CONTRACT_OPTIONS,
    start=1,
):
    print(
        f"{number}. {option}"
    )

while True:
    contract_input = input(
        "\nSelect contract (1-4): "
    ).strip()

    try:
        contract_number = int(contract_input)

        if 1 <= contract_number <= len(CONTRACT_OPTIONS):
            break

    except ValueError:
        pass

    print("Invalid contract selection.")

CONTRACT = CONTRACT_OPTIONS[contract_number - 1]


# ============================================================
# CURRENT DATE
# ============================================================

today = datetime.now(IST).date()


# ============================================================
# FIND CONTRACTS FOR SELECTED INDEX
# ============================================================

index_mask = (
    df["contract"]
    .astype(str)
    .str.upper()
    .str.startswith(
        INDEX.upper() + " "
    )
)

index_contracts = (
    df.loc[
        index_mask,
        [
            "symbol",
            "contract",
            "expiry",
        ],
    ]
    .drop_duplicates()
    .copy()
)

if index_contracts.empty:
    raise ValueError(
        f"No contracts found for {INDEX}."
    )


# ============================================================
# EXPIRY DATE
# ============================================================

index_contracts["expiry_date"] = (
    pd.to_datetime(
        index_contracts["expiry"]
    ).dt.date
)


# ============================================================
# ACTIVE CONTRACTS
# ============================================================

active_contracts = (
    index_contracts[
        index_contracts["expiry_date"] >= today
    ]
    .sort_values("expiry_date")
    .reset_index(drop=True)
)

if active_contracts.empty:
    raise ValueError(
        f"No active contracts available for {INDEX}."
    )


# ============================================================
# DISPLAY ACTIVE CONTRACTS
# ============================================================

print()
print("=" * 70)
print("ACTIVE CONTRACTS")
print("=" * 70)

for number, row in active_contracts.iterrows():

    if number == 0:
        position_name = "CURRENT"
    elif number == 1:
        position_name = "NEXT"
    elif number == 2:
        position_name = "FAR"
    else:
        position_name = ""

    print(
        f"{number + 1}. "
        f"{position_name:<8} | "
        f"{row['contract']} | "
        f"{row['symbol']} | "
        f"Expiry: {row['expiry_date']}"
    )


# ============================================================
# CONTRACT REQUIREMENTS
# ============================================================

if CONTRACT == "CURRENT":
    required_contracts = 1
elif CONTRACT == "NEXT":
    required_contracts = 2
elif CONTRACT == "FAR":
    required_contracts = 3
else:
    required_contracts = 3

if len(active_contracts) < required_contracts:
    raise ValueError(
        f"{INDEX} has only "
        f"{len(active_contracts)} active contracts. "
        f"{CONTRACT} requires "
        f"{required_contracts}."
    )


# ============================================================
# SELECT CONTRACTS
# ============================================================

if CONTRACT == "CURRENT":
    selected_contracts = active_contracts.head(1).copy()

elif CONTRACT == "NEXT":
    selected_contracts = active_contracts.iloc[1:2].copy()

elif CONTRACT == "FAR":
    selected_contracts = active_contracts.iloc[2:3].copy()

else:
    selected_contracts = active_contracts.head(3).copy()

selected_symbol = selected_contracts.iloc[0]["symbol"]
selected_contract_name = selected_contracts.iloc[0]["contract"]


# ============================================================
# SELECTION SUMMARY
# ============================================================

print()
print("=" * 70)
print("SELECTION")
print("=" * 70)

print(
    f"Index     : {INDEX}"
)

print(
    f"Contract  : {CONTRACT}"
)

print(
    f"Timeframe : {TIMEFRAME}"
)

print(
    f"Today     : {today}"
)

print()
print("Selected contracts:")

for _, row in selected_contracts.iterrows():
    print(
        f"  {row['contract']} | "
        f"{row['symbol']} | "
        f"Expiry: {row['expiry_date']}"
    )


# ============================================================
# RESAMPLING FUNCTION
# ============================================================

def resample_contract(data, timeframe):

    data = (
        data
        .sort_values("datetime")
        .set_index("datetime")
    )

    aggregation = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "open_interest": "last",
    }

    if timeframe == "1D":

        result = (
            data
            .resample("1D")
            .agg(aggregation)
        )

    elif timeframe == "1W":

        # Friday-ending weekly candle.
        # This matches the Indian trading week and
        # prevents Sunday-labelled weekly observations.
        result = (
            data
            .resample("W-FRI")
            .agg(aggregation)
        )

    else:

        result = (
            data
            .resample(
                timeframe,
                origin="start_day",
                offset="9h15min",
            )
            .agg(aggregation)
        )

        # Keep only normal NSE trading-session bins.
        result = result.between_time(
            "09:15",
            "15:30",
        )

    result = (
        result
        .dropna(
            subset=[
                "open",
                "high",
                "low",
                "close",
            ]
        )
    )

    return result


# ============================================================
# INDIVIDUAL CONTRACT ANALYSIS
# ============================================================

if CONTRACT in [
    "CURRENT",
    "NEXT",
    "FAR",
]:

    contract_symbol = selected_contracts.iloc[0]["symbol"]
    contract_expiry = selected_contracts.iloc[0]["expiry"]

    contract_data = df[
        (
            df["symbol"] == contract_symbol
        )
        &
        (
            df["expiry"] == contract_expiry
        )
    ].copy()

    if contract_data.empty:
        raise ValueError(
            "No data found for selected contract."
        )

    analysis_df = (
        resample_contract(
            contract_data,
            TIMEFRAME,
        )
        .reset_index()
    )

    analysis_df = (
        analysis_df
        .sort_values("datetime")
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # PREVIOUS VALUES
    # --------------------------------------------------------

    analysis_df["previous_close"] = (
        analysis_df["close"].shift(1)
    )

    analysis_df["previous_oi"] = (
        analysis_df["open_interest"].shift(1)
    )

    analysis_df["previous_volume"] = (
        analysis_df["volume"].shift(1)
    )

    # --------------------------------------------------------
    # ABSOLUTE CHANGES
    # --------------------------------------------------------

    analysis_df["ltp_change"] = (
        analysis_df["close"]
        - analysis_df["previous_close"]
    )

    analysis_df["oi_change"] = (
        analysis_df["open_interest"]
        - analysis_df["previous_oi"]
    )

    analysis_df["volume_change"] = (
        analysis_df["volume"]
        - analysis_df["previous_volume"]
    )

    # --------------------------------------------------------
    # PERCENTAGE CHANGES
    # --------------------------------------------------------

    analysis_df["ltp_change_pct"] = (
        analysis_df["ltp_change"]
        .div(analysis_df["previous_close"])
        .mul(100)
    )

    analysis_df["oi_change_pct"] = (
        analysis_df["oi_change"]
        .div(
            analysis_df["previous_oi"].replace(
                0,
                np.nan,
            )
        )
        .mul(100)
    )

    analysis_df["volume_change_pct"] = (
        analysis_df["volume_change"]
        .div(
            analysis_df["previous_volume"].replace(
                0,
                np.nan,
            )
        )
        .mul(100)
    )


# ============================================================
# CUMULATIVE CURRENT + NEXT + FAR
# ============================================================

else:

    cumulative_parts = []

    for _, contract in selected_contracts.iterrows():

        contract_data = df[
            (
                df["symbol"] == contract["symbol"]
            )
            &
            (
                df["expiry"] == contract["expiry"]
            )
        ].copy()

        if contract_data.empty:
            continue

        contract_resampled = (
            resample_contract(
                contract_data,
                TIMEFRAME,
            )
            .reset_index()
        )

        contract_resampled["contract_symbol"] = (
            contract["symbol"]
        )

        contract_resampled["contract_name"] = (
            contract["contract"]
        )

        cumulative_parts.append(
            contract_resampled
        )

    if not cumulative_parts:
        raise ValueError(
            "No data available for "
            "Current + Next + Far."
        )

    all_contracts = pd.concat(
        cumulative_parts,
        ignore_index=True,
    )

    # --------------------------------------------------------
    # TOTAL VOLUME
    # --------------------------------------------------------

    volume_total = (
        all_contracts
        .groupby("datetime")["volume"]
        .sum()
    )

    # --------------------------------------------------------
    # TOTAL OI
    # --------------------------------------------------------

    oi_total = (
        all_contracts
        .groupby("datetime")["open_interest"]
        .sum()
    )

    # --------------------------------------------------------
    # CURRENT CONTRACT PRICE
    # --------------------------------------------------------
    #
    # Price cannot be added across contracts.
    # CURRENT contract is used as representative price.
    # --------------------------------------------------------

    current_symbol = selected_contracts.iloc[0]["symbol"]

    current_ohlc = (
        all_contracts[
            all_contracts["contract_symbol"]
            == current_symbol
        ]
        .set_index("datetime")[
            [
                "open",
                "high",
                "low",
                "close",
            ]
        ]
    )

    # --------------------------------------------------------
    # COMBINE
    # --------------------------------------------------------

    analysis_df = current_ohlc.copy()

    analysis_df["volume"] = volume_total
    analysis_df["open_interest"] = oi_total

    analysis_df = (
        analysis_df
        .dropna(
            subset=[
                "open",
                "high",
                "low",
                "close",
            ]
        )
        .reset_index()
    )

    # --------------------------------------------------------
    # PREVIOUS VALUES
    # --------------------------------------------------------

    analysis_df["previous_close"] = (
        analysis_df["close"].shift(1)
    )

    analysis_df["previous_oi"] = (
        analysis_df["open_interest"].shift(1)
    )

    analysis_df["previous_volume"] = (
        analysis_df["volume"].shift(1)
    )

    # --------------------------------------------------------
    # ABSOLUTE CHANGES
    # --------------------------------------------------------

    analysis_df["ltp_change"] = (
        analysis_df["close"]
        - analysis_df["previous_close"]
    )

    analysis_df["oi_change"] = (
        analysis_df["open_interest"]
        - analysis_df["previous_oi"]
    )

    analysis_df["volume_change"] = (
        analysis_df["volume"]
        - analysis_df["previous_volume"]
    )

    # --------------------------------------------------------
    # PERCENTAGE CHANGES
    # --------------------------------------------------------

    analysis_df["ltp_change_pct"] = (
        analysis_df["ltp_change"]
        .div(analysis_df["previous_close"])
        .mul(100)
    )

    analysis_df["oi_change_pct"] = (
        analysis_df["oi_change"]
        .div(
            analysis_df["previous_oi"].replace(
                0,
                np.nan,
            )
        )
        .mul(100)
    )

    analysis_df["volume_change_pct"] = (
        analysis_df["volume_change"]
        .div(
            analysis_df["previous_volume"].replace(
                0,
                np.nan,
            )
        )
        .mul(100)
    )


# ============================================================
# F&O POSITION CLASSIFICATION
# ============================================================

def classify_position(row):

    price_change = row["ltp_change"]
    oi_change = row["oi_change"]

    if (
        pd.isna(price_change)
        or pd.isna(oi_change)
    ):
        return "No Data"

    if (
        price_change > 0
        and oi_change > 0
    ):
        return "Long Buildup"

    elif (
        price_change < 0
        and oi_change > 0
    ):
        return "Short Buildup"

    elif (
        price_change > 0
        and oi_change < 0
    ):
        return "Short Covering"

    elif (
        price_change < 0
        and oi_change < 0
    ):
        return "Long Unwinding"

    elif (
        price_change == 0
        and oi_change > 0
    ):
        return "Price Flat + OI Increase"

    elif (
        price_change == 0
        and oi_change < 0
    ):
        return "Price Flat + OI Decrease"

    else:
        return "Neutral"


analysis_df["position"] = (
    analysis_df
    .apply(
        classify_position,
        axis=1,
    )
)


# ============================================================
# PRICE RETURN
# ============================================================

analysis_df["return_pct"] = (
    analysis_df["close"]
    .pct_change()
    .mul(100)
)


# ============================================================
# FINAL ANALYSIS DATA
# ============================================================

analysis_df = (
    analysis_df
    .sort_values("datetime")
    .reset_index(drop=True)
)


# ============================================================
# DATA SUMMARY
# ============================================================

print()
print("=" * 70)
print("ANALYSIS DATA")
print("=" * 70)

print(
    f"Index      : {INDEX}"
)

print(
    f"Contract   : {CONTRACT}"
)

print(
    f"Timeframe  : {TIMEFRAME}"
)

print(
    f"Rows       : {len(analysis_df):,}"
)

print(
    f"Start      : "
    f"{analysis_df['datetime'].min()}"
)

print(
    f"End        : "
    f"{analysis_df['datetime'].max()}"
)


# ============================================================
# POSITION SUMMARY
# ============================================================

position_counts = (
    analysis_df["position"].value_counts()
)

print()
print("=" * 70)
print("F&O POSITION SUMMARY")
print("=" * 70)

position_order = [
    "Long Buildup",
    "Short Buildup",
    "Short Covering",
    "Long Unwinding",
    "Price Flat + OI Increase",
    "Price Flat + OI Decrease",
    "Neutral",
    "No Data",
]

position_symbols = {
    "Long Buildup": "🟢",
    "Short Buildup": "🔴",
    "Short Covering": "🔵",
    "Long Unwinding": "🟠",
    "Price Flat + OI Increase": "🟡",
    "Price Flat + OI Decrease": "🟣",
    "Neutral": "⚪",
    "No Data": "⚪",
}

for position in position_order:

    print(
        f"{position_symbols[position]} "
        f"{position:<25}: "
        f"{position_counts.get(position, 0):,}"
    )


# ============================================================
# LATEST MARKET STATE
# ============================================================

latest = analysis_df.iloc[-1]

print()
print("=" * 70)
print("LATEST MARKET STATE")
print("=" * 70)

print(
    f"Index          : {INDEX}"
)

print(
    f"Contract       : {CONTRACT}"
)

print(
    f"Timeframe      : {TIMEFRAME}"
)

print(
    f"Date           : {latest['datetime']}"
)

print(
    f"Price          : {latest['close']:.2f}"
)

print(
    f"Volume         : {latest['volume']:.0f}"
)

print(
    f"Open Interest  : {latest['open_interest']:.0f}"
)

if pd.notna(latest["return_pct"]):

    print(
        f"Price Return   : "
        f"{latest['return_pct']:.2f}%"
    )

else:

    print("Price Return   : N/A")

if pd.notna(latest["oi_change_pct"]):

    print(
        f"OI Change      : "
        f"{latest['oi_change_pct']:.2f}%"
    )

else:

    print("OI Change      : N/A")

if pd.notna(latest["volume_change_pct"]):

    print(
        f"Volume Change  : "
        f"{latest['volume_change_pct']:.2f}%"
    )

else:

    print("Volume Change  : N/A")

print(
    f"Position       : "
    f"{position_symbols.get(latest['position'], '⚪')} "
    f"{latest['position']}"
)


# ============================================================
# POSITION INTERPRETATION
# ============================================================

position_description = {

    "Long Buildup":
        "Price is rising while OI is increasing. "
        "This indicates fresh long participation.",

    "Short Buildup":
        "Price is falling while OI is increasing. "
        "This indicates fresh short participation.",

    "Short Covering":
        "Price is rising while OI is decreasing. "
        "This indicates short positions are being reduced.",

    "Long Unwinding":
        "Price is falling while OI is decreasing. "
        "This indicates long positions are being reduced.",

    "Price Flat + OI Increase":
        "Price is flat while OI is increasing.",

    "Price Flat + OI Decrease":
        "Price is flat while OI is decreasing.",

    "Neutral":
        "Price and OI did not show a directional combination.",

    "No Data":
        "There is insufficient data for classification.",
}

print()
print("Interpretation:")

print(
    position_description[
        latest["position"]
    ]
)


# ============================================================
# LATEST 15 OBSERVATIONS
# ============================================================

print()
print("=" * 70)
print("LATEST 15 OBSERVATIONS")
print("=" * 70)

display_columns = [
    "datetime",
    "close",
    "open_interest",
    "volume",
    "ltp_change_pct",
    "oi_change_pct",
    "volume_change_pct",
    "position",
]

latest_display = (
    analysis_df[
        display_columns
    ]
    .tail(15)
    .copy()
)

print(
    latest_display.to_string(
        index=False
    )
)


# ============================================================
# NEXT-PERIOD HISTORICAL PROBABILITY
# ============================================================

threshold = PROBABILITY_THRESHOLDS[TIMEFRAME]

prob_df = analysis_df.copy()

# Next-period return.
# The final observation is automatically excluded because
# it has no future period available yet.
prob_df["next_return_pct"] = (
    prob_df["close"].shift(-1)
    .div(prob_df["close"])
    .sub(1)
    .mul(100)
)

prob_df = prob_df.dropna(
    subset=["next_return_pct"]
).copy()


# ------------------------------------------------------------
# CLASSIFY NEXT-PERIOD OUTCOME
# ------------------------------------------------------------

def classify_next_move(return_pct):

    if return_pct > threshold:
        return "Upside"

    elif return_pct < -threshold:
        return "Downside"

    else:
        return "Sideways"


prob_df["next_outcome"] = (
    prob_df["next_return_pct"]
    .apply(classify_next_move)
)


# ------------------------------------------------------------
# PROBABILITY CALCULATION
# ------------------------------------------------------------

def calculate_probability(data):

    total = len(data)

    if total == 0:

        return {
            "Upside": 0.0,
            "Sideways": 0.0,
            "Downside": 0.0,
            "Total": 0,
        }

    counts = data["next_outcome"].value_counts()

    return {
        "Upside":
            counts.get("Upside", 0)
            / total
            * 100,

        "Sideways":
            counts.get("Sideways", 0)
            / total
            * 100,

        "Downside":
            counts.get("Downside", 0)
            / total
            * 100,

        "Total": total,
    }


# ============================================================
# OVERALL PROBABILITY
# ============================================================

overall_probability = (
    calculate_probability(prob_df)
)

print()
print("=" * 70)
print("NEXT-PERIOD HISTORICAL PROBABILITY")
print("=" * 70)

print(
    f"Index     : {INDEX}"
)

print(
    f"Contract  : {CONTRACT}"
)

print(
    f"Timeframe : {TIMEFRAME}"
)

print(
    f"Threshold : ±{threshold:.2f}%"
)

print()
print("OVERALL PROBABILITY")
print("-" * 70)

print(
    f"Upside    : "
    f"{overall_probability['Upside']:.2f}%"
)

print(
    f"Sideways  : "
    f"{overall_probability['Sideways']:.2f}%"
)

print(
    f"Downside  : "
    f"{overall_probability['Downside']:.2f}%"
)

print(
    f"Historical cases : "
    f"{overall_probability['Total']}"
)


# ============================================================
# CURRENT POSITION CONDITIONAL PROBABILITY
# ============================================================

latest_position = analysis_df.iloc[-1]["position"]

conditional_df = prob_df[
    prob_df["position"] == latest_position
].copy()

conditional_probability = (
    calculate_probability(
        conditional_df
    )
)

print()
print(
    "CURRENT POSITION CONDITIONAL PROBABILITY"
)
print("-" * 70)

print(
    f"Current position : "
    f"{latest_position}"
)

print(
    f"Upside    : "
    f"{conditional_probability['Upside']:.2f}%"
)

print(
    f"Sideways  : "
    f"{conditional_probability['Sideways']:.2f}%"
)

print(
    f"Downside  : "
    f"{conditional_probability['Downside']:.2f}%"
)

print(
    f"Historical cases : "
    f"{conditional_probability['Total']}"
)

if conditional_probability["Total"] < 10:

    print(
        "Warning: Conditional probability is based on fewer "
        "than 10 historical cases and should be treated as "
        "low-confidence."
    )


# ============================================================
# FINAL SUMMARY
# ============================================================

print()
print("=" * 70)
print("FINAL INDEX FUTURES ANALYSIS SUMMARY")
print("=" * 70)

print()
print(
    f"Index          : {INDEX}"
)

print(
    f"Contract       : {CONTRACT}"
)

print(
    f"Timeframe      : "
    f"{TIMEFRAME} "
    f"({TIMEFRAME_NAMES[TIMEFRAME]})"
)

if CONTRACT == "CURRENT":

    print(
        f"Selected       : "
        f"{selected_contract_name}"
    )

elif CONTRACT == "NEXT":

    print(
        f"Selected       : "
        f"{selected_contracts.iloc[0]['contract']}"
    )

elif CONTRACT == "FAR":

    print(
        f"Selected       : "
        f"{selected_contracts.iloc[0]['contract']}"
    )

else:

    print(
        "Selected       : "
        "CURRENT + NEXT + FAR"
    )


print()
print("-" * 70)
print("LATEST MARKET STATE")
print("-" * 70)

print(
    f"Date           : "
    f"{latest['datetime'].strftime('%d-%b-%Y')}"
)

print(
    f"Price          : "
    f"{latest['close']:.2f}"
)

if pd.notna(latest["return_pct"]):

    print(
        f"Price Return   : "
        f"{latest['return_pct']:.2f}%"
    )

else:

    print("Price Return   : N/A")

if pd.notna(latest["oi_change_pct"]):

    print(
        f"OI Change      : "
        f"{latest['oi_change_pct']:.2f}%"
    )

else:

    print("OI Change      : N/A")

print(
    f"Position       : "
    f"{position_symbols.get(latest['position'], '⚪')} "
    f"{latest['position']}"
)

print()
print("Interpretation:")

print(
    position_description[
        latest["position"]
    ]
)


# ============================================================
# FINAL NOTE
# ============================================================

print()
print("-" * 70)

print(
    "Raw database was not modified."
)

print(
    "Analysis is based on historical futures data."
)

print("=" * 70)
