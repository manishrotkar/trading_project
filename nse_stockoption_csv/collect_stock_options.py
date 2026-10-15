
import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# ============================================================
# PATHS AND SETTINGS
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent
TRADING_DIR = Path.home() / "trading_project"
ENV_FILE = TRADING_DIR / ".env"
TOKEN_FILE = TRADING_DIR / "access.txt"
DB_FILE = PROJECT_DIR / "database" / "stock_option_chain.db"

NSE_API = "https://www.nseindia.com/api/option-chain-equities"
NSE_PAGE = "https://www.nseindia.com/option-chain"
FYERS_API = "https://api-t1.fyers.in/data/options-chain-v3"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": NSE_PAGE,
}

# ============================================================
# DATABASE
# ============================================================

def connect_db():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.executescript("""
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
        );

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
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_symbol_time
            ON snapshots(symbol, captured_at);

        CREATE INDEX IF NOT EXISTS idx_contracts_snapshot
            ON option_contracts(snapshot_id);

        CREATE INDEX IF NOT EXISTS idx_contracts_strike_type
            ON option_contracts(strike_price, option_type);
    """)

    conn.commit()
    return conn


# ============================================================
# HELPERS
# ============================================================

def number(value):
    """Convert API numbers and comma-formatted strings safely."""
    if value is None or value == "" or value == "-":
        return None

    if isinstance(value, (int, float)):
        return value

    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def integer(value):
    value = number(value)
    return int(value) if value is not None else None


def normalize_symbol(value):
    value = value.strip().upper()

    if value.startswith("NSE:"):
        value = value[4:]

    if value.endswith("-EQ"):
        value = value[:-3]

    if not value:
        raise ValueError("Stock symbol cannot be empty.")

    if not all(ch.isalnum() or ch in "&_- " for ch in value):
        raise ValueError("Invalid stock symbol.")

    return value


def expiry_date_from_fyers(item):
    return datetime.strptime(item["date"], "%d-%m-%Y").date()


def choose_expiry(expiries):
    today = date.today()
    valid = []

    for item in expiries:
        try:
            exp_date = expiry_date_from_fyers(item)
            if exp_date >= today:
                valid.append((exp_date, item))
        except (KeyError, ValueError, TypeError):
            continue

    valid.sort(key=lambda entry: entry[0])

    if not valid:
        raise RuntimeError("No non-expired expiry dates were returned.")

    print("\nAvailable expiries:")
    for index, (exp_date, _) in enumerate(valid, start=1):
        marker = " (default)" if index == 1 else ""
        print(f"{index}. {exp_date.isoformat()}{marker}")

    answer = input(
        "Choose expiry number, or press Enter for nearest: "
    ).strip()

    if not answer:
        return valid[0][1]

    try:
        selected = int(answer)
        if 1 <= selected <= len(valid):
            return valid[selected - 1][1]
    except ValueError:
        pass

    print("Invalid selection. Using nearest expiry.")
    return valid[0][1]


# ============================================================
# NSE ATTEMPT
# ============================================================

def try_nse(symbol):
    """
    Return a usable NSE response if it contains option records.
    Return None when NSE blocks the request or data is unusable.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        session.get(NSE_PAGE, timeout=15)

        response = session.get(
            NSE_API,
            params={"symbol": symbol},
            timeout=20,
        )

        if response.status_code != 200:
            print(f"NSE unavailable (HTTP {response.status_code}).")
            return None

        data = response.json()
        records = data.get("records", {})
        rows = records.get("data", [])

        usable = any(
            isinstance(row, dict)
            and (
                isinstance(row.get("CE"), dict)
                or isinstance(row.get("PE"), dict)
            )
            for row in rows
        )

        if usable:
            print("NSE returned usable option-chain data.")
            return data

        print("NSE returned no usable option records; trying FYERS.")
        return None

    except (requests.RequestException, ValueError, AttributeError) as exc:
        print(f"NSE request failed ({type(exc).__name__}); trying FYERS.")
        return None


# ============================================================
# FYERS
# ============================================================

def fetch_fyers(symbol, expiry=None):
    load_dotenv(ENV_FILE)

    app_id = os.getenv("FYERS_APP_ID", "").strip()

    if not app_id:
        raise RuntimeError(
            f"FYERS_APP_ID was not found in {ENV_FILE}"
        )

    if not TOKEN_FILE.is_file():
        raise RuntimeError(f"Token file not found: {TOKEN_FILE}")

    token = TOKEN_FILE.read_text().strip()

    if not token:
        raise RuntimeError("The FYERS access-token file is empty.")

    headers = {
        "Authorization": f"{app_id}:{token}",
        "Content-Type": "application/json",
    }

    params = {
        "symbol": f"NSE:{symbol}-EQ",
        "strikecount": 10,
        "timestamp": expiry["expiry"] if expiry else "",
        "greeks": "1",
    }

    try:
        response = requests.get(
            FYERS_API,
            headers=headers,
            params=params,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"FYERS network request failed: {type(exc).__name__}"
        ) from None

    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(
            f"FYERS returned non-JSON content (HTTP {response.status_code})."
        ) from None

    if response.status_code != 200 or data.get("s") != "ok":
        message = data.get("message", "No API message provided")
        raise RuntimeError(
            f"FYERS request failed (HTTP {response.status_code}): {message}"
        )

    return data.get("data", {})


# ============================================================
# NORMALIZE FYERS CONTRACTS
# ============================================================

def normalize_fyers_records(chain):
    contracts = []

    for item in chain.get("optionsChain", []):
        if not isinstance(item, dict):
            continue

        strike = number(item.get("strike_price"))
        option_type = str(item.get("option_type", "")).upper()

        # FYERS can include an underlying-price record with strike -1.
        if strike is None or strike <= 0:
            continue

        if option_type not in ("CE", "PE"):
            continue

        greeks = item.get("greeks") or {}

        contracts.append({
            "strike_price": strike,
            "option_type": option_type,
            "option_symbol": item.get("symbol"),
            "ltp": number(item.get("ltp")),
            "ltp_change": number(item.get("ltpch")),
            "ltp_change_pct": number(item.get("ltpchp")),
            "oi": integer(item.get("oi")),
            "oi_change": integer(item.get("oich")),
            "oi_change_pct": number(item.get("oichp")),
            "previous_oi": integer(item.get("prev_oi")),
            "volume": integer(item.get("volume")),
            "bid": number(item.get("bid")),
            "ask": number(item.get("ask")),
            "iv": number(greeks.get("iv")),
            "delta": number(greeks.get("delta")),
            "gamma": number(greeks.get("gamma")),
            "theta": number(greeks.get("theta")),
            "vega": number(greeks.get("vega")),
            "raw_record": json.dumps(item, separators=(",", ":")),
        })

    return contracts


# ============================================================
# SAVE SNAPSHOT
# ============================================================

def save_snapshot(
    symbol,
    expiry_date,
    expiry_timestamp,
    source,
    chain,
    contracts,
):
    if not contracts:
        raise RuntimeError("No valid CE/PE contracts to save.")

    captured_at = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    underlying_price = None
    for item in chain.get("optionsChain", []):
        if isinstance(item, dict) and number(item.get("strike_price")) == -1:
            underlying_price = number(item.get("fp"))
            if underlying_price is None:
                underlying_price = number(item.get("ltp"))
            break

    # If the underlying record is absent, don't substitute a random option.
    aggregate_call_oi = integer(chain.get("callOi"))
    aggregate_put_oi = integer(chain.get("putOi"))

    conn = connect_db()

    try:
        cursor = conn.execute("""
            INSERT INTO snapshots (
                symbol, expiry_date, expiry_timestamp, captured_at,
                source, underlying_price, aggregate_call_oi,
                aggregate_put_oi, contract_count, raw_response
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            symbol,
            expiry_date,
            str(expiry_timestamp or ""),
            captured_at,
            source,
            underlying_price,
            aggregate_call_oi,
            aggregate_put_oi,
            len(contracts),
            json.dumps(chain, separators=(",", ":")),
        ))

        snapshot_id = cursor.lastrowid

        for item in contracts:
            conn.execute("""
                INSERT INTO option_contracts (
                    snapshot_id, strike_price, option_type, option_symbol,
                    ltp, ltp_change, ltp_change_pct, oi, oi_change,
                    oi_change_pct, previous_oi, volume, bid, ask, iv,
                    delta, gamma, theta, vega, raw_record
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
            """, (
                snapshot_id,
                item["strike_price"],
                item["option_type"],
                item["option_symbol"],
                item["ltp"],
                item["ltp_change"],
                item["ltp_change_pct"],
                item["oi"],
                item["oi_change"],
                item["oi_change_pct"],
                item["previous_oi"],
                item["volume"],
                item["bid"],
                item["ask"],
                item["iv"],
                item["delta"],
                item["gamma"],
                item["theta"],
                item["vega"],
                item["raw_record"],
            ))

        conn.commit()
        return snapshot_id, captured_at

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("STOCK OPTION-CHAIN COLLECTOR")
    print("=" * 60)

    raw_symbol = input("Enter stock symbol [RELIANCE]: ").strip()
    symbol = normalize_symbol(raw_symbol or "RELIANCE")

    # Try NSE first, as requested. The current known NSE response is {}.
    nse_data = try_nse(symbol)

    # FYERS is currently the verified source. Its expiry list is needed
    # to select the nearest non-expired contract.
    initial_chain = fetch_fyers(symbol)
    expiry = choose_expiry(initial_chain.get("expiryData", []))

    selected_chain = fetch_fyers(symbol, expiry)
    contracts = normalize_fyers_records(selected_chain)

    if not contracts:
        raise RuntimeError(
            "FYERS returned no valid CE/PE contracts for the selected expiry."
        )

    expiry_date = expiry_date_from_fyers(expiry).isoformat()

    snapshot_id, captured_at = save_snapshot(
        symbol=symbol,
        expiry_date=expiry_date,
        expiry_timestamp=expiry.get("expiry"),
        source="FYERS",
        chain=selected_chain,
        contracts=contracts,
    )

    call_count = sum(
        1 for item in contracts if item["option_type"] == "CE"
    )
    put_count = sum(
        1 for item in contracts if item["option_type"] == "PE"
    )

    print("\nSnapshot saved successfully.")
    print("Source:", "FYERS")
    print("Symbol:", symbol)
    print("Expiry:", expiry_date)
    print("Captured at:", captured_at)
    print("Snapshot ID:", snapshot_id)
    print("CE contracts:", call_count)
    print("PE contracts:", put_count)
    print("Total valid contracts:", len(contracts))
    print("Database:", DB_FILE)
    print("\nRun this program again to save another snapshot.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, sqlite3.Error) as exc:
        print("\nERROR:", exc)
        raise SystemExit(1)
