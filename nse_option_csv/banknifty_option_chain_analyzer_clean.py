import csv
import hashlib
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
DATABASE_DIR = BASE_DIR / "database"

DATABASE_FILE = DATABASE_DIR / "nse_option_chain.db"


# ============================================================
# NSE CSV COLUMN MAPPING
# ============================================================

COLUMNS = [
    "ce_oi",
    "ce_change_oi",
    "ce_volume",
    "ce_iv",
    "ce_ltp",
    "ce_change",
    "ce_bid_qty",
    "ce_bid",
    "ce_ask",
    "ce_ask_qty",
    "strike",
    "pe_bid_qty",
    "pe_bid",
    "pe_ask",
    "pe_ask_qty",
    "pe_change",
    "pe_ltp",
    "pe_iv",
    "pe_volume",
    "pe_change_oi",
    "pe_oi",
]


NUMERIC_COLUMNS = [
    "ce_oi",
    "ce_change_oi",
    "ce_volume",
    "ce_iv",
    "ce_ltp",
    "ce_change",
    "ce_bid_qty",
    "ce_bid",
    "ce_ask",
    "ce_ask_qty",
    "strike",
    "pe_bid_qty",
    "pe_bid",
    "pe_ask",
    "pe_ask_qty",
    "pe_change",
    "pe_ltp",
    "pe_iv",
    "pe_volume",
    "pe_change_oi",
    "pe_oi",
]


# ============================================================
# INDEX DETECTION
# ============================================================

def detect_index(file_path):
    name = file_path.name.upper()

    if "BANKNIFTY" in name:
        return "BANKNIFTY"

    if "NIFTY" in name:
        return "NIFTY"

    return "UNKNOWN"


# ============================================================
# NUMBER CLEANING
# ============================================================

def clean_number(value):
    """
    Convert NSE values such as:

        43,500.00
        9,678.75
        -
        blank

    into numeric values.
    """

    if value is None:
        return None

    value = str(value).strip()

    if value in ("", "-", "NA", "N/A"):
        return None

    # Remove commas
    value = value.replace(",", "")

    # Remove accidental whitespace
    value = value.replace(" ", "")

    try:
        return float(value)
    except ValueError:
        return None


# ============================================================
# READ NSE CSV
# ============================================================

def read_nse_csv(file_path):
    """
    Read NSE option-chain CSV.

    Actual NSE format observed:

        Row 0 -> CALLS / PUTS
        Row 1 -> column headers
        Row 2+ -> option-chain data

    Raw data rows contain 23 columns.
    The first and last columns are blank.

    We extract the 21 useful option-chain columns.
    """

    rows = []

    with open(
        file_path,
        "r",
        encoding="utf-8-sig",
        errors="replace",
        newline=""
    ) as file:

        reader = csv.reader(file)

        for row in reader:

            # Actual NSE data rows have 23 columns
            if len(row) != 23:
                continue

            # Remove first and last blank columns
            useful_row = row[1:22]

            rows.append(useful_row)

    if not rows:
        raise ValueError(
            "No valid NSE option-chain rows found."
        )

    df = pd.DataFrame(
        rows,
        columns=COLUMNS
    )

    # --------------------------------------------------------
    # Convert all numerical columns
    # --------------------------------------------------------

    for column in NUMERIC_COLUMNS:

        df[column] = df[column].apply(clean_number)

    # --------------------------------------------------------
    # Remove rows without strike
    # --------------------------------------------------------

    df = df.dropna(
        subset=["strike"]
    )

    # --------------------------------------------------------
    # Remove duplicate strikes
    # --------------------------------------------------------

    df = df.drop_duplicates(
        subset=["strike"],
        keep="first"
    )

    # --------------------------------------------------------
    # Sort strikes
    # --------------------------------------------------------

    df = df.sort_values(
        "strike"
    ).reset_index(drop=True)

    if df.empty:
        raise ValueError(
            "No valid strike data found."
        )

    return df


# ============================================================
# FILE HASH
# ============================================================

def calculate_file_hash(file_path):

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:

        while True:

            chunk = file.read(1024 * 1024)

            if not chunk:
                break

            sha256.update(chunk)

    return sha256.hexdigest()


# ============================================================
# DATABASE CREATION
# ============================================================

def create_database():

    DATABASE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    conn = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = conn.cursor()

    # --------------------------------------------------------
    # SNAPSHOTS TABLE
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS snapshots (

            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,

            snapshot_time TEXT NOT NULL,

            index_name TEXT NOT NULL,

            source_file TEXT NOT NULL,

            file_hash TEXT NOT NULL UNIQUE,

            strikes INTEGER,

            max_pain REAL,

            reference_strike REAL,

            ce_oi REAL,

            pe_oi REAL,

            pcr_oi REAL,

            ce_change_oi REAL,

            pe_change_oi REAL,

            pcr_change_oi REAL,

            ce_volume REAL,

            pe_volume REAL,

            pcr_volume REAL,

            max_ce_oi_strike REAL,

            max_pe_oi_strike REAL,

            max_ce_change_oi_strike REAL,

            max_pe_change_oi_strike REAL,

            possible_call_writing_strike REAL,

            possible_put_writing_strike REAL,

            possible_call_unwinding_strike REAL,

            possible_put_unwinding_strike REAL
        )
        """
    )

    # --------------------------------------------------------
    # OPTION CHAIN TABLE
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS option_chain (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            snapshot_id INTEGER NOT NULL,

            strike REAL,

            ce_oi REAL,

            ce_change_oi REAL,

            ce_volume REAL,

            ce_iv REAL,

            ce_ltp REAL,

            ce_change REAL,

            pe_change REAL,

            pe_ltp REAL,

            pe_iv REAL,

            pe_volume REAL,

            pe_change_oi REAL,

            pe_oi REAL,

            FOREIGN KEY(snapshot_id)
                REFERENCES snapshots(snapshot_id)
        )
        """
    )

    # --------------------------------------------------------
    # INDEXES
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_snapshots_index
        ON snapshots(index_name)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_snapshots_time
        ON snapshots(snapshot_time)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_option_chain_snapshot
        ON option_chain(snapshot_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_option_chain_strike
        ON option_chain(strike)
        """
    )

    conn.commit()

    return conn


# ============================================================
# SAFE SUM
# ============================================================

def safe_sum(series):

    return float(
        series.fillna(0).sum()
    )


# ============================================================
# MAX PAIN
# ============================================================

def calculate_max_pain(df):

    strikes = (
        df["strike"]
        .dropna()
        .tolist()
    )

    min_loss = None
    max_pain_strike = None

    for possible_strike in strikes:

        call_loss = (
            (
                possible_strike
                - df["strike"]
            )
            .clip(lower=0)
            * df["ce_oi"].fillna(0)
        ).sum()

        put_loss = (
            (
                df["strike"]
                - possible_strike
            )
            .clip(lower=0)
            * df["pe_oi"].fillna(0)
        ).sum()

        total_loss = (
            call_loss
            + put_loss
        )

        if (
            min_loss is None
            or total_loss < min_loss
        ):

            min_loss = total_loss

            max_pain_strike = (
                possible_strike
            )

    return float(
        max_pain_strike
    )


# ============================================================
# REFERENCE STRIKE
# ============================================================

def calculate_reference_strike(df):

    """
    This is NOT the actual index spot.

    It is an OI-based reference strike because
    the CSV data itself may not contain a usable
    underlying spot value.
    """

    temp = df.copy()

    temp["total_oi"] = (
        temp["ce_oi"].fillna(0)
        + temp["pe_oi"].fillna(0)
    )

    row = temp.loc[
        temp["total_oi"].idxmax()
    ]

    return float(
        row["strike"]
    )


# ============================================================
# POSSIBLE OI ACTIVITY
# ============================================================

def find_possible_activity(df):

    # --------------------------------------------------------
    # Possible Call Writing
    #
    # CE OI increases
    # CE LTP decreases
    # --------------------------------------------------------

    call_writing = df[
        (df["ce_change_oi"] > 0)
        &
        (df["ce_change"] < 0)
    ]

    possible_call_writing = None

    if not call_writing.empty:

        row = call_writing.loc[
            call_writing[
                "ce_change_oi"
            ].idxmax()
        ]

        possible_call_writing = (
            float(row["strike"])
        )

    # --------------------------------------------------------
    # Possible Put Writing
    #
    # PE OI increases
    # PE LTP decreases
    # --------------------------------------------------------

    put_writing = df[
        (df["pe_change_oi"] > 0)
        &
        (df["pe_change"] < 0)
    ]

    possible_put_writing = None

    if not put_writing.empty:

        row = put_writing.loc[
            put_writing[
                "pe_change_oi"
            ].idxmax()
        ]

        possible_put_writing = (
            float(row["strike"])
        )

    # --------------------------------------------------------
    # Possible Call Unwinding
    #
    # CE OI decreases
    # CE LTP increases
    # --------------------------------------------------------

    call_unwinding = df[
        (df["ce_change_oi"] < 0)
        &
        (df["ce_change"] > 0)
    ]

    possible_call_unwinding = None

    if not call_unwinding.empty:

        row = call_unwinding.loc[
            call_unwinding[
                "ce_change_oi"
            ].idxmin()
        ]

        possible_call_unwinding = (
            float(row["strike"])
        )

    # --------------------------------------------------------
    # Possible Put Unwinding
    #
    # PE OI decreases
    # PE LTP increases
    # --------------------------------------------------------

    put_unwinding = df[
        (df["pe_change_oi"] < 0)
        &
        (df["pe_change"] > 0)
    ]

    possible_put_unwinding = None

    if not put_unwinding.empty:

        row = put_unwinding.loc[
            put_unwinding[
                "pe_change_oi"
            ].idxmin()
        ]

        possible_put_unwinding = (
            float(row["strike"])
        )

    return (
        possible_call_writing,
        possible_put_writing,
        possible_call_unwinding,
        possible_put_unwinding
    )


# ============================================================
# ANALYZE OPTION CHAIN
# ============================================================

def analyze_option_chain(df):

    ce_oi = safe_sum(
        df["ce_oi"]
    )

    pe_oi = safe_sum(
        df["pe_oi"]
    )

    ce_change_oi = safe_sum(
        df["ce_change_oi"]
    )

    pe_change_oi = safe_sum(
        df["pe_change_oi"]
    )

    ce_volume = safe_sum(
        df["ce_volume"]
    )

    pe_volume = safe_sum(
        df["pe_volume"]
    )

    # --------------------------------------------------------
    # PCR
    # --------------------------------------------------------

    pcr_oi = (
        pe_oi / ce_oi
        if ce_oi != 0
        else None
    )

    pcr_change_oi = (
        pe_change_oi / ce_change_oi
        if ce_change_oi != 0
        else None
    )

    pcr_volume = (
        pe_volume / ce_volume
        if ce_volume != 0
        else None
    )

    # --------------------------------------------------------
    # Maximum OI
    # --------------------------------------------------------

    max_ce_oi_strike = float(
        df.loc[
            df["ce_oi"]
            .fillna(0)
            .idxmax(),
            "strike"
        ]
    )

    max_pe_oi_strike = float(
        df.loc[
            df["pe_oi"]
            .fillna(0)
            .idxmax(),
            "strike"
        ]
    )

    max_ce_change_oi_strike = float(
        df.loc[
            df["ce_change_oi"]
            .fillna(0)
            .idxmax(),
            "strike"
        ]
    )

    max_pe_change_oi_strike = float(
        df.loc[
            df["pe_change_oi"]
            .fillna(0)
            .idxmax(),
            "strike"
        ]
    )

    # --------------------------------------------------------
    # Max Pain
    # --------------------------------------------------------

    max_pain = calculate_max_pain(
        df
    )

    # --------------------------------------------------------
    # Reference Strike
    # --------------------------------------------------------

    reference_strike = (
        calculate_reference_strike(df)
    )

    # --------------------------------------------------------
    # Activity
    # --------------------------------------------------------

    (
        possible_call_writing,
        possible_put_writing,
        possible_call_unwinding,
        possible_put_unwinding
    ) = find_possible_activity(df)

    return {

        "strikes": len(df),

        "max_pain": max_pain,

        "reference_strike":
            reference_strike,

        "ce_oi": ce_oi,

        "pe_oi": pe_oi,

        "pcr_oi": pcr_oi,

        "ce_change_oi":
            ce_change_oi,

        "pe_change_oi":
            pe_change_oi,

        "pcr_change_oi":
            pcr_change_oi,

        "ce_volume":
            ce_volume,

        "pe_volume":
            pe_volume,

        "pcr_volume":
            pcr_volume,

        "max_ce_oi_strike":
            max_ce_oi_strike,

        "max_pe_oi_strike":
            max_pe_oi_strike,

        "max_ce_change_oi_strike":
            max_ce_change_oi_strike,

        "max_pe_change_oi_strike":
            max_pe_change_oi_strike,

        "possible_call_writing_strike":
            possible_call_writing,

        "possible_put_writing_strike":
            possible_put_writing,

        "possible_call_unwinding_strike":
            possible_call_unwinding,

        "possible_put_unwinding_strike":
            possible_put_unwinding
    }


# ============================================================
# SAVE SNAPSHOT
# ============================================================

def save_snapshot(
    conn,
    file_path,
    index_name,
    file_hash,
    df,
    analysis
):

    snapshot_time = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    cursor = conn.cursor()

    # --------------------------------------------------------
    # Duplicate check
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT snapshot_id
        FROM snapshots
        WHERE file_hash = ?
        """,
        (file_hash,)
    )

    existing = cursor.fetchone()

    if existing:

        return (
            False,
            existing[0],
            snapshot_time
        )

    # --------------------------------------------------------
    # Insert snapshot summary
    # --------------------------------------------------------

    cursor.execute(
        """
        INSERT INTO snapshots (

            snapshot_time,
            index_name,
            source_file,
            file_hash,

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

        )

        VALUES (

            ?, ?, ?, ?,

            ?, ?, ?,

            ?, ?, ?,

            ?, ?, ?,

            ?, ?, ?,

            ?, ?,

            ?, ?,

            ?, ?,

            ?, ?

        )
        """,
        (
            snapshot_time,
            index_name,
            file_path.name,
            file_hash,

            analysis["strikes"],
            analysis["max_pain"],
            analysis["reference_strike"],

            analysis["ce_oi"],
            analysis["pe_oi"],
            analysis["pcr_oi"],

            analysis["ce_change_oi"],
            analysis["pe_change_oi"],
            analysis["pcr_change_oi"],

            analysis["ce_volume"],
            analysis["pe_volume"],
            analysis["pcr_volume"],

            analysis["max_ce_oi_strike"],
            analysis["max_pe_oi_strike"],

            analysis[
                "max_ce_change_oi_strike"
            ],

            analysis[
                "max_pe_change_oi_strike"
            ],

            analysis[
                "possible_call_writing_strike"
            ],

            analysis[
                "possible_put_writing_strike"
            ],

            analysis[
                "possible_call_unwinding_strike"
            ],

            analysis[
                "possible_put_unwinding_strike"
            ]
        )
    )

    snapshot_id = cursor.lastrowid

    # --------------------------------------------------------
    # Insert full strike-level data
    # --------------------------------------------------------

    rows = []

    for _, row in df.iterrows():

        rows.append(
            (
                snapshot_id,

                row["strike"],

                row["ce_oi"],
                row["ce_change_oi"],
                row["ce_volume"],
                row["ce_iv"],
                row["ce_ltp"],
                row["ce_change"],

                row["pe_change"],
                row["pe_ltp"],
                row["pe_iv"],
                row["pe_volume"],
                row["pe_change_oi"],
                row["pe_oi"]
            )
        )

    cursor.executemany(
        """
        INSERT INTO option_chain (

            snapshot_id,
            strike,

            ce_oi,
            ce_change_oi,
            ce_volume,
            ce_iv,
            ce_ltp,
            ce_change,

            pe_change,
            pe_ltp,
            pe_iv,
            pe_volume,
            pe_change_oi,
            pe_oi

        )

        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?
        )
        """,
        rows
    )

    conn.commit()

    return (
        True,
        snapshot_id,
        snapshot_time
    )


# ============================================================
# DISPLAY HELPERS
# ============================================================

def format_strike(value):

    if value is None:
        return "None"

    return f"{value:,.0f}"


def format_number(value):

    if value is None:
        return "None"

    return f"{value:,.0f}"


def format_ratio(value):

    if value is None:
        return "None"

    return f"{value:.3f}"


# ============================================================
# TERMINAL SUMMARY
# ============================================================

def display_summary(
    file_path,
    index_name,
    analysis,
    snapshot_time,
    saved,
    snapshot_id
):

    print()

    print("=" * 64)

    print(
        f" {index_name} OPTION CHAIN ANALYSIS"
    )

    print("=" * 64)

    print(
        f"Run time       : {snapshot_time}"
    )

    print(
        f"Source file    : {file_path.name}"
    )

    print(
        f"Strikes        : {analysis['strikes']}"
    )

    print()

    print("-" * 64)

    print(" MARKET STRUCTURE")

    print("-" * 64)

    print(
        f"Max Pain       : "
        f"{format_strike(analysis['max_pain'])}"
    )

    print(
        f"Reference      : "
        f"{format_strike(analysis['reference_strike'])} "
        f"(OI proxy)"
    )

    print()

    print(
        f"CE OI          : "
        f"{format_number(analysis['ce_oi'])}"
    )

    print(
        f"PE OI          : "
        f"{format_number(analysis['pe_oi'])}"
    )

    print(
        f"OI PCR         : "
        f"{format_ratio(analysis['pcr_oi'])}"
    )

    print()

    print(
        f"CE Change OI   : "
        f"{analysis['ce_change_oi']:+,.0f}"
    )

    print(
        f"PE Change OI   : "
        f"{analysis['pe_change_oi']:+,.0f}"
    )

    print(
        f"Change OI PCR  : "
        f"{format_ratio(analysis['pcr_change_oi'])}"
    )

    print()

    print(
        f"CE Volume      : "
        f"{format_number(analysis['ce_volume'])}"
    )

    print(
        f"PE Volume      : "
        f"{format_number(analysis['pe_volume'])}"
    )

    print(
        f"Volume PCR     : "
        f"{format_ratio(analysis['pcr_volume'])}"
    )

    print()

    print("-" * 64)

    print(" OI CONCENTRATION")

    print("-" * 64)

    print(
        f"Max CE OI             : "
        f"{format_strike(analysis['max_ce_oi_strike'])}"
    )

    print(
        f"Max PE OI             : "
        f"{format_strike(analysis['max_pe_oi_strike'])}"
    )

    print(
        f"Max CE Change OI      : "
        f"{format_strike(analysis['max_ce_change_oi_strike'])}"
    )

    print(
        f"Max PE Change OI      : "
        f"{format_strike(analysis['max_pe_change_oi_strike'])}"
    )

    print()

    print("-" * 64)

    print(" POSSIBLE OI ACTIVITY")

    print("-" * 64)

    print(
        f"Possible CE writing   : "
        f"{format_strike(analysis['possible_call_writing_strike'])}"
    )

    print(
        f"Possible PE writing   : "
        f"{format_strike(analysis['possible_put_writing_strike'])}"
    )

    print(
        f"Possible CE unwinding : "
        f"{format_strike(analysis['possible_call_unwinding_strike'])}"
    )

    print(
        f"Possible PE unwinding : "
        f"{format_strike(analysis['possible_put_unwinding_strike'])}"
    )

    print()

    print("-" * 64)

    if saved:

        print(
            f"Database          : NEW SNAPSHOT SAVED"
        )

    else:

        print(
            f"Database          : ALREADY IMPORTED"
        )

    print(
        f"Snapshot ID       : {snapshot_id}"
    )

    print(
        f"SQLite database   : {DATABASE_FILE}"
    )

    print()

    print(
        "Note: OI activity is descriptive analysis, "
        "not a trading signal."
    )

    print("=" * 64)


# ============================================================
# FIND CSV FILES
# ============================================================

def find_csv_files():

    files = []

    # --------------------------------------------------------
    # BANKNIFTY
    # --------------------------------------------------------

    banknifty_dir = (
        DATA_DIR / "banknifty"
    )

    if banknifty_dir.exists():

        files.extend(
            banknifty_dir.glob("*.csv")
        )

    # --------------------------------------------------------
    # NIFTY
    # --------------------------------------------------------

    nifty_dir = (
        DATA_DIR / "nifty"
    )

    if nifty_dir.exists():

        files.extend(
            nifty_dir.glob("*.csv")
        )

    return sorted(
        files,
        key=lambda path: str(path)
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print(
        "=" * 64
    )

    print(
        " NSE OPTION CHAIN ANALYZER"
    )

    print(
        " NIFTY + BANKNIFTY"
    )

    print(
        "=" * 64
    )

    csv_files = find_csv_files()

    if not csv_files:

        print()

        print(
            "No NSE CSV files found."
        )

        print()

        print(
            "Put files into:"
        )

        print(
            "data/banknifty/"
        )

        print(
            "data/nifty/"
        )

        print()

        return

    print()

    print(
        f"CSV files found : {len(csv_files)}"
    )

    conn = create_database()

    total_saved = 0

    try:

        for file_path in csv_files:

            index_name = detect_index(
                file_path
            )

            print()

            print(
                f"Processing {index_name}: "
                f"{file_path.name}"
            )

            try:

                file_hash = (
                    calculate_file_hash(
                        file_path
                    )
                )

                df = read_nse_csv(
                    file_path
                )

                print(
                    f"Parsed          : "
                    f"{len(df)} strikes"
                )

                analysis = (
                    analyze_option_chain(
                        df
                    )
                )

                (
                    saved,
                    snapshot_id,
                    snapshot_time
                ) = save_snapshot(
                    conn,
                    file_path,
                    index_name,
                    file_hash,
                    df,
                    analysis
                )

                if saved:

                    total_saved += 1

                display_summary(
                    file_path,
                    index_name,
                    analysis,
                    snapshot_time,
                    saved,
                    snapshot_id
                )

            except Exception as error:

                print()

                print(
                    f"ERROR: {file_path.name}"
                )

                print(
                    f"Reason: {error}"
                )

    finally:

        conn.close()

    print()

    print(
        "=" * 64
    )

    print(
        f"New snapshots saved : {total_saved}"
    )

    print(
        f"Database            : {DATABASE_FILE}"
    )

    print(
        "=" * 64
    )

    print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()