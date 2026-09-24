#!/usr/bin/env python3
"""Paper-only intraday portfolio driven by Qualified=YES scanner results.

This program never places an order. It uses FYERS WebSocket LTPs only for
paper entries/exits, records each completed run in its own SQLite session, and
writes one compact CSV report when the run closes.
"""

from __future__ import annotations

import argparse
import csv
import logging
import math
import os
import sqlite3
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, time as clock_time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fyers_apiv3.FyersWebsocket import data_ws


PROJECT_ROOT = Path("/home/manish/trading_project")
PAPER_PORTFOLIO_DIR = PROJECT_ROOT / "paper_portfolio"
CSV_PATH = PROJECT_ROOT / "stock_screener/notebooks/mtf_indicator_scan_csv_v5_results.csv"
DATABASE_PATH = PAPER_PORTFOLIO_DIR / "database/paper_portfolio.db"
RESULTS_DIR = PAPER_PORTFOLIO_DIR / "results"
ENV_PATH = PROJECT_ROOT / ".env"
ACCESS_TOKEN_PATH = PROJECT_ROOT / "access.txt"
LOG_PATH = PAPER_PORTFOLIO_DIR / "paper_intraday_portfolio.log"

IST = ZoneInfo("Asia/Kolkata")
CAPITAL = 100_000.00
DEFAULT_ENTRY_TIME = clock_time(9, 15)
DEFAULT_EXIT_TIME = clock_time(15, 0)
SCREEN_REFRESH_SECONDS = 1.0
LIVE_LOG_SECONDS = 30.0
LOG_BACKUP_DAYS = 30


@dataclass
class Position:
    symbol: str
    entry_time: datetime
    entry_price: float
    quantity: int
    invested_amount: float
    latest_ltp: float
    latest_ltp_time: datetime


@dataclass(frozen=True)
class ClosedTrade:
    stock: str
    entry_time: datetime
    entry_price: float
    quantity: int
    invested_amount: float
    exit_time: datetime
    exit_price: float
    exit_value: float
    pnl: float
    pnl_percent: float
    status: str


@dataclass(frozen=True)
class ClosingSummary:
    total_invested: float
    total_exit_value: float
    pnl: float
    pnl_percent: float
    report_path: Path


def now_ist() -> datetime:
    return datetime.now(IST)


def configure_logging() -> logging.Logger:
    """Keep detailed logs, rotating at local midnight and retaining 30 days."""
    PAPER_PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("paper_intraday_portfolio")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler = TimedRotatingFileHandler(
        LOG_PATH, when="midnight", interval=1, backupCount=LOG_BACKUP_DAYS, encoding="utf-8"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


LOGGER = configure_logging()


def ensure_database(database_path: Path = DATABASE_PATH) -> None:
    """Create/migrate only the paper database, retaining all existing trades.

    Older versions used UNIQUE(trade_date, stock), which prevented a second
    paper run on the same day. The migration adds session_id, preserves every
    old row, removes that legacy index, and makes (session_id, stock) unique.
    """
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_runs (
                session_id TEXT PRIMARY KEY,
                trade_date TEXT NOT NULL,
                started_at TEXT NOT NULL,
                entry_at TEXT NOT NULL,
                exit_at TEXT NOT NULL,
                ended_at TEXT,
                completion_status TEXT NOT NULL,
                symbol_count INTEGER NOT NULL,
                positions_closed INTEGER NOT NULL DEFAULT 0,
                total_invested REAL,
                total_exit_value REAL,
                total_pnl REAL,
                total_pnl_percent REAL,
                report_path TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                stock TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                entry_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                invested_amount REAL NOT NULL,
                exit_time TEXT,
                exit_price REAL,
                exit_value REAL,
                pnl REAL,
                pnl_percent REAL,
                status TEXT NOT NULL,
                session_id TEXT
            )
            """
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(paper_trades)")}
        if "session_id" not in columns:
            connection.execute("ALTER TABLE paper_trades ADD COLUMN session_id TEXT")

        legacy_rows = connection.execute(
            """
            SELECT id, trade_date, stock, entry_time, exit_time, invested_amount,
                   exit_value, pnl, pnl_percent, status
            FROM paper_trades WHERE session_id IS NULL
            """
        ).fetchall()
        for row in legacy_rows:
            legacy_session_id = f"legacy-{row[1]}-{row[0]:06d}"
            connection.execute("UPDATE paper_trades SET session_id = ? WHERE id = ?", (legacy_session_id, row[0]))
            connection.execute(
                """
                INSERT OR IGNORE INTO paper_runs (
                    session_id, trade_date, started_at, entry_at, exit_at, ended_at,
                    completion_status, symbol_count, positions_closed, total_invested,
                    total_exit_value, total_pnl, total_pnl_percent, report_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?, NULL)
                """,
                (legacy_session_id, row[1], row[3], row[3], row[4] or row[3], row[4],
                 f"MIGRATED_{row[9]}", row[5], row[6], row[7], row[8]),
            )

        # This was the old explicit index. Removing an index never deletes rows.
        connection.execute("DROP INDEX IF EXISTS idx_paper_trade_unique")
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_trade_session_stock "
            "ON paper_trades(session_id, stock)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_paper_trades_trade_date ON paper_trades(trade_date)"
        )


def create_paper_run(
    session_id: str, started_at: datetime, entry_at: datetime, exit_at: datetime,
    symbol_count: int, database_path: Path = DATABASE_PATH,
) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO paper_runs (
                session_id, trade_date, started_at, entry_at, exit_at,
                completion_status, symbol_count
            ) VALUES (?, ?, ?, ?, ?, 'RUNNING', ?)
            """,
            (session_id, started_at.date().isoformat(), started_at.isoformat(timespec="seconds"),
             entry_at.isoformat(timespec="seconds"), exit_at.isoformat(timespec="seconds"), symbol_count),
        )


def save_completed_run(
    session_id: str, closed_trades: list[ClosedTrade], summary: ClosingSummary,
    exited_at: datetime, database_path: Path = DATABASE_PATH,
) -> None:
    """Atomically save all paper trades and mark their session complete."""
    sql = """
        INSERT INTO paper_trades (
            trade_date, stock, entry_time, entry_price, quantity, invested_amount,
            exit_time, exit_price, exit_value, pnl, pnl_percent, status, session_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    rows = [
        (trade.entry_time.date().isoformat(), trade.stock,
         trade.entry_time.isoformat(timespec="seconds"), trade.entry_price, trade.quantity,
         trade.invested_amount, trade.exit_time.isoformat(timespec="seconds"), trade.exit_price,
         trade.exit_value, trade.pnl, trade.pnl_percent, trade.status, session_id)
        for trade in closed_trades
    ]
    with sqlite3.connect(database_path) as connection:
        if rows:
            connection.executemany(sql, rows)
        updated = connection.execute(
            """
            UPDATE paper_runs
            SET ended_at = ?, completion_status = ?, positions_closed = ?,
                total_invested = ?, total_exit_value = ?, total_pnl = ?,
                total_pnl_percent = ?, report_path = ?
            WHERE session_id = ?
            """,
            (exited_at.isoformat(timespec="seconds"),
             closed_trades[0].status if closed_trades else "CLOSED_NO_ENTRIES",
             len(closed_trades), summary.total_invested, summary.total_exit_value,
             summary.pnl, summary.pnl_percent, str(summary.report_path), session_id),
        )
        if updated.rowcount != 1:
            raise RuntimeError(f"Paper session {session_id} was not found in SQLite.")


def next_report_path(started_at: datetime, results_dir: Path = RESULTS_DIR) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    stem = f"paper_portfolio_{started_at.strftime('%Y-%m-%d_%H%M%S')}"
    report_path = results_dir / f"{stem}.csv"
    suffix = 2
    while report_path.exists():
        report_path = results_dir / f"{stem}_{suffix}.csv"
        suffix += 1
    return report_path


def write_closing_csv(report_path: Path, closed_trades: list[ClosedTrade], summary: ClosingSummary) -> None:
    """Write only the requested per-stock fields plus portfolio totals."""
    with report_path.open("w", newline="", encoding="utf-8") as report_file:
        writer = csv.DictWriter(
            report_file,
            fieldnames=["stock", "entry_time", "entry_price", "quantity", "exit_time",
                        "exit_price", "stock_pnl_rupees", "stock_pnl_percent",
                        "portfolio_total_pnl_rupees", "portfolio_total_pnl_percent"],
        )
        writer.writeheader()
        for trade in closed_trades:
            writer.writerow({
                "stock": trade.stock,
                "entry_time": trade.entry_time.isoformat(timespec="seconds"),
                "entry_price": f"{trade.entry_price:.2f}",
                "quantity": trade.quantity,
                "exit_time": trade.exit_time.isoformat(timespec="seconds"),
                "exit_price": f"{trade.exit_price:.2f}",
                "stock_pnl_rupees": f"{trade.pnl:.2f}",
                "stock_pnl_percent": f"{trade.pnl_percent:.2f}",
                "portfolio_total_pnl_rupees": "",
                "portfolio_total_pnl_percent": "",
            })
        writer.writerow({
            "stock": "PORTFOLIO TOTAL",
            "entry_time": "",
            "entry_price": "",
            "quantity": "",
            "exit_time": "",
            "exit_price": "",
            "stock_pnl_rupees": "",
            "stock_pnl_percent": "",
            "portfolio_total_pnl_rupees": f"{summary.pnl:.2f}",
            "portfolio_total_pnl_percent": f"{summary.pnl_percent:.2f}",
        })


class PaperIntradayPortfolio:
    """Thread-safe state shared by FYERS callbacks and the scheduled clock."""

    def __init__(self, symbols: list[str], entry_at: datetime, exit_at: datetime, session_id: str) -> None:
        self.symbols = symbols
        self.allocation_per_stock = CAPITAL / len(symbols)
        self.entry_at = entry_at
        self.exit_at = exit_at
        self.session_id = session_id
        self.positions: dict[str, Position] = {}
        self.last_valid_ltp: dict[str, float] = {}
        self._lock = threading.RLock()
        self._exited = False
        self._status = "Waiting to connect to FYERS..."

    def set_status(self, status: str) -> None:
        with self._lock:
            self._status = status

    @property
    def is_exited(self) -> bool:
        with self._lock:
            return self._exited

    def snapshot(self) -> tuple[list[Position], str]:
        with self._lock:
            return list(self.positions.values()), self._status

    def handle_tick(self, message: Any) -> None:
        """Use the first valid post-entry tick as entry; keep later valid LTPs."""
        tick = extract_tick(message)
        if tick is None:
            return
        symbol, ltp = tick
        if symbol not in self.symbols:
            return
        received_at = now_ist()
        with self._lock:
            if self._exited or received_at >= self.exit_at:
                return
            self.last_valid_ltp[symbol] = ltp
            position = self.positions.get(symbol)
            if position is not None:
                position.latest_ltp = ltp
                position.latest_ltp_time = received_at
                return
            if received_at < self.entry_at:
                return
            quantity = math.floor(self.allocation_per_stock / ltp)
            if quantity <= 0:
                LOGGER.error("Skipping %s: LTP %.2f exceeds allocation %.2f", symbol, ltp, self.allocation_per_stock)
                return
            invested_amount = quantity * ltp
            self.positions[symbol] = Position(symbol, received_at, ltp, quantity, invested_amount, ltp, received_at)
            self._status = f"Live | entered {symbol} at ₹{ltp:,.2f}"
            LOGGER.info("PAPER ENTRY %s | qty=%d | entry=%.2f | invested=%.2f | cash_left=%.2f", symbol, quantity, ltp, invested_amount, self.allocation_per_stock - invested_amount)

    def exit_all(self, exited_at: datetime, status: str = "CLOSED") -> ClosingSummary:
        """Close with retained latest valid LTP, save SQLite, and write the CSV."""
        with self._lock:
            if self._exited:
                raise RuntimeError("Paper positions have already been closed.")
            self._exited = True
            self._status = "Closing paper positions using latest valid LTP..."
            completed_positions = list(self.positions.values())

        closed_trades: list[ClosedTrade] = []
        total_invested = 0.0
        total_exit_value = 0.0
        for position in completed_positions:
            exit_price = position.latest_ltp  # Retained through temporary socket failures.
            exit_value = position.quantity * exit_price
            pnl = exit_value - position.invested_amount
            pnl_percent = pnl / position.invested_amount * 100
            total_invested += position.invested_amount
            total_exit_value += exit_value
            closed_trades.append(ClosedTrade(
                position.symbol, position.entry_time, position.entry_price, position.quantity,
                position.invested_amount, exited_at, exit_price, exit_value, pnl, pnl_percent, status,
            ))
            LOGGER.info("PAPER EXIT %s | exit=%.2f | P&L=%+.2f (%+.2f%%)", position.symbol, exit_price, pnl, pnl_percent)

        portfolio_pnl = total_exit_value - total_invested
        portfolio_pnl_percent = portfolio_pnl / total_invested * 100 if total_invested else 0.0
        report_path = next_report_path(self.entry_at)
        summary = ClosingSummary(total_invested, total_exit_value, portfolio_pnl, portfolio_pnl_percent, report_path)
        write_closing_csv(report_path, closed_trades, summary)
        try:
            save_completed_run(self.session_id, closed_trades, summary, exited_at)
        except Exception:
            LOGGER.exception("Could not save completed paper run %s to %s", self.session_id, DATABASE_PATH)
            raise
        LOGGER.info("PORTFOLIO CLOSED | invested=%.2f | value=%.2f | P&L=%+.2f (%+.2f%%) | CSV=%s", total_invested, total_exit_value, portfolio_pnl, portfolio_pnl_percent, report_path)
        self.set_status(f"Closed | total P&L ₹{portfolio_pnl:+,.2f} ({portfolio_pnl_percent:+.2f}%)")
        return summary


class TerminalDashboard:
    """Small in-place terminal view; it is display-only and sends no orders."""

    def __init__(self, portfolio: PaperIntradayPortfolio) -> None:
        self.portfolio = portfolio
        self.enabled = sys.stdout.isatty()
        self._started = False

    def start(self) -> None:
        if self.enabled:
            sys.stdout.write("\033[?25l")
            sys.stdout.flush()
            self._started = True
        self.render()

    def stop(self) -> None:
        if self._started:
            sys.stdout.write("\033[0m\033[?25h\n")
            sys.stdout.flush()
            self._started = False

    def render(self) -> None:
        positions, status = self.portfolio.snapshot()
        total_invested = sum(position.invested_amount for position in positions)
        total_value = sum(position.quantity * position.latest_ltp for position in positions)
        pnl = total_value - total_invested
        pnl_percent = pnl / total_invested * 100 if total_invested else 0.0
        lines = [
            "PAPER INTRADAY PORTFOLIO — paper only, no orders are sent",
            f"TOTAL P&L ₹{pnl:+,.2f} ({pnl_percent:+.2f}%) | Invested ₹{total_invested:,.2f} | Value ₹{total_value:,.2f}",
            f"Status: {status} | Updated: {now_ist().strftime('%H:%M:%S IST')}",
            "SYMBOL                 QTY      ENTRY        LTP       P&L",
        ]
        for position in positions:
            item_pnl = position.quantity * position.latest_ltp - position.invested_amount
            lines.append(f"{position.symbol:<22}{position.quantity:>5}  ₹{position.entry_price:>8.2f}  ₹{position.latest_ltp:>8.2f}  ₹{item_pnl:>+9.2f}")
        if not positions:
            lines.append("Waiting for the first valid FYERS WebSocket LTP after entry time...")
        lines.append(f"Scheduled automatic exit: {self.portfolio.exit_at.strftime('%H:%M IST')}")
        screen = "\n".join(lines)
        if self.enabled:
            sys.stdout.write(f"\033[2J\033[H{screen}\n")
            sys.stdout.flush()
        elif not self._started:
            print(screen)


def log_live_portfolio(portfolio: PaperIntradayPortfolio) -> None:
    positions, _ = portfolio.snapshot()
    if not positions:
        return
    invested = sum(position.invested_amount for position in positions)
    value = sum(position.quantity * position.latest_ltp for position in positions)
    pnl = value - invested
    percent = pnl / invested * 100 if invested else 0.0
    LOGGER.info("LIVE PORTFOLIO | positions=%d | invested=%.2f | value=%.2f | P&L=%+.2f (%+.2f%%)", len(positions), invested, value, pnl, percent)


def qualified_symbols() -> list[str]:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Qualified-stock CSV not found: {CSV_PATH}")
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        required_columns = {"Stock", "Qualified"}
        if not reader.fieldnames or not required_columns.issubset(reader.fieldnames):
            raise ValueError("CSV must include Stock and Qualified columns.")
        symbols = [row["Stock"].strip() for row in reader if row.get("Stock") and row.get("Qualified", "").strip().upper() == "YES"]
    return list(dict.fromkeys(symbols))


def extract_tick(message: Any) -> tuple[str, float] | None:
    payloads = message if isinstance(message, list) else [message]
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        symbol = payload.get("symbol")
        try:
            price = float(payload.get("ltp"))
        except (TypeError, ValueError):
            continue
        if isinstance(symbol, str) and math.isfinite(price) and price > 0:
            return symbol, price
    return None


def load_websocket_token() -> str:
    load_dotenv(ENV_PATH)
    app_id = os.getenv("FYERS_APP_ID")
    if not app_id:
        raise RuntimeError(f"FYERS_APP_ID not found in {ENV_PATH}")
    if not ACCESS_TOKEN_PATH.exists():
        raise FileNotFoundError(f"Access token file not found: {ACCESS_TOKEN_PATH}")
    access_token = ACCESS_TOKEN_PATH.read_text(encoding="utf-8").strip()
    if not access_token:
        raise RuntimeError("Access token file is empty.")
    return f"{app_id}:{access_token}"


def build_socket(portfolio: PaperIntradayPortfolio) -> Any:
    def on_connect() -> None:
        portfolio.set_status("Live | FYERS WebSocket connected")
        LOGGER.info("FYERS WebSocket connected; subscribing to %s", ", ".join(portfolio.symbols))
        try:
            socket.subscribe(symbols=portfolio.symbols, data_type="SymbolUpdate")
        except Exception:
            portfolio.set_status("Error | FYERS subscription failed; reconnect remains enabled")
            LOGGER.exception("FYERS subscription failed.")

    def on_message(message: Any) -> None:
        try:
            portfolio.handle_tick(message)
        except Exception:
            LOGGER.exception("Unexpected error while processing WebSocket message.")

    def on_error(message: Any) -> None:
        if not portfolio.is_exited:
            portfolio.set_status("Error | connection issue; retaining latest valid LTP")
        LOGGER.error("FYERS WebSocket error: %s; retaining latest valid LTPs.", message)

    def on_close(message: Any) -> None:
        if not portfolio.is_exited:
            portfolio.set_status("Disconnected | FYERS reconnect is enabled; retaining latest valid LTP")
        LOGGER.warning("FYERS WebSocket closed: %s", message)

    socket = data_ws.FyersDataSocket(
        access_token=load_websocket_token(), log_path="", litemode=False,
        write_to_file=False, reconnect=True, on_connect=on_connect, on_close=on_close,
        on_error=on_error, on_message=on_message,
    )
    return socket


def close_socket(socket: Any) -> None:
    """Stop FYERS reconnection first, then close its WebSocket worker cleanly."""
    try:
        socket.restart_flag = False
        socket.close_connection()
        LOGGER.info("FYERS WebSocket disconnected cleanly.")
    except Exception:
        LOGGER.exception("Failed to close the FYERS WebSocket cleanly.")


def parse_clock_time(value: str) -> clock_time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as error:
        raise argparse.ArgumentTypeError("Time must use 24-hour HH:MM format.") from error


def scheduled_times(started_at: datetime, entry_time: clock_time, exit_time: clock_time) -> tuple[datetime, datetime] | None:
    entry_at = started_at.replace(hour=entry_time.hour, minute=entry_time.minute, second=0, microsecond=0)
    exit_at = started_at.replace(hour=exit_time.hour, minute=exit_time.minute, second=0, microsecond=0)
    if entry_at >= exit_at:
        raise ValueError("Exit time must be later than entry time.")
    if started_at >= exit_at:
        return None
    return max(started_at, entry_at), exit_at


def command_line_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a paper-only intraday portfolio from qualified stocks.")
    parser.add_argument("--entry-time", type=parse_clock_time, default=DEFAULT_ENTRY_TIME, help="IST entry time in HH:MM (default: 09:15).")
    parser.add_argument("--exit-time", type=parse_clock_time, default=DEFAULT_EXIT_TIME, help="IST exit time in HH:MM (default: 15:00).")
    parser.add_argument("--self-test", action="store_true", help="Run an offline paper-only storage/report test; FYERS is not contacted.")
    return parser.parse_args()


def run_self_test() -> int:
    """Offline verification of session storage and closing CSV without credentials."""
    with tempfile.TemporaryDirectory(prefix="paper_portfolio_test_") as temporary_directory:
        temporary_path = Path(temporary_directory)
        database_path = temporary_path / "paper_portfolio.db"
        results_path = temporary_path / "results"
        legacy_database_path = temporary_path / "legacy_paper_portfolio.db"
        with sqlite3.connect(legacy_database_path) as connection:
            connection.execute(
                """
                CREATE TABLE paper_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, trade_date TEXT NOT NULL,
                    stock TEXT NOT NULL, entry_time TEXT NOT NULL, entry_price REAL NOT NULL,
                    quantity INTEGER NOT NULL, invested_amount REAL NOT NULL, exit_time TEXT,
                    exit_price REAL, exit_value REAL, pnl REAL, pnl_percent REAL,
                    status TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE UNIQUE INDEX idx_paper_trade_unique ON paper_trades(trade_date, stock)"
            )
            connection.execute(
                """
                INSERT INTO paper_trades (
                    trade_date, stock, entry_time, entry_price, quantity, invested_amount,
                    exit_time, exit_price, exit_value, pnl, pnl_percent, status
                ) VALUES ('2026-09-16', 'NSE:LEGACY-EQ', '2026-09-16T10:00:00+05:30',
                          100, 10, 1000, '2026-09-16T15:00:00+05:30', 105, 1050, 50, 5,
                          'CLOSED')
                """
            )
        ensure_database(legacy_database_path)
        with sqlite3.connect(legacy_database_path) as connection:
            legacy_trade = connection.execute(
                "SELECT stock, session_id FROM paper_trades"
            ).fetchone()
            legacy_index_names = {row[1] for row in connection.execute("PRAGMA index_list(paper_trades)")}
        if legacy_trade[0] != "NSE:LEGACY-EQ" or not legacy_trade[1] or "idx_paper_trade_unique" in legacy_index_names:
            raise AssertionError("Legacy database migration did not preserve its trade safely.")

        ensure_database(database_path)
        started_at = datetime(2026, 9, 16, 10, 0, tzinfo=IST)
        for run_number in (1, 2):
            session_id = f"self-test-{run_number}"
            create_paper_run(session_id, started_at, started_at, started_at.replace(hour=15), 2, database_path)
            report_path = next_report_path(started_at, results_path)
            trade = ClosedTrade("NSE:TEST-EQ", started_at, 100.0, 10, 1000.0, started_at.replace(hour=15), 105.0, 1050.0, 50.0, 5.0, "CLOSED")
            summary = ClosingSummary(1000.0, 1050.0, 50.0, 5.0, report_path)
            write_closing_csv(report_path, [trade], summary)
            save_completed_run(session_id, [trade], summary, started_at.replace(hour=15), database_path)
        with sqlite3.connect(database_path) as connection:
            trade_count = connection.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]
            run_count = connection.execute("SELECT COUNT(*) FROM paper_runs WHERE completion_status = 'CLOSED'").fetchone()[0]
        reports = sorted(results_path.glob("paper_portfolio_*.csv"))
        with reports[0].open(newline="", encoding="utf-8") as report_file:
            report_columns = csv.DictReader(report_file).fieldnames
        expected_columns = [
            "stock", "entry_time", "entry_price", "quantity", "exit_time", "exit_price",
            "stock_pnl_rupees", "stock_pnl_percent", "portfolio_total_pnl_rupees",
            "portfolio_total_pnl_percent",
        ]
        if trade_count != 2 or run_count != 2 or len(reports) != 2 or report_columns != expected_columns:
            raise AssertionError("Repeated same-day paper sessions were not saved independently.")
    print("Self-test passed: two same-day paper sessions and two closing CSV reports were saved offline.")
    return 0


def main() -> int:
    arguments = command_line_arguments()
    if arguments.self_test:
        return run_self_test()
    try:
        symbols = qualified_symbols()
        ensure_database()
    except Exception as error:
        LOGGER.exception("Paper portfolio could not initialize: %s", error)
        return 2
    if not symbols:
        LOGGER.warning("No stocks are marked Qualified=YES; nothing to trade.")
        return 0

    started_at = now_ist()
    try:
        schedule = scheduled_times(started_at, arguments.entry_time, arguments.exit_time)
    except ValueError as error:
        LOGGER.error("Invalid schedule: %s", error)
        return 2
    if schedule is None:
        LOGGER.info("Started at %s, at or after 15:00 IST; no paper trade will be opened.", started_at)
        return 0

    entry_at, exit_at = schedule
    session_id = f"run-{started_at.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    try:
        create_paper_run(session_id, started_at, entry_at, exit_at, len(symbols))
    except Exception:
        LOGGER.exception("Could not create paper session %s; no trades will be started.", session_id)
        return 2

    portfolio = PaperIntradayPortfolio(symbols, entry_at, exit_at, session_id)
    portfolio.set_status(f"Preparing | entry {entry_at.strftime('%H:%M IST')} | automatic exit {exit_at.strftime('%H:%M IST')}")
    LOGGER.info("PAPER-ONLY portfolio starting | session=%s | capital=%.2f | allocation=%.2f | entry=%s | exit=%s | symbols=%s", session_id, CAPITAL, portfolio.allocation_per_stock, entry_at.isoformat(timespec="seconds"), exit_at.isoformat(timespec="seconds"), ", ".join(symbols))

    dashboard = TerminalDashboard(portfolio)
    socket: Any | None = None
    closing_summary: ClosingSummary | None = None
    next_live_log = time.monotonic() + LIVE_LOG_SECONDS
    dashboard.start()
    try:
        socket = build_socket(portfolio)
        try:
            socket.connect()
        except Exception:
            portfolio.set_status("Error | initial connection failed; waiting for reconnect until automatic exit")
            LOGGER.exception("Initial FYERS WebSocket connection failed.")
        while now_ist() < exit_at:
            dashboard.render()
            if time.monotonic() >= next_live_log:
                log_live_portfolio(portfolio)
                next_live_log = time.monotonic() + LIVE_LOG_SECONDS
            seconds_remaining = (exit_at - now_ist()).total_seconds()
            time.sleep(min(max(seconds_remaining, 0.0), SCREEN_REFRESH_SECONDS))
        closing_summary = portfolio.exit_all(now_ist())
    except KeyboardInterrupt:
        LOGGER.warning("Manual exit requested; closing paper positions using retained latest valid LTP.")
        closing_summary = portfolio.exit_all(now_ist(), status="CLOSED_MANUAL")
    except Exception:
        LOGGER.exception("Paper portfolio stopped because of an unexpected error.")
        return 1
    finally:
        if socket is not None:
            close_socket(socket)
        dashboard.render()
        dashboard.stop()

    if closing_summary is not None:
        print(f"Paper run closed. Closing CSV report: {closing_summary.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
