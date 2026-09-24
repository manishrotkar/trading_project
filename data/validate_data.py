import pandas as pd


FILE_PATH = "data/index/raw/nifty50_1m.parquet"

def main():
    df = pd.read_parquet(FILE_PATH)

    print("\n📊 HISTORICAL DATA QUALITY REPORT")
    print("=" * 50)

    # --------------------------------------------------
    # Basic information
    # --------------------------------------------------

    print("\n📅 DATA RANGE")
    print("-" * 50)
    print(f"Start:         {df['datetime'].min()}")
    print(f"End:           {df['datetime'].max()}")
    print(f"Total candles: {len(df):,}")
    print(f"Trading days:  {df['datetime'].dt.date.nunique():,}")

    # --------------------------------------------------
    # Duplicate timestamps
    # --------------------------------------------------

    duplicates = df["datetime"].duplicated().sum()

    print("\n🔁 DUPLICATES")
    print("-" * 50)
    print(f"Duplicate timestamps: {duplicates:,}")

    # --------------------------------------------------
    # Chronological order
    # --------------------------------------------------

    chronological = df["datetime"].is_monotonic_increasing

    print("\n⏱️ TIMESTAMP ORDER")
    print("-" * 50)
    print(f"Chronological order: {chronological}")

    # --------------------------------------------------
    # Missing values
    # --------------------------------------------------

    missing = df.isna().sum()

    print("\n❓ MISSING VALUES")
    print("-" * 50)

    total_missing = missing.sum()

    if total_missing == 0:
        print("Missing values: 0")
    else:
        print(missing[missing > 0].to_string())

    # --------------------------------------------------
    # OHLC structural anomalies
    # --------------------------------------------------

    bad_ohlc = df[
        (df["high"] < df["open"]) |
        (df["high"] < df["close"]) |
        (df["low"] > df["open"]) |
        (df["low"] > df["close"])
    ]

    print("\n📈 OHLC CHECK")
    print("-" * 50)
    print(f"OHLC anomalies: {len(bad_ohlc):,}")

    if len(bad_ohlc) > 0:
        print("\nAffected dates:")

        affected_dates = (
            bad_ohlc.groupby(
                bad_ohlc["datetime"].dt.date
            )
            .size()
            .sort_values(ascending=False)
        )

        print(affected_dates.to_string())

    # --------------------------------------------------
    # Intraday gaps
    # --------------------------------------------------

    df["date"] = df["datetime"].dt.date

    df["minute_diff"] = (
        df.groupby("date")["datetime"]
        .diff()
        .dt.total_seconds()
        .div(60)
    )

    gaps = df[df["minute_diff"] > 1]

    print("\n⏳ INTRADAY GAPS")
    print("-" * 50)
    print(f"Intraday gaps: {len(gaps):,}")

    if len(gaps) > 0:
        print("\nDetected gaps:")

        print(
            gaps[
                ["datetime", "minute_diff"]
            ]
            .to_string(index=False)
        )

    # --------------------------------------------------
    # Candles per trading day
    # --------------------------------------------------

    daily_counts = df.groupby("date").size()

    print("\n📊 CANDLES PER DAY")
    print("-" * 50)
    print(f"Minimum: {daily_counts.min()}")
    print(f"Maximum: {daily_counts.max()}")
    print(f"Average: {daily_counts.mean():.2f}")

    short_days = daily_counts[daily_counts < 375]

    print(f"Days with < 375 candles: {len(short_days)}")

    # --------------------------------------------------
    # Volume information
    # --------------------------------------------------

    print("\n📦 VOLUME")
    print("-" * 50)
    print(f"Total volume: {df['volume'].sum():,.0f}")
    print(f"Zero-volume candles: {(df['volume'] == 0).sum():,}")

    # --------------------------------------------------
    # Final status
    # --------------------------------------------------

    print("\n" + "=" * 50)
    print("✅ DATASET AUDIT COMPLETED")
    print("=" * 50)


if __name__ == "__main__":
    main()
