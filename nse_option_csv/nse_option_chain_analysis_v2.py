import csv
import math
import re
from pathlib import Path
from datetime import datetime

import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
NIFTY_DIR = DATA_DIR / "nifty"
BANKNIFTY_DIR = DATA_DIR / "banknifty"

# If True, analyze all CSV files found in the configured folders.
# If False, analyze only the newest CSV for each index.
ANALYZE_ALL_FILES = True

# Use a limited strike region around the estimated reference.
# This is a strike-selection filter, NOT an actual spot price.
ATM_REGION_PERCENT = 0.05

# Maximum relative distance permitted for a synthetic
# put-call-parity estimate to be considered usable.
MAX_PARITY_DISPERSION = 0.025

# A rough IV comparison region around the reference price.
IV_REGION_PERCENT = 0.03

# No database, output CSV, or other persistent data is created.
# All analysis is printed to the terminal.


# ============================================================
# CSV COLUMN MAPPING
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

NUMERIC_COLUMNS = COLUMNS


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_number(value):
    """Convert NSE-formatted numbers into floats."""

    if value is None:
        return None

    value = str(value).strip()

    if value.upper() in ("", "-", "NA", "N/A", "NONE", "NULL"):
        return None

    value = value.replace(",", "").replace(" ", "")

    try:
        number = float(value)

        if not math.isfinite(number):
            return None

        return number

    except (ValueError, TypeError):
        return None


def safe_sum(series):
    return float(series.fillna(0).sum())


def safe_ratio(numerator, denominator):
    if denominator is None or denominator == 0:
        return None

    return numerator / denominator


def fmt_number(value):
    if value is None or pd.isna(value):
        return "N/A"

    return f"{value:,.2f}"


def fmt_integer(value):
    if value is None or pd.isna(value):
        return "N/A"

    return f"{value:,.0f}"


def fmt_ratio(value):
    if value is None or pd.isna(value):
        return "N/A"

    return f"{value:.3f}"


def fmt_percent(value):
    if value is None or pd.isna(value):
        return "N/A"

    return f"{value:.2f}%"


def detect_index(file_path):
    name = file_path.name.upper()

    if "BANKNIFTY" in name:
        return "BANKNIFTY"

    if "NIFTY" in name:
        return "NIFTY"

    return "UNKNOWN"


# ============================================================
# FIND CSV FILES
# ============================================================

def find_csv_files():
    files = []

    for folder in (NIFTY_DIR, BANKNIFTY_DIR):
        if folder.exists():
            files.extend(folder.glob("*.csv"))

    # Also support CSV files placed beside this Python script.
    # Files already found in the data folders are not duplicated.
    files.extend(
        path for path in BASE_DIR.glob("*.csv")
        if path not in files
    )

    files = [
        path for path in files
        if detect_index(path) in ("NIFTY", "BANKNIFTY")
    ]

    files = sorted(set(files))

    if not ANALYZE_ALL_FILES:
        newest = {}

        for path in files:
            index_name = detect_index(path)

            if (
                index_name not in newest
                or path.stat().st_mtime
                > newest[index_name].stat().st_mtime
            ):
                newest[index_name] = path

        files = list(newest.values())

    return sorted(files)


# ============================================================
# READ NSE CSV
# ============================================================

def read_nse_csv(file_path):
    """
    Read the 23-column NSE option-chain format.

    Expected layout:
      Row 1: CALLS / PUTS section labels
      Row 2: column headers
      Row 3 onward: option-chain records

    The first and last columns are unused.
    """

    rows = []

    with open(
        file_path,
        "r",
        encoding="utf-8-sig",
        errors="replace",
        newline="",
    ) as file:

        reader = csv.reader(file)

        for row in reader:
            if len(row) != 23:
                continue

            useful_row = row[1:22]

            strike = clean_number(useful_row[10])

            if strike is None:
                continue

            # Ignore section headings or malformed records.
            if strike <= 0:
                continue

            rows.append(useful_row)

    if not rows:
        raise ValueError(
            "No valid 23-column NSE option-chain rows found."
        )

    df = pd.DataFrame(rows, columns=COLUMNS)

    for column in NUMERIC_COLUMNS:
        df[column] = df[column].map(clean_number)

    df = df.dropna(subset=["strike"])

    df = (
        df.sort_values("strike")
        .drop_duplicates(subset=["strike"], keep="first")
        .reset_index(drop=True)
    )

    if df.empty:
        raise ValueError("No valid strikes after cleaning.")

    # Missing OI and volume are treated as zero for aggregation.
    # Missing option prices and IVs remain missing.
    return df


# ============================================================
# SPOT / REFERENCE PRICE
# ============================================================

def find_explicit_underlying_price(file_path):
    """
    Look for a separate metadata file containing an explicit
    underlying/spot/index LTP field.

    The standard uploaded 23-column NSE option-chain rows do not
    contain a dedicated underlying spot-price column.

    Do not infer spot from an arbitrary strike or OI maximum.
    """

    # This standard NSE format contains only option-chain rows.
    # No explicit underlying value is available in these rows.
    return None


def estimate_parity_reference(df):
    """
    Approximate spot from put-call parity:

        S ~= Call LTP - Put LTP + Strike

    This simplified calculation ignores discounting, dividends,
    stale quotes and bid-ask effects. It is NOT an actual spot feed.

    The estimate is accepted only when enough usable pairs exist
    and their dispersion is reasonably small.
    """

    paired = df[
        (df["ce_ltp"] > 0)
        & (df["pe_ltp"] > 0)
        & (df["strike"] > 0)
    ].copy()

    if len(paired) < 3:
        return None, "Unavailable: insufficient paired option LTPs"

    paired["parity_spot"] = (
        paired["ce_ltp"]
        - paired["pe_ltp"]
        + paired["strike"]
    )

    paired = paired[
        (paired["parity_spot"] > 0)
        & (paired["parity_spot"] > paired["strike"] * 0.5)
        & (paired["parity_spot"] < paired["strike"] * 1.5)
    ]

    if len(paired) < 3:
        return None, "Unavailable: invalid parity estimates"

    # Prefer strikes where both sides have reasonably usable quotes.
    paired["quote_quality"] = 1.0

    if {"ce_bid", "ce_ask", "pe_bid", "pe_ask"}.issubset(
        paired.columns
    ):
        spreads = (
            (paired["ce_ask"] - paired["ce_bid"]).clip(lower=0)
            + (paired["pe_ask"] - paired["pe_bid"]).clip(lower=0)
        )

        paired["quote_quality"] = 1 / (
            1 + spreads.fillna(spreads.median())
        )

    median_spot = float(paired["parity_spot"].median())

    if median_spot <= 0:
        return None, "Unavailable: invalid parity median"

    relative_deviation = (
        (paired["parity_spot"] - median_spot).abs().median()
        / median_spot
    )

    if relative_deviation > MAX_PARITY_DISPERSION:
        return None, (
            "Unavailable: paired option prices are inconsistent"
        )

    return median_spot, (
        "Approximate put-call-parity estimate; not live spot"
    )


def calculate_reference(df, file_path):
    """
    Choose a reference price without blindly using the highest-OI
    strike. Explicit underlying data is preferred, then parity.

    If neither is available, return a clearly labelled OI proxy
    restricted to the central strike region. This proxy must never
    be reported as actual spot.
    """

    explicit_spot = find_explicit_underlying_price(file_path)

    if explicit_spot is not None and explicit_spot > 0:
        return explicit_spot, "Explicit underlying price"

    parity_spot, parity_label = estimate_parity_reference(df)

    if parity_spot is not None:
        return parity_spot, parity_label

    strikes = df["strike"].dropna().sort_values()

    if len(strikes) < 3:
        return float(strikes.median()), "Strike-median proxy; not spot"

    low = strikes.quantile(0.15)
    high = strikes.quantile(0.85)

    central = df[
        df["strike"].between(low, high)
    ].copy()

    central["total_oi"] = (
        central["ce_oi"].fillna(0)
        + central["pe_oi"].fillna(0)
    )

    central["total_volume"] = (
        central["ce_volume"].fillna(0)
        + central["pe_volume"].fillna(0)
    )

    # Use OI as the main criterion and volume as a small tie-breaker.
    central["activity_score"] = (
        central["total_oi"]
        + central["total_volume"] * 0.01
    )

    if central["activity_score"].max() <= 0:
        return float(strikes.median()), (
            "Strike-median proxy; not spot"
        )

    row = central.loc[central["activity_score"].idxmax()]

    return float(row["strike"]), (
        "Central-range OI proxy; NOT actual spot"
    )


# ============================================================
# MAX PAIN
# ============================================================

def calculate_max_pain(df):
    strikes = df["strike"].to_numpy()
    ce_oi = df["ce_oi"].fillna(0).to_numpy()
    pe_oi = df["pe_oi"].fillna(0).to_numpy()

    if len(strikes) == 0:
        return None

    losses = []

    for settlement in strikes:
        call_loss = (
            (settlement - strikes).clip(0) * ce_oi
        ).sum()

        put_loss = (
            (strikes - settlement).clip(0) * pe_oi
        ).sum()

        losses.append(call_loss + put_loss)

    return float(strikes[int(losses.index(min(losses)))])


# ============================================================
# ATM REGION AND OI WALLS
# ============================================================

def select_region(df, reference):
    """
    Select strikes within a percentage of the reference price.

    If the reference is only a weak OI proxy, this is a proxy-centred
    region, not a confirmed ATM region.
    """

    if reference is None or reference <= 0:
        return df.copy()

    region = df[
        (df["strike"] >= reference * (1 - ATM_REGION_PERCENT))
        & (df["strike"] <= reference * (1 + ATM_REGION_PERCENT))
    ].copy()

    if len(region) < 3:
        distances = (df["strike"] - reference).abs()
        region = df.loc[distances.nsmallest(min(7, len(df))).index]

    return region.sort_values("strike").copy()


def largest_oi_strike(df, column, region=None):
    """
    Report both local and full-chain OI walls.
    """

    source = region if region is not None and not region.empty else df

    valid = source[column].fillna(0)

    if valid.max() <= 0:
        return None

    return float(source.loc[valid.idxmax(), "strike"])


def find_possible_activity(df, region):
    """
    Activity is a possible interpretation, not proof of writing.

    CE writing candidate:
        CE change in OI positive and CE price change negative

    PE writing candidate:
        PE change in OI positive and PE price change negative
    """

    def strongest(frame, oi_col, change_col, condition):
        selected = frame[condition].copy()

        if selected.empty:
            return None

        idx = selected[oi_col].abs().idxmax()

        return float(selected.loc[idx, "strike"])

    # Restrict activity candidates to the reference-centred region
    # to prevent remote strikes from dominating the summary.
    ce_write_condition = (
        (region["ce_change_oi"] > 0)
        & (region["ce_change"] < 0)
    )

    pe_write_condition = (
        (region["pe_change_oi"] > 0)
        & (region["pe_change"] < 0)
    )

    ce_unwind_condition = (
        (region["ce_change_oi"] < 0)
        & (region["ce_change"] > 0)
    )

    pe_unwind_condition = (
        (region["pe_change_oi"] < 0)
        & (region["pe_change"] > 0)
    )

    return {
        "call_writing": strongest(
            region, "ce_change_oi", "ce_change", ce_write_condition
        ),
        "put_writing": strongest(
            region, "pe_change_oi", "pe_change", pe_write_condition
        ),
        "call_unwinding": strongest(
            region, "ce_change_oi", "ce_change", ce_unwind_condition
        ),
        "put_unwinding": strongest(
            region, "pe_change_oi", "pe_change", pe_unwind_condition
        ),
    }


# ============================================================
# IV ANALYSIS
# ============================================================

def analyze_iv(df, region):
    ce_iv = df["ce_iv"].dropna()
    pe_iv = df["pe_iv"].dropna()

    region_ce_iv = region["ce_iv"].dropna()
    region_pe_iv = region["pe_iv"].dropna()

    all_ivs = pd.concat([ce_iv, pe_iv]).dropna()

    ce_mean = float(ce_iv.mean()) if not ce_iv.empty else None
    pe_mean = float(pe_iv.mean()) if not pe_iv.empty else None

    atm_ce = (
        float(region_ce_iv.mean())
        if not region_ce_iv.empty else None
    )

    atm_pe = (
        float(region_pe_iv.mean())
        if not region_pe_iv.empty else None
    )

    # Difference is in IV percentage points.
    iv_skew = (
        atm_pe - atm_ce
        if atm_pe is not None and atm_ce is not None
        else None
    )

    max_ce_iv_strike = None
    max_pe_iv_strike = None

    valid_ce = df.dropna(subset=["ce_iv"])
    valid_pe = df.dropna(subset=["pe_iv"])

    if not valid_ce.empty:
        max_ce_iv_strike = float(
            valid_ce.loc[valid_ce["ce_iv"].idxmax(), "strike"]
        )

    if not valid_pe.empty:
        max_pe_iv_strike = float(
            valid_pe.loc[valid_pe["pe_iv"].idxmax(), "strike"]
        )

    return {
        "ce_iv_mean": ce_mean,
        "pe_iv_mean": pe_mean,
        "atm_ce_iv": atm_ce,
        "atm_pe_iv": atm_pe,
        "iv_skew": iv_skew,
        "overall_iv_mean": (
            float(all_ivs.mean()) if not all_ivs.empty else None
        ),
        "max_ce_iv": (
            float(valid_ce["ce_iv"].max())
            if not valid_ce.empty else None
        ),
        "max_pe_iv": (
            float(valid_pe["pe_iv"].max())
            if not valid_pe.empty else None
        ),
        "max_ce_iv_strike": max_ce_iv_strike,
        "max_pe_iv_strike": max_pe_iv_strike,
    }


# ============================================================
# MARKET BIAS AND HEURISTIC PROBABILITIES
# ============================================================

def calculate_probabilities(analysis):
    """
    Transparent heuristic probabilities.

    These are NOT calibrated forecasts or guaranteed probabilities.
    A single snapshot cannot establish future price direction.

    The score combines:
      - Change in OI
      - Total OI PCR
      - Volume PCR
      - Call/put writing and unwinding
      - Put-call IV skew

    Missing or contradictory data reduces confidence.
    """

    score = 0.0
    evidence = 0

    pcr = analysis["pcr_oi"]
    volume_pcr = analysis["pcr_volume"]

    ce_change = analysis["ce_change_oi"]
    pe_change = analysis["pe_change_oi"]

    # Total OI PCR: mild directional weight.
    if pcr is not None:
        if pcr >= 1.20:
            score += 1.0
        elif pcr >= 1.05:
            score += 0.5
        elif pcr <= 0.80:
            score -= 1.0
        elif pcr <= 0.95:
            score -= 0.5

        evidence += 1

    # Change in OI: relative put-vs-call buildup.
    change_total = abs(ce_change) + abs(pe_change)

    if change_total > 0:
        change_balance = (pe_change - ce_change) / change_total
        score += max(-1.0, min(1.0, change_balance)) * 1.5
        evidence += 1

    # Volume PCR is a supporting signal, not a standalone signal.
    if volume_pcr is not None:
        if volume_pcr >= 1.20:
            score += 0.5
        elif volume_pcr <= 0.80:
            score -= 0.5

        evidence += 1

    # Option writing / unwinding patterns.
    if analysis["possible_put_writing_strike"] is not None:
        score += 0.5
        evidence += 1

    if analysis["possible_call_writing_strike"] is not None:
        score -= 0.5
        evidence += 1

    if analysis["possible_call_unwinding_strike"] is not None:
        score += 0.4
        evidence += 1

    if analysis["possible_put_unwinding_strike"] is not None:
        score -= 0.4
        evidence += 1

    # IV skew is a weak supporting factor.
    iv_skew = analysis["iv_skew"]

    if iv_skew is not None:
        if iv_skew >= 3:
            score -= 0.4
        elif iv_skew <= -3:
            score += 0.4

        evidence += 1

    # Convert score into a smooth, bounded heuristic distribution.
    # Sideways receives more weight when directional evidence is weak.
    strength = min(1.0, abs(score) / 3.5)

    directional_probability = 20.0 + 60.0 * strength
    sideways_probability = 100.0 - directional_probability

    if score > 0:
        long_probability = directional_probability
        short_probability = 0.0
    elif score < 0:
        long_probability = 0.0
        short_probability = directional_probability
    else:
        long_probability = 0.0
        short_probability = 0.0

    # Allocate probabilities so all three always sum to 100%.
    if score > 0:
        long_probability = 50.0 + 30.0 * strength
        short_probability = 20.0 - 10.0 * strength
        sideways_probability = 30.0 - 20.0 * strength

    elif score < 0:
        short_probability = 50.0 + 30.0 * strength
        long_probability = 20.0 - 10.0 * strength
        sideways_probability = 30.0 - 20.0 * strength

    else:
        long_probability = 25.0
        short_probability = 25.0
        sideways_probability = 50.0

    # If almost no usable evidence exists, do not imply a strong view.
    if evidence < 2:
        long_probability = 25.0
        short_probability = 25.0
        sideways_probability = 50.0

    total = (
        long_probability
        + short_probability
        + sideways_probability
    )

    return {
        "long_probability": long_probability / total * 100,
        "short_probability": short_probability / total * 100,
        "sideways_probability": sideways_probability / total * 100,
        "bias_score": score,
        "evidence_count": evidence,
    }


# ============================================================
# COMPLETE OPTION CHAIN ANALYSIS
# ============================================================

def analyze_option_chain(df, file_path):
    ce_oi = safe_sum(df["ce_oi"])
    pe_oi = safe_sum(df["pe_oi"])

    ce_change_oi = safe_sum(df["ce_change_oi"])
    pe_change_oi = safe_sum(df["pe_change_oi"])

    ce_volume = safe_sum(df["ce_volume"])
    pe_volume = safe_sum(df["pe_volume"])

    reference, reference_label = calculate_reference(df, file_path)
    region = select_region(df, reference)

    pcr_oi = safe_ratio(pe_oi, ce_oi)
    pcr_change_oi = safe_ratio(pe_change_oi, ce_change_oi)
    pcr_volume = safe_ratio(pe_volume, ce_volume)

    max_ce_oi = largest_oi_strike(df, "ce_oi")
    max_pe_oi = largest_oi_strike(df, "pe_oi")

    local_max_ce_oi = largest_oi_strike(
        df, "ce_oi", region
    )
    local_max_pe_oi = largest_oi_strike(
        df, "pe_oi", region
    )

    activity = find_possible_activity(df, region)
    iv = analyze_iv(df, region)

    analysis = {
        "strikes": len(df),
        "reference": reference,
        "reference_label": reference_label,
        "max_pain": calculate_max_pain(df),

        "ce_oi": ce_oi,
        "pe_oi": pe_oi,
        "pcr_oi": pcr_oi,

        "ce_change_oi": ce_change_oi,
        "pe_change_oi": pe_change_oi,
        "pcr_change_oi": pcr_change_oi,

        "ce_volume": ce_volume,
        "pe_volume": pe_volume,
        "pcr_volume": pcr_volume,

        "max_ce_oi_strike": max_ce_oi,
        "max_pe_oi_strike": max_pe_oi,

        "local_max_ce_oi_strike": local_max_ce_oi,
        "local_max_pe_oi_strike": local_max_pe_oi,

        "region_low": float(region["strike"].min()),
        "region_high": float(region["strike"].max()),

        "possible_call_writing_strike": activity["call_writing"],
        "possible_put_writing_strike": activity["put_writing"],
        "possible_call_unwinding_strike": activity["call_unwinding"],
        "possible_put_unwinding_strike": activity["put_unwinding"],

        "explicit_spot": find_explicit_underlying_price(file_path),
    }

    analysis.update(iv)
    analysis.update(calculate_probabilities(analysis))

    return analysis


# ============================================================
# DISPLAY
# ============================================================

def display_summary(file_path, index_name, analysis):
    print()
    print("=" * 76)
    print(f" {index_name} OPTION CHAIN ANALYSIS")
    print("=" * 76)

    print(f"Source file             : {file_path.name}")
    print(f"Analysis time            : {datetime.now().astimezone().isoformat(timespec='seconds')}")
    print(f"Valid strikes            : {analysis['strikes']}")

    print()
    print("-" * 76)
    print("1. SPOT / REFERENCE AND MARKET STRUCTURE")
    print("-" * 76)

    if analysis["explicit_spot"] is not None:
        print(f"Underlying spot/LTP      : {fmt_number(analysis['explicit_spot'])}")
    else:
        print("Underlying spot/LTP      : NOT AVAILABLE in this CSV")

    print(f"Reference price          : {fmt_number(analysis['reference'])}")
    print(f"Reference method         : {analysis['reference_label']}")
    print(f"Max Pain                 : {fmt_number(analysis['max_pain'])}")
    print(
        f"Reference strike region  : "
        f"{fmt_number(analysis['region_low'])} - "
        f"{fmt_number(analysis['region_high'])}"
    )

    print()
    print("-" * 76)
    print("2. OPEN INTEREST AND PCR")
    print("-" * 76)

    print(f"Total CE OI              : {fmt_integer(analysis['ce_oi'])}")
    print(f"Total PE OI              : {fmt_integer(analysis['pe_oi'])}")
    print(f"OI PCR                   : {fmt_ratio(analysis['pcr_oi'])}")

    print(f"CE Change in OI          : {analysis['ce_change_oi']:+,.0f}")
    print(f"PE Change in OI          : {analysis['pe_change_oi']:+,.0f}")
    print(f"Change OI PCR            : {fmt_ratio(analysis['pcr_change_oi'])}")

    print(f"CE Volume                : {fmt_integer(analysis['ce_volume'])}")
    print(f"PE Volume                : {fmt_integer(analysis['pe_volume'])}")
    print(f"Volume PCR               : {fmt_ratio(analysis['pcr_volume'])}")

    print()
    print("-" * 76)
    print("3. OI CONCENTRATION")
    print("-" * 76)

    print(f"Highest CE OI strike     : {fmt_number(analysis['max_ce_oi_strike'])}")
    print(f"Highest PE OI strike     : {fmt_number(analysis['max_pe_oi_strike'])}")

    print(
        f"Local CE OI wall         : "
        f"{fmt_number(analysis['local_max_ce_oi_strike'])}"
    )
    print(
        f"Local PE OI wall         : "
        f"{fmt_number(analysis['local_max_pe_oi_strike'])}"
    )

    print()
    print("-" * 76)
    print("4. IMPLIED VOLATILITY ANALYSIS")
    print("-" * 76)

    print(f"Mean CE IV               : {fmt_percent(analysis['ce_iv_mean'])}")
    print(f"Mean PE IV               : {fmt_percent(analysis['pe_iv_mean'])}")
    print(f"Overall mean IV          : {fmt_percent(analysis['overall_iv_mean'])}")

    print(f"Reference-region CE IV   : {fmt_percent(analysis['atm_ce_iv'])}")
    print(f"Reference-region PE IV   : {fmt_percent(analysis['atm_pe_iv'])}")
    print(f"PE minus CE IV           : {fmt_percent(analysis['iv_skew'])}")

    print(
        f"Highest CE IV            : {fmt_percent(analysis['max_ce_iv'])} "
        f"at {fmt_number(analysis['max_ce_iv_strike'])}"
    )
    print(
        f"Highest PE IV            : {fmt_percent(analysis['max_pe_iv'])} "
        f"at {fmt_number(analysis['max_pe_iv_strike'])}"
    )

    print()
    print("-" * 76)
    print("5. POSSIBLE OPTION ACTIVITY")
    print("-" * 76)

    print(
        f"Possible CE writing      : "
        f"{fmt_number(analysis['possible_call_writing_strike'])}"
    )
    print(
        f"Possible PE writing      : "
        f"{fmt_number(analysis['possible_put_writing_strike'])}"
    )
    print(
        f"Possible CE unwinding    : "
        f"{fmt_number(analysis['possible_call_unwinding_strike'])}"
    )
    print(
        f"Possible PE unwinding    : "
        f"{fmt_number(analysis['possible_put_unwinding_strike'])}"
    )

    print()
    print("-" * 76)
    print("6. LONG / SHORT / SIDEWAYS HEURISTIC")
    print("-" * 76)

    print(f"LONG probability         : {analysis['long_probability']:.1f}%")
    print(f"SHORT probability        : {analysis['short_probability']:.1f}%")
    print(f"SIDEWAYS probability     : {analysis['sideways_probability']:.1f}%")
    print(f"Bias score               : {analysis['bias_score']:+.2f}")
    print(f"Evidence items           : {analysis['evidence_count']}")

    probabilities = {
        "LONG": analysis["long_probability"],
        "SHORT": analysis["short_probability"],
        "SIDEWAYS": analysis["sideways_probability"],
    }

    strongest = max(probabilities, key=probabilities.get)

    print(f"Dominant heuristic view  : {strongest}")

    print()
    print("IMPORTANT:")
    print("- Probabilities are heuristic scores, not trained forecasts.")
    print("- A single CSV snapshot cannot establish future direction.")
    print("- OI alone cannot prove option writing or unwinding.")
    print("- An OI proxy is not actual spot price.")
    print("- IV is a market-implied volatility measure, not a direction signal.")
    print("=" * 76)


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print("=" * 76)
    print(" NSE OPTION CHAIN ANALYZER V2")
    print(" NIFTY + BANKNIFTY | READ-ONLY CSV ANALYSIS")
    print(" No SQLite | No database writes | No output files")
    print("=" * 76)

    csv_files = find_csv_files()

    if not csv_files:
        print()
        print("No matching CSV files found.")
        print("Expected locations:")
        print(f"  {NIFTY_DIR}")
        print(f"  {BANKNIFTY_DIR}")
        print(f"Or place CSV files beside this Python script.")
        return

    print(f"\nCSV files found: {len(csv_files)}")

    for file_path in csv_files:
        index_name = detect_index(file_path)

        print()
        print(f"Processing {index_name}: {file_path.name}")

        try:
            df = read_nse_csv(file_path)
            analysis = analyze_option_chain(df, file_path)

            display_summary(
                file_path=file_path,
                index_name=index_name,
                analysis=analysis,
            )

        except Exception as error:
            print(f"ERROR processing {file_path.name}: {error}")

    print()
    print("=" * 76)
    print("Analysis completed. No database or output files were modified.")
    print("=" * 76)


if __name__ == "__main__":
    main()