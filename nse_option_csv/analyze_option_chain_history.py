import sqlite3
from pathlib import Path

import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATABASE_FILE = (
    BASE_DIR
    / "database"
    / "nse_option_chain.db"
)


# ============================================================
# LOAD SNAPSHOT DATA
# ============================================================

def load_snapshots():

    conn = sqlite3.connect(
        DATABASE_FILE
    )

    query = """
        SELECT
            snapshot_id,
            snapshot_time,
            index_name,
            source_file,
            strikes,
            max_pain,
            reference_strike,

            ce_oi,
            pe_oi,
            pcr_oi,

            ce_change_oi,
            pe_change_oi,
            pcr_change_oi,

            ce_volume,
            pe_volume,
            pcr_volume,

            max_ce_oi_strike,
            max_pe_oi_strike,

            max_ce_change_oi_strike,
            max_pe_change_oi_strike,

            possible_call_writing_strike,
            possible_put_writing_strike,

            possible_call_unwinding_strike,
            possible_put_unwinding_strike

        FROM snapshots

        ORDER BY
            index_name,
            snapshot_time
    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()

    return df


# ============================================================
# PREPARE DATAFRAME
# ============================================================

def prepare_dataframe(df):

    if df.empty:
        return df

    # --------------------------------------------------------
    # Convert timestamp
    # --------------------------------------------------------

    df["snapshot_time"] = pd.to_datetime(
        df["snapshot_time"],
        utc=True
    ).dt.tz_convert(
        "Asia/Kolkata"
    )

    # --------------------------------------------------------
    # Date and market-time columns
    # --------------------------------------------------------

    df["date"] = (
        df["snapshot_time"]
        .dt.strftime("%Y-%m-%d")
    )

    df["time"] = (
        df["snapshot_time"]
        .dt.strftime("%H:%M:%S")
    )

    # --------------------------------------------------------
    # Previous snapshot values
    #
    # Calculated separately for NIFTY and BANKNIFTY
    # --------------------------------------------------------

    df["previous_snapshot_time"] = (
        df.groupby("index_name")[
            "snapshot_time"
        ]
        .shift(1)
    )

    df["previous_pcr_oi"] = (
        df.groupby("index_name")[
            "pcr_oi"
        ]
        .shift(1)
    )

    df["previous_ce_oi"] = (
        df.groupby("index_name")[
            "ce_oi"
        ]
        .shift(1)
    )

    df["previous_pe_oi"] = (
        df.groupby("index_name")[
            "pe_oi"
        ]
        .shift(1)
    )

    df["previous_ce_change_oi"] = (
        df.groupby("index_name")[
            "ce_change_oi"
        ]
        .shift(1)
    )

    df["previous_pe_change_oi"] = (
        df.groupby("index_name")[
            "pe_change_oi"
        ]
        .shift(1)
    )

    # --------------------------------------------------------
    # Change since previous snapshot
    # --------------------------------------------------------

    df["pcr_oi_change"] = (
        df["pcr_oi"]
        - df["previous_pcr_oi"]
    )

    df["ce_oi_change"] = (
        df["ce_oi"]
        - df["previous_ce_oi"]
    )

    df["pe_oi_change"] = (
        df["pe_oi"]
        - df["previous_pe_oi"]
    )

    # --------------------------------------------------------
    # OI balance
    # --------------------------------------------------------

    df["ce_pe_oi_difference"] = (
        df["ce_oi"]
        - df["pe_oi"]
    )

    # --------------------------------------------------------
    # Change OI balance
    # --------------------------------------------------------

    df["ce_pe_change_oi_difference"] = (
        df["ce_change_oi"]
        - df["pe_change_oi"]
    )

    return df


# ============================================================
# SHOW LATEST SNAPSHOT
# ============================================================

def show_latest(df):

    if df.empty:
        print()
        print("No snapshot data found.")
        return

    print()
    print("=" * 72)
    print(" LATEST OPTION CHAIN SNAPSHOT")
    print("=" * 72)

    for index_name in [
        "NIFTY",
        "BANKNIFTY"
    ]:

        data = df[
            df["index_name"]
            == index_name
        ]

        if data.empty:
            continue

        row = data.iloc[-1]

        print()
        print("-" * 72)
        print(index_name)
        print("-" * 72)

        print(
            f"Date             : "
            f"{row['date']}"
        )

        print(
            f"Market time      : "
            f"{row['time']} IST"
        )

        print(
            f"Snapshot ID      : "
            f"{int(row['snapshot_id'])}"
        )

        print(
            f"Reference strike : "
            f"{row['reference_strike']:,.0f}"
        )

        print(
            f"Max Pain         : "
            f"{row['max_pain']:,.0f}"
        )

        print()

        print(
            f"CE OI            : "
            f"{row['ce_oi']:,.0f}"
        )

        print(
            f"PE OI            : "
            f"{row['pe_oi']:,.0f}"
        )

        print(
            f"OI PCR           : "
            f"{row['pcr_oi']:.3f}"
        )

        print()

        print(
            f"CE Change OI     : "
            f"{row['ce_change_oi']:+,.0f}"
        )

        print(
            f"PE Change OI     : "
            f"{row['pe_change_oi']:+,.0f}"
        )

        print(
            f"Change OI PCR    : "
            f"{row['pcr_change_oi']:.3f}"
        )

        print()

        print(
            f"CE Volume        : "
            f"{row['ce_volume']:,.0f}"
        )

        print(
            f"PE Volume        : "
            f"{row['pe_volume']:,.0f}"
        )

        print(
            f"Volume PCR       : "
            f"{row['pcr_volume']:.3f}"
        )

        print()

        print(
            f"Max CE OI strike : "
            f"{row['max_ce_oi_strike']:,.0f}"
        )

        print(
            f"Max PE OI strike : "
            f"{row['max_pe_oi_strike']:,.0f}"
        )

        print(
            f"Max CE Chg OI    : "
            f"{row['max_ce_change_oi_strike']:,.0f}"
        )

        print(
            f"Max PE Chg OI    : "
            f"{row['max_pe_change_oi_strike']:,.0f}"
        )


# ============================================================
# SHOW SNAPSHOT HISTORY
# ============================================================

def show_history(df):

    if df.empty:
        return

    print()
    print("=" * 72)
    print(" SNAPSHOT HISTORY")
    print("=" * 72)

    columns = [
        "index_name",
        "date",
        "time",
        "reference_strike",
        "max_pain",
        "pcr_oi",
        "ce_oi",
        "pe_oi",
        "ce_change_oi",
        "pe_change_oi",
        "pcr_volume"
    ]

    history = df[columns].copy()

    history["reference_strike"] = (
        history["reference_strike"]
        .round(0)
    )

    history["max_pain"] = (
        history["max_pain"]
        .round(0)
    )

    history["pcr_oi"] = (
        history["pcr_oi"]
        .round(3)
    )

    history["pcr_volume"] = (
        history["pcr_volume"]
        .round(3)
    )

    print(
        history.to_string(
            index=False
        )
    )


# ============================================================
# SHOW CHANGES FROM PREVIOUS SNAPSHOT
# ============================================================

def show_previous_changes(df):

    if df.empty:
        return

    print()
    print("=" * 72)
    print(" CHANGE FROM PREVIOUS SNAPSHOT")
    print("=" * 72)

    for index_name in [
        "NIFTY",
        "BANKNIFTY"
    ]:

        data = df[
            df["index_name"]
            == index_name
        ]

        if len(data) < 2:
            continue

        row = data.iloc[-1]

        print()
        print("-" * 72)
        print(index_name)
        print("-" * 72)

        print(
            f"Previous time    : "
            f"{row['previous_snapshot_time']}"
        )

        print(
            f"Current time     : "
            f"{row['snapshot_time']}"
        )

        print()

        print(
            f"PCR change       : "
            f"{row['pcr_oi_change']:+.3f}"
        )

        print(
            f"CE OI change     : "
            f"{row['ce_oi_change']:+,.0f}"
        )

        print(
            f"PE OI change     : "
            f"{row['pe_oi_change']:+,.0f}"
        )

        print(
            f"OI balance       : "
            f"{row['ce_pe_oi_difference']:+,.0f}"
        )

        print(
            f"Change OI balance: "
            f"{row['ce_pe_change_oi_difference']:+,.0f}"
        )


# ============================================================
# SAVE ANALYSIS DATAFRAME
# ============================================================

def save_dataframe(df):

    if df.empty:
        return

    output_file = (
        BASE_DIR
        / "database"
        / "option_chain_analysis.csv"
    )

    df.to_csv(
        output_file,
        index=False
    )

    print()
    print(
        f"Analysis DataFrame saved to:"
    )

    print(
        output_file
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 72)
    print(" OPTION CHAIN HISTORICAL ANALYSIS")
    print(" Pandas + SQLite")
    print("=" * 72)

    if not DATABASE_FILE.exists():

        print()
        print(
            "Database not found:"
        )

        print(
            DATABASE_FILE
        )

        return

    df = load_snapshots()

    if df.empty:

        print()
        print(
            "No snapshots found in database."
        )

        return

    df = prepare_dataframe(
        df
    )

    print()
    print(
        f"Total snapshots : {len(df)}"
    )

    print(
        f"NIFTY snapshots : "
        f"{len(df[df['index_name'] == 'NIFTY'])}"
    )

    print(
        f"BANKNIFTY       : "
        f"{len(df[df['index_name'] == 'BANKNIFTY'])}"
    )

    show_latest(df)

    show_history(df)

    show_previous_changes(df)

    # Uncomment when you want a CSV export
    # save_dataframe(df)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()