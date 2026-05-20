# Project Kessler
> A deterministic systemic risk simulation engine. Model 1,000,000+ autonomous trading agents on consumer hardware. Map the exact fracture lines where liquidity vanishes and cascades trigger.

## Overview
Current top-down risk models, including VaR, CCAR, and Monte Carlo simulations, fundamentally assume normal distributions and treat market participants as static variables. This architecture blinds them to endogenous cascades and liquidity black holes. Project Kessler is an agent-based systemic risk simulator designed for tier-1 financial institutions to solve this exact failing. By modeling millions of autonomous, interacting trading agents on bare-metal hardware, the engine generates market collapses from first principles. Kessler maps the exact phase transitions where individual panic metastasizes into global financial contagion.

## Key Capabilities
* 1,000,000+ agents executing on consumer hardware (tested on Dell Latitude, 8 GB RAM)
* 37 institutional macro assets across equities, FX, sovereign bonds, futures, credit, volatility, and crypto
* Historical replay mode ingesting 4,013 trading days of real market data
* Forward stress-testing parameterized with full Gai-Kapadia contagion physics
* Cryptographic deterministic replay verified via `SHA-256` hashing
* Enterprise telemetry suite including stylized facts, implied volatility surfaces, tail-risk reporting, and network health metrics
* Air-gapped deployment via the Kessler Box hardware appliance
* Zero heap allocations after initialization relying on 64-byte aligned Struct of Arrays (`SoA`)

## Technical Architecture

| Component | Specification |
| :--- | :--- |
| **Language** | `Zig` (stable, 0.16.0) |
| **Memory Model** | Single fixed arena, bump-pointer allocation, minimum 64-byte alignment on all memory boundaries |
| **Agent State** | Struct of Arrays (`SoA`) with separate contiguous arrays for cash, equity, theta, sigma, leverage, and portfolio for optimal L1/L2 cache streaming |
| **Order Book** | Exponential limit order book featuring dynamic depth (`Kyle's Lambda`), circuit breakers, and liquidity black hole detection |
| **Contagion Engine** | Gai-Kapadia framework for concurrent direct credit losses and mark-to-market fire sales across a multi-layer network |
| **Determinism** | Independent `xoshiro256+` PRNG per agent, fixed-order execution loops, and `SHA-256` hash of full tick output |
| **Concurrency** | Fork-join thread pool utilizing lock-free SPSC intent buffers and work-stealing algorithms for the contagion phase |
| **Data Pipeline** | Frozen CSV ingestion at initialization guaranteeing zero network calls during the active simulation loop |

## Physics Models

### Gai-Kapadia Contagion
A dual-channel cascade model that triggers simultaneous financial shocks through direct counterparty credit losses and mark-to-market fire sales. The simulation iterates continuously through the network until structural equilibrium is reached and no new defaults occur.

### Hawkes Self-Exciting Defaults
A statistical model for event clustering applied to corporate defaults, functioning similarly to earthquake aftershocks. Default intensity spikes immediately across the network upon a single failure and decays exponentially over time.

### Kyle's Lambda
A market microstructure model defining dynamic market depth based on order flow. Price impact scales non-linearly, increasing severity when order flow becomes heavily one-sided or when broader market volatility spikes.

### Rough Volatility
A volatility forecasting approach using a fractional process with power-law memory. This mathematical structure generates the jagged, highly clustered volatility regimes characteristic of actual institutional financial markets.

### VPIN (Volume-Synchronized Probability of Informed Trading)
A metric for detecting order flow toxicity in real time. When informed traders begin picking off market makers, VPIN triggers automated liquidity withdrawal, draining the order book prior to a severe price dislocation.

### Explosive Synchronization Proximity
A predictive phase-transition model based on the correlation of agent theta values. This measures the proximity to a complete herd stampede, historically validated against the synchronization of 39 global stock markets prior to the 2008 crash.

### NTIDE Silence Waves
A mechanism where liquidity withdrawal propagates systematically through the correlation space of different assets. This mirrors the microstructure dynamics of modern algorithmic flash crashes where liquidity vanishes concurrently across distinct asset classes.

### Centrality-Based Risk
A network topology vulnerability metric where eigenvector centrality amplifies the severity of a cascade. The default of highly connected, systemically important agents mathematically forces exponentially larger fire sales across the system.

### Agent Memory & Learning
Agents possess internal state mechanisms to adapt to changing environments through performance-chasing, loss-aversion biases, and localized strategy mutation over sequential ticks.

### Levy Flight Jumps
An exogenous shock injection system utilizing power-law distributions to model extreme market movements. This produces the fat-tail events that standard normal-distribution risk models consistently fail to predict.

## Enterprise Features
* Stylized Fact Validation (kurtosis, volatility clustering, long memory)
* Implied Volatility Surface (ATM IV derived from historical volatility, combined with OTM put skew)
* Tail-Risk Report (top 5 drawdowns, standard VaR, and Tail VaR)
* Network Health Report (edge severance metrics, surviving centrality tracking)
* Central Bank Policy Learning (credibility degradation constraints, intervention size adaptation)
* Institutional Readiness Report (data density formatted for CRO review)
* CSV export of full tick-level data for downstream quantitative analysis
* Cryptographic deterministic replay hash (`SHA-256`)

## The Kessler Box

| Feature | Detail |
| :--- | :--- |
| **Chassis** | Fanless, ruggedized embedded computing unit |
| **Physical Security** | FIPS 140-2 Level 3 compliant tamper-detection mesh |
| **Hardware Root of Trust** | TPM 2.0 measured boot paired with OpenTitan integration |
| **Storage** | Dual encrypted NVMe solid-state drives |
| **Interface** | Fiber optic serial console serving as the sole physical I/O vector |
| **Environment** | Fully reproducible build utilizing a Nix-based toolchain |
| **Verification** | Same seed yields same hash, independently verifiable by the client |

## Market Data Pipeline
* 37 institutional tickers spanning 6 asset classes
* Sourced historically via yfinance and stored as frozen CSV state
* Ingested entirely into the memory arena at initialization to ensure zero network calls during simulation
* Spans 4,013 continuous trading days from 2015 to 2025
* Historical replay mode iterates sequentially to calibrate agent state and network topology
* Forward mode assumes control at the historical terminus to begin synthetic stress testing

## Performance
* Tested on consumer hardware (Dell Latitude 5400, Core i5-8365U, 8 GB RAM)
* Simultaneously processes 1,000,000 agents and 37 assets across a 4,013-day historical replay
* Core tick execution loop resolves in microseconds
* Strict zero heap allocation policy enforced after the initialization phase
* Memory boundaries aligned to 64-byte `SoA` patterns to saturate L1/L2 cache streaming bandwidth

## Roadmap
* Pilot-ready version complete (API access, client-controlled parameters, technical documentation) within 30 days of funding
* Enterprise pilot deployment by Month 2–3
* Finalization of the Kessler Box physical prototype by Month 4–6
* Execution of the first paid enterprise license by Month 6–12
* Reach permanent hard-cap of 5 to 10 total institutional clients by Year 2–3

## Funding
* Currently unfunded. Operating as a bootstrapped solo founder utilizing consumer hardware.
* Applications submitted to 1517 Fund, Thiel Fellowship, and Y Combinator (Summer 2026).
* Seeking $500K pre-seed allocation to finance relocation to New York City, hardware R&D, and 12-month operational runway.

## Contact
* Founder: Srijan Mandal
* Email: srijaan@proton.me
* X: @unemployed61269
* Instagram: @unemployedguyfromearth
* GitHub: github.com/wheelerninja67

## License
Proprietary. All rights reserved. This repository contains architecture documentation only. The source code is private.
