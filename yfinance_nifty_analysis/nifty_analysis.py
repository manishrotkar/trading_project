"""
Small project: download one month of NIFTY 50 (^NSEI) daily data with yfinance,
save it as CSV, load it with pandas, and print a descriptive-analysis report.
"""

import numpy as np
import pandas as pd
import yfinance as yf

CSV_PATH = "nifty50_1mo.csv"
TICKER = "^NSEI"


def download_data() -> pd.DataFrame:
    """Download one month of daily OHLCV data and save it as CSV."""
    df = yf.download(TICKER, period="1mo", interval="1d", progress=False)
    # yfinance may return MultiIndex columns; flatten them
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.to_csv(CSV_PATH)
    return df


def load_data(path: str = CSV_PATH) -> pd.DataFrame:
    """Load the saved CSV with pandas."""
    return pd.read_csv(path, index_col=0, parse_dates=True)


def analyze(df: pd.DataFrame) -> dict:
    """Compute descriptive statistics from the OHLCV data.

    Daily returns use pct_change(), so the first day's return is NaN
    because there is no previous trading day to compare against.
    """
    close = df["Close"]
    daily_ret = close.pct_change() * 100  # daily return in %

    return {
        "trading_days": int(len(df)),
        "start_date": df.index[0].date(),
        "end_date": df.index[-1].date(),
        "first_close": float(close.iloc[0]),
        "last_close": float(close.iloc[-1]),
        "highest_high": float(df["High"].max()),
        "lowest_low": float(df["Low"].min()),
        "avg_close": float(close.mean()),
        "avg_volume": float(df["Volume"].mean()),
        "total_return_pct": float((close.iloc[-1] / close.iloc[0] - 1) * 100),
        "avg_daily_return_pct": float(daily_ret.dropna().mean()),
        "best_daily_return_pct": float(daily_ret.max()),
        "worst_daily_return_pct": float(daily_ret.min()),
        "daily_return_std": float(daily_ret.std()),
        "positive_days": int((daily_ret > 0).sum()),
        "negative_days": int((daily_ret < 0).sum()),
    }


def print_report(stats: dict) -> None:
    """Print a clean descriptive-analysis report."""
    print("=" * 46)
    print(f"{'NIFTY 50 (^NSEI) - Descriptive Analysis':^46}")
    print("=" * 46)
    print(f"Trading days            : {stats['trading_days']}")
    print(f"Start date              : {stats['start_date']}")
    print(f"End date                : {stats['end_date']}")
    print("-" * 46)
    print(f"First close             : {stats['first_close']:,.2f}")
    print(f"Last close              : {stats['last_close']:,.2f}")
    print(f"Highest high            : {stats['highest_high']:,.2f}")
    print(f"Lowest low              : {stats['lowest_low']:,.2f}")
    print(f"Average close           : {stats['avg_close']:,.2f}")
    print(f"Average daily volume    : {stats['avg_volume']:,.0f}")
    print("-" * 46)
    print(f"Total return            : {stats['total_return_pct']:.2f}%")
    print(f"Avg daily return        : {stats['avg_daily_return_pct']:.2f}%")
    print(f"Best daily return       : {stats['best_daily_return_pct']:.2f}%")
    print(f"Worst daily return      : {stats['worst_daily_return_pct']:.2f}%")
    print(f"Daily return std dev    : {stats['daily_return_std']:.2f}%")
    print(f"Positive days           : {stats['positive_days']}")
    print(f"Negative days           : {stats['negative_days']}")
    print("=" * 46)


if __name__ == "__main__":
    data = download_data()
    data = load_data()  # load it back with pandas, as required
    print_report(analyze(data))
