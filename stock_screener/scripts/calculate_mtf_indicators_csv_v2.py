from pathlib import Path
import sqlite3
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

CSV_PATH = BASE_DIR / "notebooks" / "above_price_scanner_results.csv"
DB_PATH = BASE_DIR / "database" / "nse_stockdata.db"

OUTPUT_PATH = (
    BASE_DIR / "notebooks" / "mtf_indicator_scan_csv_v5_results.csv"
)


# ============================================================
# SETTINGS
# ============================================================

MA_LENGTH = 5

SUPERTREND_LENGTH = 10
SUPERTREND_FACTOR = 3.0

# Enough history for reliable weekly Supertrend
LOOKBACK_DAYS = 365


# ============================================================
# WILDER RMA
# ============================================================

def calculate_rma(series, length):

    return series.ewm(
        alpha=1 / length,
        adjust=False,
        min_periods=length,
    ).mean()


# ============================================================
# SUPERTREND
# ============================================================

def calculate_supertrend(
    df,
    length=10,
    factor=3.0,
):

    df = df.copy()

    high = df["high"]
    low = df["low"]
    close = df["close"]

    previous_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - previous_close).abs()
    tr3 = (low - previous_close).abs()

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1,
    ).max(axis=1)

    atr = calculate_rma(
        true_range,
        length,
    )

    hl2 = (high + low) / 2

    basic_upper = hl2 + factor * atr
    basic_lower = hl2 - factor * atr

    final_upper = pd.Series(
        np.nan,
        index=df.index,
        dtype=float,
    )

    final_lower = pd.Series(
        np.nan,
        index=df.index,
        dtype=float,
    )

    supertrend = pd.Series(
        np.nan,
        index=df.index,
        dtype=float,
    )

    direction = pd.Series(
        np.nan,
        index=df.index,
        dtype=float,
    )

    for i in range(len(df)):

        if pd.isna(atr.iloc[i]):
            continue

        # First ATR-valid candle
        if i == 0 or pd.isna(final_upper.iloc[i - 1]):

            final_upper.iloc[i] = basic_upper.iloc[i]
            final_lower.iloc[i] = basic_lower.iloc[i]

            if close.iloc[i] > final_upper.iloc[i]:
                direction.iloc[i] = 1
                supertrend.iloc[i] = final_lower.iloc[i]
            else:
                direction.iloc[i] = -1
                supertrend.iloc[i] = final_upper.iloc[i]

            continue

        # ----------------------------------------------------
        # FINAL UPPER BAND
        # ----------------------------------------------------

        if (
            basic_upper.iloc[i] < final_upper.iloc[i - 1]
            or close.iloc[i - 1] > final_upper.iloc[i - 1]
        ):

            final_upper.iloc[i] = basic_upper.iloc[i]

        else:

            final_upper.iloc[i] = final_upper.iloc[i - 1]

        # ----------------------------------------------------
        # FINAL LOWER BAND
        # ----------------------------------------------------

        if (
            basic_lower.iloc[i] > final_lower.iloc[i - 1]
            or close.iloc[i - 1] < final_lower.iloc[i - 1]
        ):

            final_lower.iloc[i] = basic_lower.iloc[i]

        else:

            final_lower.iloc[i] = final_lower.iloc[i - 1]

        # ----------------------------------------------------
        # TREND
        # ----------------------------------------------------

        if direction.iloc[i - 1] == -1:

            if close.iloc[i] > final_upper.iloc[i]:

                direction.iloc[i] = 1

            else:

                direction.iloc[i] = -1

        else:

            if close.iloc[i] < final_lower.iloc[i]:

                direction.iloc[i] = -1

            else:

                direction.iloc[i] = 1

        # ----------------------------------------------------
        # SUPERTREND
        # ----------------------------------------------------

        if direction.iloc[i] == 1:

            supertrend.iloc[i] = final_lower.iloc[i]

        else:

            supertrend.iloc[i] = final_upper.iloc[i]

    df["supertrend"] = supertrend
    df["st_direction"] = direction

    return df


# ============================================================
# LOAD SYMBOLS
# ============================================================

def load_symbols():

    df = pd.read_csv(CSV_PATH)

    if "Symbol" not in df.columns:

        raise ValueError(
            "Column 'Symbol' not found in scanner CSV."
        )

    return (
        df["Symbol"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )


# ============================================================
# LOAD RAW DATA
# ============================================================

def load_stock_data(
    conn,
    symbol,
    start_datetime,
):

    query = """
        SELECT
            datetime,
            open,
            high,
            low,
            close,
            volume
        FROM nse_stockdata
        WHERE symbol = ?
          AND datetime >= ?
        ORDER BY datetime ASC
    """

    df = pd.read_sql_query(
        query,
        conn,
        params=[
            symbol,
            start_datetime.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        ],
    )

    if df.empty:

        return df

    df["datetime"] = pd.to_datetime(
        df["datetime"],
        errors="coerce",
    )

    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(
        subset=[
            "datetime",
            "open",
            "high",
            "low",
            "close",
        ]
    )

    df = df.drop_duplicates(
        subset=["datetime"]
    )

    return df.sort_values(
        "datetime"
    )


# ============================================================
# RESAMPLE
# ============================================================

def resample_ohlcv(
    df,
    timeframe,
):

    x = df.copy()

    x = x.set_index(
        "datetime"
    )

    candles = x.resample(
        timeframe
    ).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )

    candles = candles.dropna(
        subset=[
            "open",
            "high",
            "low",
            "close",
        ]
    )

    return candles


# ============================================================
# REMOVE INCOMPLETE CANDLES
# ============================================================

def remove_incomplete_candles(
    df,
    timeframe,
):

    if df.empty:

        return df

    now = pd.Timestamp.now()

    # --------------------------------------------------------
    # HOURLY
    # --------------------------------------------------------

    if timeframe == "1h":

        current_hour = now.floor("h")

        return df[
            df.index < current_hour
        ]

    # --------------------------------------------------------
    # DAILY
    # --------------------------------------------------------

    if timeframe == "1D":

        today = now.normalize()

        return df[
            df.index < today
        ]

    # --------------------------------------------------------
    # WEEKLY
    # --------------------------------------------------------

    if timeframe == "1W":

        current_week_start = (
            now.normalize()
            - pd.Timedelta(
                days=now.weekday()
            )
        )

        return df[
            df.index < current_week_start
        ]

    return df


# ============================================================
# ANALYZE TIMEFRAME
# ============================================================

def analyze_timeframe(
    raw_df,
    timeframe,
):

    candles = resample_ohlcv(
        raw_df,
        timeframe,
    )

    candles = remove_incomplete_candles(
        candles,
        timeframe,
    )

    candle_count = len(candles)

    # Need:
    # 10 candles for Supertrend
    # 5 candles for SMA
    # Extra warm-up
    if candle_count < 15:

        return None, candle_count

    candles = calculate_supertrend(
        candles,
        length=SUPERTREND_LENGTH,
        factor=SUPERTREND_FACTOR,
    )

    candles["ma5"] = (
        candles["close"]
        .rolling(
            MA_LENGTH
        )
        .mean()
    )

    latest = candles.iloc[-1]

    if pd.isna(
        latest["ma5"]
    ):

        return None, candle_count

    if pd.isna(
        latest["supertrend"]
    ):

        return None, candle_count

    close = float(
        latest["close"]
    )

    ma5 = float(
        latest["ma5"]
    )

    supertrend = float(
        latest["supertrend"]
    )

    return {
        "date": candles.index[-1],
        "close": close,
        "ma5": ma5,
        "supertrend": supertrend,
        "close_above_ma5": close > ma5,
        "close_above_supertrend": close > supertrend,
    }, candle_count


# ============================================================
# MAIN
# ============================================================

def main():

    timer_start = time.perf_counter()

    start_time = datetime.now()

    print("=" * 115)
    print(
        "MULTI-TIMEFRAME STOCK SCANNER - V5"
    )
    print("=" * 115)

    print(
        f"Input CSV          : {CSV_PATH}"
    )

    print(
        f"Database           : {DB_PATH}"
    )

    print(
        f"Output CSV         : {OUTPUT_PATH}"
    )

    print(
        "5-Candle Average   : Close SMA(5)"
    )

    print(
        "Supertrend         : 10,3.0"
    )

    print(
        "Timeframes         : 1H + 1D + 1W"
    )

    print(
        "Monthly            : DISABLED"
    )

    print(
        f"Data Lookback      : "
        f"{LOOKBACK_DAYS} calendar days"
    )

    print("=" * 115)

    symbols = load_symbols()

    total_stocks = len(symbols)

    print(
        f"Stocks from CSV    : {total_stocks}"
    )

    print(
        f"START TIME         : "
        f"{start_time.strftime('%H:%M:%S')}"
    )

    print("=" * 115)

    conn = sqlite3.connect(
        DB_PATH
    )

    start_datetime = (
        datetime.now()
        - timedelta(
            days=LOOKBACK_DAYS
        )
    )

    qualified_results = []

    no_data_count = 0
    insufficient_count = 0

    # ========================================================
    # SCAN
    # ========================================================

    for number, symbol in enumerate(
        symbols,
        start=1,
    ):

        print(
            f"[{number}/{total_stocks}] "
            f"{symbol} ... ",
            end="",
            flush=True,
        )

        try:

            raw_df = load_stock_data(
                conn,
                symbol,
                start_datetime,
            )

            if raw_df.empty:

                no_data_count += 1

                print(
                    "NO DB DATA"
                )

                continue

            # ------------------------------------------------
            # TIMEFRAMES
            # ------------------------------------------------

            h1, h1_count = analyze_timeframe(
                raw_df,
                "1h",
            )

            d1, d1_count = analyze_timeframe(
                raw_df,
                "1D",
            )

            w1, w1_count = analyze_timeframe(
                raw_df,
                "1W",
            )

            # ------------------------------------------------
            # DATA CHECK
            # ------------------------------------------------

            if (
                h1 is None
                or d1 is None
                or w1 is None
            ):

                insufficient_count += 1

                print(
                    "INSUFFICIENT "
                    f"(1H:{h1_count}, "
                    f"1D:{d1_count}, "
                    f"1W:{w1_count})"
                )

                continue

            # ------------------------------------------------
            # SIX CONDITIONS
            # ------------------------------------------------

            qualified = (
                h1["close_above_ma5"]
                and h1["close_above_supertrend"]
                and d1["close_above_ma5"]
                and d1["close_above_supertrend"]
                and w1["close_above_ma5"]
                and w1["close_above_supertrend"]
            )

            if qualified:

                qualified_results.append(
                    {
                        "Stock": symbol,

                        "1H_Date": h1["date"],
                        "1H_Close": h1["close"],
                        "1H_MA5": h1["ma5"],
                        "1H_Supertrend": h1["supertrend"],

                        "1D_Date": d1["date"],
                        "1D_Close": d1["close"],
                        "1D_MA5": d1["ma5"],
                        "1D_Supertrend": d1["supertrend"],

                        "1W_Date": w1["date"],
                        "1W_Close": w1["close"],
                        "1W_MA5": w1["ma5"],
                        "1W_Supertrend": w1["supertrend"],

                        "Qualified": "YES",
                    }
                )

                print(
                    "QUALIFIED"
                )

            else:

                print(
                    "—"
                )

        except Exception as error:

            print(
                f"ERROR: "
                f"{type(error).__name__}: "
                f"{error}"
            )

    conn.close()

    # ========================================================
    # SAVE
    # ========================================================

    columns = [
        "Stock",

        "1H_Date",
        "1H_Close",
        "1H_MA5",
        "1H_Supertrend",

        "1D_Date",
        "1D_Close",
        "1D_MA5",
        "1D_Supertrend",

        "1W_Date",
        "1W_Close",
        "1W_MA5",
        "1W_Supertrend",

        "Qualified",
    ]

    result_df = pd.DataFrame(
        qualified_results,
        columns=columns,
    )

    result_df.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    # ========================================================
    # TIMER
    # ========================================================

    end_time = datetime.now()

    elapsed = (
        time.perf_counter()
        - timer_start
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 115)
    print("SCAN COMPLETE")
    print("=" * 115)

    print(
        f"Stocks in scanner CSV : "
        f"{total_stocks}"
    )

    print(
        f"Qualified stocks      : "
        f"{len(result_df)}"
    )

    print(
        f"No DB data            : "
        f"{no_data_count}"
    )

    print(
        f"Insufficient data     : "
        f"{insufficient_count}"
    )

    print(
        f"Output                : "
        f"{OUTPUT_PATH}"
    )

    print()
    print(
        f"START TIME            : "
        f"{start_time.strftime('%H:%M:%S')}"
    )

    print(
        f"END TIME              : "
        f"{end_time.strftime('%H:%M:%S')}"
    )

    print(
        f"TOTAL TIME            : "
        f"{elapsed:.2f} seconds"
    )

    print(
        f"AVERAGE / STOCK       : "
        f"{elapsed / total_stocks:.3f} seconds"
    )

    print("=" * 115)

    # ========================================================
    # QUALIFIED STOCKS
    # ========================================================

    if not result_df.empty:

        print()
        print(
            "QUALIFIED STOCKS"
        )

        print("-" * 115)

        print(
            result_df.to_string(
                index=False
            )
        )

    else:

        print()
        print(
            "NO STOCKS QUALIFIED"
        )

    print("=" * 115)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
