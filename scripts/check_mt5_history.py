import MetaTrader5 as mt5
from datetime import datetime, timedelta

if not mt5.initialize():
    print("initialize() failed")
    mt5.shutdown()
    quit()

from_date = datetime.now() - timedelta(days=1)
to_date = datetime.now() + timedelta(days=1)

history_deals = mt5.history_deals_get(from_date, to_date)
if history_deals == None or len(history_deals) == 0:
    print("[*] No trades found in the last 24 hours.")
else:
    print(f"[*] Found {len(history_deals)} trades in the last 24 hours:")
    for deal in history_deals:
        if deal.symbol != "":
            print(f"Ticket: {deal.ticket}, Symbol: {deal.symbol}, Volume: {deal.volume}, Profit: {deal.profit}")

mt5.shutdown()
