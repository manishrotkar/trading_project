import sqlite3
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

OPTION_PROJECT = Path(__file__).resolve().parents[1]

SOURCE_DATABASE = (
    OPTION_PROJECT
    / "database"
    / "index_options.db"
)

ANALYSIS_DATABASE = (
    OPTION_PROJECT
    / "database"
    / "oi_analysis.db"
)


# ============================================================
# SETTINGS
# ============================================================

EXPIRY = "2026-09-29"

INDEXES = (
    "NIFTY",
    "BANKNIFTY",
)


# ============================================================
# CALCULATE PRICE CHANGE
# ============================================================

def calculate_price_change(
    source,
    analysis,
    index_name,
    option_type,
    column_name,
):
    """
    Calculate option premium change for each strike.

    Comparison is made only within the same trading day.
    """

    rows = source.execute(
        """
        SELECT
            datetime,
            strike,
            close
        FROM index_options_data
        WHERE
            index_name = ?
            AND expiry = ?
            AND option_type = ?
        ORDER BY
            datetime,
            strike
        """,
        (
            index_name,
            EXPIRY,
            option_type,
        ),
    )

    previous_prices = {}
    updates = []

    updated_count = 0

    for (
        timestamp,
        strike,
        close_price,
    ) in rows:

        trading_date = timestamp[:10]

        key = (
            trading_date,
            float(strike),
        )

        current_price = float(close_price)

        # ----------------------------------------------------
        # Calculate change only if previous candle exists
        # on the same trading day.
        # ----------------------------------------------------

        if key in previous_prices:

            price_change = (
                current_price
                - previous_prices[key]
            )

            updates.append(
                (
                    price_change,
                    index_name,
                    EXPIRY,
                    timestamp,
                    float(strike),
                )
            )

        # ----------------------------------------------------
        # Store current price for next candle.
        # ----------------------------------------------------

        previous_prices[key] = current_price

        # ----------------------------------------------------
        # Batch update.
        # ----------------------------------------------------

        if len(updates) >= 5000:

            analysis.executemany(
                f"""
                UPDATE strike_oi_analysis
                SET {column_name} = ?
                WHERE
                    index_name = ?
                    AND expiry = ?
                    AND datetime = ?
                    AND strike = ?
                """,
                updates,
            )

            updated_count += len(updates)
            updates.clear()

    # --------------------------------------------------------
    # Remaining updates.
    # --------------------------------------------------------

    if updates:

        analysis.executemany(
            f"""
            UPDATE strike_oi_analysis
            SET {column_name} = ?
            WHERE
                index_name = ?
                AND expiry = ?
                AND datetime = ?
                AND strike = ?
            """,
            updates,
        )

        updated_count += len(updates)

    analysis.commit()

    return updated_count


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 65)
    print("CALCULATING OPTION PRICE CHANGE")
    print("=" * 65)

    print(f"Source database   : {SOURCE_DATABASE}")
    print(f"Analysis database : {ANALYSIS_DATABASE}")
    print(f"Expiry            : {EXPIRY}")
    print()

    source = sqlite3.connect(SOURCE_DATABASE)
    analysis = sqlite3.connect(ANALYSIS_DATABASE)

    try:

        # ----------------------------------------------------
        # Clear previous price changes.
        # ----------------------------------------------------

        analysis.execute(
            """
            UPDATE strike_oi_analysis
            SET
                ce_price_change = NULL,
                pe_price_change = NULL
            """
        )

        analysis.commit()

        total_ce = 0
        total_pe = 0

        # ----------------------------------------------------
        # Process each index.
        # ----------------------------------------------------

        for index_name in INDEXES:

            print(f"Processing {index_name}...")

            # ------------------------------------------------
            # CE price change
            # ------------------------------------------------

            ce_count = calculate_price_change(
                source,
                analysis,
                index_name,
                "CE",
                "ce_price_change",
            )

            # ------------------------------------------------
            # PE price change
            # ------------------------------------------------

            pe_count = calculate_price_change(
                source,
                analysis,
                index_name,
                "PE",
                "pe_price_change",
            )

            total_ce += ce_count
            total_pe += pe_count

            print(
                f"{index_name} completed | "
                f"CE: {ce_count:,} | "
                f"PE: {pe_count:,}"
            )

    finally:

        source.close()
        analysis.close()

    print()
    print("=" * 65)
    print("OPTION PRICE CHANGE COMPLETED")
    print("=" * 65)

    print(
        f"CE price changes : {total_ce:,}"
    )

    print(
        f"PE price changes : {total_pe:,}"
    )


if __name__ == "__main__":
    main()