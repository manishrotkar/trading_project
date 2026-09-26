from datetime import datetime
from math import exp, log, sqrt
from pathlib import Path
import sqlite3

from scipy.optimize import brentq
from scipy.stats import norm


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OPTIONS_DB = PROJECT_ROOT / "option_analysis/database/index_options.db"
UNDERLYING_DB = PROJECT_ROOT / "option_analysis/database/underlying_data.db"
IV_DB = PROJECT_ROOT / "option_analysis/database/option_iv.db"


# ============================================================
# SETTINGS
# ============================================================

RISK_FREE_RATE = 0.08
EXPIRY_TIME = "15:30:00"
DAYS_IN_YEAR = 365.0

BATCH_SIZE = 5000

# Keep True for testing.
# Change to False only after test is verified.
TEST_MODE = False

TEST_INDEX = "NIFTY"
TEST_SYMBOL = "NSE:NIFTY26SEP22550CE"
TEST_DATE = "2026-09-15"


# ============================================================
# BLACK-SCHOLES CALL
# ============================================================

def black_scholes_call(S, K, T, r, sigma):

    d1 = (
        log(S / K)
        + (r + 0.5 * sigma**2) * T
    ) / (sigma * sqrt(T))

    d2 = d1 - sigma * sqrt(T)

    return (
        S * norm.cdf(d1)
        - K * exp(-r * T) * norm.cdf(d2)
    )


# ============================================================
# BLACK-SCHOLES PUT
# ============================================================

def black_scholes_put(S, K, T, r, sigma):

    d1 = (
        log(S / K)
        + (r + 0.5 * sigma**2) * T
    ) / (sigma * sqrt(T))

    d2 = d1 - sigma * sqrt(T)

    return (
        K * exp(-r * T) * norm.cdf(-d2)
        - S * norm.cdf(-d1)
    )


# ============================================================
# IV CALCULATION
# ============================================================

def calculate_iv(
    option_type,
    S,
    K,
    option_price,
    T,
    r,
):

    if S is None or S <= 0:
        return None, "invalid_underlying"

    if K is None or K <= 0:
        return None, "invalid_strike"

    if option_price is None or option_price <= 0:
        return None, "invalid_option_price"

    if T <= 0:
        return None, "expired"

    if option_type == "CE":

        intrinsic = max(S - K, 0.0)

        if option_price < intrinsic:
            return None, "below_intrinsic"

        def objective(sigma):
            return (
                black_scholes_call(
                    S,
                    K,
                    T,
                    r,
                    sigma,
                )
                - option_price
            )

    elif option_type == "PE":

        intrinsic = max(K - S, 0.0)

        if option_price < intrinsic:
            return None, "below_intrinsic"

        def objective(sigma):
            return (
                black_scholes_put(
                    S,
                    K,
                    T,
                    r,
                    sigma,
                )
                - option_price
            )

    else:
        return None, "unknown_option_type"

    try:

        iv = brentq(
            objective,
            0.0001,
            5.0,
        )

        return iv, "ok"

    except ValueError:

        return None, "no_solution"


# ============================================================
# TIME TO EXPIRY
# ============================================================

def calculate_time_to_expiry(datetime_text, expiry):

    timestamp = datetime.strptime(
        datetime_text,
        "%Y-%m-%d %H:%M:%S",
    )

    expiry_datetime = datetime.strptime(
        f"{expiry} {EXPIRY_TIME}",
        "%Y-%m-%d %H:%M:%S",
    )

    seconds = (
        expiry_datetime - timestamp
    ).total_seconds()

    return seconds / (
        DAYS_IN_YEAR * 24 * 60 * 60
    )


# ============================================================
# DATABASE CONNECTIONS
# ============================================================

def get_connections():

    option_conn = sqlite3.connect(
        OPTIONS_DB
    )

    option_conn.execute(
        "ATTACH DATABASE ? AS underlying_db",
        (str(UNDERLYING_DB),),
    )

    iv_conn = sqlite3.connect(
        IV_DB
    )

    return option_conn, iv_conn


# ============================================================
# GET OPTION SYMBOLS
# ============================================================

def get_option_symbols(option_cur):

    option_cur.execute(
        """
        SELECT DISTINCT
            index_name,
            symbol
        FROM index_options_data
        WHERE index_name IN ('NIFTY', 'BANKNIFTY')
        ORDER BY
            index_name,
            symbol
        """
    )

    return option_cur.fetchall()


# ============================================================
# GET LAST PROCESSED DATETIME FOR ONE SYMBOL
# ============================================================

def get_last_processed(iv_cur, symbol):

    iv_cur.execute(
        """
        SELECT MAX(datetime)
        FROM option_iv_data
        WHERE symbol = ?
        """,
        (symbol,),
    )

    row = iv_cur.fetchone()

    if row and row[0]:
        return row[0]

    return None


# ============================================================
# BUILD TEST QUERY
# ============================================================

def build_test_query():

    query = """
        SELECT
            o.index_name,
            o.symbol,
            o.option_type,
            o.strike,
            o.expiry,
            o.datetime,
            o.close AS option_price,
            u.close AS underlying_price

        FROM index_options_data o

        INNER JOIN underlying_db.underlying_data u
            ON o.datetime = u.datetime
           AND o.index_name = u.index_name

        WHERE
            o.index_name = ?
            AND o.symbol = ?
            AND o.datetime >= ?
            AND o.datetime < date(?, '+1 day')

            AND (
                (
                    o.index_name = 'NIFTY'
                    AND u.symbol = 'NSE:NIFTY50-INDEX'
                )

                OR

                (
                    o.index_name = 'BANKNIFTY'
                    AND u.symbol = 'NSE:NIFTYBANK-INDEX'
                )
            )

        ORDER BY o.datetime
    """

    params = (
        TEST_INDEX,
        TEST_SYMBOL,
        TEST_DATE,
        TEST_DATE,
    )

    return query, params


# ============================================================
# BUILD PRODUCTION QUERY
# ============================================================

def build_production_query(
    index_name,
    symbol,
    last_datetime=None,
):

    if index_name == "NIFTY":

        underlying_symbol = "NSE:NIFTY50-INDEX"

    elif index_name == "BANKNIFTY":

        underlying_symbol = "NSE:NIFTYBANK-INDEX"

    else:

        raise ValueError(
            f"Unsupported index: {index_name}"
        )

    if last_datetime is None:

        query = """
            SELECT
                o.index_name,
                o.symbol,
                o.option_type,
                o.strike,
                o.expiry,
                o.datetime,
                o.close AS option_price,
                u.close AS underlying_price

            FROM index_options_data o

            INNER JOIN underlying_db.underlying_data u
                ON o.datetime = u.datetime
               AND o.index_name = u.index_name

            WHERE
                o.index_name = ?
                AND o.symbol = ?
                AND u.symbol = ?

            ORDER BY o.datetime

            LIMIT ?
        """

        params = (
            index_name,
            symbol,
            underlying_symbol,
            BATCH_SIZE,
        )

    else:

        query = """
            SELECT
                o.index_name,
                o.symbol,
                o.option_type,
                o.strike,
                o.expiry,
                o.datetime,
                o.close AS option_price,
                u.close AS underlying_price

            FROM index_options_data o

            INNER JOIN underlying_db.underlying_data u
                ON o.datetime = u.datetime
               AND o.index_name = u.index_name

            WHERE
                o.index_name = ?
                AND o.symbol = ?
                AND u.symbol = ?
                AND o.datetime > ?

            ORDER BY o.datetime

            LIMIT ?
        """

        params = (
            index_name,
            symbol,
            underlying_symbol,
            last_datetime,
            BATCH_SIZE,
        )

    return query, params


# ============================================================
# INSERT IV RECORDS
# ============================================================

def insert_records(iv_cur, iv_conn, records):

    if not records:
        return 0

    iv_cur.executemany(
        """
        INSERT OR IGNORE INTO option_iv_data (
            index_name,
            symbol,
            option_type,
            strike,
            expiry,
            datetime,
            option_price,
            underlying_price,
            time_to_expiry,
            risk_free_rate,
            iv,
            calculation_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )

    inserted = iv_cur.rowcount

    iv_conn.commit()

    return inserted


# ============================================================
# PROCESS ONE BATCH
# ============================================================

def process_batch(
    rows,
    iv_cur,
    iv_conn,
):

    successful = 0
    failed = 0

    records = []

    for row in rows:

        (
            index_name,
            symbol,
            option_type,
            strike,
            expiry,
            datetime_text,
            option_price,
            underlying_price,
        ) = row

        T = calculate_time_to_expiry(
            datetime_text,
            expiry,
        )

        iv, status = calculate_iv(
            option_type,
            underlying_price,
            strike,
            option_price,
            T,
            RISK_FREE_RATE,
        )

        if status == "ok":

            successful += 1

        else:

            failed += 1

        records.append(
            (
                index_name,
                symbol,
                option_type,
                strike,
                expiry,
                datetime_text,
                option_price,
                underlying_price,
                T,
                RISK_FREE_RATE,
                iv,
                status,
            )
        )

    inserted = insert_records(
        iv_cur,
        iv_conn,
        records,
    )

    return successful, failed, inserted


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 80)
    print("HISTORICAL IV CALCULATION")
    print("=" * 80)

    print("Risk-free rate :", f"{RISK_FREE_RATE:.2%}")
    print("Expiry time    :", EXPIRY_TIME)
    print("Day count      :", DAYS_IN_YEAR)
    print("Batch size     :", BATCH_SIZE)
    print("Test mode      :", TEST_MODE)

    option_conn, iv_conn = get_connections()

    option_cur = option_conn.cursor()
    iv_cur = iv_conn.cursor()

    # ========================================================
    # TEST MODE
    # ========================================================

    if TEST_MODE:

        print()
        print("=" * 80)
        print("TEST MODE")
        print("=" * 80)

        query, params = build_test_query()

        option_cur.execute(
            query,
            params,
        )

        rows = option_cur.fetchall()

        print()
        print("Index  :", TEST_INDEX)
        print("Symbol :", TEST_SYMBOL)
        print("Date   :", TEST_DATE)
        print("Rows selected :", len(rows))

        if rows:

            successful, failed, inserted = process_batch(
                rows,
                iv_cur,
                iv_conn,
            )

            print()
            print("Test batch complete")
            print("-" * 80)
            print("Rows selected :", len(rows))
            print("Successful IV :", successful)
            print("Failed/skipped:", failed)
            print("Rows inserted :", inserted)

            print()
            print("Last processed row:")
            print("Datetime :", rows[-1][5])
            print("Symbol   :", rows[-1][1])

        else:

            print()
            print("No test rows found.")

        iv_cur.execute(
            """
            SELECT COUNT(*)
            FROM option_iv_data
            """
        )

        total_rows = iv_cur.fetchone()[0]

        print()
        print("Total IV rows :", total_rows)

        option_conn.close()
        iv_conn.close()

        print()
        print("=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)

        return

    # ========================================================
    # PRODUCTION MODE
    # ========================================================

    print()
    print("=" * 80)
    print("PRODUCTION MODE")
    print("=" * 80)

    symbols = get_option_symbols(option_cur)

    print()
    print("Total contracts :", len(symbols))

    if not symbols:

        print("No NIFTY/BANKNIFTY contracts found.")

        option_conn.close()
        iv_conn.close()

        return

    total_selected = 0
    total_successful = 0
    total_failed = 0
    total_inserted = 0

    # ========================================================
    # PROCESS EACH CONTRACT
    # ========================================================

    for contract_number, (
        index_name,
        symbol,
    ) in enumerate(symbols, start=1):

        print()
        print("=" * 80)
        print(
            f"CONTRACT {contract_number}/{len(symbols)}"
        )
        print("=" * 80)

        print("Index  :", index_name)
        print("Symbol :", symbol)

        last_datetime = get_last_processed(
            iv_cur,
            symbol,
        )

        if last_datetime:

            print("Resume :", last_datetime)

        else:

            print("Resume : beginning")

        contract_selected = 0
        contract_successful = 0
        contract_failed = 0
        contract_inserted = 0

        # ====================================================
        # BATCH LOOP FOR THIS CONTRACT
        # ====================================================

        while True:

            query, params = build_production_query(
                index_name,
                symbol,
                last_datetime,
            )

            option_cur.execute(
                query,
                params,
            )

            rows = option_cur.fetchall()

            if not rows:

                break

            selected = len(rows)

            successful, failed, inserted = process_batch(
                rows,
                iv_cur,
                iv_conn,
            )

            contract_selected += selected
            contract_successful += successful
            contract_failed += failed
            contract_inserted += inserted

            total_selected += selected
            total_successful += successful
            total_failed += failed
            total_inserted += inserted

            last_datetime = rows[-1][5]

            print(
                f"Batch: {selected:,} | "
                f"OK: {successful:,} | "
                f"Failed: {failed:,} | "
                f"Inserted: {inserted:,} | "
                f"Last: {last_datetime}"
            )

            # Safety check.
            # Prevent an unexpected infinite loop.
            if selected == 0:

                break

        print()
        print("Contract complete")
        print("-" * 80)
        print("Rows selected :", contract_selected)
        print("Successful IV :", contract_successful)
        print("Failed/skipped:", contract_failed)
        print("Rows inserted :", contract_inserted)

    # ========================================================
    # FINAL TOTAL
    # ========================================================

    iv_cur.execute(
        """
        SELECT COUNT(*)
        FROM option_iv_data
        """
    )

    total_rows = iv_cur.fetchone()[0]

    print()
    print("=" * 80)
    print("CALCULATION COMPLETE")
    print("=" * 80)

    print("Total selected :", total_selected)
    print("Total successful:", total_successful)
    print("Total failed   :", total_failed)
    print("Total inserted :", total_inserted)
    print("Total IV rows  :", total_rows)

    option_conn.close()
    iv_conn.close()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()