"""One-stop entry point for downloading NIFTY 50 option data from NSE India.

This script ties together the two stages of the project's option-data
pipeline so one command does the whole job:

    python download_nifty_options.py

Stage 1 -- REFRESH (fetch_nifty50_option_contracts.py main()):
    The live option-chain API is tried first; when it is blocked (HTTP 404
    from this environment, see NSE_BLOCKED_NOTES.md) the official daily FO
    bhavcopy from nsearchives.nseindia.com is downloaded instead.  Both are
    NSE India, the only permitted source.  Outputs land in
    data/downloads/nse_nifty50_option_contracts.csv and
    data/downloads/nifty50_option_chain_status.json.

Stage 2 -- REPORT (nifty50_open_interest.py main()):
    Per-strike CE/PE open interest around the money for the nearest expiry,
    plus the top-OI strikes and the put-call ratio, read back from the
    freshly saved contract data.

Stage 3 -- INVENTORY:
    A freshness listing of every NIFTY option file under data/downloads/,
    so it is obvious how old each artifact is.

The script never substitutes another exchange or data provider: if NSE
India cannot be reached, stage 1 exits with a loud FAIL and nothing else
runs.  Passing --no-refresh skips stages 1-2 and only prints the report
and inventory from whatever is already on disk (the OI report still fails
loudly if the contract CSV is missing).
"""
import sys
import time
from pathlib import Path

import fetch_nifty50_option_contracts as fetcher
import nifty50_open_interest as reporter

DOWNLOADS = Path("data/downloads")

# NIFTY option artifacts this pipeline produces or consumes.
REPORT_FILES = [
    fetcher.OUT_CSV,
    fetcher.OUT_STATUS,
    Path("data/downloads/nifty50_options_summary.json"),
    Path("data/downloads/nse_all_indices.json"),
    Path("data/downloads/ltp.json"),
]

STALE_AFTER_SECONDS = 24 * 60 * 60   # flag files older than a day


def human_size(nbytes: int) -> str:
    """Bytes as a short human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024 or unit == "GB":
            return f"{nbytes:,.1f} {unit}" if unit != "B" else f"{nbytes:,} B"
        nbytes /= 1024
    return f"{nbytes:,.1f} GB"  # unreachable, keeps linters happy


def age_seconds(path: Path):
    """Seconds since `path` was last written, or None if it doesn't exist."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return max(0.0, time.time() - mtime)


def human_age(seconds):
    """Seconds as '3s' / '12m' / '5h' / '2d'; '-' when unknown."""
    if seconds is None:
        return "-"
    if seconds < 90:
        return f"{int(seconds)}s"
    for size, unit in ((3600, "m"), (86400, "h")):
        if seconds < size * 60:
            return f"{int(seconds // size)}{unit}"
    return f"{int(seconds // 86400)}d"


def inventory() -> None:
    """Print what NIFTY option data is on disk and how fresh it is."""
    print(f"\nfiles in {DOWNLOADS}/")
    for path in REPORT_FILES:
        if not path.exists():
            print(f"  {path.name:<44} MISSING")
            continue
        age = age_seconds(path)
        stale = "  <-- stale" if age is not None and age > STALE_AFTER_SECONDS else ""
        print(f"  {path.name:<44} {human_size(path.stat().st_size):>10}   "
              f"age {human_age(age):>4}{stale}")
    print("  (everything here is gitignored except the folder's README.md)")


def main() -> None:
    t0 = time.monotonic()
    skip_refresh = "--no-refresh" in sys.argv[1:]

    print("NIFTY 50 option download -- source: NSE India only "
          "(no other provider is ever used)")

    # ---- stage 1: refresh from NSE India ---------------------------------
    if skip_refresh:
        print("\n--no-refresh: keeping the data already on disk")
    else:
        print("\n[1/3] refreshing option-contract data from NSE India ...")
        # Fetcher main() tries the live API, falls back inside the allowed
        # source set to the official archive bhavcopy, and raises SystemExit
        # with a FAIL message if NSE India is unreachable.  It never
        # silently substitutes another provider -- neither do we.
        fetcher.main()

    # ---- stage 2: report --------------------------------------------------
    print("\n[2/3] open-interest report for the nearest expiry ...")
    reporter.main()   # exits loudly if the contract CSV is absent

    # ---- stage 3: inventory ------------------------------------------------
    print("\n[3/3] downloaded files")
    inventory()

    print(f"\ndone in {time.monotonic() - t0:.2f}s")
    print("NOTE: chain data is end-of-session official exchange data, "
          "not live quotes -- see NSE_BLOCKED_NOTES.md.")


if __name__ == "__main__":
    main()
