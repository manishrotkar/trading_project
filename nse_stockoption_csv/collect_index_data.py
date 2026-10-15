
import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent
TRADING_DIR = Path.home() / "trading_project"
ENV_FILE = TRADING_DIR / ".env"
TOKEN_FILE = TRADING_DIR / "access.txt"
DB_FILE = PROJECT_DIR / "database" / "stock_option_chain.db"

OPTIONS_URL = "https://api-t1.fyers.in/data/options-chain-v3"
MASTER_URL = "https://public.fyers.in/sym_details/NSE_FO_sym_master.json"
QUOTES_URL = "https://api-t1.fyers.in/data/quotes"
DEPTH_URL = "https://api-t1.fyers.in/data/depth"

INSTRUMENTS = {
    "1": {
        "name": "NIFTY 50",
        "symbol": "NIFTY50",
        "spot": "NSE:NIFTY50-INDEX",
        "future_prefix": "NSE:NIFTY",
        "future_pattern": "NIFTY",
        "options_symbol": "NSE:NIFTY50-INDEX",
    },
    "2": {
        "name": "BANKNIFTY",
        "symbol": "BANKNIFTY",
        "spot": "NSE:NIFTYBANK-INDEX",
        "future_prefix": "NSE:BANKNIFTY",
        "future_pattern": "BANKNIFTY",
        "options_symbol": "NSE:NIFTYBANK-INDEX",
    },
}


def get_api():
    load_dotenv(ENV_FILE)
    app_id = os.getenv("FYERS_APP_ID", "").strip()

    if not app_id:
        raise RuntimeError(f"FYERS_APP_ID is missing from {ENV_FILE}")

    if not TOKEN_FILE.is_file():
        raise RuntimeError(f"FYERS access-token file not found: {TOKEN_FILE}")

    token = TOKEN_FILE.read_text().strip()
    if not token:
        raise RuntimeError("FYERS access-token file is empty")

    session = requests.Session()
    headers = {
        "Authorization": f"{app_id}:{token}",
        "Content-Type": "application/json",
    }
    return session, headers


def checked_json(response, description):
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(
            f"{description}: non-JSON response, HTTP {response.status_code}"
        ) from None

    if response.status_code != 200:
        message = data.get("message", "No API error message")
        raise RuntimeError(
            f"{description}: HTTP {response.status_code}: {message}"
        )
    return data


def get_number(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def get_integer(value):
    number = get_number(value)
    return int(number) if number is not None else None


def choose_instrument():
    print("\nSelect index to collect:")
    print("1. NIFTY 50")
    print("2. BANKNIFTY")
    choice = input("Enter 1 or 2: ").strip()

    if choice not in INSTRUMENTS:
        raise ValueError("Invalid choice. Enter 1 for NIFTY 50 or 2 for BANKNIFTY.")
    return INSTRUMENTS[choice]


def resolve_instrument(value):
    value = value.strip().upper()
    aliases = {
        "1": "NIFTY50",
        "NIFTY": "NIFTY50",
        "NIFTY 50": "NIFTY50",
        "NIFTY50": "NIFTY50",
        "2": "BANKNIFTY",
        "BANK NIFTY": "BANKNIFTY",
        "BANKNIFTY": "BANKNIFTY",
    }
    canonical = aliases.get(value)
    if not canonical:
        raise ValueError("Instrument must be NIFTY50 or BANKNIFTY.")

    for item in INSTRUMENTS.values():
        if item["symbol"] == canonical:
            return item
    raise ValueError("Unsupported index.")


def expiry_items(data):
    items = data.get("data", {}).get("expiryData", [])
    if not isinstance(items, list):
        return []
    return [
        item for item in items
        if isinstance(item, dict) and item.get("expiry") is not None
    ]


def expiry_date(item):
    # FYERS expiry labels are commonly DD-MM-YYYY.
    label = str(item.get("date", "")).strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(label, fmt).date()
        except ValueError:
            pass

    timestamp = get_integer(item.get("expiry"))
    if timestamp is not None:
        try:
            return datetime.fromtimestamp(timestamp, timezone.utc).date()
        except (ValueError, OSError, OverflowError):
            pass
    return None


def get_options_chain(session, headers, instrument, expiry=None):
    params = {
        "symbol": instrument["options_symbol"],
        "strikecount": 10,
        "timestamp": str(expiry["expiry"]) if expiry else "",
        "greeks": "1",
    }
    response = session.get(
        OPTIONS_URL, headers=headers, params=params, timeout=30
    )
    data = checked_json(response, "FYERS options-chain request")
    if data.get("s") != "ok":
        raise RuntimeError(
            f"FYERS options-chain API error: {data.get('message', 'unknown error')}"
        )
    return data.get("data", {})


def choose_nearest_expiry(chain):
    expiries = expiry_items(chain)
    today = date.today()
    valid = []

    for item in expiries:
        expiry = expiry_date(item)
        if expiry and expiry >= today:
            valid.append((expiry, item))

    if not valid:
        raise RuntimeError("FYERS returned no valid, non-expired options expiry.")

    valid.sort(key=lambda pair: pair[0])
    return valid[0][1], valid[0][0]


def normalize_contracts(chain):
    contracts = []

    for item in chain.get("optionsChain", []):
        if not isinstance(item, dict):
            continue

        strike = get_number(item.get("strike_price"))
        option_type = str(item.get("option_type", "")).upper()

        if strike is None or strike <= 0 or option_type not in ("CE", "PE"):
            continue

        greeks = item.get("greeks") or {}
        contracts.append({
            "strike_price": strike,
            "option_type": option_type,
            "option_symbol": item.get("symbol"),
            "ltp": get_number(item.get("ltp")),
            "ltp_change": get_number(item.get("ltpch")),
            "ltp_change_pct": get_number(item.get("ltpchp")),
            "oi": get_integer(item.get("oi")),
            "oi_change": get_integer(item.get("oich")),
            "oi_change_pct": get_number(item.get("oichp")),
            "previous_oi": get_integer(item.get("prev_oi")),
            "volume": get_integer(item.get("volume")),
            "bid": get_number(item.get("bid")),
            "ask": get_number(item.get("ask")),
            "iv": get_number(greeks.get("iv")),
            "delta": get_number(greeks.get("delta")),
            "gamma": get_number(greeks.get("gamma")),
            "theta": get_number(greeks.get("theta")),
            "vega": get_number(greeks.get("vega")),
            "raw_record": json.dumps(item, separators=(",", ":")),
        })

    if not contracts:
        raise RuntimeError("No valid CE/PE option contracts were returned.")
    if not any(c["option_type"] == "CE" for c in contracts):
        raise RuntimeError("Options response contains no call contracts.")
    if not any(c["option_type"] == "PE" for c in contracts):
        raise RuntimeError("Options response contains no put contracts.")
    return contracts


def find_nearest_future(session, instrument):
    response = session.get(MASTER_URL, timeout=60)
    master = checked_json(response, "FYERS futures symbol master")

    if not isinstance(master, dict):
        raise RuntimeError("Unexpected FYERS symbol-master format.")

    candidates = []
    today = date.today()

    # Exact prefixes prevent FINNIFTY/MIDCPNIFTY/NIFTYNXT50 from
    # being mistaken for NIFTY 50.
    for key, item in master.items():
        if not isinstance(item, dict) or item.get("optType") != "XX":
            continue

        symbol = str(item.get("symTicker", key)).strip()
        if not symbol.startswith(instrument["future_prefix"]):
            continue

        if instrument["symbol"] == "NIFTY50":
            if not symbol.startswith("NSE:NIFTY") or "NIFTY" not in symbol:
                continue
            # Contract format should be NIFTY + expiry + FUT, excluding
            # FINNIFTY, MIDCPNIFTY, NIFTYNXT50, and other index families.
            if not symbol.startswith("NSE:NIFTY") or not symbol.endswith("FUT"):
                continue
            remainder = symbol[len("NSE:NIFTY"):]
            if not remainder or remainder.startswith(
                ("F", "NXT", "MID", "BANK", "IT", "PHARMA", "ENERGY", "INFRA")
            ):
                continue
        else:
            if not symbol.startswith("NSE:BANKNIFTY") or not symbol.endswith("FUT"):
                continue

        try:
            timestamp = int(item.get("expiryDate", 0))
            expiry = datetime.fromtimestamp(timestamp, timezone.utc).date()
        except (TypeError, ValueError, OSError, OverflowError):
            continue

        if expiry >= today:
            candidates.append((expiry, symbol))

    if not candidates:
        raise RuntimeError(
            f"No matching non-expired futures contract found for {instrument['name']}."
        )

    candidates.sort(key=lambda pair: (pair[0], pair[1]))
    return candidates[0]


def get_quotes_and_depth(session, headers, instrument, future_symbol):
    spot_symbol = instrument["spot"]
    response = session.get(
        QUOTES_URL,
        headers=headers,
        params={"symbols": f"{spot_symbol},{future_symbol}"},
        timeout=30,
    )
    quote_data = checked_json(response, "FYERS quotes request")
    if quote_data.get("s") != "ok":
        raise RuntimeError(
            f"FYERS quotes API error: {quote_data.get('message', 'unknown error')}"
        )

    quotes = {
        item.get("n"): item.get("v", {})
        for item in quote_data.get("d", [])
        if isinstance(item, dict)
    }
    if spot_symbol not in quotes or future_symbol not in quotes:
        raise RuntimeError(
            "FYERS did not return both the index spot and matching futures quote."
        )

    response = session.get(
        DEPTH_URL,
        headers=headers,
        params={"symbol": future_symbol, "ohlcv_flag": "1"},
        timeout=30,
    )
    depth_data = checked_json(response, "FYERS futures depth request")
    if depth_data.get("s") != "ok":
        raise RuntimeError(
            f"FYERS depth API error: {depth_data.get('message', 'unknown error')}"
        )

    depth_map = depth_data.get("d", {})
    depth = depth_map.get(future_symbol, {}) if isinstance(depth_map, dict) else {}
    if not depth and isinstance(depth_map, dict) and depth_map:
        # Accept a single returned depth record only if the API omitted its key.
        if len(depth_map) == 1:
            depth = next(iter(depth_map.values()))

    return quotes[spot_symbol], quotes[future_symbol], depth


def save_options_snapshot(
    instrument, expiry_item, expiry, chain, contracts, spot_ltp=None
):
    captured_at = datetime.now().astimezone().isoformat(timespec="seconds")

    # First try the underlying price returned by FYERS.
    underlying = get_number(chain.get("underlyingValue"))

    # If unavailable, check the underlying-price record in optionsChain.
    for item in chain.get("optionsChain", []):
        if not isinstance(item, dict):
            continue

        strike = get_number(item.get("strike_price"))
        option_type = str(item.get("option_type", "")).upper()

        if (
            strike is not None
            and strike <= 0
            and option_type not in ("CE", "PE")
        ):
            underlying = get_number(item.get("ltp"))
            if underlying is not None and underlying > 0:
                break

    # Final fallback: use the verified spot quote from FYERS.
    if underlying is None or underlying <= 0:
        underlying = get_number(spot_ltp)

    call_oi = sum(
        c["oi"] or 0
        for c in contracts
        if c["option_type"] == "CE"
    )
    put_oi = sum(
        c["oi"] or 0
        for c in contracts
        if c["option_type"] == "PE"
    )

    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_FILE, timeout=30) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                expiry_date TEXT NOT NULL,
                expiry_timestamp TEXT,
                captured_at TEXT NOT NULL,
                source TEXT NOT NULL,
                underlying_price REAL,
                aggregate_call_oi INTEGER,
                aggregate_put_oi INTEGER,
                contract_count INTEGER NOT NULL,
                raw_response TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS option_contracts (
                contract_id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                strike_price REAL NOT NULL,
                option_type TEXT NOT NULL,
                option_symbol TEXT,
                ltp REAL,
                ltp_change REAL,
                ltp_change_pct REAL,
                oi INTEGER,
                oi_change INTEGER,
                oi_change_pct REAL,
                previous_oi INTEGER,
                volume INTEGER,
                bid REAL,
                ask REAL,
                iv REAL,
                delta REAL,
                gamma REAL,
                theta REAL,
                vega REAL,
                raw_record TEXT,
                FOREIGN KEY (snapshot_id)
                    REFERENCES snapshots(snapshot_id)
                    ON DELETE CASCADE
            )
        """)

        cursor = conn.execute("""
            INSERT INTO snapshots (
                symbol,
                expiry_date,
                expiry_timestamp,
                captured_at,
                source,
                underlying_price,
                aggregate_call_oi,
                aggregate_put_oi,
                contract_count,
                raw_response
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            instrument["symbol"],
            expiry.isoformat(),
            str(expiry_item.get("expiry")),
            captured_at,
            "FYERS",
            underlying,
            call_oi,
            put_oi,
            len(contracts),
            json.dumps(chain, separators=(",", ":")),
        ))

        snapshot_id = cursor.lastrowid

        conn.executemany("""
            INSERT INTO option_contracts (
                snapshot_id,
                strike_price,
                option_type,
                option_symbol,
                ltp,
                ltp_change,
                ltp_change_pct,
                oi,
                oi_change,
                oi_change_pct,
                previous_oi,
                volume,
                bid,
                ask,
                iv,
                delta,
                gamma,
                theta,
                vega,
                raw_record
            )
            VALUES (
                :snapshot_id,
                :strike_price,
                :option_type,
                :option_symbol,
                :ltp,
                :ltp_change,
                :ltp_change_pct,
                :oi,
                :oi_change,
                :oi_change_pct,
                :previous_oi,
                :volume,
                :bid,
                :ask,
                :iv,
                :delta,
                :gamma,
                :theta,
                :vega,
                :raw_record
            )
        """, [
            {"snapshot_id": snapshot_id, **contract}
            for contract in contracts
        ])

    return snapshot_id, captured_at, underlying, call_oi, put_oi


def save_cash_futures(instrument, future_expiry, future_symbol, cash, future, depth):
    captured_at = datetime.now().astimezone().isoformat(timespec="seconds")
    cash_ltp = get_number(cash.get("lp"))
    future_ltp = get_number(future.get("lp"))
    premium = (
        future_ltp - cash_ltp
        if cash_ltp is not None and future_ltp is not None
        else None
    )
    premium_pct = (
        100.0 * premium / cash_ltp
        if premium is not None and cash_ltp
        else None
    )

    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_FILE, timeout=30) as conn:
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
            instrument["symbol"],
            captured_at,
            cash.get("lp"),
            cash.get("ch"),
            cash.get("chp"),
            get_integer(cash.get("volume")),
            future_symbol,
            future_expiry.isoformat(),
            future.get("lp"),
            future.get("ch"),
            future.get("chp"),
            get_integer(future.get("volume", depth.get("v"))),
            get_integer(depth.get("oi")),
            get_number(depth.get("atp")),
            premium,
            premium_pct,
        ))

    return captured_at, premium, premium_pct


def collect(instrument):
    session, headers = get_api()
    print(f"\nInstrument: {instrument['name']} ({instrument['symbol']})")

    # Get available expiries, choose the nearest valid one, then fetch that chain.
    initial_chain = get_options_chain(session, headers, instrument)
    expiry_item, expiry = choose_nearest_expiry({"data": initial_chain})
    chain = get_options_chain(session, headers, instrument, expiry_item)
    contracts = normalize_contracts(chain)

    future_expiry, future_symbol = find_nearest_future(session, instrument)
    cash, future, depth = get_quotes_and_depth(
        session, headers, instrument, future_symbol
    )

    # Only write after all API requests and validations have succeeded.
    option_result = save_options_snapshot(
        instrument, expiry_item, expiry, chain, contracts
    )
    futures_result = save_cash_futures(
        instrument, future_expiry, future_symbol, cash, future, depth
    )

    print("\nCollection successful.")
    print("Captured at:", option_result[1])
    print("Options expiry:", expiry.isoformat())
    print("Option contracts:", len(contracts))
    print("Calls:", sum(c["option_type"] == "CE" for c in contracts))
    print("Puts:", sum(c["option_type"] == "PE" for c in contracts))
    print("Underlying/reference price:", option_result[2])
    print("Call OI:", option_result[3])
    print("Put OI:", option_result[4])
    print("Option snapshot ID:", option_result[0])
    print("Spot LTP:", cash.get("lp"))
    print("Futures symbol:", future_symbol)
    print("Futures expiry:", future_expiry.isoformat())
    print("Futures LTP:", future.get("lp"))
    print("Futures OI:", depth.get("oi"))
    print("Futures premium:", futures_result[1])
    print("Futures premium (%):", futures_result[2])
    print("Database:", DB_FILE)


def main():
    parser = argparse.ArgumentParser(
        description="Collect FYERS index options, spot, and futures snapshots."
    )
    parser.add_argument(
        "--symbol",
        choices=("NIFTY50", "BANKNIFTY"),
        help="Instrument for scheduled/non-interactive runs.",
    )
    args = parser.parse_args()

    instrument = resolve_instrument(args.symbol) if args.symbol else choose_instrument()
    collect(instrument)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, sqlite3.Error, requests.RequestException) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
