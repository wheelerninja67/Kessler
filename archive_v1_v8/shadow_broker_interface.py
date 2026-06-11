"""
KESSLER SHADOW BROKER v1.0
==========================
A zero-API, fully local paper trading engine that simulates realistic
institutional trade execution against live market data.

This module tracks:
- Position entries/exits with realistic slippage and spread modeling
- Commission costs (Interactive Brokers fee schedule)
- Margin requirements for short positions
- Portfolio equity curve over time
- Maximum drawdown and Sharpe ratio
- Full audit trail in SQLite

All prices are fetched from Yahoo Finance's public endpoints.
No API keys. No brokerage accounts. No KYC.
"""

import sqlite3
import json
import time
import datetime
import urllib.request
import os
import math

# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = "data/shadow_broker.db"
INITIAL_CAPITAL = 65000.00  # USD

# Realistic cost modeling (Interactive Brokers fee schedule)
COMMISSION_PER_SHARE = 0.005       # $0.005 per share
MIN_COMMISSION = 1.00              # $1.00 minimum per order
MAX_COMMISSION_PCT = 0.005         # 0.5% of trade value max
SLIPPAGE_BPS = 5                   # 5 basis points of slippage per fill
SPREAD_BPS = 3                     # 3 basis points bid/ask spread

# Risk management
MAX_POSITION_PCT = 0.25            # Never risk more than 25% of capital on one trade
MAX_DRAWDOWN_HALT = 0.20           # Halt all trading if drawdown exceeds 20%
DEFAULT_STOP_LOSS_PCT = 0.03       # 3% stop loss
DEFAULT_TAKE_PROFIT_PCT = 0.10     # 10% take profit

# Margin requirements for short positions
SHORT_MARGIN_REQUIREMENT = 1.50    # 150% margin requirement (Reg T)

# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():
    """Initialize the SQLite database with proper schema."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Portfolio state table
    c.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            cash REAL NOT NULL,
            total_equity REAL NOT NULL,
            initial_capital REAL NOT NULL,
            total_realized_pnl REAL NOT NULL DEFAULT 0.0,
            total_commissions_paid REAL NOT NULL DEFAULT 0.0,
            total_trades INTEGER NOT NULL DEFAULT 0,
            winning_trades INTEGER NOT NULL DEFAULT 0,
            losing_trades INTEGER NOT NULL DEFAULT 0,
            max_drawdown REAL NOT NULL DEFAULT 0.0,
            peak_equity REAL NOT NULL,
            trading_halted INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Individual trade records (full audit trail)
    c.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
            status TEXT NOT NULL CHECK (status IN ('OPEN', 'CLOSED', 'STOPPED_OUT', 'TAKE_PROFIT')),
            entry_price REAL NOT NULL,
            entry_fill_price REAL NOT NULL,
            exit_price REAL,
            exit_fill_price REAL,
            shares INTEGER NOT NULL,
            notional_value REAL NOT NULL,
            commission_entry REAL NOT NULL,
            commission_exit REAL DEFAULT 0.0,
            slippage_entry REAL NOT NULL,
            slippage_exit REAL DEFAULT 0.0,
            stop_loss_price REAL NOT NULL,
            take_profit_price REAL NOT NULL,
            realized_pnl REAL DEFAULT 0.0,
            unrealized_pnl REAL DEFAULT 0.0,
            kessler_confidence REAL,
            kessler_cascade_depth INTEGER,
            kessler_defaults INTEGER,
            entry_reason TEXT,
            exit_reason TEXT,
            opened_at TEXT NOT NULL,
            closed_at TEXT
        )
    """)

    # Equity curve snapshots (for Sharpe ratio and drawdown tracking)
    c.execute("""
        CREATE TABLE IF NOT EXISTS equity_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            cash REAL NOT NULL,
            unrealized_pnl REAL NOT NULL,
            total_equity REAL NOT NULL,
            open_positions INTEGER NOT NULL,
            drawdown_pct REAL NOT NULL
        )
    """)

    # Kessler signal log (every signal the engine produces)
    c.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            signal_type TEXT NOT NULL CHECK (signal_type IN ('CASCADE_DETECTED', 'BOUNCE_DETECTED', 'NO_SIGNAL')),
            confidence REAL,
            cascade_depth INTEGER,
            defaults_count INTEGER,
            mbs_price REAL,
            spx_price REAL,
            action_taken TEXT,
            raw_output TEXT
        )
    """)

    # Initialize portfolio if it doesn't exist
    c.execute("SELECT COUNT(*) FROM portfolio")
    if c.fetchone()[0] == 0:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        c.execute("""
            INSERT INTO portfolio (id, cash, total_equity, initial_capital, peak_equity, created_at, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, ?)
        """, (INITIAL_CAPITAL, INITIAL_CAPITAL, INITIAL_CAPITAL, INITIAL_CAPITAL, now, now))

    conn.commit()
    conn.close()


# ============================================================
# MARKET DATA
# ============================================================

def fetch_live_price(ticker):
    """Fetch the latest price for a ticker from Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            meta = data["chart"]["result"][0]["meta"]
            return float(meta["regularMarketPrice"])
    except Exception as e:
        print(f"  [!] Price fetch failed for {ticker}: {e}")
        return None


def get_fill_price(market_price, direction, is_entry):
    """
    Calculate a realistic fill price accounting for:
    - Bid/Ask spread (you buy at ask, sell at bid)
    - Slippage (market impact of your order)
    """
    spread_adjustment = market_price * (SPREAD_BPS / 10000.0)
    slippage_adjustment = market_price * (SLIPPAGE_BPS / 10000.0)

    if direction == "SHORT":
        if is_entry:
            # Shorting: you sell at the bid, minus slippage
            return market_price - spread_adjustment - slippage_adjustment
        else:
            # Covering: you buy at the ask, plus slippage
            return market_price + spread_adjustment + slippage_adjustment
    else:  # LONG
        if is_entry:
            # Buying: you buy at the ask, plus slippage
            return market_price + spread_adjustment + slippage_adjustment
        else:
            # Selling: you sell at the bid, minus slippage
            return market_price - spread_adjustment - slippage_adjustment


def calculate_commission(shares, fill_price):
    """Calculate commission using Interactive Brokers tiered fee schedule."""
    raw_commission = shares * COMMISSION_PER_SHARE
    max_commission = shares * fill_price * MAX_COMMISSION_PCT
    return max(MIN_COMMISSION, min(raw_commission, max_commission))


# ============================================================
# PORTFOLIO OPERATIONS
# ============================================================

def get_portfolio():
    """Retrieve current portfolio state."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM portfolio WHERE id = 1")
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_open_positions():
    """Retrieve all currently open positions."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM trades WHERE status = 'OPEN'")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def open_position(symbol, direction, market_price, kessler_confidence=None,
                  kessler_cascade_depth=None, kessler_defaults=None, reason=None):
    """
    Open a new position with realistic execution modeling.
    Returns the trade record or None if rejected by risk management.
    """
    portfolio = get_portfolio()

    # --- RISK CHECK 1: Is trading halted? ---
    if portfolio["trading_halted"]:
        print("  [RISK] Trading halted due to max drawdown breach. No new positions.")
        return None

    # --- RISK CHECK 2: Do we already have an open position in this symbol? ---
    open_pos = get_open_positions()
    for pos in open_pos:
        if pos["symbol"] == symbol:
            print(f"  [RISK] Already have an open {pos['direction']} position in {symbol}. Skipping.")
            return None

    # --- RISK CHECK 3: Position sizing ---
    max_notional = portfolio["cash"] * MAX_POSITION_PCT
    fill_price = get_fill_price(market_price, direction, is_entry=True)

    # Calculate shares (round down to whole shares)
    if direction == "SHORT":
        # For shorts, we need 150% margin
        effective_buying_power = max_notional / SHORT_MARGIN_REQUIREMENT
        shares = int(effective_buying_power / fill_price)
    else:
        shares = int(max_notional / fill_price)

    if shares <= 0:
        print("  [RISK] Insufficient capital for minimum position size.")
        return None

    notional_value = shares * fill_price
    commission = calculate_commission(shares, fill_price)
    slippage_cost = abs(fill_price - market_price) * shares

    # --- RISK CHECK 4: Can we afford the commission + margin? ---
    total_cost = commission
    if direction == "LONG":
        total_cost += notional_value
    else:
        # For shorts, we need to post margin
        total_cost += notional_value * SHORT_MARGIN_REQUIREMENT

    if total_cost > portfolio["cash"]:
        print(f"  [RISK] Insufficient cash. Need ${total_cost:.2f}, have ${portfolio['cash']:.2f}")
        return None

    # --- Calculate stop loss and take profit ---
    if direction == "SHORT":
        stop_loss_price = fill_price * (1.0 + DEFAULT_STOP_LOSS_PCT)
        take_profit_price = fill_price * (1.0 - DEFAULT_TAKE_PROFIT_PCT)
    else:
        stop_loss_price = fill_price * (1.0 - DEFAULT_STOP_LOSS_PCT)
        take_profit_price = fill_price * (1.0 + DEFAULT_TAKE_PROFIT_PCT)

    # --- EXECUTE ---
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        INSERT INTO trades (
            symbol, direction, status, entry_price, entry_fill_price,
            shares, notional_value, commission_entry, slippage_entry,
            stop_loss_price, take_profit_price,
            kessler_confidence, kessler_cascade_depth, kessler_defaults,
            entry_reason, opened_at
        ) VALUES (?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        symbol, direction, market_price, fill_price,
        shares, notional_value, commission, slippage_cost,
        stop_loss_price, take_profit_price,
        kessler_confidence, kessler_cascade_depth, kessler_defaults,
        reason, now
    ))

    # Deduct commission and margin from cash
    new_cash = portfolio["cash"] - commission
    if direction == "LONG":
        new_cash -= notional_value

    c.execute("""
        UPDATE portfolio SET
            cash = ?,
            total_commissions_paid = total_commissions_paid + ?,
            total_trades = total_trades + 1,
            updated_at = ?
        WHERE id = 1
    """, (new_cash, commission, now))

    conn.commit()
    conn.close()

    print(f"  [EXECUTED] {direction} {shares} shares of {symbol}")
    print(f"    Market Price:  ${market_price:.2f}")
    print(f"    Fill Price:    ${fill_price:.2f}")
    print(f"    Notional:      ${notional_value:.2f}")
    print(f"    Commission:    ${commission:.2f}")
    print(f"    Slippage Cost: ${slippage_cost:.2f}")
    print(f"    Stop Loss:     ${stop_loss_price:.2f}")
    print(f"    Take Profit:   ${take_profit_price:.2f}")

    return {
        "symbol": symbol,
        "direction": direction,
        "shares": shares,
        "fill_price": fill_price,
        "notional_value": notional_value
    }


def close_position(trade_id, market_price, reason="MANUAL"):
    """Close an open position with realistic exit execution."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM trades WHERE id = ? AND status = 'OPEN'", (trade_id,))
    trade = c.fetchone()
    if not trade:
        print(f"  [!] Trade {trade_id} not found or already closed.")
        conn.close()
        return None

    trade = dict(trade)
    direction = trade["direction"]
    shares = trade["shares"]
    entry_fill = trade["entry_fill_price"]

    fill_price = get_fill_price(market_price, direction, is_entry=False)
    commission = calculate_commission(shares, fill_price)
    slippage_cost = abs(fill_price - market_price) * shares

    # Calculate realized P&L
    if direction == "SHORT":
        realized_pnl = (entry_fill - fill_price) * shares
    else:
        realized_pnl = (fill_price - entry_fill) * shares

    # Subtract exit commission from P&L
    realized_pnl -= commission

    # Determine close status
    if reason == "STOP_LOSS":
        status = "STOPPED_OUT"
    elif reason == "TAKE_PROFIT":
        status = "TAKE_PROFIT"
    else:
        status = "CLOSED"

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    c.execute("""
        UPDATE trades SET
            status = ?,
            exit_price = ?,
            exit_fill_price = ?,
            commission_exit = ?,
            slippage_exit = ?,
            realized_pnl = ?,
            exit_reason = ?,
            closed_at = ?
        WHERE id = ?
    """, (status, market_price, fill_price, commission, slippage_cost,
          realized_pnl, reason, now, trade_id))

    # Update portfolio
    portfolio = get_portfolio()
    new_cash = portfolio["cash"] + realized_pnl + trade["notional_value"] + trade["commission_entry"]
    # Return the margin for shorts, or the proceeds for longs
    if direction == "SHORT":
        new_cash = portfolio["cash"] + realized_pnl + commission  # commission already deducted from pnl
        new_cash = portfolio["cash"] + (entry_fill * shares) - (fill_price * shares) - commission
    else:
        new_cash = portfolio["cash"] + (fill_price * shares) - commission

    is_winner = 1 if realized_pnl > 0 else 0

    c.execute("""
        UPDATE portfolio SET
            cash = ?,
            total_realized_pnl = total_realized_pnl + ?,
            total_commissions_paid = total_commissions_paid + ?,
            winning_trades = winning_trades + ?,
            losing_trades = losing_trades + ?,
            updated_at = ?
        WHERE id = 1
    """, (new_cash, realized_pnl, commission, is_winner, 1 - is_winner, now))

    conn.commit()
    conn.close()

    pnl_symbol = "+" if realized_pnl >= 0 else ""
    print(f"  [CLOSED] Trade #{trade_id} | {direction} {shares}x {trade['symbol']}")
    print(f"    Entry Fill:    ${entry_fill:.2f}")
    print(f"    Exit Fill:     ${fill_price:.2f}")
    print(f"    Realized P&L:  {pnl_symbol}${realized_pnl:.2f}")
    print(f"    Reason:        {reason}")

    return realized_pnl


def check_stop_loss_take_profit():
    """Check all open positions against their stop loss and take profit levels."""
    positions = get_open_positions()
    for pos in positions:
        price = fetch_live_price(pos["symbol"])
        if price is None:
            continue

        if pos["direction"] == "SHORT":
            if price >= pos["stop_loss_price"]:
                print(f"  [STOP LOSS TRIGGERED] {pos['symbol']} hit ${price:.2f} >= ${pos['stop_loss_price']:.2f}")
                close_position(pos["id"], price, reason="STOP_LOSS")
            elif price <= pos["take_profit_price"]:
                print(f"  [TAKE PROFIT TRIGGERED] {pos['symbol']} hit ${price:.2f} <= ${pos['take_profit_price']:.2f}")
                close_position(pos["id"], price, reason="TAKE_PROFIT")
        else:  # LONG
            if price <= pos["stop_loss_price"]:
                print(f"  [STOP LOSS TRIGGERED] {pos['symbol']} hit ${price:.2f} <= ${pos['stop_loss_price']:.2f}")
                close_position(pos["id"], price, reason="STOP_LOSS")
            elif price >= pos["take_profit_price"]:
                print(f"  [TAKE PROFIT TRIGGERED] {pos['symbol']} hit ${price:.2f} >= ${pos['take_profit_price']:.2f}")
                close_position(pos["id"], price, reason="TAKE_PROFIT")


def update_equity_snapshot():
    """Take a snapshot of current portfolio equity for tracking."""
    portfolio = get_portfolio()
    positions = get_open_positions()

    total_unrealized = 0.0
    for pos in positions:
        price = fetch_live_price(pos["symbol"])
        if price is None:
            continue
        if pos["direction"] == "SHORT":
            unrealized = (pos["entry_fill_price"] - price) * pos["shares"]
        else:
            unrealized = (price - pos["entry_fill_price"]) * pos["shares"]
        total_unrealized += unrealized

    total_equity = portfolio["cash"] + total_unrealized
    drawdown_pct = 0.0

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Update peak equity and drawdown
    peak = max(portfolio["peak_equity"], total_equity)
    if peak > 0:
        drawdown_pct = (peak - total_equity) / peak

    # Check if we need to halt trading
    trading_halted = 1 if drawdown_pct >= MAX_DRAWDOWN_HALT else 0

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    c.execute("""
        INSERT INTO equity_snapshots (timestamp, cash, unrealized_pnl, total_equity, open_positions, drawdown_pct)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (now, portfolio["cash"], total_unrealized, total_equity, len(positions), drawdown_pct))

    c.execute("""
        UPDATE portfolio SET
            total_equity = ?,
            peak_equity = ?,
            max_drawdown = MAX(max_drawdown, ?),
            trading_halted = ?,
            updated_at = ?
        WHERE id = 1
    """, (total_equity, peak, drawdown_pct, trading_halted, now))

    conn.commit()
    conn.close()

    return total_equity, total_unrealized, drawdown_pct


def log_signal(signal_type, confidence=None, cascade_depth=None, defaults_count=None,
               mbs_price=None, spx_price=None, action_taken=None, raw_output=None):
    """Log a Kessler signal to the database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    c.execute("""
        INSERT INTO signals (timestamp, signal_type, confidence, cascade_depth,
                            defaults_count, mbs_price, spx_price, action_taken, raw_output)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (now, signal_type, confidence, cascade_depth, defaults_count,
          mbs_price, spx_price, action_taken, raw_output))
    conn.commit()
    conn.close()


# ============================================================
# PORTFOLIO REPORTING
# ============================================================

def print_portfolio_report():
    """Print a full portfolio status report."""
    portfolio = get_portfolio()
    positions = get_open_positions()

    total_equity, unrealized, drawdown = update_equity_snapshot()

    print("")
    print("=" * 65)
    print("           KESSLER SHADOW BROKER — PORTFOLIO REPORT")
    print("=" * 65)
    print(f"  Initial Capital:      ${portfolio['initial_capital']:>12,.2f}")
    print(f"  Current Cash:         ${portfolio['cash']:>12,.2f}")
    print(f"  Unrealized P&L:       ${unrealized:>12,.2f}")
    print(f"  Total Equity:         ${total_equity:>12,.2f}")
    print(f"  Realized P&L:         ${portfolio['total_realized_pnl']:>12,.2f}")
    print(f"  Total Commissions:    ${portfolio['total_commissions_paid']:>12,.2f}")
    print("-" * 65)
    pct_return = ((total_equity - portfolio["initial_capital"]) / portfolio["initial_capital"]) * 100
    print(f"  Return:               {pct_return:>11.2f}%")
    print(f"  Max Drawdown:         {portfolio['max_drawdown'] * 100:>11.2f}%")
    print(f"  Total Trades:         {portfolio['total_trades']:>12d}")
    print(f"  Winning Trades:       {portfolio['winning_trades']:>12d}")
    print(f"  Losing Trades:        {portfolio['losing_trades']:>12d}")

    if portfolio["total_trades"] > 0:
        win_rate = (portfolio["winning_trades"] / portfolio["total_trades"]) * 100
        print(f"  Win Rate:             {win_rate:>11.2f}%")

    print(f"  Trading Halted:       {'YES' if portfolio['trading_halted'] else 'NO':>12s}")
    print("-" * 65)

    if positions:
        print(f"  OPEN POSITIONS ({len(positions)}):")
        for pos in positions:
            price = fetch_live_price(pos["symbol"])
            if price and pos["direction"] == "SHORT":
                unr = (pos["entry_fill_price"] - price) * pos["shares"]
            elif price:
                unr = (price - pos["entry_fill_price"]) * pos["shares"]
            else:
                unr = 0.0
            pnl_sym = "+" if unr >= 0 else ""
            print(f"    [{pos['id']}] {pos['direction']:>5s} {pos['shares']}x {pos['symbol']}"
                  f" @ ${pos['entry_fill_price']:.2f}"
                  f" | Now: ${price:.2f if price else 0:.2f}"
                  f" | P&L: {pnl_sym}${unr:.2f}")
    else:
        print("  OPEN POSITIONS: None")

    print("=" * 65)
    print("")


# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    init_db()
    print_portfolio_report()
