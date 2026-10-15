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
#   3. Individual / Cumulative analysis
#   4. Timeframe selection
#   5. Resampling
#   6. F&O position classification
#   7. Latest market state
#   8. Latest observations
#   9. Next-period empirical probability
#  10. V3 similar-condition historical analysis
#  11. Overbought / oversold reversal analysis
#  12. Estimated long-side / short-side activity
#  13. Final analysis summary
#
# IMPORTANT:
#   Only the selected stock is loaded into pandas.
#   The complete database is NEVER loaded into RAM.
#
# Database is READ ONLY from this script.
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
DB_PATH = PROJECT_DIR / "database" / "fno_stocks.db"
# ============================================================
# DATABASE CHECK
# ============================================================
if not DB_PATH.exists():
       raise FileNotFoundError(
           f"Database not found:\n{DB_PATH}"
       )
# ============================================================
# DISPLAY HELPERS
# ============================================================
SEPARATOR = "=" * 70
SUB_SEPARATOR = "-" * 70
POSITION_ORDER = [
       "Long Buildup",
       "Short Buildup",
       "Short Covering",
       "Long Unwinding",
       "Price Flat + OI Increase",
       "Price Flat + OI Decrease",
       "Neutral",
       "No OI Data",
]
POSITION_SYMBOLS = {
       "Long Buildup": "🟢",
       "Short Buildup": "🔴",
       "Short Covering": "🔵",
       "Long Unwinding": "🟠",
       "Price Flat + OI Increase": "🟡",
       "Price Flat + OI Decrease": "🟣",
       "Neutral": "⚪",
       "No OI Data": "⚪",
}
POSITION_DESCRIPTION = {
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
           "Price is broadly flat while OI is increasing. "
           "This indicates additional positioning without a clear price direction.",
       "Price Flat + OI Decrease":
           "Price is broadly flat while OI is decreasing. "
           "This indicates position reduction without a clear price direction.",
       "Neutral":
           "Price and OI did not show a directional combination.",
       "No OI Data":
           "There is insufficient valid OI data for classification.",
}
TIMEFRAMES = [
       "5min",
       "15min",
       "30min",
       "1h",
       "4h",
       "1D",
       "1W",
]
MOVE_THRESHOLDS = {
       "5min": 0.15,
       "15min": 0.25,
       "30min": 0.35,
       "1h": 0.50,
       "4h": 0.75,
       "1D": 0.50,
       "1W": 1.00,
}
# ============================================================
# DATABASE INFORMATION
# ============================================================
with sqlite3.connect(
    f"file:{DB_PATH.as_posix()}?mode=ro", uri=True
) as conn:
       database_row_count = conn.execute(
           "SELECT COUNT(*) FROM fno_stocks_data"
       ).fetchone()[0]
       database_stock_count = conn.execute(
           """
           SELECT COUNT(DISTINCT stock)
           FROM fno_stocks_data
           WHERE stock IS NOT NULL
           """
       ).fetchone()[0]
       database_contract_count = conn.execute(
           """
           SELECT COUNT(DISTINCT symbol)
           FROM fno_stocks_data
           WHERE symbol IS NOT NULL
           """
       ).fetchone()[0]
       database_min_datetime = conn.execute(
           """
           SELECT MIN(datetime)
           FROM fno_stocks_data
           """
       ).fetchone()[0]
       database_max_datetime = conn.execute(
           """
           SELECT MAX(datetime)
           FROM fno_stocks_data
           """
       ).fetchone()[0]
print(SEPARATOR)
print("STOCK FUTURES CLEAN ANALYSIS")
print(SEPARATOR)
print(f"Database : {DB_PATH}")
db_size_bytes = DB_PATH.stat().st_size
if db_size_bytes >= 1024 ** 3:
       print(
           f"Database size : "
           f"{db_size_bytes / (1024 ** 3):.2f} GB"
       )
else:
       print(
           f"Database size : "
           f"{db_size_bytes / (1024 ** 2):.2f} MB"
       )
# ============================================================
# DATABASE SUMMARY
# ============================================================
print()
print(SEPARATOR)
print("DATABASE SUMMARY")
print(SEPARATOR)
print(
       f"Total rows     : "
       f"{database_row_count:,}"
)
print(
       f"Total contracts: "
       f"{database_contract_count:,}"
)
print(
       f"Total stocks   : "
       f"{database_stock_count:,}"
)
print()
print("Date range:")
print(
       f"From : {database_min_datetime}"
)
print(
       f"To   : {database_max_datetime}"
)
# ============================================================
# GET AVAILABLE STOCKS
# ============================================================
print()
print(SEPARATOR)
print("AVAILABLE STOCKS")
print(SEPARATOR)
with sqlite3.connect(
    f"file:{DB_PATH.as_posix()}?mode=ro", uri=True
) as conn:
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
# STOCK SELECTION
# ============================================================
print()
print(SEPARATOR)
print("STOCK SELECTION")
print(SEPARATOR)
while True:
       selected_stock = input(
           "\nEnter stock symbol: "
       ).strip().upper()
       if selected_stock in available_stocks:
           break
       print()
       print("Invalid stock symbol.")
       print(
           "Please enter a stock from the "
           "available F&O universe."
       )
# ============================================================
# LOAD ONLY SELECTED STOCK
# ============================================================
print()
print(
       f"Loading data for "
       f"{selected_stock}..."
)
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
with sqlite3.connect(
    f"file:{DB_PATH.as_posix()}?mode=ro", uri=True
) as conn:
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
           f"No data found for stock: "
           f"{selected_stock}"
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
               "datetime",
           ]
       )
       .sort_values(
           [
               "expiry",
               "datetime",
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
# VALID OI PREPARATION
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
invalid_oi = total_oi - valid_oi
negative_oi = (
       analysis["open_interest"] < 0
).sum()
zero_oi = (
       analysis["open_interest"] == 0
).sum()
print()
print(SEPARATOR)
print("OI QUALITY")
print(SEPARATOR)
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
# ANALYSIS MODE
# ============================================================
print()
print(SEPARATOR)
print("ANALYSIS MODE")
print(SEPARATOR)
print("1. Individual Contract")
print("2. Cumulative Current + Next + Far")
while True:
       mode_input = input(
           "Select mode (1/2): "
       ).strip()
       if mode_input == "1":
           analysis_mode = "Individual"
           break
       if mode_input == "2":
           analysis_mode = "Cumulative"
           break
       print(
           "Invalid choice. Enter 1 or 2."
       )
# ============================================================
# CONTRACT SELECTION (EXPIRY-AWARE)
# ============================================================
IST = ZoneInfo("Asia/Kolkata")
as_of_date = datetime.now(IST).date()

stock_contracts = (
    analysis[analysis["stock"] == selected_stock][
        ["symbol", "expiry", "contract"]
    ]
    .drop_duplicates()
    .sort_values("expiry")
    .reset_index(drop=True)
)

if stock_contracts.empty:
    raise ValueError(f"No futures contracts found for {selected_stock}.")

stock_contracts["expiry_status"] = stock_contracts["expiry"].apply(
    lambda expiry: "ACTIVE" if expiry >= as_of_date else "EXPIRED"
)
active_contracts = (
    stock_contracts[stock_contracts["expiry"] >= as_of_date]
    .sort_values("expiry")
    .reset_index(drop=True)
)

print(f"Analysis date (IST): {as_of_date}")

# ============================================================
# INDIVIDUAL CONTRACT / CUMULATIVE CURRENT-NEXT-FAR
# ============================================================
if analysis_mode == "Individual":
    print()
    print(SEPARATOR)
    print("AVAILABLE CONTRACTS")
    print(SEPARATOR)
    for i, row in stock_contracts.iterrows():
        status = "ACTIVE" if row["expiry"] >= as_of_date else "EXPIRED - historical research only"
        print(
            f"{i + 1}. {row['contract']} | {row['symbol']} | "
            f"Expiry: {row['expiry']} | {status}"
        )

    while True:
        contract_input = input("\nSelect contract number: ").strip()
        try:
            contract_number = int(contract_input)
            if 1 <= contract_number <= len(stock_contracts):
                break
        except ValueError:
            pass
        print("Invalid contract number.")

    selected_contract = stock_contracts.iloc[contract_number - 1]
    selected_symbol = selected_contract["symbol"]
    selected_expiry = selected_contract["expiry"]
    current_symbol = selected_symbol
    selected_contract_status = selected_contract["expiry_status"]
else:
    cumulative_contracts = active_contracts.head(3).copy()
    if len(cumulative_contracts) < 3:
        available = ", ".join(
            f"{row.contract} (expiry {row.expiry})"
            for row in cumulative_contracts.itertuples()
        ) or "none"
        raise ValueError(
            f"Only {len(cumulative_contracts)} unexpired contracts are available "
            f"for {selected_stock} as of {as_of_date}; three are required. "
            f"Available: {available}. Update the database before running cumulative mode."
        )

    current_contract = cumulative_contracts.iloc[0]
    next_contract = cumulative_contracts.iloc[1]
    far_contract = cumulative_contracts.iloc[2]
    current_symbol = current_contract["symbol"]
    selected_symbol = current_symbol
    selected_expiry = current_contract["expiry"]
    selected_contract_status = "ACTIVE"

# ============================================================
# TIMEFRAME SELECTION
# ============================================================
print()
print(SEPARATOR)
print("TIMEFRAME")
print(SEPARATOR)
for i, timeframe in enumerate(
       TIMEFRAMES,
       start=1
):
       labels = {
           "5min": "5 Minute",
           "15min": "15 Minute",
           "30min": "30 Minute",
           "1h": "1 Hour",
           "4h": "4 Hour",
           "1D": "Daily",
           "1W": "Weekly",
       }
       print(
           f"{i}. {timeframe} "
           f"({labels[timeframe]})"
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
               <= len(TIMEFRAMES)
           ):
               break
       except ValueError:
           pass
       print(
           "Invalid timeframe choice."
       )
selected_timeframe = TIMEFRAMES[
       timeframe_number - 1
]
# ============================================================
# SELECTION SUMMARY
# ============================================================
print()
print(SEPARATOR)
print("SELECTION")
print(SEPARATOR)
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
print(f"Analysis date (IST): {as_of_date}")
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
           f"{selected_expiry} ({selected_contract_status})"
       )
else:
       print(
           "Contracts : "
           "Current + Next + Far (signals use CURRENT contract only)"
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
# RESAMPLING FUNCTIONS
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
           "close": "last",
       }
       if timeframe in [
           "1D",
           "1W",
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
                   offset="9h15min",
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
           "open_interest": "last",
       }
       if timeframe in [
           "1D",
           "1W",
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
                   offset="9h15min",
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
else:
       contract_list = [
           current_contract,
           next_contract,
           far_contract,
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
       # IMPORTANT METHODOLOGY:
       # Position classification and all historical/statistical calculations use
       # the CURRENT contract's own price, volume and OI series. Do not combine
       # current-contract price with summed OI from different expiries.
       current_ohlc = ohlc_list[0]
       current_volume_oi = volume_oi_list[0]
       combined_volume_oi = pd.concat(
           volume_oi_list,
           axis=1,
           keys=["current", "next", "far"],
       )
       aggregate_volume = combined_volume_oi[
           [("current", "volume"), ("next", "volume"), ("far", "volume")]
       ].sum(axis=1, min_count=1)
       aggregate_oi = combined_volume_oi[
           [
               ("current", "open_interest"),
               ("next", "open_interest"),
               ("far", "open_interest"),
           ]
       ].sum(axis=1, min_count=1)

       resampled = current_ohlc.join(current_volume_oi, how="left")
       # Descriptive totals only; these columns are never used for classification.
       resampled["combined_3_contract_volume"] = aggregate_volume
       resampled["combined_3_contract_open_interest"] = aggregate_oi
       resampled = resampled.reset_index()
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
               "close",
           ]
       )
       .copy()
)
# ============================================================
# INTRADAY MARKET-HOUR FILTER
# ============================================================
if selected_timeframe not in [
       "1D",
       "1W",
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
print(SEPARATOR)
print("ANALYSIS DATA")
print(SEPARATOR)
print(
       f"Stock      : "
       f"{selected_stock}"
)
if analysis_mode == "Individual":
       print(
           f"Contract   : "
           f"{selected_symbol}"
       )
else:
       print(
           "Contract   : "
           "CURRENT + NEXT + FAR (signals use CURRENT contract only)"
       )
print(
       f"Timeframe  : "
       f"{selected_timeframe}"
)
print(
       f"Rows       : "
       f"{len(resampled):,}"
)
if not resampled.empty:
       print(
           f"Start      : "
           f"{resampled['datetime'].min()}"
       )
       print(
           f"End        : "
           f"{resampled['datetime'].max()}"
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
# TIMEFRAME F&O ANALYSIS
# ============================================================
tf_analysis = resampled.copy()
tf_analysis["prev_close"] = (
       tf_analysis["close"]
       .shift(1)
)
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
tf_analysis["price_change"] = (
       tf_analysis["close"]
       - tf_analysis["prev_close"]
)
tf_analysis["price_change_pct"] = (
       tf_analysis["price_change"]
       .div(
           tf_analysis["prev_close"]
       )
       * 100
)
tf_analysis["oi_change"] = (
       tf_analysis["valid_oi"]
       - tf_analysis["prev_oi"]
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
       price_change = row[
           "price_change"
       ]
       oi_change = row[
           "oi_change"
       ]
       if (
           pd.isna(price_change)
           or
           pd.isna(oi_change)
       ):
           return "No OI Data"
       # Small price movements are treated as flat.
       # The threshold is deliberately small so normal
       # stock-futures noise is not over-classified.
       flat_epsilon = 1e-12
       if (
           price_change > flat_epsilon
           and
           oi_change > 0
       ):
           return "Long Buildup"
       elif (
           price_change < -flat_epsilon
           and
           oi_change > 0
       ):
           return "Short Buildup"
       elif (
           price_change > flat_epsilon
           and
           oi_change < 0
       ):
           return "Short Covering"
       elif (
           price_change < -flat_epsilon
           and
           oi_change < 0
       ):
           return "Long Unwinding"
       elif (
           abs(price_change) <= flat_epsilon
           and
           oi_change > 0
       ):
           return "Price Flat + OI Increase"
       elif (
           abs(price_change) <= flat_epsilon
           and
           oi_change < 0
       ):
           return "Price Flat + OI Decrease"
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
# F&O POSITION SUMMARY
# ============================================================
position_counts = (
       tf_analysis["position"]
       .value_counts()
)
print()
print(SEPARATOR)
print("F&O POSITION SUMMARY")
print(SEPARATOR)
for position in POSITION_ORDER:
       print(
           f"{POSITION_SYMBOLS[position]} "
           f"{position:<25}: "
           f"{position_counts.get(position, 0):,}"
       )
# ============================================================
# LATEST MARKET STATE
# ============================================================
latest = tf_analysis.iloc[-1]
current_position = latest[
       "position"
]
print()
print(SEPARATOR)
print("LATEST MARKET STATE")
print(SEPARATOR)
print(
       f"Stock          : "
       f"{selected_stock}"
)
if analysis_mode == "Individual":
       print(
           f"Contract       : "
           f"{selected_symbol}"
       )
else:
       print(
           "Contract       : "
           "CURRENT + NEXT + FAR (signals use CURRENT contract only)"
       )
print(
       f"Timeframe      : "
       f"{selected_timeframe}"
)
print(
       f"Date           : "
       f"{latest['datetime']}"
)
print(
       f"Price          : "
       f"{latest['close']:.2f}"
)
print(
       f"Volume         : "
       f"{latest['volume']}"
)
print(
       f"Open Interest  : "
       f"{latest['open_interest']}"
)
if analysis_mode == "Cumulative":
       print(
           f"3-contract Volume (descriptive): "
           f"{latest.get('combined_3_contract_volume', float('nan'))}"
       )
       print(
           f"3-contract OI (descriptive)    : "
           f"{latest.get('combined_3_contract_open_interest', float('nan'))}"
       )
       print("Note: Position classification uses CURRENT contract OI only.")
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
       f"{POSITION_SYMBOLS[current_position]} "
       f"{current_position}"
)
print()
print("Interpretation:")
print(
       POSITION_DESCRIPTION[
           current_position
       ]
)
# ============================================================
# LATEST 30 OBSERVATIONS
# ============================================================
print()
print(SEPARATOR)
print("LATEST 30 OBSERVATIONS")
print(SEPARATOR)
latest_columns = [
       "datetime",
       "close",
       "open_interest",
       "volume",
       "price_return_pct",
       "oi_change_pct",
       "position",
]
print(
       tf_analysis[
           latest_columns
       ]
       .tail(30)
       .to_string(index=False)
)
# ============================================================
# NEXT-PERIOD HISTORICAL PROBABILITY
# ============================================================
prob_data = tf_analysis.copy()
threshold = MOVE_THRESHOLDS[
       selected_timeframe
]
prob_data["next_return_pct"] = (
       prob_data["close"]
       .shift(-1)
       .div(
           prob_data["close"]
       )
       .sub(1)
       * 100
)
def classify_next_move(
       return_pct
):
       if pd.isna(return_pct):
           return np.nan
       if return_pct > threshold:
           return "Upside"
       if return_pct < -threshold:
           return "Downside"
       return "Sideways"
prob_data["next_move"] = (
       prob_data["next_return_pct"]
       .apply(
           classify_next_move
       )
)
historical_moves = (
       prob_data
       .dropna(
           subset=[
               "next_move"
           ]
       )
       .copy()
)
probability = (
       historical_moves["next_move"]
       .value_counts(
           normalize=True
       )
       * 100
)
upside_probability = probability.get(
       "Upside",
       0
)
sideways_probability = probability.get(
       "Sideways",
       0
)
downside_probability = probability.get(
       "Downside",
       0
)
# ============================================================
# CURRENT POSITION CONDITIONAL PROBABILITY
# ============================================================
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
print()
print(SEPARATOR)
print("NEXT-PERIOD HISTORICAL PROBABILITY")
print(SEPARATOR)
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
print(f"Analysis date (IST): {as_of_date}")
print(
       f"Move threshold : "
       f"±{threshold:.2f}%"
)
print()
print("OVERALL PROBABILITY")
print(SUB_SEPARATOR)
print(
       f"Upside    : "
       f"{upside_probability:.2f}%"
)
print(
       f"Sideways  : "
       f"{sideways_probability:.2f}%"
)
print(
       f"Downside  : "
       f"{downside_probability:.2f}%"
)
print(
       f"Historical cases : "
       f"{len(historical_moves):,}"
)
print()
print("CURRENT POSITION CONDITIONAL PROBABILITY")
print(SUB_SEPARATOR)
print(
       f"Current position : "
       f"{current_position}"
)
print(
       f"Upside    : "
       f"{conditional_upside:.2f}%"
)
print(
       f"Sideways  : "
       f"{conditional_sideways:.2f}%"
)
print(
       f"Downside  : "
       f"{conditional_downside:.2f}%"
)
print(
       f"Historical cases : "
       f"{len(conditional_data):,}"
)
# ============================================================
# V3 SIMILAR-CONDITION HISTORICAL ANALYSIS
# ============================================================
v3_data = tf_analysis.copy()
v3_data["rsi_14"] = (
       v3_data["close"]
       .pct_change()
       .rolling(14)
       .mean()
)
# RSI using standard average gain / average loss.
delta = v3_data["close"].diff()
gain = (
       delta.clip(lower=0)
       .rolling(14)
       .mean()
)
loss = (
       -delta.clip(upper=0)
       .rolling(14)
       .mean()
)
rs = gain.div(
       loss.replace(0, np.nan)
)
v3_data["rsi_14"] = (
       100 - (
           100 / (1 + rs)
       )
)
rolling_mean = (
       v3_data["close"]
       .rolling(20)
       .mean()
)
rolling_std = (
       v3_data["close"]
       .rolling(20)
       .std()
)
v3_data["price_zscore_20"] = (
       v3_data["close"]
       .sub(rolling_mean)
       .div(
           rolling_std.replace(0, np.nan)
       )
)
v3_data["volume_change_pct"] = (
       v3_data["volume"]
       .pct_change()
       * 100
)
v3_data["future_1_return_pct"] = (
       v3_data["close"]
       .shift(-1)
       .div(
           v3_data["close"]
       )
       .sub(1)
       * 100
)
v3_data["future_3_return_pct"] = (
       v3_data["close"]
       .shift(-3)
       .div(
           v3_data["close"]
       )
       .sub(1)
       * 100
)
v3_data["future_5_return_pct"] = (
       v3_data["close"]
       .shift(-5)
       .div(
           v3_data["close"]
       )
       .sub(1)
       * 100
)
v3_data["similarity_distance"] = np.nan
latest_v3 = v3_data.iloc[-1]
feature_columns = [
       "price_return_pct",
       "oi_change_pct",
       "volume_change_pct",
       "rsi_14",
       "price_zscore_20",
]
valid_v3 = v3_data.dropna(
       subset=feature_columns
).copy()
if len(valid_v3) > 1:
       feature_matrix = valid_v3[
           feature_columns
       ].astype(float)
       latest_features = latest_v3[
           feature_columns
       ].astype(float)
       std_values = (
           feature_matrix.std()
           .replace(0, 1)
       )
       distances = np.sqrt(
           (
               (
                   feature_matrix
                   - latest_features
               )
               .div(std_values)
               ** 2
           )
           .sum(axis=1)
       )
       valid_v3[
           "similarity_distance"
       ] = distances
       # Remove the current observation itself.
       if len(valid_v3) > 1:
           valid_v3 = (
               valid_v3[
                   valid_v3.index
                   != latest_v3.name
               ]
               .copy()
           )
       similar_cases = (
           valid_v3
           .sort_values(
               "similarity_distance"
           )
           .head(20)
           .copy()
       )
else:
       similar_cases = pd.DataFrame()
# ============================================================
# REVERSAL STATE
# ============================================================
latest_rsi = latest_v3[
       "rsi_14"
]
latest_zscore = latest_v3[
       "price_zscore_20"
]
short_side_exhaustion = (
       current_position
       in [
           "Short Buildup",
           "Long Unwinding",
       ]
)
long_side_exhaustion = (
       current_position
       in [
           "Long Buildup",
           "Short Covering",
       ]
)
if (
       pd.notna(latest_rsi)
       and
       pd.notna(latest_zscore)
       and
       latest_rsi <= 30
       and
       latest_zscore <= -1.5
       and
       short_side_exhaustion
):
       reversal_state = (
           "Oversold Reversal Setup"
       )
elif (
       pd.notna(latest_rsi)
       and
       pd.notna(latest_zscore)
       and
       latest_rsi >= 70
       and
       latest_zscore >= 1.5
       and
       long_side_exhaustion
):
       reversal_state = (
           "Overbought Reversal Setup"
       )
else:
       reversal_state = "No Strong Reversal Setup"
# ============================================================
# V3 DISPLAY
# ============================================================
print()
print(SEPARATOR)
print("V3 SIMILAR-CONDITION HISTORICAL ANALYSIS")
print(SEPARATOR)
print(
       f"Position       : "
       f"{current_position}"
)
print(
       f"Price Return   : "
       f"{latest.get('price_return_pct', np.nan):.2f}%"
       if pd.notna(
           latest.get("price_return_pct")
       )
       else
       "Price Return   : N/A"
)
print(
       f"OI Change      : "
       f"{latest.get('oi_change_pct', np.nan):.2f}%"
       if pd.notna(
           latest.get("oi_change_pct")
       )
       else
       "OI Change      : N/A"
)
print(
       f"Volume Change  : "
       f"{latest_v3.get('volume_change_pct', np.nan):.2f}%"
       if pd.notna(
           latest_v3.get("volume_change_pct")
       )
       else
       "Volume Change  : N/A"
)
print(
       f"RSI(14)        : "
       f"{latest_rsi:.2f}"
       if pd.notna(latest_rsi)
       else
       "RSI(14)        : N/A"
)
print(
       f"Price Z-Score  : "
       f"{latest_zscore:.2f}"
       if pd.notna(latest_zscore)
       else
       "Price Z-Score  : N/A"
)
print(
       f"Reversal State : "
       f"{reversal_state}"
)
# ============================================================
# SIMILAR HISTORICAL CASES
# ============================================================
print()
print("SIMILAR HISTORICAL CASES")
print(SUB_SEPARATOR)
if similar_cases.empty:
       print(
           "No sufficient similar historical "
           "cases available."
       )
else:
       print(
           f"Cases selected : "
           f"{len(similar_cases)}"
       )
       print()
       similar_display_columns = [
           "datetime",
           "position",
           "price_return_pct",
           "oi_change_pct",
           "volume_change_pct",
           "rsi_14",
           "price_zscore_20",
           "future_1_return_pct",
           "future_3_return_pct",
           "future_5_return_pct",
           "similarity_distance",
       ]
       print(
           similar_cases[
               similar_display_columns
           ]
           .to_string(index=False)
       )
       for periods, column in [
           (
               1,
               "future_1_return_pct"
           ),
           (
               3,
               "future_3_return_pct"
           ),
           (
               5,
               "future_5_return_pct"
           ),
       ]:
           future = (
               similar_cases[column]
               .dropna()
           )
           if future.empty:
               continue
           positive = (
               future > 0
           ).sum()
           negative = (
               future < 0
           ).sum()
           print()
           print(
               f"NEXT {periods} PERIOD(S)"
           )
           print(
               f"Positive outcomes : "
               f"{positive / len(future) * 100:.2f}%"
           )
           print(
               f"Negative outcomes : "
               f"{negative / len(future) * 100:.2f}%"
           )
           print(
               f"Average return    : "
               f"{future.mean():.3f}%"
           )
           print(
               f"Median return     : "
               f"{future.median():.3f}%"
           )
           print(
               f"Historical cases  : "
               f"{len(future)}"
           )
# ============================================================
# OVERBOUGHT / OVERSOLD REVERSAL ANALYSIS
# ============================================================
print()
print(SEPARATOR)
print("OVERBOUGHT / OVERSOLD REVERSAL ANALYSIS")
print(SEPARATOR)
print(
       "These are research SETUPS, "
       "not guaranteed reversal signals."
)
print(
       "Oversold setup   : "
       "RSI <= 30, Price Z <= -1.5, "
       "and short-side exhaustion."
)
print(
       "Overbought setup : "
       "RSI >= 70, Price Z >= +1.5, "
       "and long-side exhaustion."
)
print(
       f"CURRENT REVERSAL STATE : "
       f"{reversal_state}"
)
# ============================================================
# REVERSAL HISTORICAL OUTCOMES
# ============================================================
def display_reversal_history(
       title,
       condition
):
       subset = (
           v3_data[
               condition
           ]
           .copy()
       )
       print()
       print(title)
       print(SUB_SEPARATOR)
       if subset.empty:
           print(
               "No historical data."
           )
           return
       for periods, column in [
           (
               1,
               "future_1_return_pct"
           ),
           (
               3,
               "future_3_return_pct"
           ),
           (
               5,
               "future_5_return_pct"
           ),
       ]:
           future = (
               subset[column]
               .dropna()
           )
           if future.empty:
               print(
                   f"Next {periods} period(s): "
                   "no historical data"
               )
               continue
           positive = (
               future > 0
           ).sum()
           negative = (
               future < 0
           ).sum()
           print(
               f"Next {periods} period(s): "
               f"cases={len(future)}, "
               f"positive={positive / len(future) * 100:.2f}%, "
               f"negative={negative / len(future) * 100:.2f}%, "
               f"avg={future.mean():.3f}%"
           )
oversold_condition = (
       (v3_data["rsi_14"] <= 30)
       &
       (v3_data["price_zscore_20"] <= -1.5)
       &
       v3_data["position"].isin(
           [
               "Short Buildup",
               "Long Unwinding",
           ]
       )
)
overbought_condition = (
       (v3_data["rsi_14"] >= 70)
       &
       (v3_data["price_zscore_20"] >= 1.5)
       &
       v3_data["position"].isin(
           [
               "Long Buildup",
               "Short Covering",
           ]
       )
)
display_reversal_history(
       "Oversold Reversal Setup",
       oversold_condition
)
print(
       "Expected reversal direction: "
       "upside"
)
display_reversal_history(
       "Overbought Reversal Setup",
       overbought_condition
)
print(
       "Expected reversal direction: "
       "downside"
)
# ============================================================
# CLOSEST HISTORICAL CONDITIONS
# ============================================================
print()
print(SEPARATOR)
print("CLOSEST HISTORICAL CONDITIONS")
print(SEPARATOR)
if similar_cases.empty:
       print(
           "No comparable historical "
           "conditions available."
       )
else:
       closest_columns = [
           "datetime",
           "position",
           "price_return_pct",
           "oi_change_pct",
           "volume_change_pct",
           "rsi_14",
           "price_zscore_20",
           "future_1_return_pct",
           "future_3_return_pct",
           "future_5_return_pct",
           "similarity_distance",
       ]
       print(
           similar_cases[
               closest_columns
           ]
           .to_string(index=False)
       )
# ============================================================
# ESTIMATED LONG-SIDE / SHORT-SIDE ACTIVITY
# ============================================================
print()
print(SEPARATOR)
print("ESTIMATED LONG-SIDE / SHORT-SIDE ACTIVITY")
print(SEPARATOR)
print(
       "IMPORTANT: These are ESTIMATED activity "
       "percentages, not exact exchange-wide "
       "long/short positions."
)
print(
       "They are derived from price + OI "
       "classification and absolute OI change."
)
activity_data = tf_analysis[
       tf_analysis["position"].isin(
           [
               "Long Buildup",
               "Short Buildup",
               "Short Covering",
               "Long Unwinding",
           ]
       )
].copy()
long_activity = activity_data[
       activity_data["position"].isin(
           [
               "Long Buildup",
               "Short Covering",
           ]
       )
]["oi_change"].abs().sum()
short_activity = activity_data[
       activity_data["position"].isin(
           [
               "Short Buildup",
               "Long Unwinding",
           ]
       )
]["oi_change"].abs().sum()
total_activity = (
       long_activity
       +
       short_activity
)
if total_activity > 0:
       estimated_long_activity = (
           long_activity
           / total_activity
           * 100
       )
       estimated_short_activity = (
           short_activity
           / total_activity
           * 100
       )
else:
       estimated_long_activity = 0
       estimated_short_activity = 0
print(
       f"Estimated Long-side activity  : "
       f"{estimated_long_activity:.2f}%"
)
print(
       f"Estimated Short-side activity : "
       f"{estimated_short_activity:.2f}%"
)
print()
print(
       f"Long-side observation count   : "
       f"{(tf_analysis['position'].isin(['Long Buildup', 'Short Covering'])).sum():,}"
)
print(
       f"Short-side observation count  : "
       f"{(tf_analysis['position'].isin(['Short Buildup', 'Long Unwinding'])).sum():,}"
)
print(
       f"Long-side OI activity value   : "
       f"{long_activity:,.0f}"
)
print(
       f"Short-side OI activity value  : "
       f"{short_activity:,.0f}"
)
# ============================================================
# FINAL STOCK FUTURES ANALYSIS SUMMARY
# ============================================================
historical_cases = len(
       conditional_data
)
if historical_cases > 0:
       historical_probabilities = {
           "Upside": conditional_upside,
           "Sideways": conditional_sideways,
           "Downside": conditional_downside,
       }
       historical_tendency = max(
           historical_probabilities,
           key=historical_probabilities.get
       )
else:
       historical_tendency = (
           "Insufficient Data"
       )
print()
print(SEPARATOR)
print("FINAL STOCK FUTURES ANALYSIS SUMMARY")
print(SEPARATOR)
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
           "Current + Next + Far (signals use CURRENT contract only)"
       )
       print(
           f"Price Contract : "
           f"{current_symbol}"
       )
# ============================================================
# FINAL LATEST MARKET STATE
# ============================================================
print()
print(SUB_SEPARATOR)
print("LATEST MARKET STATE")
print(SUB_SEPARATOR)
print(
       f"Date           : "
       f"{latest['datetime']}"
)
print(
       f"Price          : "
       f"{latest['close']:.2f}"
)
print(
       f"Volume         : "
       f"{latest['volume']}"
)
print(
       f"Open Interest  : "
       f"{latest['open_interest']}"
)
if analysis_mode == "Cumulative":
       print(
           f"3-contract Volume (descriptive): "
           f"{latest.get('combined_3_contract_volume', float('nan'))}"
       )
       print(
           f"3-contract OI (descriptive)    : "
           f"{latest.get('combined_3_contract_open_interest', float('nan'))}"
       )
       print("Note: Position classification uses CURRENT contract OI only.")
print(
       f"Price Return   : "
       f"{latest['price_return_pct']:.2f}%"
       if pd.notna(
           latest["price_return_pct"]
       )
       else
       "Price Return   : N/A"
)
print(
       f"OI Change      : "
       f"{latest['oi_change_pct']:.2f}%"
       if pd.notna(
           latest["oi_change_pct"]
       )
       else
       "OI Change      : N/A"
)
print(
       f"Position       : "
       f"{POSITION_SYMBOLS[current_position]} "
       f"{current_position}"
)
print()
print("Interpretation:")
print(
       POSITION_DESCRIPTION[
           current_position
       ]
)
# ============================================================
# HISTORICAL TENDENCY
# ============================================================
print()
print(SUB_SEPARATOR)
print("HISTORICAL NEXT-PERIOD TENDENCY")
print(SUB_SEPARATOR)
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
print(SUB_SEPARATOR)
print(
       "Note: Historical probabilities describe "
       "past observations only and are not "
       "guaranteed predictions."
)
print(
       "Database was not modified."
)
print(
       "Analysis is based on historical "
       "stock-futures data."
)
print()
print(SEPARATOR)
print("ANALYSIS COMPLETED")
print(SEPARATOR)
