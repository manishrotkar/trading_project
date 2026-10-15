from pathlib import Path
import sqlite3

import pandas as pd


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_PATH = (
    PROJECT_ROOT
    / "option_analysis"
    / "database"
    / "oi_analysis.db"
)

CSV_PATH = (
    PROJECT_ROOT
    / "option_analysis"
    / "database"
    / "market_state_hourly_analysis.csv"
)


# ============================================================
# STATE FUNCTIONS
# ============================================================

def price_state(change):
    if pd.isna(change):
        return None

    if change > 0:
        return "UP"

    if change < 0:
        return "DOWN"

    return "FLAT"


def oi_state(change):
    if pd.isna(change):
        return None

    if change > 0:
        return "OI_BUILDUP"

    if change < 0:
        return "OI_REDUCTION"

    return "FLAT"


def pcr_state(pcr):
    if pd.isna(pcr):
        return None

    if pcr < 0.80:
        return "LOW"

    if pcr <= 1.20:
        return "NORMAL"

    return "HIGH"


def iv_rank_state(iv_rank):
    if pd.isna(iv_rank):
        return None

    if iv_rank < 25:
        return "LOW"

    if iv_rank < 50:
        return "MEDIUM"

    if iv_rank < 75:
        return "HIGH"

    return "VERY_HIGH"


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("HOURLY MARKET STATE ANALYSIS")
    print("=" * 80)

    print(f"\nDatabase : {DB_PATH}")
    print(f"CSV file : {CSV_PATH}")

    # --------------------------------------------------------
    # READ ONLY DATABASE CONNECTION
    # --------------------------------------------------------

    conn = sqlite3.connect(
        f"file:{DB_PATH}?mode=ro",
        uri=True,
    )

    try:

        # ----------------------------------------------------
        # READ COMBINED MARKET ANALYSIS
        # ----------------------------------------------------

        query = """
            SELECT
                index_name,
                expiry,
                datetime,
                futures_price,
                ce_activity_balance_pm5,
                pe_activity_balance_pm5,
                total_pcr,
                atm_iv,
                iv_rank,
                iv_percentile
            FROM combined_market_analysis
            ORDER BY
                index_name,
                datetime
        """

        df = pd.read_sql_query(
            query,
            conn,
        )

    finally:

        conn.close()


    # ========================================================
    # BASIC DATA CLEANING
    # ========================================================

    if df.empty:

        print("\nNo data found.")

        return

    df["datetime"] = pd.to_datetime(
        df["datetime"]
    )

    df["date"] = df["datetime"].dt.date

    df["hour"] = df["datetime"].dt.hour


    # ========================================================
    # HOURLY AGGREGATION
    # ========================================================

    hourly_rows = []

    grouped = df.groupby(
        [
            "index_name",
            "expiry",
            "date",
            "hour",
        ],
        sort=True,
    )


    for (
        index_name,
        expiry,
        trading_date,
        hour,
    ), group in grouped:

        group = group.sort_values(
            "datetime"
        )

        # ----------------------------------------------------
        # First and last observation of the hour
        # ----------------------------------------------------

        first_row = group.iloc[0]

        last_row = group.iloc[-1]

        first_price = first_row[
            "futures_price"
        ]

        last_price = last_row[
            "futures_price"
        ]

        # ----------------------------------------------------
        # Hourly price change
        # ----------------------------------------------------

        price_change = (
            last_price - first_price
        )

        if first_price:

            price_change_pct = (
                price_change
                / first_price
                * 100
            )

        else:

            price_change_pct = None


        # ----------------------------------------------------
        # Hourly activity balance
        #
        # Sum of all 1-minute activity balances
        # ----------------------------------------------------

        ce_activity = group[
            "ce_activity_balance_pm5"
        ].sum(
            min_count=1
        )

        pe_activity = group[
            "pe_activity_balance_pm5"
        ].sum(
            min_count=1
        )


        # ----------------------------------------------------
        # Last available PCR / IV values
        # ----------------------------------------------------

        last_pcr = last_row[
            "total_pcr"
        ]

        last_iv = last_row[
            "atm_iv"
        ]

        last_iv_rank = last_row[
            "iv_rank"
        ]

        last_iv_percentile = last_row[
            "iv_percentile"
        ]


        # ----------------------------------------------------
        # Build hourly row
        # ----------------------------------------------------

        hourly_rows.append(
            {
                "index_name": index_name,

                "expiry": expiry,

                "date": trading_date,

                "hour": hour,

                "hour_start": group[
                    "datetime"
                ].min(),

                "hour_end": group[
                    "datetime"
                ].max(),

                "first_futures_price": first_price,

                "last_futures_price": last_price,

                "price_change": price_change,

                "price_change_pct": price_change_pct,

                "price_state": price_state(
                    price_change
                ),

                "ce_activity_balance": ce_activity,

                "pe_activity_balance": pe_activity,

                "ce_oi_state": oi_state(
                    ce_activity
                ),

                "pe_oi_state": oi_state(
                    pe_activity
                ),

                "total_pcr": last_pcr,

                "pcr_state": pcr_state(
                    last_pcr
                ),

                "atm_iv": last_iv,

                "iv_rank": last_iv_rank,

                "iv_percentile": last_iv_percentile,

                "iv_rank_state": iv_rank_state(
                    last_iv_rank
                ),

                "minute_observations": len(
                    group
                ),
            }
        )


    # ========================================================
    # CREATE DATAFRAME
    # ========================================================

    hourly_df = pd.DataFrame(
        hourly_rows
    )


    # ========================================================
    # SORT
    # ========================================================

    hourly_df = hourly_df.sort_values(
        [
            "index_name",
            "hour_start",
        ]
    ).reset_index(
        drop=True
    )


    # ========================================================
    # ROUND NUMERIC VALUES
    # ========================================================

    hourly_df["first_futures_price"] = (
        hourly_df[
            "first_futures_price"
        ].round(2)
    )

    hourly_df["last_futures_price"] = (
        hourly_df[
            "last_futures_price"
        ].round(2)
    )

    hourly_df["price_change"] = (
        hourly_df[
            "price_change"
        ].round(2)
    )

    hourly_df["price_change_pct"] = (
        hourly_df[
            "price_change_pct"
        ].round(4)
    )

    hourly_df["total_pcr"] = (
        hourly_df[
            "total_pcr"
        ].round(4)
    )

    hourly_df["atm_iv"] = (
        hourly_df[
            "atm_iv"
        ].round(6)
    )

    hourly_df["iv_rank"] = (
        hourly_df[
            "iv_rank"
        ].round(2)
    )

    hourly_df["iv_percentile"] = (
        hourly_df[
            "iv_percentile"
        ].round(2)
    )


    # ========================================================
    # SAVE CSV
    # ========================================================

    hourly_df.to_csv(
        CSV_PATH,
        index=False,
    )


    # ========================================================
    # SUMMARY
    # ========================================================

    print("\n" + "=" * 80)
    print("HOURLY DATA SUMMARY")
    print("=" * 80)

    print(
        f"\nRows created : {len(hourly_df):,}"
    )

    print(
        f"CSV saved    : {CSV_PATH}"
    )


    # ========================================================
    # DISPLAY CLEAN DATAFRAME
    # ========================================================

    display_columns = [
        "index_name",
        "date",
        "hour",
        "price_state",
        "ce_oi_state",
        "pe_oi_state",
        "ce_activity_balance",
        "pe_activity_balance",
        "total_pcr",
        "pcr_state",
        "atm_iv",
        "iv_rank",
        "iv_rank_state",
    ]


    print("\n" + "=" * 80)
    print("HOURLY MARKET INTERPRETATION")
    print("=" * 80)

    print(
        hourly_df[
            display_columns
        ].to_string(
            index=False
        )
    )


    # ========================================================
    # LATEST HOUR
    # ========================================================

    latest_time = hourly_df[
        "hour_end"
    ].max()


    latest_df = hourly_df[
        hourly_df["hour_end"] == latest_time
    ]


    print("\n" + "=" * 80)
    print(
        f"LATEST HOURLY STATE : {latest_time}"
    )
    print("=" * 80)

    print(
        latest_df[
            display_columns
        ].to_string(
            index=False
        )
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()