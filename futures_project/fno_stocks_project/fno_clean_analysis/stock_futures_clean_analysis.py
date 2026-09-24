# ============================================================
# STOCK FUTURES CLEAN ANALYSIS
# ============================================================
#
# Purpose:
#   Clean, interactive analysis of stock futures data.
#
# Database:
#   ../database/fno_stocks.db
#
# Includes:
#   1. Read-only database access
#   2. Stock selection
#   3. Valid OI preparation
#   4. Individual / Cumulative analysis
#   5. Timeframe selection
#   6. Resampling
#   7. F&O position classification
#   8. Latest F&O status
#   9. Next-period empirical probability
#  10. Final analysis summary
#
# IMPORTANT:
#   Only the selected stock is loaded into pandas.
#   The complete database is NEVER loaded into RAM.
#
# Excludes:
#   - Charts
#   - Dashboard
#   - Matplotlib
#
# Database is READ ONLY from this script.
# ============================================================


# ============================================================
# CELL 1 — IMPORTS
# ============================================================

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent

DB_PATH = PROJECT_DIR / "database" / "fno_stocks.db"


# ============================================================
# DATABASE CHECK
# ============================================================

if not DB_PATH.exists():
    raise FileNotFoundError(
        f"Database not found:\n{DB_PATH}"
    )


print("=" * 70)
print("STOCK FUTURES CLEAN ANALYSIS")
print("=" * 70)

print(f"Database : {DB_PATH}")

print(
    f"Database size : "
    f"{DB_PATH.stat().st_size / (1024 ** 3):.2f} GB"
)


# ============================================================
# GET AVAILABLE STOCKS
# ============================================================
#
# IMPORTANT:
# Do NOT load the complete database here.
# Only retrieve the list of stocks.
# ============================================================

print()
print("Reading stock list from SQLite...")

with sqlite3.connect(DB_PATH) as conn:

    stock_query = """
    SELECT DISTINCT stock
    FROM fno_stocks_data
    WHERE stock IS NOT NULL
    ORDER BY stock
    """

    available_stocks = pd.read_sql_query(
        stock_query,
        conn
    )["stock"].tolist()


print(
    f"Available stocks: "
    f"{len(available_stocks)}"
)


# ============================================================
# CELL 2 — STOCK SELECTION
# ============================================================

print()
print("=" * 70)
print("STOCK SELECTION")
print("=" * 70)

while True:

    selected_stock = input(
        "\nEnter stock symbol: "
    ).strip().upper()

    if selected_stock in available_stocks:
        break

    print()
    print("Invalid stock symbol.")
    print(
        "Please enter a stock from the available F&O universe."
    )


# ============================================================
# LOAD ONLY SELECTED STOCK
# ============================================================
#
# This is the main RAM/OOM fix.
#
# Example:
# HDFCBANK ≈ 45,920 rows
# instead of
# complete DB ≈ 8,988,543 rows
# ============================================================

print()
print(f"Loading data for {selected_stock}...")

query = """
SELECT
    stock,
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
FROM fno_stocks_data
WHERE stock = ?
ORDER BY expiry, datetime
"""

with sqlite3.connect(DB_PATH) as conn:

    df = pd.read_sql_query(
        query,
        conn,
        params=(selected_stock,)
    )


print(
    f"Rows loaded : "
    f"{len(df):,}"
)


# ============================================================
# SAFETY CHECK
# ============================================================

if df.empty:

    raise ValueError(
        f"No data found for stock: {selected_stock}"
    )


# ============================================================
# DATA PREPARATION
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
            "stock",
            "symbol",
            "expiry",
            "datetime"
        ]
    )
    .sort_values(
        [
            "expiry",
            "datetime"
        ]
    )
    .reset_index(drop=True)
)


print(
    f"Stocks   : "
    f"{df['stock'].nunique()}"
)

print(
    f"Contracts: "
    f"{df['symbol'].nunique()}"
)

print(
    f"Date range: "
    f"{df['datetime'].min()} → "
    f"{df['datetime'].max()}"
)


# ============================================================
# CELL 3 — VALID OI PREPARATION
# ============================================================

analysis = df.copy()

analysis["valid_oi"] = (
    analysis["open_interest"]
    .where(
        analysis["open_interest"] > 0
    )
)


total_oi = len(analysis)

valid_oi = (
    analysis["valid_oi"]
    .notna()
    .sum()
)

invalid_oi = (
    total_oi - valid_oi
)

negative_oi = (
    analysis["open_interest"] < 0
).sum()

zero_oi = (
    analysis["open_interest"] == 0
).sum()


print()
print("=" * 70)
print("OI QUALITY")
print("=" * 70)

print(
    f"Total rows : "
    f"{total_oi:,}"
)

print(
    f"Valid OI   : "
    f"{valid_oi:,}"
)

print(
    f"Invalid OI : "
    f"{invalid_oi:,}"
)

print(
    f"Negative OI: "
    f"{negative_oi:,}"
)

print(
    f"Zero OI    : "
    f"{zero_oi:,}"
)


# ============================================================
# CELL 4 — ANALYSIS MODE
# ============================================================

print()
print("=" * 70)
print("ANALYSIS MODE")
print("=" * 70)

print(
    "1. Individual Contract"
)

print(
    "2. Cumulative Current + Next + Far"
)


while True:

    mode_input = input(
        "Select mode (1/2): "
    ).strip()

    if mode_input == "1":

        analysis_mode = "Individual"
        break

    elif mode_input == "2":

        analysis_mode = "Cumulative"
        break

    else:

        print(
            "Invalid choice. "
            "Enter 1 or 2."
        )


# ============================================================
# CONTRACT SELECTION
# ============================================================

stock_contracts = (
    analysis[
        analysis["stock"] == selected_stock
    ][
        [
            "symbol",
            "expiry",
            "contract"
        ]
    ]
    .drop_duplicates()
    .sort_values("expiry")
    .reset_index(drop=True)
)


if stock_contracts.empty:

    raise ValueError(
        f"No futures contracts found "
        f"for {selected_stock}."
    )


# ============================================================
# INDIVIDUAL CONTRACT
# ============================================================

if analysis_mode == "Individual":

    print()
    print("=" * 70)
    print("AVAILABLE CONTRACTS")
    print("=" * 70)

    for i, row in stock_contracts.iterrows():

        print(
            f"{i + 1}. "
            f"{row['contract']} | "
            f"{row['symbol']} | "
            f"Expiry: {row['expiry']}"
        )


    while True:

        contract_input = input(
            "\nSelect contract number: "
        ).strip()

        try:

            contract_number = int(
                contract_input
            )

            if (
                1
                <= contract_number
                <= len(stock_contracts)
            ):
                break

        except ValueError:

            pass

        print(
            "Invalid contract number."
        )


    selected_contract = (
        stock_contracts.iloc[
            contract_number - 1
        ]
    )

    selected_symbol = (
        selected_contract["symbol"]
    )

    selected_expiry = (
        selected_contract["expiry"]
    )

    current_symbol = selected_symbol


# ============================================================
# CUMULATIVE CURRENT + NEXT + FAR
# ============================================================

else:

    cumulative_contracts = (
        stock_contracts
        .head(3)
        .copy()
    )

    if len(cumulative_contracts) < 3:

        raise ValueError(
            f"{selected_stock} does not have "
            f"three futures contracts available."
        )


    current_contract = (
        cumulative_contracts.iloc[0]
    )

    next_contract = (
        cumulative_contracts.iloc[1]
    )

    far_contract = (
        cumulative_contracts.iloc[2]
    )


    current_symbol = (
        current_contract["symbol"]
    )

    selected_symbol = current_symbol

    selected_expiry = (
        current_contract["expiry"]
    )


# ============================================================
# TIMEFRAME SELECTION
# ============================================================

timeframes = [
    "5min",
    "15min",
    "30min",
    "1h",
    "4h",
    "1D",
    "1W"
]


print()
print("=" * 70)
print("TIMEFRAME SELECTION")
print("=" * 70)


for i, timeframe in enumerate(
    timeframes,
    start=1
):

    print(
        f"{i}. {timeframe}"
    )


while True:

    timeframe_input = input(
        "\nSelect timeframe (1-7): "
    ).strip()

    try:

        timeframe_number = int(
            timeframe_input
        )

        if (
            1
            <= timeframe_number
            <= len(timeframes)
        ):
            break

    except ValueError:

        pass

    print(
        "Invalid timeframe choice."
    )


selected_timeframe = timeframes[
    timeframe_number - 1
]


# ============================================================
# SELECTION SUMMARY
# ============================================================

print()
print("=" * 70)
print("SELECTION")
print("=" * 70)

print(
    f"Stock     : "
    f"{selected_stock}"
)

print(
    f"Mode      : "
    f"{analysis_mode}"
)

print(
    f"Timeframe : "
    f"{selected_timeframe}"
)


if analysis_mode == "Individual":

    print(
        f"Contract  : "
        f"{selected_contract['contract']}"
    )

    print(
        f"Symbol    : "
        f"{selected_symbol}"
    )

    print(
        f"Expiry    : "
        f"{selected_expiry}"
    )

else:

    print(
        "Contracts : "
        "Current + Next + Far"
    )

    print(
        f"Current   : "
        f"{current_contract['contract']}"
    )

    print(
        f"Next      : "
        f"{next_contract['contract']}"
    )

    print(
        f"Far       : "
        f"{far_contract['contract']}"
    )


# ============================================================
# CELL 5 — RESAMPLING FUNCTIONS
# ============================================================

def resample_ohlc(
    data,
    timeframe
):

    data = (
        data
        .sort_values("datetime")
        .set_index("datetime")
    )


    aggregation = {

        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last"

    }


    if timeframe in [
        "1D",
        "1W"
    ]:

        result = (
            data
            .resample(timeframe)
            .agg(aggregation)
        )

    else:

        result = (
            data
            .resample(
                timeframe,
                origin="start_day",
                offset="9h15min"
            )
            .agg(aggregation)
        )


    return result


def resample_volume_oi(
    data,
    timeframe
):

    data = (
        data
        .sort_values("datetime")
        .set_index("datetime")
    )


    aggregation = {

        "volume": "sum",
        "open_interest": "last"

    }


    if timeframe in [
        "1D",
        "1W"
    ]:

        result = (
            data
            .resample(timeframe)
            .agg(aggregation)
        )

    else:

        result = (
            data
            .resample(
                timeframe,
                origin="start_day",
                offset="9h15min"
            )
            .agg(aggregation)
        )


    return result


# ============================================================
# RESAMPLE DATA
# ============================================================

stock_data = (
    df[
        df["stock"] == selected_stock
    ]
    .copy()
)


# ============================================================
# INDIVIDUAL CONTRACT
# ============================================================

if analysis_mode == "Individual":

    contract_data = (
        stock_data[
            (
                stock_data["symbol"]
                == selected_symbol
            )
            &
            (
                stock_data["expiry"]
                == selected_expiry
            )
        ]
        .copy()
    )


    ohlc = resample_ohlc(
        contract_data,
        selected_timeframe
    )


    volume_oi = resample_volume_oi(
        contract_data,
        selected_timeframe
    )


    resampled = (
        ohlc
        .join(volume_oi)
        .reset_index()
    )


# ============================================================
# CUMULATIVE CURRENT + NEXT + FAR
# ============================================================

else:

    contract_list = [
        current_contract,
        next_contract,
        far_contract
    ]


    ohlc_list = []

    volume_oi_list = []


    for contract in contract_list:

        contract_data = (
            stock_data[
                (
                    stock_data["symbol"]
                    == contract["symbol"]
                )
                &
                (
                    stock_data["expiry"]
                    == contract["expiry"]
                )
            ]
            .copy()
        )


        contract_ohlc = resample_ohlc(
            contract_data,
            selected_timeframe
        )


        contract_volume_oi = (
            resample_volume_oi(
                contract_data,
                selected_timeframe
            )
        )


        ohlc_list.append(
            contract_ohlc
        )

        volume_oi_list.append(
            contract_volume_oi
        )


    # --------------------------------------------------------
    # PRICE = CURRENT CONTRACT ONLY
    # --------------------------------------------------------

    current_ohlc = ohlc_list[0]


    # --------------------------------------------------------
    # VOLUME + OI = CURRENT + NEXT + FAR
    # --------------------------------------------------------

    combined_volume_oi = pd.concat(
        volume_oi_list,
        axis=1,
        keys=[
            "current",
            "next",
            "far"
        ]
    )


    cumulative_volume = (
        combined_volume_oi[
            [
                ("current", "volume"),
                ("next", "volume"),
                ("far", "volume")
            ]
        ]
        .sum(
            axis=1,
            min_count=1
        )
    )


    cumulative_oi = (
        combined_volume_oi[
            [
                ("current", "open_interest"),
                ("next", "open_interest"),
                ("far", "open_interest")
            ]
        ]
        .sum(
            axis=1,
            min_count=1
        )
    )


    resampled = (
        current_ohlc
        .copy()
    )


    resampled["volume"] = (
        cumulative_volume
    )

    resampled["open_interest"] = (
        cumulative_oi
    )


    resampled = (
        resampled
        .reset_index()
    )


# ============================================================
# CLEAN EMPTY CANDLES
# ============================================================

resampled = (
    resampled
    .dropna(
        subset=[
            "open",
            "high",
            "low",
            "close"
        ]
    )
    .copy()
)


# ============================================================
# INTRADAY MARKET-HOUR FILTER
# ============================================================

if selected_timeframe not in [
    "1D",
    "1W"
]:

    time_values = (
        resampled["datetime"]
        .dt.time
    )


    market_open = pd.Timestamp(
        "09:15"
    ).time()


    market_close = pd.Timestamp(
        "15:30"
    ).time()


    resampled = (
        resampled[
            (
                time_values
                >= market_open
            )
            &
            (
                time_values
                <= market_close
            )
        ]
        .copy()
    )


resampled = (
    resampled
    .sort_values("datetime")
    .reset_index(drop=True)
)


# ============================================================
# RESAMPLED DATA SUMMARY
# ============================================================

print()
print("=" * 70)
print("RESAMPLED DATA")
print("=" * 70)

print(
    f"Stock       : "
    f"{selected_stock}"
)

print(
    f"Mode        : "
    f"{analysis_mode}"
)

print(
    f"Timeframe   : "
    f"{selected_timeframe}"
)


if analysis_mode == "Individual":

    print(
        f"Contract    : "
        f"{selected_symbol}"
    )

else:

    print(
        "Price       : Current contract"
    )

    print(
        "Volume + OI : Current + Next + Far"
    )


print(
    f"Candles     : "
    f"{len(resampled):,}"
)


if not resampled.empty:

    print(
        f"Start       : "
        f"{resampled['datetime'].min()}"
    )

    print(
        f"End         : "
        f"{resampled['datetime'].max()}"
    )

    print()
    print("Recent data:")

    print(
        resampled.tail(10)
        .to_string(index=False)
    )


# ============================================================
# SAFETY CHECK
# ============================================================

if resampled.empty:

    raise ValueError(
        "No resampled data available "
        "for the selected stock, contract "
        "and timeframe."
    )


# ============================================================
# CELL 6 — TIMEFRAME F&O ANALYSIS
# ============================================================

tf_analysis = resampled.copy()


# ============================================================
# PREVIOUS CLOSE
# ============================================================

tf_analysis["prev_close"] = (
    tf_analysis["close"]
    .shift(1)
)


# ============================================================
# VALID OI
# ============================================================

tf_analysis["valid_oi"] = (
    tf_analysis["open_interest"]
    .where(
        tf_analysis["open_interest"] > 0
    )
)


tf_analysis["prev_oi"] = (
    tf_analysis["valid_oi"]
    .shift(1)
)


# ============================================================
# PRICE CHANGE
# ============================================================

tf_analysis["price_change"] = (
    tf_analysis["close"]
    -
    tf_analysis["prev_close"]
)


tf_analysis["price_change_pct"] = (
    tf_analysis["price_change"]
    .div(
        tf_analysis["prev_close"]
    )
    * 100
)


# ============================================================
# OI CHANGE
# ============================================================

tf_analysis["oi_change"] = (
    tf_analysis["valid_oi"]
    -
    tf_analysis["prev_oi"]
)


tf_analysis["oi_change_pct"] = (
    tf_analysis["oi_change"]
    .div(
        tf_analysis["prev_oi"]
    )
    * 100
)


# ============================================================
# F&O POSITION CLASSIFICATION
# ============================================================

def classify_position(row):

    price_change = (
        row["price_change"]
    )

    oi_change = (
        row["oi_change"]
    )


    if (
        pd.isna(price_change)
        or
        pd.isna(oi_change)
    ):

        return "No OI Data"


    if (
        price_change > 0
        and
        oi_change > 0
    ):

        return "Long Buildup"


    elif (
        price_change < 0
        and
        oi_change > 0
    ):

        return "Short Buildup"


    elif (
        price_change > 0
        and
        oi_change < 0
    ):

        return "Short Covering"


    elif (
        price_change < 0
        and
        oi_change < 0
    ):

        return "Long Unwinding"


    else:

        return "Neutral"


tf_analysis["position"] = (
    tf_analysis
    .apply(
        classify_position,
        axis=1
    )
)


tf_analysis["price_return_pct"] = (
    tf_analysis["close"]
    .pct_change()
    * 100
)


# ============================================================
# POSITION SUMMARY
# ============================================================

position_order = [

    "Long Buildup",
    "Short Buildup",
    "Short Covering",
    "Long Unwinding",
    "Neutral",
    "No OI Data"

]


position_counts = (
    tf_analysis["position"]
    .value_counts()
)


print()
print("=" * 70)
print("F&O POSITION SUMMARY")
print("=" * 70)


for position in position_order:

    print(
        f"{position:<18}: "
        f"{position_counts.get(position, 0):,}"
    )


print()
print("Latest 15 observations:")

print(
    tf_analysis[
        [
            "datetime",
            "close",
            "valid_oi",
            "price_change_pct",
            "oi_change_pct",
            "position"
        ]
    ]
    .tail(15)
    .to_string(index=False)
)


# ============================================================
# CELL 7 — LATEST F&O STATUS
# ============================================================

latest = tf_analysis.iloc[-1]


position_symbols = {

    "Long Buildup": "🟢",
    "Short Buildup": "🔴",
    "Short Covering": "🔵",
    "Long Unwinding": "🟠",
    "Neutral": "⚪",
    "No OI Data": "⚪"

}


latest_symbol = position_symbols.get(
    latest["position"],
    "⚪"
)


print()
print("=" * 70)
print("LATEST F&O STATUS")
print("=" * 70)


if analysis_mode == "Cumulative":

    print(
        "Mode: Cumulative "
        "Current + Next + Far"
    )

else:

    print(
        f"Mode: Individual | "
        f"Contract: {selected_symbol}"
    )


print(
    f"Latest Date     : "
    f"{latest['datetime']}"
)


print(
    f"Current Price   : "
    f"{latest['close']:.2f}"
)


print(
    f"Volume          : "
    f"{latest['volume']}"
)


print(
    f"OI              : "
    f"{latest['open_interest']}"
)


if pd.notna(
    latest["oi_change_pct"]
):

    print(
        f"OI Change       : "
        f"{latest['oi_change_pct']:.2f}%"
    )

else:

    print(
        "OI Change       : N/A"
    )


if pd.notna(
    latest["price_change_pct"]
):

    print(
        f"Price Return    : "
        f"{latest['price_change_pct']:.2f}%"
    )

else:

    print(
        "Price Return    : N/A"
    )


print(
    f"Latest Position : "
    f"{latest_symbol} "
    f"{latest['position']}"
)


print()
print("Signal Counts:")


for position in position_order:

    symbol = position_symbols[position]

    print(
        f"{symbol} "
        f"{position:<18}: "
        f"{position_counts.get(position, 0):,}"
    )


# ============================================================
# CELL 8 — NEXT-PERIOD EMPIRICAL PROBABILITY
# ============================================================

prob_data = tf_analysis.copy()


# ============================================================
# TIMEFRAME-BASED MOVE THRESHOLD
# ============================================================

move_thresholds = {

    "5min": 0.15,
    "15min": 0.25,
    "30min": 0.35,
    "1h": 0.50,
    "4h": 0.75,
    "1D": 0.50,
    "1W": 1.00

}


threshold = move_thresholds[
    selected_timeframe
]


# ============================================================
# NEXT PERIOD RETURN
# ============================================================

prob_data["next_return_pct"] = (
    prob_data["close"]
    .shift(-1)
    .div(
        prob_data["close"]
    )
    .sub(1)
    * 100
)


# ============================================================
# CLASSIFY NEXT MOVE
# ============================================================

def classify_next_move(
    return_pct
):

    if pd.isna(return_pct):

        return np.nan


    if return_pct > threshold:

        return "Upside"


    elif return_pct < -threshold:

        return "Downside"


    else:

        return "Sideways"


prob_data["next_move"] = (
    prob_data["next_return_pct"]
    .apply(
        classify_next_move
    )
)


# ============================================================
# REMOVE LAST ROW
# ============================================================

historical_moves = (
    prob_data
    .dropna(
        subset=[
            "next_move"
        ]
    )
    .copy()
)


# ============================================================
# OVERALL HISTORICAL PROBABILITY
# ============================================================

probability = (
    historical_moves["next_move"]
    .value_counts(
        normalize=True
    )
    * 100
)


upside_probability = (
    probability.get(
        "Upside",
        0
    )
)


sideways_probability = (
    probability.get(
        "Sideways",
        0
    )
)


downside_probability = (
    probability.get(
        "Downside",
        0
    )
)


# ============================================================
# CURRENT POSITION CONDITIONAL PROBABILITY
# ============================================================

current_position = (
    tf_analysis.iloc[-1]["position"]
)


conditional_data = (
    historical_moves[
        historical_moves["position"]
        ==
        current_position
    ]
    .copy()
)


if not conditional_data.empty:

    conditional_probability = (
        conditional_data["next_move"]
        .value_counts(
            normalize=True
        )
        * 100
    )

else:

    conditional_probability = (
        pd.Series(dtype=float)
    )


conditional_upside = (
    conditional_probability.get(
        "Upside",
        0
    )
)


conditional_sideways = (
    conditional_probability.get(
        "Sideways",
        0
    )
)


conditional_downside = (
    conditional_probability.get(
        "Downside",
        0
    )
)


# ============================================================
# DISPLAY PROBABILITY
# ============================================================

print()
print("=" * 70)
print("NEXT-PERIOD EMPIRICAL PROBABILITY")
print("=" * 70)


print(
    f"Stock     : "
    f"{selected_stock}"
)


print(
    f"Mode      : "
    f"{analysis_mode}"
)


print(
    f"Timeframe : "
    f"{selected_timeframe}"
)


print(
    f"Move threshold : "
    f"±{threshold:.2f}%"
)


# ============================================================
# OVERALL PROBABILITY
# ============================================================

print()
print("OVERALL HISTORICAL PROBABILITY")
print("-" * 70)


print(
    f"Upside       : "
    f"{upside_probability:.1f}%"
)


print(
    f"Sideways     : "
    f"{sideways_probability:.1f}%"
)


print(
    f"Downside     : "
    f"{downside_probability:.1f}%"
)


print(
    f"Observations : "
    f"{len(historical_moves):,}"
)


# ============================================================
# CONDITIONAL PROBABILITY
# ============================================================

print()

print(
    f"CURRENT STATE: "
    f"{current_position}"
)

print("-" * 70)


print(
    f"Upside       : "
    f"{conditional_upside:.1f}%"
)


print(
    f"Sideways     : "
    f"{conditional_sideways:.1f}%"
)


print(
    f"Downside     : "
    f"{conditional_downside:.1f}%"
)


print(
    f"Matching historical cases: "
    f"{len(conditional_data):,}"
)


print("=" * 70)


# ============================================================
# CELL 9 — FINAL ANALYSIS SUMMARY
# ============================================================

latest = tf_analysis.iloc[-1]


current_position = latest[
    "position"
]


# ============================================================
# SIGNAL DESCRIPTION
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

    "Neutral":
        "Price and OI did not show a directional combination.",

    "No OI Data":
        "There is insufficient valid OI data for classification."

}


# ============================================================
# HISTORICAL TENDENCY
# ============================================================

historical_cases = len(
    conditional_data
)


if historical_cases > 0:

    probabilities = {

        "Upside":
            conditional_upside,

        "Sideways":
            conditional_sideways,

        "Downside":
            conditional_downside

    }


    historical_tendency = max(
        probabilities,
        key=probabilities.get
    )

else:

    historical_tendency = (
        "Insufficient Data"
    )


# ============================================================
# FINAL DISPLAY
# ============================================================

print()
print("=" * 70)
print("FINAL STOCK FUTURES ANALYSIS SUMMARY")
print("=" * 70)


print()

print(
    f"Stock          : "
    f"{selected_stock}"
)


print(
    f"Analysis Mode  : "
    f"{analysis_mode}"
)


print(
    f"Timeframe      : "
    f"{selected_timeframe}"
)


if analysis_mode == "Individual":

    print(
        f"Contract       : "
        f"{selected_symbol}"
    )

else:

    print(
        "Contracts      : "
        "Current + Next + Far"
    )

    print(
        f"Price Contract : "
        f"{current_symbol}"
    )


# ============================================================
# LATEST MARKET STATE
# ============================================================

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


if pd.notna(
    latest["price_return_pct"]
):

    print(
        f"Price Return   : "
        f"{latest['price_return_pct']:.2f}%"
    )

else:

    print(
        "Price Return   : N/A"
    )


if pd.notna(
    latest["oi_change_pct"]
):

    print(
        f"OI Change      : "
        f"{latest['oi_change_pct']:.2f}%"
    )

else:

    print(
        "OI Change      : N/A"
    )


print(
    f"Position       : "
    f"{current_position}"
)


print()
print("Interpretation:")

print(
    position_description[
        current_position
    ]
)


# ============================================================
# HISTORICAL NEXT-PERIOD TENDENCY
# ============================================================

print()
print("-" * 70)

print(
    "HISTORICAL NEXT-PERIOD TENDENCY"
)

print("-" * 70)


print(
    f"Move Threshold : "
    f"±{threshold:.2f}%"
)


print(
    f"Historical Cases: "
    f"{historical_cases:,}"
)


if historical_cases > 0:

    print()

    print(
        f"Upside        : "
        f"{conditional_upside:.1f}%"
    )


    print(
        f"Sideways      : "
        f"{conditional_sideways:.1f}%"
    )


    print(
        f"Downside      : "
        f"{conditional_downside:.1f}%"
    )


    print()

    print(
        f"Most Frequent Historical Outcome: "
        f"{historical_tendency}"
    )

else:

    print(
        "Not enough matching historical cases."
    )


# ============================================================
# FINAL NOTE
# ============================================================

print()
print("-" * 70)

print(
    "Note: Historical probabilities describe past "
    "observations only and are not guaranteed predictions."
)

print()
print("=" * 70)
print("ANALYSIS COMPLETED")
print("=" * 70)
