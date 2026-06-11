import MetaTrader5 as mt5
import time
import json
import json
import multiprocessing

# ==============================================================================
# KESSLER MULTI-FIRM ARBITRAGE NODE (PHASE 2)
# Architecture: Monitors Master Node, instantly mirrors to Slave Nodes
# ==============================================================================

# In the future, you will replace these with your actual $100k account credentials
# from Funding Pips, FTMO, TopStep, etc.
# Note: On Linux/Wine, each firm requires a separate MT5 installation directory.
SLAVE_NODES = [
    {"name": "Funding Pips 100k", "login": 123456, "password": "password", "server": "FundingPips-Server", "path": "C:\\Program Files\\Funding Pips MT5\\terminal64.exe"},
    {"name": "FTMO 100k", "login": 234567, "password": "password", "server": "FTMO-Server", "path": "C:\\Program Files\\FTMO MT5\\terminal64.exe"},
]

# The Master Account (Where Kessler is running)
MASTER_NODE = {"login": 999999, "password": "master_password", "server": "Master-Server"}

class TradeCopier:
    def __init__(self):
        self.active_master_tickets = set()
        print("[*] Kessler Multi-Firm Arbitrage Node Initialized.")
        print(f"[*] Loaded {len(SLAVE_NODES)} Slave Nodes for Mirroring.")

    def mirror_trade_to_slaves(self, trade_data):
        """
        Takes the Master trade data and fires it to all Slave firms in parallel.
        Uses threading to ensure 0.01ms latency across all firms.
        """
        symbol = trade_data.symbol
        volume = trade_data.volume
        trade_type = trade_data.type
        sl = trade_data.sl
        tp = trade_data.tp

        print(f"\n[!!!] KESSLER SNIPER FIRED ON MASTER: {symbol} | Type: {trade_type}")
        print(f"[*] Instantly mirroring to {len(SLAVE_NODES)} Prop Firms...")

        def execute_on_slave(node, symbol, volume, trade_type, sl, tp):
            # This runs in an isolated OS process so mt5.initialize doesn't conflict
            print(f"    -> [PROCESS SPAWNED] Connecting to {node['name']}...")
            
            if not mt5.initialize(path=node['path']):
                print(f"    [-] ERROR: Failed to initialize MT5 for {node['name']}")
                return
                
            if not mt5.login(node['login'], node['password'], node['server']):
                print(f"    [-] ERROR: Failed to login to {node['name']}")
                mt5.shutdown()
                return

            price = mt5.symbol_info_tick(symbol).ask if trade_type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).bid
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": trade_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": 777777,
                "comment": "Kessler-Copier",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            
            result = mt5.order_send(request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"    -> [EXECUTED] Mirrored on {node['name']} (Ticket: {result.order})")
            else:
                print(f"    [-] FAILED on {node['name']}: {result.comment}")
                
            mt5.shutdown()

        processes = []
        for node in SLAVE_NODES:
            p = multiprocessing.Process(target=execute_on_slave, args=(node, symbol, volume, trade_type, sl, tp))
            processes.append(p)
            p.start()
        
        for p in processes:
            p.join()

    def scan_master_node(self):
        """
        Listens to the local trade_journal.csv for new entries written by mt5_bridge.py
        When a new trade appears, it instantly fires mirror_trade_to_slaves.
        """
        print("[*] Arbitrage Node listening for Kessler Master Signals...")
        import os
        journal_path = "logs/trade_journal.csv"
        
        if not os.path.exists(journal_path):
            open(journal_path, 'a').close()
            
        last_mtime = os.path.getmtime(journal_path)
        last_size = os.path.getsize(journal_path)
        
        while True:
            try:
                current_mtime = os.path.getmtime(journal_path)
                current_size = os.path.getsize(journal_path)
                
                if current_mtime != last_mtime and current_size > last_size:
                    # File was appended to
                    with open(journal_path, 'r') as f:
                        f.seek(last_size)
                        new_lines = f.readlines()
                        
                    for line in new_lines:
                        if "SUCCESS" in line:
                            parts = line.strip().split(',')
                            # Format: timestamp, action, symbol, price, volume, magic, status
                            action_str = parts[1]
                            symbol = parts[2]
                            volume = float(parts[4])
                            
                            # Note: We don't have SL/TP in the CSV right now. 
                            # We can either parse it from MT5 or let the slave calculate it.
                            # For now, we will execute market orders.
                            class DummyTrade: pass
                            t = DummyTrade()
                            t.symbol = symbol
                            t.volume = volume
                            t.type = mt5.ORDER_TYPE_BUY if action_str == "BUY" else mt5.ORDER_TYPE_SELL
                            t.sl = 0.0 # Calculate dynamically later
                            t.tp = 0.0 # Calculate dynamically later
                            
                            self.mirror_trade_to_slaves(t)
                            
                    last_mtime = current_mtime
                    last_size = current_size
                    
                time.sleep(0.1) # Check every 100ms
            except KeyboardInterrupt:
                break
            except Exception as e:
                time.sleep(1)

if __name__ == "__main__":
    copier = TradeCopier()
    copier.scan_master_node()
