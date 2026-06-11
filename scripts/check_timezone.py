"""Quick probe to check MT5 candle timestamp timezone"""
import MetaTrader5 as mt5
import time as pytime
from datetime import datetime, timezone

if not mt5.initialize():
    print(f"[!] MT5 init failed: {mt5.last_error()}")
    exit(1)

mt5.login(20073104, password="EVoDLj0>E", server="FundingPips-SIM1")

# Get the latest NDX100 candle
rates = mt5.copy_rates_from_pos("NDX100", mt5.TIMEFRAME_M5, 0, 1)
if rates is None or len(rates) == 0:
    print("[!] Could not fetch NDX100 candles. Trying NAS100...")
    rates = mt5.copy_rates_from_pos("NAS100", mt5.TIMEFRAME_M5, 0, 1)

if rates is not None and len(rates) > 0:
    candle_time = rates[0]['time']
    
    # What gmtime thinks (treats as UTC)
    gm = pytime.gmtime(candle_time)
    
    # Current actual UTC
    now_utc = datetime.now(timezone.utc)
    
    print("=" * 50)
    print("  MT5 TIMESTAMP TIMEZONE PROBE")
    print("=" * 50)
    print(f"[*] Raw candle timestamp:  {candle_time}")
    print(f"[*] gmtime(candle_time):   {pytime.strftime('%Y-%m-%d %H:%M:%S', gm)}")
    print(f"[*] Actual UTC right now:  {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[*] gmtime hour:           {gm.tm_hour}")
    print(f"[*] Actual UTC hour:       {now_utc.hour}")
    
    diff = gm.tm_hour - now_utc.hour
    if diff < -12: diff += 24
    if diff > 12: diff -= 24
    
    print(f"[*] Offset:                {diff:+d} hours")
    
    if abs(diff) <= 1:
        print("\n[RESULT] MT5 timestamps are in UTC")
        print("[ACTION] Session filter 16-23 = 16:00-23:00 UTC = 9:30 PM - 4:30 AM IST")
        print("[WARNING] You're MISSING the NY open (7:00 PM IST). Change filter to 13 <= hour < 23")
    elif 2 <= diff <= 4:
        print(f"\n[RESULT] MT5 timestamps are in UTC+{diff} (broker server time)")
        print(f"[ACTION] Session filter 16-23 = {16-diff}:00-{23-diff}:00 UTC")
        print("[OK] You're likely catching the NY open already")
    else:
        print(f"\n[RESULT] Unexpected offset: {diff:+d}h. Check manually.")
    
    # Also check: what symbols are available?
    print("\n[*] Checking symbol names...")
    for sym in ["NDX100", "NAS100", "USTEC", "US100"]:
        info = mt5.symbol_info(sym)
        if info:
            print(f"  ✅ {sym} — visible: {info.visible}, trade_mode: {info.trade_mode}")
        else:
            print(f"  ❌ {sym} — not found")
else:
    print("[!] Could not fetch any candles.")

# Also show account status
account = mt5.account_info()
if account:
    print(f"\n[*] Account Balance: ${account.balance:,.2f}")
    print(f"[*] Account Equity:  ${account.equity:,.2f}")
    print(f"[*] Open Positions:  {mt5.positions_total()}")

mt5.shutdown()
