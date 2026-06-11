"""
KESSLER DAEMON v2.0
====================
Continuous market monitoring daemon with integrated Shadow Broker execution.

Every cycle:
1. Fetches live MBS and SPX prices
2. Runs the Kessler physics engine against current market state
3. Parses the engine output for cascade signals
4. If a cascade is detected -> executes a SHORT via shadow_broker
5. Checks all open positions for stop-loss / take-profit triggers
6. Logs everything to SQLite and flat files
"""

import time
import subprocess
import datetime
import sys
import os
import re

# Import the shadow broker
from shadow_broker import (
    init_db, fetch_live_price, open_position, close_position,
    check_stop_loss_take_profit, update_equity_snapshot,
    print_portfolio_report, log_signal, get_open_positions, get_portfolio
)

CYCLE_INTERVAL = 300  # 5 minutes
LOG_DIR = "data/logs"


def parse_kessler_output(output):
    """
    Parse the raw Kessler terminal output to extract:
    - Final defaults count
    - Peak cascade depth
    - Final market prices
    - Oracle confidence rating
    """
    result = {
        "defaults": 0,
        "cascade_depth": 0,
        "final_mbs": 100.0,
        "final_spx": 100.0,
        "confidence": 0.0,
        "action": None,
        "entry_price": 0.0,
        "exit_price": 0.0,
        "time_to_cascade": 0,
    }

    lines = output.split("\n")

    for line in lines:
        # Parse TICK lines for defaults and cascade depth
        tick_match = re.search(
            r"DEFAULTS:\s*(\d+)\s*\|\s*CAS:\s*(\d+)", line
        )
        if tick_match:
            defaults = int(tick_match.group(1))
            cascade = int(tick_match.group(2))
            if defaults > result["defaults"]:
                result["defaults"] = defaults
            if cascade > result["cascade_depth"]:
                result["cascade_depth"] = cascade

        # Parse final MBS price
        mbs_match = re.search(r"MBS:\s*([\d.]+)", line)
        if mbs_match:
            result["final_mbs"] = float(mbs_match.group(1))

        # Parse final SPX price
        spx_match = re.search(r"SPX:\s*([\d.]+)", line)
        if spx_match:
            result["final_spx"] = float(spx_match.group(1))

        # Parse Oracle output
        if "DETERMINISTIC CONFIDENCE RATING" in line:
            conf_match = re.search(r"([\d.]+)%", line)
            if conf_match:
                result["confidence"] = float(conf_match.group(1))

        if "EXECUTED ACTION:" in line:
            if "SHORT" in line:
                result["action"] = "SHORT"
            elif "LONG" in line:
                result["action"] = "LONG"

        if "ENTRY PRICE:" in line:
            price_match = re.search(r"([\d.]+)", line.split(":")[-1])
            if price_match:
                result["entry_price"] = float(price_match.group(1))

        if "COMPUTED EXIT:" in line:
            price_match = re.search(r"([\d.]+)", line.split(":")[-1])
            if price_match:
                result["exit_price"] = float(price_match.group(1))

        if "TIME TO CASCADE:" in line:
            tick_match_inner = re.search(r"(\d+)", line.split(":")[-1])
            if tick_match_inner:
                result["time_to_cascade"] = int(tick_match_inner.group(1))

    return result


def run_kessler_cycle(cycle_num):
    """Execute a single Kessler monitoring cycle."""
    now = datetime.datetime.now()
    print(f"\n{'='*65}")
    print(f"  KESSLER DAEMON — CYCLE #{cycle_num} [{now.strftime('%Y-%m-%d %H:%M:%S')}]")
    print(f"{'='*65}")

    # -------------------------------------------------------
    # PHASE 1: Fetch live market data
    # -------------------------------------------------------
    print("\n[PHASE 1] Fetching live market data...")
    spx_price = fetch_live_price("SPY")
    mbs_price = fetch_live_price("MBB")

    if spx_price is None or mbs_price is None:
        print("  [!] Failed to fetch market data. Skipping cycle.")
        log_signal("NO_SIGNAL", mbs_price=mbs_price, spx_price=spx_price,
                   action_taken="SKIPPED_NO_DATA")
        return

    print(f"  SPY (S&P 500):  ${spx_price:.2f}")
    print(f"  MBB (MBS ETF):  ${mbs_price:.2f}")

    # -------------------------------------------------------
    # PHASE 2: Run the Kessler Engine
    # -------------------------------------------------------
    print("\n[PHASE 2] Running Kessler physics engine...")
    try:
        # Run ingest + engine
        result = subprocess.run(
            ["/home/mid/.local/bin/kessler", "predict", "live"],
            capture_output=True, text=True, timeout=120
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        print("  [!] Engine execution timed out (120s). Skipping cycle.")
        log_signal("NO_SIGNAL", mbs_price=mbs_price, spx_price=spx_price,
                   action_taken="SKIPPED_TIMEOUT")
        return
    except Exception as e:
        print(f"  [!] Engine execution failed: {e}")
        log_signal("NO_SIGNAL", mbs_price=mbs_price, spx_price=spx_price,
                   action_taken=f"SKIPPED_ERROR: {e}")
        return

    # -------------------------------------------------------
    # PHASE 3: Parse engine output for signals
    # -------------------------------------------------------
    print("\n[PHASE 3] Parsing engine output for cascade signals...")
    parsed = parse_kessler_output(output)

    print(f"  Peak Defaults:     {parsed['defaults']:,}")
    print(f"  Peak Cascade:      {parsed['cascade_depth']}")
    print(f"  Oracle Confidence: {parsed['confidence']:.2f}%")
    print(f"  Oracle Action:     {parsed['action'] or 'NONE'}")

    # -------------------------------------------------------
    # PHASE 4: Signal Classification & Trade Execution
    # -------------------------------------------------------
    print("\n[PHASE 4] Evaluating trade signals...")

    # A "real" cascade: defaults > 500,000 agents AND cascade depth > 5
    is_critical_cascade = parsed["defaults"] > 500000 and parsed["cascade_depth"] > 5
    # A strong signal: Oracle confidence > 90%
    is_high_confidence = parsed["confidence"] >= 90.0

    if is_critical_cascade and is_high_confidence:
        signal_type = "CASCADE_DETECTED"
        print("  [!!!] CRITICAL CASCADE DETECTED — HIGH CONFIDENCE")
        print(f"        Defaults: {parsed['defaults']:,} | Cascade Depth: {parsed['cascade_depth']}")
        print(f"        Oracle says: {parsed['action']} with {parsed['confidence']:.2f}% confidence")

        # Execute the trade
        action = parsed["action"] or "SHORT"
        trade = open_position(
            symbol="SPY",
            direction=action,
            market_price=spx_price,
            kessler_confidence=parsed["confidence"],
            kessler_cascade_depth=parsed["cascade_depth"],
            kessler_defaults=parsed["defaults"],
            reason=f"Kessler CASCADE signal: {parsed['defaults']:,} defaults, "
                   f"depth {parsed['cascade_depth']}, conf {parsed['confidence']:.1f}%"
        )
        action_taken = f"OPENED_{action}_SPY" if trade else "REJECTED_BY_RISK"
    else:
        signal_type = "NO_SIGNAL"
        action_taken = "HOLD"
        if parsed["defaults"] > 100000:
            print(f"  [~] Elevated defaults ({parsed['defaults']:,}) but below critical threshold.")
        else:
            print("  [—] No actionable signal detected. Market structure stable.")

    log_signal(
        signal_type=signal_type,
        confidence=parsed["confidence"],
        cascade_depth=parsed["cascade_depth"],
        defaults_count=parsed["defaults"],
        mbs_price=mbs_price,
        spx_price=spx_price,
        action_taken=action_taken,
        raw_output=output[:2000]  # Store first 2000 chars
    )

    # -------------------------------------------------------
    # PHASE 5: Check existing positions for stop-loss / take-profit
    # -------------------------------------------------------
    print("\n[PHASE 5] Checking open positions for exits...")
    check_stop_loss_take_profit()

    # -------------------------------------------------------
    # PHASE 6: Update equity snapshot
    # -------------------------------------------------------
    print("\n[PHASE 6] Updating equity snapshot...")
    total_equity, unrealized, drawdown = update_equity_snapshot()
    print(f"  Total Equity:   ${total_equity:,.2f}")
    print(f"  Unrealized P&L: ${unrealized:,.2f}")
    print(f"  Drawdown:       {drawdown * 100:.2f}%")

    # -------------------------------------------------------
    # PHASE 7: Write to flat log file
    # -------------------------------------------------------
    log_filename = os.path.join(
        LOG_DIR, f"kessler_live_{now.strftime('%Y%m%d')}.log"
    )
    with open(log_filename, "a") as logfile:
        logfile.write(f"\n{'='*50}\n")
        logfile.write(f"CYCLE: {cycle_num} | TIME: {now.isoformat()}\n")
        logfile.write(f"SPY: ${spx_price:.2f} | MBB: ${mbs_price:.2f}\n")
        logfile.write(f"DEFAULTS: {parsed['defaults']:,} | CASCADE: {parsed['cascade_depth']}\n")
        logfile.write(f"SIGNAL: {signal_type} | ACTION: {action_taken}\n")
        logfile.write(f"EQUITY: ${total_equity:,.2f} | DRAWDOWN: {drawdown*100:.2f}%\n")
        logfile.write(f"{'='*50}\n")


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    init_db()

    print("\n" + "=" * 65)
    print("  KESSLER DAEMON v2.0 — SHADOW BROKER INTEGRATED")
    print("  Continuous Market Monitoring + Autonomous Trade Execution")
    print("=" * 65)

    # Print initial portfolio state
    print_portfolio_report()

    cycle = 1

    # Run first cycle immediately
    run_kessler_cycle(cycle)

    print(f"\n[*] CONTINUOUS MONITORING ENGAGED ({CYCLE_INTERVAL}s intervals)")
    print("[*] Press Ctrl+C to terminate.\n")

    try:
        while True:
            time.sleep(CYCLE_INTERVAL)
            cycle += 1
            run_kessler_cycle(cycle)

            # Print full report every 6 cycles (30 minutes)
            if cycle % 6 == 0:
                print_portfolio_report()

    except KeyboardInterrupt:
        print("\n\n[*] Daemon terminated by operator.")
        print("[*] Final Portfolio State:")
        print_portfolio_report()
        sys.exit(0)


if __name__ == "__main__":
    main()
