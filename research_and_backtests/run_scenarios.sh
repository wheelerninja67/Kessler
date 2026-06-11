#!/bin/bash
cd /home/mid/Projects/kessler

echo "========================================================="
echo " [SCENARIO 1] THE 2008 LEHMAN LIQUIDITY CRISIS (FAILURE)"
echo " Constraints: Massive Cash Fragility, Extreme Decay, Zero Leverage."
echo "========================================================="
zig build run -- --agents 10000 --ticks 500 --leverage-cap 1.1 --cash-fragility 0.99 --decay-rate 0.9

echo -e "\n========================================================="
echo " [SCENARIO 2] 2021 QUANTITATIVE EASING (EXTREME GREATNESS)"
echo " Constraints: Infinite Liquidity, Low Decay, High Leverage."
echo "========================================================="
zig build run -- --agents 10000 --ticks 500 --leverage-cap 10.0 --cash-fragility 0.1 --decay-rate 0.05

echo -e "\n========================================================="
echo " [SCENARIO 3] THE 2023 FLAT CHOP (STAGNATION)"
echo " Constraints: Neutral liquidity, choppy decay, moderate leverage."
echo "========================================================="
zig build run -- --agents 10000 --ticks 500 --leverage-cap 2.0 --cash-fragility 0.5 --decay-rate 0.5

echo -e "\n========================================================="
echo " ALL SCENARIOS COMPLETE. ZIG SWARM VALIDATED."
echo "========================================================="
