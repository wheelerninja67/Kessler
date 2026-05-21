# Project Kessler: Apex Oracle Engine

**A deterministic, zero-heap systemic risk and contagion oracle built in Zig.**

Traditional Value-at-Risk (VaR) models fundamentally fail during liquidity crises because they assume normal market distributions and ignore structural network contagion. Project Kessler is a deep-tech alternative: an agent-based market micro-structure simulator that uses a 10-phase Gai-Kapadia contagion model to mathematically prove the fragility of interconnected financial systems.

It is calibrated using a Python machine-learning pipeline (XGBoost + Bayesian Optimization) and executes 100-path Monte Carlo simulations in milliseconds.

## Proof of Execution: Lehman 2008 Calibrated

*100-path Monte Carlo prediction showing 100% cascade probability and -8.8% expected drawdown following the exogenous bankruptcy of 3 highly-leveraged network agents.*

```text
==================================================
PROJECT KESSLER: APEX ORACLE ENGINE
SCENARIO: Lehman 2008 Calibrated
==================================================
[*] LOADING CALIBRATED PARAMETERS...
Loaded Params: Lev=7.65, Depth=787.22, Decay=0.1041
[*] IGNITING 100-PATH MONTE CARLO PREDICTION...
>>> SYSTEMIC SHOCK: Bankrupting 3 agents to trigger contagion <<<
>>> MARKET SHOCK: Asset 0 liquidity withdrawn by 15% <<<
>>> INITIATING 10-PHASE GAI-KAPADIA TICK LOOP <<<

... [Tick loops executing market drift & contagion physics] ...

CRISIS PROBABILITY: 100% of paths trigger a cascade within 500 ticks
EXPECTED DRAWDOWN: -8.8% (90% confidence interval: -19.5% to -5.0%)
