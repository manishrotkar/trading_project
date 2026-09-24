from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_DIR = Path("/home/manish/trading_project/stock_screener")
DB_PATH = PROJECT_DIR / "database" / "nse_stockdata.db"

OUTPUT_PATH = PROJECT_DIR / "notebooks" / "mtf_indicator_scan_results.csv"

EMA_LENGTH = 5
SUPERTREND_LENGTH = 10
SUPERTREND_FACTOR = 3.0


# ============================================================
# SUPERTREND
# ============================================================

def calculate_supertrend(data, length=10, factor=3.0):

    data = data.copy()

    previous_close = data["close"].shift(1)

    tr1 = data["high"] - data["low"]
    tr2 = (data["high"] - previous_close).abs()
    tr3 = (data["low"] - previous_close).abs()

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    atr = true_range.ewm(
        alpha=1 / length,
        adjust=False
    ).mean()

    hl2 = (data["high"] + data["low"]) / 2

    basic_upper = hl2 + factor * atr
    basic_lower = hl2 - factor * atr

    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()

    direction = pd.Series(
        index=data.index,
        dtype="int64"
    )

    supertrend = pd.Series(
        index=data.index,
        dtype="float64"
    )

    direction.iloc[0] = 1
    supertrend.iloc[0] = np.nan

    for i in range(1, len(data)):

        if (
            basic_upper.iloc[i] < final_upper.iloc[i - 1]
            or data["close"].iloc[i - 1] > final_upper.iloc[i - 1]
        ):
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i - 1]

        if (
            basic_lower.iloc[i] > final_lower.iloc[i - 1]
            or data["close"].iloc[i - 1] < final_lower.iloc[i - 1]
        ):
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i - 1]

        if data["close"].iloc[i] > final_upper.iloc[i - 1]:
            direction.iloc[i] = 1

        elif data["close"].iloc[i] < final_lower.iloc[i - 1]:
            direction.iloc[i] = -1

        else:
            direction.iloc[i] = direction.iloc[i - 1]

        if direction.iloc[i] == 1:
            supertrend.iloc[i] = final_lower.iloc[i]
        else:
            supertrend.iloc[i] = final_upper.iloc[i]

    data["Supertrend"] = supertrend
    data["ST_Direction"] = direction

    return data


# ============================================================
# RESAMPLE 1-MINUTE DATA
# ============================================================

def create_timeframe_data(df, timeframe):

    temp = df.copy()
    temp = temp.set_index("datetime")

    candles = temp.resample(timeframe).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    })

    candles = candles.dropna(
        subset=["open", "high", "low", "close"]
    )

    return candles.reset_index()


# ============================================================
# CALCULATE EMA + SUPERTREND
# ============================================================

def calculate_indicators(data):

    data = data.copy()

    data["EMA_5"] = data["close"].ewm(
        span=EMA_LENGTH,
        adjust=False
    ).mean()

    data = calculate_supertrend(
        data,
        length=SUPERTREND_LENGTH,
        factor=SUPERTREND_FACTOR
    )

    data["Above_EMA"] = (
        data["close"] > data["EMA_5"]
    )

    data["Above_Supertrend"] = (
        data["close"] > data["Supertrend"]
    )

    data["Qualified"] = (
        data["Above_EMA"]
        & data["Above_Supertrend"]
    )

    return data


# ============================================================
# GET STOCK LIST FROM DATABASE
# ============================================================

conn = sqlite3.connect(DB_PATH)

stocks_df = pd.read_sql_query(
    """
    SELECT DISTINCT stock
    FROM nse_stockdata
    ORDER BY stock
    """,
    conn
)

stocks = stocks_df["stock"].tolist()

conn.close()

print("=" * 100)
print("MULTI-TIMEFRAME STOCK SCANNER")
print("=" * 100)
print(f"Stocks found in database : {len(stocks)}")
print(f"EMA                     : {EMA_LENGTH}")
print(
    f"Supertrend              : "
    f"Length {SUPERTREND_LENGTH}, Factor {SUPERTREND_FACTOR}"
)
print("=" * 100)


# ============================================================
# SCAN ALL STOCKS
# ============================================================

results = []

for number, stock in enumerate(stocks, start=1):

    print(
        f"[{number}/{len(stocks)}] "
        f"{stock}",
        end=" ... "
    )

    conn = sqlite3.connect(DB_PATH)

    df = pd.read_sql_query(
        """
        SELECT
            datetime,
            open,
            high,
            low,
            close,
            volume
        FROM nse_stockdata
        WHERE stock = ?
        ORDER BY datetime
        """,
        conn,
        params=(stock,)
    )

    conn.close()

    if df.empty:
        print("NO DATA")
        continue

    df["datetime"] = pd.to_datetime(df["datetime"])

    # --------------------------------------------------------
    # 1 DAY
    # --------------------------------------------------------

    daily = create_timeframe_data(df, "1D")

    if len(daily) < EMA_LENGTH:
        print("INSUFFICIENT DATA")
        continue

    daily = calculate_indicators(daily)

    # --------------------------------------------------------
    # 1 WEEK
    # --------------------------------------------------------

    weekly = create_timeframe_data(df, "1W")

    if len(weekly) < EMA_LENGTH:
        print("INSUFFICIENT DATA")
        continue

    weekly = calculate_indicators(weekly)

    # --------------------------------------------------------
    # 1 MONTH
    # --------------------------------------------------------

    monthly = create_timeframe_data(df, "1ME")

    if len(monthly) < EMA_LENGTH:
        print("INSUFFICIENT DATA")
        continue

    monthly = calculate_indicators(monthly)

    # --------------------------------------------------------
    # LATEST CANDLES
    # --------------------------------------------------------

    d = daily.iloc[-1]
    w = weekly.iloc[-1]
    m = monthly.iloc[-1]

    # --------------------------------------------------------
    # REQUIRE ALL THREE TIMEFRAMES
    # --------------------------------------------------------

    daily_ok = (
        d["close"] > d["EMA_5"]
        and d["close"] > d["Supertrend"]
    )

    weekly_ok = (
        w["close"] > w["EMA_5"]
        and w["close"] > w["Supertrend"]
    )

    monthly_ok = (
        m["close"] > m["EMA_5"]
        and m["close"] > m["Supertrend"]
    )

    qualified = (
        daily_ok
        and weekly_ok
        and monthly_ok
    )

    if qualified:

        results.append({
            "Stock": stock,

            "1D_Close": round(d["close"], 2),
            "1D_EMA5": round(d["EMA_5"], 2),
            "1D_Supertrend": round(d["Supertrend"], 2),

            "1W_Close": round(w["close"], 2),
            "1W_EMA5": round(w["EMA_5"], 2),
            "1W_Supertrend": round(w["Supertrend"], 2),

            "1M_Close": round(m["close"], 2),
            "1M_EMA5": round(m["EMA_5"], 2),
            "1M_Supertrend": round(m["Supertrend"], 2),

            "Qualified": "YES"
        })

        print("✅ QUALIFIED")

    else:
        print("—")


# ============================================================
# SAVE RESULTS
# ============================================================

results_df = pd.DataFrame(results)

if not results_df.empty:
    results_df = results_df.sort_values(
        "Stock"
    ).reset_index(drop=True)

results_df.to_csv(
    OUTPUT_PATH,
    index=False
)


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n" + "=" * 100)
print("SCAN COMPLETE")
print("=" * 100)

print(f"Stocks scanned       : {len(stocks)}")
print(f"Qualified stocks     : {len(results_df)}")
print(f"Results saved to     : {OUTPUT_PATH}")

print("=" * 100)

if results_df.empty:

    print("❌ No stock satisfies all 1D + 1W + 1M conditions.")

else:

    print("\nQUALIFIED STOCKS:")
    print("-" * 100)

    print(
        results_df[
            [
                "Stock",
                "1D_Close",
                "1D_EMA5",
                "1D_Supertrend",
                "1W_Close",
                "1W_EMA5",
                "1W_Supertrend",
                "1M_Close",
                "1M_EMA5",
                "1M_Supertrend"
            ]
        ].to_string(index=False)
    )
