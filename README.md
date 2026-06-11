# KESSLER: Institutional Risk & Execution Engine

![License](https://img.shields.io/badge/License-MIT-blue.svg)
![Status](https://img.shields.io/badge/Status-Operational-brightgreen)
![Platform](https://img.shields.io/badge/Platform-MetaTrader_5-orange)

Kessler is a high-performance algorithmic risk management and execution engine designed explicitly for institutional index trading (NAS100/US100). 

It operates by physically decoupling the trading logic from the MT5 terminal via a custom HTTP/C++ Bridge, allowing complex machine-learning risk models to execute trades with zero cross-contamination.

## Architecture

Kessler utilizes a dual-node execution topology:
1. **The Daemon (`kessler_daemon.py`)**: The central nervous system. It continuously polls market state, volume physics, and spread variance.
2. **The Shadow Broker (`shadow_broker_interface.py`)**: The execution layer. It handles raw order dispatching, slippage protection, and prop-firm compliance constraints.
3. **The MT5 Bridge (`mt5_live_router.py`)**: The high-speed interconnect. It acts as the translation layer between the Kessler Python engine and the MetaTrader 5 C++ backend.

## Enterprise Features

* **Prop-Firm Compliance Matrix**: Natively designed to pass proprietary trading firm challenges (e.g., Funding Pips, FTMO) by strictly enforcing Maximum Daily Drawdown (3%) and Maximum Overall Loss (8%) rules at the hardware level. See `kessler_prop_firm_compliance_engine.py`.
* **Sub-Millisecond Execution**: Uses a custom MQL5/HTTP bridge (`Kessler_HTTP_Bridge.mq5`) to bypass standard Python MT5 library limitations, achieving institutional execution latency.
* **Asynchronous Market Ingestion**: Tracks liquidity voids and order-block formations dynamically, preventing executions in low-liquidity zones.

## Component Breakdown

* `kessler_nas100_execution.py`: The core operational script for live NAS100 execution.
* `kessler_prop_firm_compliance_engine.py`: The rigid FTMO/Funding Pips rule enforcer.
* `mt5_linux_bridge.py`: Enables execution bridging from Unix/Linux environments.
* `shadow_broker_interface.py`: Handles raw order routing and position sizing math.

## Disclaimer
This software is built for private institutional execution. Use at your own risk. Past performance does not guarantee future results.
