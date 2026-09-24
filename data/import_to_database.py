import sqlite3
import pandas as pd


DATABASE_FILE = "data/database/market_data.db"


def import_parquet(parquet_file, asset_type, symbol):
    print(f"\n📥 Importing {symbol}")
    print("=" * 50)

    df = pd.read_parquet(parquet_file)

    print(f"Rows loaded: {len(df):,}")

    df["asset_type"] = asset_type
    df["symbol"] = symbol
    df["datetime"] = df["datetime"].astype(str)

    df = df[
        [
            "asset_type",
            "symbol",
            "datetime",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ]

    connection = sqlite3.connect(DATABASE_FILE)

    try:
        before_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM market_data
            WHERE asset_type = ? AND symbol = ?
            """,
            (asset_type, symbol),
        ).fetchone()[0]

        rows = df.itertuples(index=False, name=None)

        connection.executemany(
            """
            INSERT OR IGNORE INTO market_data
            (
                asset_type,
                symbol,
                datetime,
                open,
                high,
                low,
                close,
                volume
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

        connection.commit()

        after_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM market_data
            WHERE asset_type = ? AND symbol = ?
            """,
            (asset_type, symbol),
        ).fetchone()[0]

        new_rows = after_count - before_count
        duplicates = len(df) - new_rows

        print(f"📊 New rows inserted: {new_rows:,}")
        print(f"🔁 Duplicates skipped: {duplicates:,}")
        print("✅ Import completed.")

    finally:
        connection.close()


if __name__ == "__main__":
    import_parquet(
        "data/index/raw/nifty50_1m.parquet",
        "index",
        "NIFTY50",
    )