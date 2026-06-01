```markdown
# Kessler 📉💥

> **A causal microscope for financial contagion.**

[![Written in Zig](https://img.shields.io/badge/Written_in-Zig-F7A41D?style=flat-square&logo=zig)](https://ziglang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen?style=flat-square)](https://github.com/)

**Kessler** is a high-performance systemic risk simulation engine developed by Srijan Mandal. Rather than predicting normal market conditions, Kessler models exactly how and why markets break down, liquidity vanishes, and contagion spreads during black-swan events. 

---

## 📖 Table of Contents
- [Core Philosophy](#-core-philosophy)
- [Architecture & Performance](#-architecture--performance)
- [The Financial Physics Engine](#-the-financial-physics-engine)
- [The Kessler Box](#-the-kessler-box)
- [Getting Started](#-getting-started)
- [Usage](#-usage)
- [License](#-license)

---

## 🧠 Core Philosophy

Most quantitative models fail because they extrapolate historical correlations into the future. Kessler assumes that during extreme distress, historical correlations approach `1.0`. Instead of statistics, Kessler relies on **mechanical market physics**—tracking the exact balance sheet health, leverage, and panic responses of over 1,000,000 autonomous trading agents.

## ⚡ Architecture & Performance

Engineered in **Zig**, Kessler is designed to simulate massive agent networks on standard consumer hardware (e.g., an i5 laptop) through brutal memory efficiency.

*   **Zero Heap Allocations:** Post-initialization, Kessler uses a single fixed arena with bump-pointer allocation. There is no garbage collection, and memory fragmentation is impossible.
*   **Struct of Arrays (SoA):** Agent states (cash, equity, leverage, network exposure) are stored in contiguous memory arrays, maximizing L1/L2 cache streaming bandwidth.
*   **Strict Determinism:** Powered by a `xoshiro256+` PRNG per agent. The evaluation loops are fixed; providing the same seed guarantees the exact same simulation hash output every single time.

## 🌪️ The Financial Physics Engine

Kessler simulates how panic mechanically spreads using advanced, non-linear risk models:

*   **Gai-Kapadia Contagion:** Accurately models how direct credit defaults and mark-to-market fire sales cascade through a heavily interconnected financial network.
*   **Hawkes Self-Exciting Defaults:** Treats market defaults like earthquake aftershocks. When one agent collapses, the probability of connected agents defaulting temporarily spikes.
*   **Kyle's Lambda & VPIN Toxicity:** Dynamically calculates the evaporation of market depth when order flow turns toxic, flawlessly recreating the "silence waves" that precede algorithmic flash crashes.

## 🧰 The "Kessler Box"

For production deployment, Kessler is designed to run as an air-gapped, ruggedized hardware appliance: **The Kessler Box**. 

It runs on a stripped-down Linux kernel with the compiled Zig binary running as `PID 1`. It mandates the use of **ECC RAM** to ensure that rogue cosmic bit-flips cannot alter the deterministic replay of a simulation.

---

## 🚀 Getting Started

### Prerequisites
*   [Zig](https://ziglang.org/download/) (v0.11.0 or higher)

### Installation

Clone the repository and build the engine with the `ReleaseFast` optimization flag to ensure maximum throughput:

```bash
# Clone the repository
git clone [https://github.com/wheelerninja67/Kessler.git](https://github.com/wheelerninja67/Kessler.git)
cd Kessler

# Build the executable
zig build -Doptimize=ReleaseFast

```

---

## 💻 Usage

Run a basic simulation from the command line by providing a seed and the number of agents.

```bash
./zig-out/bin/kessler --agents 1000000 --seed 42 --shock-node 14502 --shock-size 50000

```

### Example Output

```text
[INFO] Initializing Kessler Engine...
[INFO] Allocating SoA for 1,000,000 agents... Done (14.2ms)
[INFO] Seeding PRNG (xoshiro256+)... Seed: 42
[WARN] Injecting systemic shock at Node 14502 (Size: $50,000)
[INFO] Running tick evaluation...
...
[RESULT] Cascade Complete.
[RESULT] Total Ticks: 420
[RESULT] Defaults Triggered: 14,029
[RESULT] Liquidity Evaporation (Kyle's Lambda): 84.2%
[RESULT] Total Systemic Wealth Erased: $4.2B
[INFO] Execution Time: 84ms

```

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.

> **Disclaimer:** Kessler is a simulation engine intended for research and educational purposes. It does not provide financial advice or guarantee the prediction of actual market events.

```

```
