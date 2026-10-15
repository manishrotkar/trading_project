import sqlite3
from pathlib import Path

# ============================================================
# PATHS
# ============================================================

OPTION_PROJECT = Path(__file__).resolve().parents[1]
DB = OPTION_PROJECT / "database" / "oi_analysis.db"

# ============================================================
# SETTINGS
# ============================================================

EXPIRY = "2026-09-29"

INDEX_CONFIG = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
}

RANGES = (1, 2, 5, 10)


# ============================================================
# HELPERS
# ============================================================

def required_strikes(atm_strike, step, range_size):
    return {
        atm_strike + step * offset
        for offset in range(-range_size, range_size + 1)
    }


def calculate_range(strikes, required):
    if not required.issubset(strikes):
        return None, None

    ce_oi = sum(strikes[s]["ce_oi"] for s in required)
    pe_oi = sum(strikes[s]["pe_oi"] for s in required)

    return ce_oi, pe_oi


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("REBUILDING ATM OI CONCENTRATION")
    print("=" * 70)
    print(f"Database : {DB}")
    print(f"Expiry   : {EXPIRY}")
    print("Method   : Futures-based ATM + exact strike ranges")
    print("PCR      : Complete ATM +/-10")
    print()

    conn = sqlite3.connect(DB)

    try:

        total_updated = 0

        for index_name, step in INDEX_CONFIG.items():

            print(f"Processing {index_name}...")

            atm_rows = conn.execute(
                """
                SELECT
                    datetime,
                    futures_price,
                    atm_strike
                FROM atm_oi_analysis
                WHERE index_name = ?
                ORDER BY datetime
                """,
                (index_name,),
            ).fetchall()

            updated = 0
            complete = {1: 0, 2: 0, 5: 0, 10: 0}

            for timestamp, futures_price, atm_strike in atm_rows:

                option_rows = conn.execute(
                    """
                    SELECT
                        strike,
                        ce_oi,
                        pe_oi
                    FROM strike_oi_analysis
                    WHERE index_name = ?
                      AND expiry = ?
                      AND datetime = ?
                    """,
                    (
                        index_name,
                        EXPIRY,
                        timestamp,
                    ),
                ).fetchall()

                strikes = {
                    float(strike): {
                        "ce_oi": float(ce_oi),
                        "pe_oi": float(pe_oi),
                    }
                    for strike, ce_oi, pe_oi in option_rows
                }

                atm_strike = float(atm_strike)

                # ------------------------------------------------
                # ATM must exist
                # ------------------------------------------------

                if atm_strike not in strikes:
                    continue

                ce_atm = strikes[atm_strike]["ce_oi"]
                pe_atm = strikes[atm_strike]["pe_oi"]

                range_values = {}

                for n in RANGES:

                    required = required_strikes(
                        atm_strike,
                        step,
                        n,
                    )

                    ce_range, pe_range = calculate_range(
                        strikes,
                        required,
                    )

                    range_values[n] = (
                        ce_range,
                        pe_range,
                    )

                    if ce_range is not None:
                        complete[n] += 1

                # ------------------------------------------------
                # Complete PCR using ATM +/-10
                # ------------------------------------------------

                ce_pm10, pe_pm10 = range_values[10]

                if (
                    ce_pm10 is not None
                    and ce_pm10 != 0
                ):
                    complete_pcr = pe_pm10 / ce_pm10
                else:
                    complete_pcr = None

                # ------------------------------------------------
                # Concentration relative to complete +/-10
                # ------------------------------------------------

                concentrations = {}

                if (
                    ce_pm10 is not None
                    and ce_pm10 != 0
                    and pe_pm10 is not None
                    and pe_pm10 != 0
                ):

                    for n in RANGES:

                        ce_range, pe_range = range_values[n]

                        if ce_range is not None:
                            ce_concentration = (
                                ce_range / ce_pm10 * 100.0
                            )
                        else:
                            ce_concentration = None

                        if pe_range is not None:
                            pe_concentration = (
                                pe_range / pe_pm10 * 100.0
                            )
                        else:
                            pe_concentration = None

                        concentrations[n] = (
                            ce_concentration,
                            pe_concentration,
                        )

                else:

                    concentrations = {
                        n: (None, None)
                        for n in RANGES
                    }

                # ------------------------------------------------
                # Insert corrected row
                #
                # ±20 intentionally remains NULL.
                # OI-change fields are calculated later.
                # ------------------------------------------------

                conn.execute(
                    """
                    INSERT OR REPLACE INTO atm_oi_concentration (
                        index_name,
                        expiry,
                        datetime,
                        futures_price,
                        atm_strike,

                        ce_oi_atm,
                        pe_oi_atm,

                        ce_oi_atm_pm1,
                        pe_oi_atm_pm1,

                        ce_oi_atm_pm2,
                        pe_oi_atm_pm2,

                        ce_oi_atm_pm5,
                        pe_oi_atm_pm5,

                        ce_oi_atm_pm10,
                        pe_oi_atm_pm10,

                        ce_oi_atm_pm20,
                        pe_oi_atm_pm20,

                        ce_concentration_pm1,
                        pe_concentration_pm1,

                        ce_concentration_pm2,
                        pe_concentration_pm2,

                        ce_concentration_pm5,
                        pe_concentration_pm5,

                        ce_concentration_pm10,
                        pe_concentration_pm10
                    )
                    VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?,
                        NULL, NULL,
                        ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?
                    )
                    """,
                    (
                        index_name,
                        EXPIRY,
                        timestamp,
                        float(futures_price),
                        atm_strike,

                        ce_atm,
                        pe_atm,

                        range_values[1][0],
                        range_values[1][1],

                        range_values[2][0],
                        range_values[2][1],

                        range_values[5][0],
                        range_values[5][1],

                        range_values[10][0],
                        range_values[10][1],

                        concentrations[1][0],
                        concentrations[1][1],

                        concentrations[2][0],
                        concentrations[2][1],

                        concentrations[5][0],
                        concentrations[5][1],

                        concentrations[10][0],
                        concentrations[10][1],
                    ),
                )

                updated += 1

            conn.commit()

            total_updated += updated

            print(f"{index_name} completed.")
            print(f"  Rows               : {updated:,}")
            print(f"  Complete +/-1      : {complete[1]:,}")
            print(f"  Complete +/-2      : {complete[2]:,}")
            print(f"  Complete +/-5      : {complete[5]:,}")
            print(f"  Complete +/-10     : {complete[10]:,}")
            print()

        print("=" * 70)
        print("REBUILD COMPLETED")
        print("=" * 70)
        print(f"Total rows inserted : {total_updated:,}")
        print()
        print("Complete PCR uses ATM +/-10.")
        print("Legacy +/-20 data is not used.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
