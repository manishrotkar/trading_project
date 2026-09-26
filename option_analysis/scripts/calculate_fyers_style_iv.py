import math
import sqlite3
from datetime import datetime, time
from pathlib import Path

from scipy.optimize import brentq
from scipy.stats import norm


# ============================================================
# PROJECT PATHS
# ============================================================

OPTION_PROJECT = Path(__file__).resolve().parents[1]
MAIN_PROJECT = OPTION_PROJECT.parent

OPTIONS_DB = OPTION_PROJECT / "database" / "index_options.db"

FUTURES_DB = (
    MAIN_PROJECT
    / "futures_project"
    / "database"
    / "futures.db"
)

OUTPUT_DB = OPTION_PROJECT / "database" / "fyers_style_iv.db"


# ============================================================
# SETTINGS
# ============================================================

INDICES = ("NIFTY", "BANKNIFTY")

RISK_FREE_RATE = 0.08
DAYS_IN_YEAR = 365.0
EXPIRY_TIME = time(15, 30)

BATCH_SIZE = 5000


# ============================================================
# BLACK-76 OPTION PRICE
# ============================================================

def black76_price(F, K, T, r, sigma, option_type):

    discount = math.exp(-r * T)

    if sigma <= 0:
        if option_type == "CE":
            return discount * max(F - K, 0.0)

        return discount * max(K - F, 0.0)

    sqrt_T = math.sqrt(T)

    d1 = (
        math.log(F / K)
        + 0.5 * sigma * sigma * T
    ) / (sigma * sqrt_T)

    d2 = d1 - sigma * sqrt_T

    if option_type == "CE":
        return discount * (
            F * norm.cdf(d1)
            - K * norm.cdf(d2)
        )

    return discount * (
        K * norm.cdf(-d2)
        - F * norm.cdf(-d1)
    )


# ============================================================
# CALCULATE IV
# ============================================================

def calculate_iv(F, K, T, r, price, option_type):

    if (
        F <= 0
        or K <= 0
        or T <= 0
        or price <= 0
    ):
        return None, "invalid_input"

    minimum_price = black76_price(
        F, K, T, r, 0.0, option_type
    )

    if price < minimum_price - 0.000001:
        return None, "below_intrinsic"

    def objective(sigma):
        return (
            black76_price(
                F, K, T, r, sigma, option_type
            )
            - price
        )

    lower = 0.0001
    upper = 5.0

    if objective(lower) * objective(upper) > 0:
        return None, "no_solution"

    try:
        iv = brentq(
            objective,
            lower,
            upper,
        )

        return iv, "ok"

    except (ValueError, OverflowError):
        return None, "no_solution"


# ============================================================
# OPEN SOURCE DATABASES READ-ONLY
# ============================================================

def open_readonly(path):

    if not path.exists():
        raise FileNotFoundError(
            f"Database not found: {path}"
        )

    return sqlite3.connect(
        path.resolve().as_uri() + "?mode=ro",
        uri=True,
    )


# ============================================================
# LOAD FUTURES INTO MEMORY
# ============================================================

def load_futures(connection):

    futures = {}
    contracts = {}

    rows = connection.execute(
        """
        SELECT
            symbol,
            expiry,
            datetime,
            close
        FROM futures_data
        WHERE symbol LIKE 'NSE:NIFTY%FUT'
           OR symbol LIKE 'NSE:BANKNIFTY%FUT'
        ORDER BY symbol, datetime
        """
    )

    count = 0

    for symbol, expiry, timestamp, close in rows:

        if symbol.startswith("NSE:BANKNIFTY"):
            index_name = "BANKNIFTY"

        elif symbol.startswith("NSE:NIFTY"):
            index_name = "NIFTY"

        else:
            continue

        # Example:
        # 2026-09-25T15:29:00+05:30
        # becomes:
        # 2026-09-25 15:29:00

        normalized_time = (
            datetime.fromisoformat(timestamp)
            .replace(tzinfo=None)
            .strftime("%Y-%m-%d %H:%M:%S")
        )

        futures[
            (symbol, normalized_time)
        ] = float(close)

        contracts[symbol] = {
            "index_name": index_name,
            "expiry": expiry,
        }

        count += 1

    print(f"Futures candles loaded: {count:,}")

    return futures, contracts


# ============================================================
# FIND CORRESPONDING FUTURES CONTRACT
# ============================================================

def get_futures_symbol(index_name, option_expiry, contracts):

    candidates = []

    for symbol, info in contracts.items():

        if info["index_name"] != index_name:
            continue

        # Use the nearest futures expiry that is
        # on or after the option expiry.

        if info["expiry"] >= option_expiry:
            candidates.append(
                (info["expiry"], symbol)
            )

    if not candidates:
        return None

    candidates.sort()

    return candidates[0][1]


# ============================================================
# CALCULATE ONE STRIKE / TIMESTAMP GROUP
# ============================================================

def process_group(group, futures, contracts):

    index_name, expiry, strike, timestamp = group[0][:4]

    futures_symbol = get_futures_symbol(
        index_name,
        expiry,
        contracts,
    )

    if futures_symbol is None:
        return []

    F = futures.get(
        (futures_symbol, timestamp)
    )

    if F is None or F <= 0:
        return []

    K = float(strike)

    option_rows = {
        row[5]: row
        for row in group
    }

    # Futures >= strike: PE is OTM.
    # Futures < strike: CE is OTM.

    otm_type = "PE" if F >= K else "CE"

    otm_row = option_rows.get(otm_type)

    if otm_row is None:
        return []

    option_price = float(otm_row[6])

    candle_time = datetime.fromisoformat(timestamp)

    expiry_datetime = datetime.combine(
        datetime.fromisoformat(expiry).date(),
        EXPIRY_TIME,
    )

    seconds_remaining = (
        expiry_datetime - candle_time
    ).total_seconds()

    if seconds_remaining <= 0:
        return []

    T = seconds_remaining / (
        DAYS_IN_YEAR * 24 * 60 * 60
    )

    iv, status = calculate_iv(
        F,
        K,
        T,
        RISK_FREE_RATE,
        option_price,
        otm_type,
    )

    results = []

    # Save the same calculated IV for the
    # available CE and PE at this strike/time.

    for option_type in ("CE", "PE"):

        row = option_rows.get(option_type)

        if row is None:
            continue

        symbol = row[4]
        own_price = float(row[6])

        results.append(
            (
                index_name,
                symbol,
                option_type,
                K,
                expiry,
                timestamp,
                own_price,
                F,
                T,
                RISK_FREE_RATE,
                iv,
                status,
            )
        )

    return results


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 65)
    print("FYERS-STYLE HISTORICAL IV")
    print("=" * 65)

    print("Indices: NIFTY, BANKNIFTY")
    print("Model: Black-76")
    print("Source databases: READ-ONLY")
    print(f"Output: {OUTPUT_DB}")
    print()

    options_connection = open_readonly(OPTIONS_DB)
    futures_connection = open_readonly(FUTURES_DB)

    output_connection = sqlite3.connect(OUTPUT_DB)

    try:

        futures, contracts = load_futures(
            futures_connection
        )

        # Read options in groups of:
        # index + expiry + strike + timestamp.

        cursor = options_connection.execute(
            """
            SELECT
                index_name,
                expiry,
                strike,
                datetime,
                symbol,
                option_type,
                close
            FROM index_options_data
            WHERE index_name IN (?, ?)
            ORDER BY
                index_name,
                expiry,
                strike,
                datetime,
                option_type
            """,
            INDICES,
        )

        current_key = None
        current_group = []

        pending = []

        total_groups = 0
        total_inserted = 0

        insert_sql = """
            INSERT OR IGNORE INTO option_iv_data (
                index_name,
                symbol,
                option_type,
                strike,
                expiry,
                datetime,
                option_price,
                futures_price,
                time_to_expiry,
                risk_free_rate,
                iv,
                calculation_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        def save_batch():

            nonlocal total_inserted

            if not pending:
                return

            before = output_connection.total_changes

            output_connection.executemany(
                insert_sql,
                pending,
            )

            output_connection.commit()

            inserted = (
                output_connection.total_changes - before
            )

            total_inserted += inserted

            pending.clear()

        def handle_group(group):

            nonlocal total_groups

            if not group:
                return

            total_groups += 1

            results = process_group(
                group,
                futures,
                contracts,
            )

            pending.extend(results)

            if len(pending) >= BATCH_SIZE:
                save_batch()

            if total_groups % 50000 == 0:
                print(
                    f"Groups processed: {total_groups:,} | "
                    f"New rows: {total_inserted:,}"
                )

        for row in cursor:

            key = row[:4]

            if current_key is None:
                current_key = key

            if key != current_key:

                handle_group(current_group)

                current_group = []
                current_key = key

            current_group.append(row)

        # Process final group.

        handle_group(current_group)

        save_batch()

        print()
        print("=" * 65)
        print("CALCULATION COMPLETED")
        print("=" * 65)

        print(f"Groups processed : {total_groups:,}")
        print(f"New rows inserted: {total_inserted:,}")

        print()
        print("IV calculation status:")

        for status, count in output_connection.execute(
            """
            SELECT calculation_status, COUNT(*)
            FROM option_iv_data
            GROUP BY calculation_status
            ORDER BY COUNT(*) DESC
            """
        ):
            print(f"{status:20} {count:,}")

    finally:

        options_connection.close()
        futures_connection.close()
        output_connection.close()


if __name__ == "__main__":
    main()