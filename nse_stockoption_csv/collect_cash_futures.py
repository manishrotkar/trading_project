
import os
import sqlite3
from pathlib import Path
from datetime import date, datetime, timezone

import requests
from dotenv import load_dotenv

ROOT = Path.home() / "trading_project"
PROJECT = ROOT / "nse_stockoption_csv"
DB = PROJECT / "database" / "stock_option_chain.db"
MASTER_URL = "https://public.fyers.in/sym_details/NSE_FO_sym_master.json"
QUOTES_URL = "https://api-t1.fyers.in/data/quotes"
DEPTH_URL = "https://api-t1.fyers.in/data/depth"


def get_api():
    load_dotenv(ROOT / ".env")
    app_id = os.getenv("FYERS_APP_ID", "").strip()
    token_file = ROOT / "access.txt"

    if not app_id or not token_file.is_file():
        raise RuntimeError("FYERS credentials or access token file missing.")

    token = token_file.read_text().strip()
    if not token:
        raise RuntimeError("FYERS access token file is empty.")

    return requests.Session(), {
        "Authorization": f"{app_id}:{token}",
        "Content-Type": "application/json",
    }


def get_nearest_future(session):
    response = session.get(MASTER_URL, timeout=60)
    response.raise_for_status()
    master = response.json()

    candidates = []
    today = date.today()

    for key, item in master.items():
        symbol = item.get("symTicker", key)
        text = f"{symbol} {item.get('exSymName', '')} {item.get('symDetails', '')}".upper()

        if "RELIANCE" not in text or item.get("optType") != "XX":
            continue

        try:
            expiry = datetime.fromtimestamp(
                int(item.get("expiryDate", 0)), timezone.utc
            ).date()
        except (ValueError, TypeError, OSError):
            continue

        if expiry >= today and symbol.startswith("NSE:"):
            candidates.append((expiry, symbol))

    if not candidates:
        raise RuntimeError("No non-expired RELIANCE futures contract found.")

    candidates.sort()
    return candidates[0]


def main():
    session, headers = get_api()

    future_expiry, future_symbol = get_nearest_future(session)
    cash_symbol = "NSE:RELIANCE-EQ"

    response = session.get(
        QUOTES_URL,
        headers=headers,
        params={"symbols": f"{cash_symbol},{future_symbol}"},
        timeout=30,
    )
    response.raise_for_status()
    quote_data = response.json()

    if quote_data.get("s") != "ok":
        raise RuntimeError(f"Quote request failed: {quote_data.get('message')}")

    quotes = {
        item.get("n"): item.get("v", {})
        for item in quote_data.get("d", [])
    }

    if cash_symbol not in quotes or future_symbol not in quotes:
        raise RuntimeError("Cash or futures quote was missing.")

    depth_response = session.get(
        DEPTH_URL,
        headers=headers,
        params={"symbol": future_symbol, "ohlcv_flag": "1"},
        timeout=30,
    )
    depth_response.raise_for_status()
    depth_data = depth_response.json()

    if depth_data.get("s") != "ok":
        raise RuntimeError(f"Depth request failed: {depth_data.get('message')}")

    depth_map = depth_data.get("d", {})
    future_depth = depth_map.get(future_symbol, {})
    if not future_depth and depth_map:
        future_depth = next(iter(depth_map.values()))

    cash = quotes[cash_symbol]
    future = quotes[future_symbol]
    captured_at = datetime.now().astimezone().isoformat(timespec="seconds")

    cash_ltp = cash.get("lp")
    future_ltp = future.get("lp")
    premium = (
        float(future_ltp) - float(cash_ltp)
        if cash_ltp is not None and future_ltp is not None
        else None
    )
    premium_pct = (
        100 * premium / float(cash_ltp)
        if premium is not None and float(cash_ltp) != 0
        else None
    )

    DB.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cash_futures_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                cash_ltp REAL,
                cash_change REAL,
                cash_change_pct REAL,
                cash_volume INTEGER,
                future_symbol TEXT NOT NULL,
                future_expiry TEXT NOT NULL,
                future_ltp REAL,
                future_change REAL,
                future_change_pct REAL,
                future_volume INTEGER,
                future_oi INTEGER,
                future_avg_price REAL,
                future_premium REAL,
                future_premium_pct REAL
            )
        """)

        conn.execute("""
            INSERT INTO cash_futures_snapshots (
                symbol, captured_at, cash_ltp, cash_change,
                cash_change_pct, cash_volume, future_symbol,
                future_expiry, future_ltp, future_change,
                future_change_pct, future_volume, future_oi,
                future_avg_price, future_premium, future_premium_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "RELIANCE", captured_at,
            cash.get("lp"), cash.get("ch"), cash.get("chp"),
            cash.get("volume"),
            future_symbol, future_expiry.isoformat(),
            future.get("lp"), future.get("ch"), future.get("chp"),
            future.get("volume", future_depth.get("v")),
            future_depth.get("oi"),
            future_depth.get("atp"),
            premium, premium_pct,
        ))

    print("\nCash and futures snapshot saved.")
    print("Captured at:", captured_at)
    print("Cash LTP:", cash.get("lp"))
    print("Cash change (%):", cash.get("chp"))
    print("Futures symbol:", future_symbol)
    print("Futures expiry:", future_expiry)
    print("Futures LTP:", future.get("lp"))
    print("Futures OI:", future_depth.get("oi"))
    print("Futures premium:", premium)
    print("Futures premium (%):", premium_pct)
    print("Database:", DB)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, requests.RequestException, ValueError, sqlite3.Error) as exc:
        print("ERROR:", exc)
        raise SystemExit(1)
