import sqlite3

OI_DB = "option_analysis/database/oi_analysis.db"

conn = sqlite3.connect(OI_DB)

# Get all option OI data
rows = conn.execute("""
    SELECT
        index_name,
        expiry,
        datetime,
        strike,
        ce_oi,
        pe_oi,
        ce_oi_change,
        pe_oi_change
    FROM strike_oi_analysis
    ORDER BY index_name, expiry, datetime, strike
""").fetchall()

# Group by index + expiry + datetime
groups = {}

for row in rows:
    index_name, expiry, datetime, strike, ce_oi, pe_oi, ce_chg, pe_chg = row

    key = (index_name, expiry, datetime)

    if key not in groups:
        groups[key] = []

    groups[key].append(row)

updated = 0

for (index_name, expiry, datetime), current_rows in groups.items():

    # Find previous candle
    previous_time = conn.execute("""
        SELECT MAX(datetime)
        FROM strike_oi_analysis
        WHERE index_name = ?
          AND expiry = ?
          AND datetime < ?
    """, (index_name, expiry, datetime)).fetchone()[0]

    # First candle has no previous candle
    if previous_time is None:
        continue

    previous_rows = conn.execute("""
        SELECT strike, ce_oi, pe_oi
        FROM strike_oi_analysis
        WHERE index_name = ?
          AND expiry = ?
          AND datetime = ?
    """, (index_name, expiry, previous_time)).fetchall()

    previous = {
        strike: (ce_oi, pe_oi)
        for strike, ce_oi, pe_oi in previous_rows
    }

    # Get ATM already calculated in our concentration table
    atm_row = conn.execute("""
        SELECT atm_strike
        FROM atm_oi_concentration
        WHERE index_name = ?
          AND expiry = ?
          AND datetime = ?
    """, (index_name, expiry, datetime)).fetchone()

    if atm_row is None:
        continue

    atm_strike = atm_row[0]

    current = [
        r for r in current_rows
        if r[6] is not None
        and r[7] is not None
        and r[3] in previous
    ]

    if not current:
        continue

    # Find strike nearest to ATM
    atm_index = min(
        range(len(current)),
        key=lambda i: abs(current[i][3] - atm_strike)
    )

    def range_pct(n):
        selected = current[
            max(0, atm_index - n):
            min(len(current), atm_index + n + 1)
        ]

        ce_change = sum(r[6] for r in selected)
        pe_change = sum(r[7] for r in selected)

        ce_previous = sum(previous[r[3]][0] for r in selected)
        pe_previous = sum(previous[r[3]][1] for r in selected)

        ce_pct = (
            ce_change * 100.0 / ce_previous
            if ce_previous != 0 else None
        )

        pe_pct = (
            pe_change * 100.0 / pe_previous
            if pe_previous != 0 else None
        )

        return ce_pct, pe_pct

    ce_atm, pe_atm = range_pct(0)
    ce_pm1, pe_pm1 = range_pct(1)
    ce_pm2, pe_pm2 = range_pct(2)
    ce_pm5, pe_pm5 = range_pct(5)
    ce_pm10, pe_pm10 = range_pct(10)
    ce_pm20, pe_pm20 = range_pct(20)

    conn.execute("""
        UPDATE atm_oi_concentration
        SET
            ce_oi_change_pct_atm = ?,
            pe_oi_change_pct_atm = ?,

            ce_oi_change_pct_pm1 = ?,
            pe_oi_change_pct_pm1 = ?,

            ce_oi_change_pct_pm2 = ?,
            pe_oi_change_pct_pm2 = ?,

            ce_oi_change_pct_pm5 = ?,
            pe_oi_change_pct_pm5 = ?,

            ce_oi_change_pct_pm10 = ?,
            pe_oi_change_pct_pm10 = ?,

            ce_oi_change_pct_pm20 = ?,
            pe_oi_change_pct_pm20 = ?

        WHERE index_name = ?
          AND expiry = ?
          AND datetime = ?
    """, (
        ce_atm, pe_atm,
        ce_pm1, pe_pm1,
        ce_pm2, pe_pm2,
        ce_pm5, pe_pm5,
        ce_pm10, pe_pm10,
        ce_pm20, pe_pm20,
        index_name, expiry, datetime
    ))

    updated += 1

conn.commit()
conn.close()

print(f"OI percentage rows updated: {updated}")