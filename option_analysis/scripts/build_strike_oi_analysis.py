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

OUTPUT_DATABASE = (
    OPTION_PROJECT
    / "database"
    / "oi_analysis.db"
)


# ============================================================
# SETTINGS
# ============================================================

INDEXES = (
    "NIFTY",
    "BANKNIFTY",
)

EXPIRY = "2026-09-29"


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 65)
    print("BUILDING STRIKE-WISE OI ANALYSIS")
    print("=" * 65)

    print(f"Source database : {SOURCE_DATABASE}")
    print(f"Output database : {OUTPUT_DATABASE}")
    print(f"Expiry          : {EXPIRY}")
    print()

    source = sqlite3.connect(SOURCE_DATABASE)
    output = sqlite3.connect(OUTPUT_DATABASE)

    try:

        # ----------------------------------------------------
        # Clear previous analysis results.
        # Raw option database is NOT modified.
        # ----------------------------------------------------

        output.execute(
            "DELETE FROM strike_oi_analysis"
        )

        output.commit()

        total_inserted = 0

        for index_name in INDEXES:

            print(f"Processing {index_name}...")

            query = """
                SELECT
                    datetime,
                    strike,

                    MAX(
                        CASE
                            WHEN option_type = 'CE'
                            THEN open_interest
                            ELSE 0
                        END
                    ) AS ce_oi,

                    MAX(
                        CASE
                            WHEN option_type = 'PE'
                            THEN open_interest
                            ELSE 0
                        END
                    ) AS pe_oi,

                    MAX(
                        CASE
                            WHEN option_type = 'CE'
                            THEN volume
                            ELSE 0
                        END
                    ) AS ce_volume,

                    MAX(
                        CASE
                            WHEN option_type = 'PE'
                            THEN volume
                            ELSE 0
                        END
                    ) AS pe_volume

                FROM index_options_data

                WHERE
                    index_name = ?
                    AND expiry = ?
                    AND option_type IN ('CE', 'PE')

                GROUP BY
                    datetime,
                    strike

                HAVING
                    SUM(
                        CASE
                            WHEN option_type = 'CE'
                            THEN 1
                            ELSE 0
                        END
                    ) > 0

                    AND

                    SUM(
                        CASE
                            WHEN option_type = 'PE'
                            THEN 1
                            ELSE 0
                        END
                    ) > 0

                ORDER BY
                    datetime,
                    strike
            """

            rows = source.execute(
                query,
                (index_name, EXPIRY),
            )

            batch = []

            for (
                timestamp,
                strike,
                ce_oi,
                pe_oi,
                ce_volume,
                pe_volume,
            ) in rows:

                ce_oi = float(ce_oi or 0)
                pe_oi = float(pe_oi or 0)
                ce_volume = float(ce_volume or 0)
                pe_volume = float(pe_volume or 0)

                total_oi = ce_oi + pe_oi

                # ------------------------------------------------
                # Put-Call Ratio based on OI.
                #
                # PCR = PE OI / CE OI
                # ------------------------------------------------

                if ce_oi > 0:
                    pcr = pe_oi / ce_oi
                else:
                    pcr = None

                batch.append(
                    (
                        index_name,
                        EXPIRY,
                        timestamp,
                        strike,
                        ce_oi,
                        pe_oi,
                        ce_volume,
                        pe_volume,
                        total_oi,
                        pcr,
                    )
                )

                if len(batch) >= 5000:

                    output.executemany(
                        """
                        INSERT OR REPLACE INTO
                        strike_oi_analysis (
                            index_name,
                            expiry,
                            datetime,
                            strike,
                            ce_oi,
                            pe_oi,
                            ce_volume,
                            pe_volume,
                            total_oi,
                            pcr
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        batch,
                    )

                    total_inserted += len(batch)
                    batch.clear()

            # ------------------------------------------------
            # Insert remaining rows.
            # ------------------------------------------------

            if batch:

                output.executemany(
                    """
                    INSERT OR REPLACE INTO
                    strike_oi_analysis (
                        index_name,
                        expiry,
                        datetime,
                        strike,
                        ce_oi,
                        pe_oi,
                        ce_volume,
                        pe_volume,
                        total_oi,
                        pcr
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    batch,
                )

                total_inserted += len(batch)

            output.commit()

            print(
                f"{index_name} completed."
            )

    finally:

        source.close()
        output.close()

    print()
    print("=" * 65)
    print("STRIKE-WISE OI ANALYSIS COMPLETED")
    print("=" * 65)
    print(
        f"Rows inserted : {total_inserted:,}"
    )


if __name__ == "__main__":
    main()