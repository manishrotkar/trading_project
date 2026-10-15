import math
import sqlite3
from datetime import datetime
from pathlib import Path

OPTION_PROJECT = Path(__file__).resolve().parents[1]
TRADING_PROJECT = OPTION_PROJECT.parents[0]

OPTION_DATABASE = OPTION_PROJECT / "database" / "index_options.db"
IV_DATABASE = OPTION_PROJECT / "database" / "fyers_style_iv.db"
FUTURES_DATABASE = (
    TRADING_PROJECT
    / "futures_project"
    / "database"
    / "futures.db"
)

INDEXES = ("NIFTY", "BANKNIFTY")

FUTURES_SYMBOL_PREFIX = {
    "NIFTY": "NSE:NIFTY",
    "BANKNIFTY": "NSE:BANKNIFTY",
}

RISK_FREE_RATE = 0.08


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black76_price(futures_price, strike, time_to_expiry, rate, volatility, option_type):
    if time_to_expiry <= 0 or volatility <= 0:
        return None

    sigma_sqrt_t = volatility * math.sqrt(time_to_expiry)

    d1 = (
        math.log(futures_price / strike)
        + 0.5 * volatility * volatility * time_to_expiry
    ) / sigma_sqrt_t

    d2 = d1 - sigma_sqrt_t

    discount = math.exp(-rate * time_to_expiry)

    if option_type == "CE":
        return discount * (
            futures_price * norm_cdf(d1)
            - strike * norm_cdf(d2)
        )

    return discount * (
        strike * norm_cdf(-d2)
        - futures_price * norm_cdf(-d1)
    )


def calculate_iv(
    option_price,
    futures_price,
    strike,
    time_to_expiry,
    rate,
    option_type,
):
    if option_price <= 0:
        return None

    intrinsic = max(
        futures_price - strike if option_type == "CE" else strike - futures_price,
        0.0,
    )

    if option_price <= 0 or futures_price <= 0 or strike <= 0:
        return None

    low = 1e-6
    high = 5.0

    low_price = black76_price(
        futures_price,
        strike,
        time_to_expiry,
        rate,
        low,
        option_type,
    )

    high_price = black76_price(
        futures_price,
        strike,
        time_to_expiry,
        rate,
        high,
        option_type,
    )

    target = option_price

    if low_price is None or high_price is None:
        return None

    if target < low_price or target > high_price:
        return None

    for _ in range(100):
        mid = (low + high) / 2.0

        mid_price = black76_price(
            futures_price,
            strike,
            time_to_expiry,
            rate,
            mid,
            option_type,
        )

        if mid_price is None:
            return None

        if mid_price < target:
            low = mid
        else:
            high = mid

    return (low + high) / 2.0


def time_to_expiry(timestamp, expiry):
    dt = datetime.fromisoformat(timestamp)

    expiry_dt = datetime.fromisoformat(
        f"{expiry} 15:30:00"
    )

    seconds = (
        expiry_dt - dt
    ).total_seconds()

    if seconds <= 0:
        return 0.0

    return seconds / (365.0 * 24.0 * 60.0 * 60.0)


def get_current_expiry(option_db, index_name, trading_date):
    row = option_db.execute(
        """
        SELECT MIN(expiry)
        FROM index_options_data
        WHERE index_name = ?
          AND expiry >= ?
        """,
        (
            index_name,
            trading_date,
        ),
    ).fetchone()

    return row[0]


def get_futures_symbol(futures_db, index_name, expiry):
    prefix = FUTURES_SYMBOL_PREFIX[index_name]

    row = futures_db.execute(
        """
        SELECT symbol
        FROM futures_data
        WHERE symbol LIKE ?
          AND expiry = ?
        ORDER BY symbol
        LIMIT 1
        """,
        (
            prefix + "%",
            expiry,
        ),
    ).fetchone()

    return row[0] if row else None


def get_latest_iv_timestamp(iv_db, index_name):
    row = iv_db.execute(
        """
        SELECT MAX(datetime)
        FROM option_iv_data
        WHERE index_name = ?
        """,
        (index_name,),
    ).fetchone()

    return row[0]


def get_option_timestamps(option_db, index_name, after_timestamp):
    if after_timestamp is None:
        query = """
            SELECT DISTINCT datetime
            FROM index_options_data
            WHERE index_name = ?
            ORDER BY datetime
        """
        return [
            row[0]
            for row in option_db.execute(
                query,
                (index_name,),
            ).fetchall()
        ]

    query = """
        SELECT DISTINCT datetime
        FROM index_options_data
        WHERE index_name = ?
          AND datetime > ?
        ORDER BY datetime
    """

    return [
        row[0]
        for row in option_db.execute(
            query,
            (
                index_name,
                after_timestamp,
            ),
        ).fetchall()
    ]


def get_futures_price(
    futures_db,
    futures_symbol,
    timestamp,
):
    row = futures_db.execute(
        """
        SELECT close
        FROM futures_data
        WHERE symbol = ?
          AND datetime LIKE ?
        LIMIT 1
        """,
        (
            futures_symbol,
            timestamp.replace(" ", "T") + "%",
        ),
    ).fetchone()

    return float(row[0]) if row else None


def process_timestamp(
    option_db,
    iv_db,
    futures_db,
    index_name,
    expiry,
    futures_symbol,
    timestamp,
):
    futures_price = get_futures_price(
        futures_db,
        futures_symbol,
        timestamp,
    )

    if futures_price is None:
        return 0

    T = time_to_expiry(
        timestamp,
        expiry,
    )

    if T <= 0:
        return 0

    rows = option_db.execute(
        """
        SELECT
            option_type,
            strike,
            close
        FROM index_options_data
        WHERE index_name = ?
          AND expiry = ?
          AND datetime = ?
        ORDER BY strike, option_type
        """,
        (
            index_name,
            expiry,
            timestamp,
        ),
    ).fetchall()

    inserts = []

    for option_type, strike, close_price in rows:

        option_price = float(close_price)
        strike = float(strike)

        iv = calculate_iv(
            option_price,
            futures_price,
            strike,
            T,
            RISK_FREE_RATE,
            option_type,
        )

        status = "OK" if iv is not None else "FAILED"

        inserts.append(
            (
                index_name,
                f"{index_name}_{expiry}_{strike}_{option_type}",
                option_type,
                strike,
                expiry,
                timestamp,
                option_price,
                futures_price,
                T,
                RISK_FREE_RATE,
                iv,
                status,
            )
        )

    if inserts:

        iv_db.executemany(
            """
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
            """,
            inserts,
        )

        iv_db.commit()

    return len(inserts)


def process_index(
    option_db,
    iv_db,
    futures_db,
    index_name,
):
    latest_option = option_db.execute(
        """
        SELECT MAX(datetime)
        FROM index_options_data
        WHERE index_name = ?
        """,
        (index_name,),
    ).fetchone()[0]

    if latest_option is None:
        print(f"{index_name}: no option data")
        return 0

    trading_date = latest_option[:10]

    expiry = get_current_expiry(
        option_db,
        index_name,
        trading_date,
    )

    if expiry is None:
        print(f"{index_name}: no active expiry")
        return 0

    futures_symbol = get_futures_symbol(
        futures_db,
        index_name,
        expiry,
    )

    if futures_symbol is None:
        print(
            f"{index_name}: "
            f"no futures symbol for expiry {expiry}"
        )
        return 0

    last_iv_timestamp = get_latest_iv_timestamp(
        iv_db,
        index_name,
    )

    timestamps = get_option_timestamps(
        option_db,
        index_name,
        last_iv_timestamp,
    )

    print(
        f"{index_name}: "
        f"expiry={expiry}, "
        f"futures={futures_symbol}, "
        f"new timestamps={len(timestamps):,}"
    )

    total = 0

    for timestamp in timestamps:

        count = process_timestamp(
            option_db,
            iv_db,
            futures_db,
            index_name,
            expiry,
            futures_symbol,
            timestamp,
        )

        total += count

    print(
        f"{index_name}: "
        f"IV rows inserted={total:,}"
    )

    return total


def main():

    print("=" * 70)
    print("INCREMENTAL FYERS-STYLE IV CALCULATION")
    print("=" * 70)

    print(f"Options : {OPTION_DATABASE}")
    print(f"IV      : {IV_DATABASE}")
    print(f"Futures : {FUTURES_DATABASE}")
    print()

    option_db = sqlite3.connect(
        OPTION_DATABASE
    )

    iv_db = sqlite3.connect(
        IV_DATABASE
    )

    futures_db = sqlite3.connect(
        FUTURES_DATABASE
    )

    try:

        total = 0

        for index_name in INDEXES:

            total += process_index(
                option_db,
                iv_db,
                futures_db,
                index_name,
            )

    finally:

        option_db.close()
        iv_db.close()
        futures_db.close()

    print()
    print("=" * 70)
    print("INCREMENTAL FYERS-STYLE IV COMPLETED")
    print("=" * 70)

    print(
        f"Total IV rows inserted : {total:,}"
    )


if __name__ == "__main__":
    main()
