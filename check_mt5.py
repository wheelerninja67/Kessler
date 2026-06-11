import MetaTrader5 as mt5
import sys

def check():
    print("[*] Connecting to MetaTrader 5 Terminal...")
    if not mt5.initialize():
        print(f"[!] MT5 initialize failed. Error: {mt5.last_error()}")
        sys.exit(1)
        
    account_info = mt5.account_info()
    if account_info is None:
        print("[!] Failed to retrieve account data.")
        mt5.shutdown()
        sys.exit(1)
        
    print("\n=============================================")
    print("      [KESSLER MT5 CONNECTION ESTABLISHED]   ")
    print("=============================================")
    print(f"[*] Account ID: {account_info.login}")
    print(f"[*] Broker:     {account_info.company}")
    print(f"[*] Server:     {account_info.server}")
    print(f"[*] Balance:    ${account_info.balance:,.2f}")
    print(f"[*] Equity:     ${account_info.equity:,.2f}")
    print("=============================================\n")
    
    mt5.shutdown()

if __name__ == "__main__":
    check()
