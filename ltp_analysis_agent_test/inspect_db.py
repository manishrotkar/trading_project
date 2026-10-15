# Inspection-only script: schema, tables, columns, symbols, samples.

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "database" / "futures.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

cur = conn.cursor()

# 1. Table list
print("=" * 70)
print("TABLES")
print("=" * 70)
tables = cur.execute(
    "SELECT name, type FROM sqlite_master WHERE type IN ('table','view')"
).fetchall()
for t in tables:
    print(f"  {t['type']}: {t['name']}")

# 2. Schema of each table
print()
print("=" * 70)
print("SCHEMA (SQL)")
print("=" * 70)
for t in tables:
    sql = cur.execute(
        "SELECT sql FROM sqlite_master WHERE name = ?", (t["name"],)
    ).fetchone()["sql"]
    print(f"--- {t['name']} ---")
    print(sql)
    print()

# 3. Column info + row counts
for t in tables:
    name = t["name"]
    print("=" * 70)
    print(f"COLUMNS + COUNT: {name}")
    print("=" * 70)
    cols = cur.execute(f"PRAGMA table_info({name})").fetchall()
    for c in cols:
        print(f"  {c['name']:<16} {c['type']:<10} pk={c['pk']}")
    n = cur.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    print(f"  -> row count: {n:,}")
    print()

# 4. Symbols / contracts / expiries
print("=" * 70)
print("SYMBOL / CONTRACT / EXPIRY COMBINATIONS")
print("=" * 70)
rows = cur.execute(
    """
    SELECT symbol, contract, MIN(datetime) AS first_ts, MAX(datetime) AS last_ts,
           COUNT(*) AS n
    FROM futures_data
    GROUP BY symbol, contract
    ORDER BY symbol, contract
    """
).fetchall()
for r in rows:
    print(f"  {r['symbol']:<16} {r['contract']:<24} "
          f"{r['first_ts']} -> {r['last_ts']}  rows={r['n']:,}")

# 5. Distinct expiry values
print()
print("=" * 70)
print("DISTINCT EXPIRIES")
print("=" * 70)
rows = cur.execute(
    "SELECT symbol, contract, expiry, COUNT(*) AS n FROM futures_data "
    "GROUP BY symbol, contract, expiry ORDER BY symbol, expiry"
).fetchall()
for r in rows:
    print(f"  {r['symbol']:<16} {r['contract']:<24} expiry={r['expiry']} rows={r['n']:,}")

conn.close()
