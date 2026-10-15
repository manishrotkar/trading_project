import sqlite3
from pathlib import Path

TRADING_PROJECT = Path(__file__).resolve().parents[2]

IV_DATABASE = (
    TRADING_PROJECT
    / "option_analysis"
    / "database"
    / "iv_analysis.db"
)

OI_DATABASE = (
    TRADING_PROJECT
    / "option_analysis"
    / "database"
    / "oi_analysis.db"
)

INDEXES = (
    "NIFTY",
    "BANKNIFTY",
)


def get_latest_expiry(oi_db, index_name):
    row = oi_db.execute(
        """
        SELECT MAX(expiry)
        FROM strike_oi_analysis
        WHERE index_name = ?
        """,
        (index_name,),
    ).fetchone()

    return row[0]


def get_latest_timestamp(iv_db, index_name):
    row = iv_db.execute(
        """
        SELECT MAX(datetime)
        FROM atm_iv
        WHERE index_name = ?
        """,
        (index_name,),
    ).fetchone()

    return row[0]


def process_index(iv_db, oi_db, index_name):

    expiry = get_latest_expiry(
        oi_db,
        index_name,
    )

    if expiry is None:
        print(f"{index_name}: no expiry found")
        return 0

    timestamp = get_latest_timestamp(
        iv_db,
        index_name,
    )

    if timestamp is None:
        print(f"{index_name}: no ATM IV timestamp found")
        return 0

    print(
        f"{index_name}: "
        f"expiry={expiry}, "
        f"timestamp={timestamp}"
    )

    iv_row = iv_db.execute(
        """
        SELECT
            a.datetime,
            a.futures_price,
            a.atm_strike,
            a.atm_iv,
            r.iv_rank,
            r.iv_percentile,
            r.actual_lookback_days
        FROM atm_iv a

        LEFT JOIN iv_rank_percentile r
            ON r.index_name = a.index_name
            AND r.datetime = a.datetime
            AND r.lookback_days = 25

        WHERE a.index_name = ?
          AND a.datetime = ?

        LIMIT 1
        """,
        (
            index_name,
            timestamp,
        ),
    ).fetchone()

    if iv_row is None:
        print(
            f"{index_name}: "
            f"no IV data for {timestamp}"
        )
        return 0

    (
        timestamp,
        futures_price,
        atm_strike,
        atm_iv,
        iv_rank,
        iv_percentile,
        actual_lookback_days,
    ) = iv_row

    oi_row = oi_db.execute(
        """
        SELECT
            ce_oi,
            pe_oi,
            total_oi,
            pcr,
            ce_oi_change,
            pe_oi_change,
            ce_activity,
            pe_activity
        FROM strike_oi_analysis
        WHERE index_name = ?
          AND expiry = ?
          AND datetime = ?
          AND strike = ?
        """,
        (
            index_name,
            expiry,
            timestamp,
            float(atm_strike),
        ),
    ).fetchone()

    if oi_row is None:
        print(
            f"{index_name}: "
            f"ATM strike {atm_strike} not found"
        )
        return 0

    (
        ce_oi,
        pe_oi,
        total_oi,
        pcr,
        ce_oi_change,
        pe_oi_change,
        ce_activity,
        pe_activity,
    ) = oi_row

    oi_db.execute(
        """
        INSERT OR REPLACE INTO atm_oi_analysis (
            index_name,
            expiry,
            datetime,
            futures_price,
            atm_strike,
            atm_ce_oi,
            atm_pe_oi,
            atm_total_oi,
            atm_pcr,
            atm_ce_oi_change,
            atm_pe_oi_change,
            atm_ce_activity,
            atm_pe_activity,
            atm_iv,
            iv_rank,
            iv_percentile,
            actual_lookback_days
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            index_name,
            expiry,
            timestamp,
            float(futures_price),
            float(atm_strike),
            float(ce_oi),
            float(pe_oi),
            float(total_oi),
            pcr,
            ce_oi_change,
            pe_oi_change,
            ce_activity,
            pe_activity,
            float(atm_iv),
            iv_rank,
            iv_percentile,
            actual_lookback_days,
        ),
    )

    oi_db.commit()

    print(
        f"{index_name}: "
        f"updated ATM strike={float(atm_strike):.0f}"
    )

    return 1


def main():

    print("=" * 70)
    print("INCREMENTAL LIVE ATM OI ANALYSIS")
    print("=" * 70)

    print(f"IV database : {IV_DATABASE}")
    print(f"OI database : {OI_DATABASE}")
    print()

    iv_db = sqlite3.connect(
        IV_DATABASE
    )

    oi_db = sqlite3.connect(
        OI_DATABASE
    )

    try:

        total = 0

        for index_name in INDEXES:
            total += process_index(
                iv_db,
                oi_db,
                index_name,
            )

    finally:

        iv_db.close()
        oi_db.close()

    print()
    print("=" * 70)
    print("INCREMENTAL ATM OI ANALYSIS COMPLETED")
    print("=" * 70)

    print(
        f"Rows updated : {total:,}"
    )


if __name__ == "__main__":
    main()
