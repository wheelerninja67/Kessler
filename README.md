```
# Kessler

> A deterministic systemic risk simulation engine. Model 1,000,000+ autonomous trading agents on consumer hardware. Map the exact fracture lines where liquidity vanishes and cascades trigger.

---

## What It Does

Kessler is not a forecasting tool. It is a causal microscope for financial contagion.

Current risk models (VaR, Monte Carlo) assume the future resembles the past. They treat market collapses as statistical anomalies rather than mechanical inevitabilities. Kessler models the inevitability. Designed specifically for quantitative hedge funds, asset managers, and systemic risk regulators to stress-test their portfolios against true black-swan cascades.

A million synthetic traders—each with a balance sheet, risk appetite, leverage, and strategy—interact on an exponential limit order book. They are connected through a multi-layer network of direct credit exposures, common asset holdings, and funding dependencies. When you press enter, prices move. Bubbles form. Someone defaults. The cascade propagates. The market breaks.

None of it is scripted. The crash builds itself from the bottom up.

---

## Architecture

| Layer | Implementation |
|-------|----------------|
| **Language** | Zig (stable, 0.16.0) |
| **Memory Model** | Single fixed arena. Bump-pointer allocation. Minimum 64‑byte alignment on all arrays. Zero heap allocations after initialization. |
| **Agent State** | Struct of Arrays (SoA). Separate contiguous arrays for `cash`, `equity`, `theta`, `sigma`, `leverage`, `portfolio`. L1/L2 cache streaming at full bandwidth. |
| **Order Book** | Exponential limit order book with dynamic depth (Kyle's Lambda). Circuit breakers. Liquidity black hole detection. Magnet‑effect freeze logic. |
| **Contagion** | Gai‑Kapadia framework. Two‑channel cascade: direct credit losses + mark‑to‑market fire sales. Multi‑layer network propagation. Iterates until stability. |
| **Determinism** | `xoshiro256+` PRNG per agent. Fixed‑order evaluation loops. SHA‑256 hash of full tick output. Same seed = same hash. Every time. |
| **Concurrency** | Fork‑join thread pool. Lock‑free SPSC intent buffers. Work‑stealing for contagion phase. |
| **Data Pipeline** | Frozen CSV ingestion at initialization. Arena‑backed parsing. Zero network calls during simulation. |

---

## Physics Models

**Gai‑Kapadia Contagion**
Two‑channel cascade: direct credit losses flow through the interbank network while mark‑to‑market losses propagate through common asset holdings. The system iterates until no new defaults occur. This is the gold standard for systemic risk modeling.

**Hawkes Self‑Exciting Defaults**
Defaults cluster like earthquake aftershocks. Each default spikes the default intensity of connected agents, which decays exponentially unless another default re‑excites it. Produces realistic aftershock patterns.

**Kyle's Lambda Dynamic Depth**
Market depth is not static. The price impact parameter increases when order flow is one‑sided or volatility spikes, and reverts during calm. Each trade moves prices disproportionately during stress.

**Rough Volatility**
Volatility is not smooth. A fractional process with power‑law memory produces jagged, clustered spikes like real markets. Hurst exponent `H ≈ 0.15`.

**VPIN Order Flow Toxicity**
Volume‑Synchronized Probability of Informed Trading tracks whether informed traders are picking off market makers. When toxicity exceeds a threshold, liquidity providers withdraw—triggering the silence wave that precedes flash crashes.

**Explosive Synchronization Proximity**
When agent risk appetites become highly correlated, the system approaches a catastrophic phase transition. Kessler detects this proximity and warns before the cascade triggers.

**NTIDE Silence Waves**
Liquidity withdrawal propagates through asset correlation space. A crash in one asset causes market makers in correlated assets to pull quotes, even without direct trading.

**Centrality‑Based Risk**
Eigenvector centrality identifies systemically important agents. When a high‑centrality agent defaults, the cascade impact is amplified proportionally.

---

## Enterprise Features

- **Stylized Fact Validation:** Kurtosis of log‑returns, volatility clustering, long memory in order flow—proving the simulated market obeys real statistical laws.
- **Implied Volatility Surface:** ATM and OTM implied volatility computed from historical price paths.
- **Tail‑Risk Report:** Top drawdowns, Value at Risk, Expected Shortfall.
- **Network Health Report:** Edge severance, survivor centrality, average remaining degree.
- **Institutional Readiness Report:** Formatted for a Chief Risk Officer to screenshot.
- **CSV Export:** Full tick‑level data for external analysis.
- **Cryptographic Deterministic Replay:** SHA‑256 hash of the full simulation output. Same seed, same hash, every time.

---

## Market Data Pipeline

```
37 institutional assets across 6 classes
├── Equities: S&P 500, DJI, NASDAQ, Russell 2000, FTSE, DAX, CAC 40, Nikkei, Hang Seng, Shanghai Composite, BSE Sensex, KOSPI, Bovespa, TSX, ASX 200, Euro STOXX 50
├── FX: EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, USD/CHF, NZD/USD
├── Sovereign Bonds: 2Y, 10Y, 30Y US Treasury yields
├── Futures: S&P E-mini, NASDAQ E-mini, 10Y Note, 30Y Bond, WTI Crude, Gold, Silver
├── Credit: High Yield (HYG), Investment Grade (LQD)
└── Volatility: VIX
```

4,013 trading days (2015–2025). Sourced via `yfinance`, frozen to CSV, ingested into the arena at startup. Historical replay mode walks through every day sequentially. Forward mode picks up where history ends.

---

## Performance

Tested on a Dell Latitude 5400 (Core i5‑8365U, 8 GB RAM). The engine runs 1,000,000 agents across 37 assets, replays 4,013 days of real market data, then forward stress‑tests with Gai‑Kapadia contagion. Tick loop executes in microseconds. Zero heap allocations after initialization. 64‑byte aligned Struct of Arrays streams through L1/L2 cache at full bandwidth.

---

## The Kessler Box

The production deployment is a sealed, fanless, air‑gapped hardware appliance.

| Component | Specification |
|-----------|---------------|
| **Enclosure** | Ruggedized, tamper‑evident, passive cooling |
| **Memory** | ECC RAM (non‑negotiable—cosmic bit‑flips break deterministic replay) |
| **Security** | TPM 2.0 measured boot. OpenTitan root of trust. Dual encrypted NVMe drives. Fiber‑optic serial console (only I/O). |
| **OS** | Stripped Linux kernel. Zig binary runs as PID 1. No shell. No SSH. No networking stack. No package manager. |
| **Build** | Reproducible Nix‑based toolchain. Client can verify binary hash against public manifest. |

---

## Calibration & Prediction Pipeline

```
Historical Data → Parameter Sweep → XGBoost Surrogate → Bayesian Optimization → Calibrated Parameters
                                                                                          ↓
                                                                              Current Market State
                                                                                          ↓
                                                                           Monte Carlo Prediction
                                                                                          ↓
                                                                   "83% cascade probability. Expected drawdown: -52%"
```

Calibrated against the 2008 Global Financial Crisis. Real S&P 500 drawdown: –56.8%. Kessler synthetic drawdown: within ±5%.

---

## Contact

```
founder: srijan mandal
email:  srijaan@proton.me
x:      @unemployed61269
github: github.com/wheelerninja67/kessy
```

---

## License

Proprietary. All rights reserved. Designed for Enterprise Deployment. Unauthorized use, distribution, or reproduction is strictly prohibited.
```
