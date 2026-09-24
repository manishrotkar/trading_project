import sqlite3
from pathlib import Path

PROJECT_DIR = Path("/home/manish/trading_project/stock_screener")
DB_PATH = PROJECT_DIR / "database" / "nse_stockdata.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS nse_stockdata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock TEXT NOT NULL,
    symbol TEXT NOT NULL,
    datetime TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER
);
""")

cursor.execute("""
CREATE UNIQUE INDEX IF NOT EXISTS idx_nse_stockdata_unique
ON nse_stockdata(symbol, datetime);
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_nse_stockdata_symbol_datetime
ON nse_stockdata(symbol, datetime);
""")

conn.commit()

print("Database schema created successfully.")
print(f"Database: {DB_PATH}")

cursor.execute("""
SELECT name
FROM sqlite_master
WHERE type = 'table';
""")

print("\nTables:")
for row in cursor.fetchall():
    print("-", row[0])

conn.close()
