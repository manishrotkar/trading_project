import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPTION_SCRIPTS = PROJECT_ROOT / "option_analysis" / "scripts"
FUTURES_SCRIPTS = PROJECT_ROOT / "futures_project" / "scripts"


PIPELINE = [
    ("Update Futures", FUTURES_SCRIPTS / "download_all_indices_future.py"),

    ("Update Options", OPTION_SCRIPTS / "download_index_options.py"),
    ("Update Underlying + VIX", OPTION_SCRIPTS / "download_underlying_data.py"),

    ("Calculate FYERS-style IV", OPTION_SCRIPTS / "calculate_fyers_style_iv.py"),
    ("Build ATM IV", OPTION_SCRIPTS / "build_atm_iv.py"),
    ("Calculate IV Rank / Percentile", OPTION_SCRIPTS / "calculate_iv_rank_percentile.py"),

    ("Build Strike OI Analysis", OPTION_SCRIPTS / "build_strike_oi_analysis.py"),
    ("Calculate OI Change", OPTION_SCRIPTS / "calculate_oi_change.py"),
    ("Calculate Option Price Change", OPTION_SCRIPTS / "calculate_option_price_change.py"),
    ("Classify Option Activity", OPTION_SCRIPTS / "classify_option_activity.py"),

    ("Build ATM OI Analysis", OPTION_SCRIPTS / "build_atm_oi_analysis.py"),
    ("Rebuild Chain Summary", OPTION_SCRIPTS / "rebuild_chain_summary.py"),
    ("Rebuild ATM OI Concentration", OPTION_SCRIPTS / "rebuild_atm_oi_concentration.py"),
    ("Calculate OI Change %", OPTION_SCRIPTS / "calculate_oi_change_pct.py"),

    ("Rebuild Market Trend", OPTION_SCRIPTS / "rebuild_market_trend_analysis.py"),
    ("Rebuild Combined Market Analysis", OPTION_SCRIPTS / "rebuild_combined_market_analysis.py"),
    ("Rebuild Market State", OPTION_SCRIPTS / "rebuild_market_state_analysis.py"),

    ("Build Hourly Market State", OPTION_SCRIPTS / "rebuild_market_state_hourly_analysis.py"),
]


def run_step(number, total, name, script):
    print()
    print("=" * 80)
    print(f"STEP {number}/{total}: {name}")
    print(f"Script: {script}")
    print("=" * 80)

    if not script.exists():
        raise FileNotFoundError(f"Script not found: {script}")

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(script.parent),
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"STEP {number} FAILED: {name} "
            f"(exit code {result.returncode})"
        )

    print(f"\nSTEP {number} COMPLETED: {name}")


def main():
    parser = argparse.ArgumentParser(
        description="Run the complete live market analysis pipeline."
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the pipeline steps without executing them.",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("LIVE MARKET ANALYSIS PIPELINE")
    print("=" * 80)
    print(f"Python : {sys.executable}")
    print(f"Root   : {PROJECT_ROOT}")
    print()

    print("Forward 5-candle outcome is intentionally NOT included.")
    print("This pipeline is for live/current market analysis.")
    print("=" * 80)

    total = len(PIPELINE)

    if args.dry_run:
        print()
        print("DRY RUN - NO SCRIPTS WILL BE EXECUTED")
        print("=" * 80)

        for number, (name, script) in enumerate(PIPELINE, start=1):
            status = "OK" if script.exists() else "MISSING"
            print(f"{number:02d}. [{status}] {name}")
            print(f"    {script}")

        print()
        print("DRY RUN COMPLETED")
        return

    try:
        for number, (name, script) in enumerate(PIPELINE, start=1):
            run_step(number, total, name, script)

    except Exception as exc:
        print()
        print("=" * 80)
        print("PIPELINE FAILED")
        print("=" * 80)
        print(exc)
        print()
        print("Pipeline stopped to prevent downstream analysis from")
        print("running on incomplete or failed upstream data.")
        sys.exit(1)

    print()
    print("=" * 80)
    print("LIVE MARKET ANALYSIS PIPELINE COMPLETED")
    print("=" * 80)
    print()
    print("Final hourly file:")
    print(
        OPTION_SCRIPTS.parent
        / "database"
        / "market_state_hourly_analysis.csv"
    )
    print()


if __name__ == "__main__":
    main()
