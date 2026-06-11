import json
import os
import subprocess
import optuna

TARGET_DRAWDOWN = -56.8
TARGET_KURTOSIS = 3.0
TARGET_VOL_CLUSTERING = 0.15
TARGET_CASCADE_DEPTH = 3.0

def objective(trial):
    leverage_cap = trial.suggest_float("leverage_cap", 10.0, 75.0)
    base_depth = trial.suggest_int("base_depth", 200, 3000)
    decay_rate = trial.suggest_float("decay_rate", 0.01, 0.1)
    freeze_threshold = trial.suggest_float("freeze_threshold", 0.3, 0.95)
    freeze_duration = trial.suggest_int("freeze_duration", 1, 8)
    cb_sensitivity = trial.suggest_float("cb_sensitivity", 0.3, 2.5)
    value_buy_threshold = trial.suggest_float("value_buy_threshold", 0.05, 0.40)
    cash_fragility = trial.suggest_float("cash_fragility", 0.01, 0.15)
    market_maker_resilience = trial.suggest_float("market_maker_resilience", 0.01, 0.20)

    exe_path = "zig-out/bin/kessler.exe" if os.name == "nt" else "./zig-out/bin/kessler"
    
    cmd = [
        exe_path,
        "--leverage-cap", str(leverage_cap),
        "--base-depth", str(base_depth),
        "--decay-rate", str(decay_rate),
        "--freeze-threshold", str(freeze_threshold),
        "--freeze-duration", str(freeze_duration),
        "--cb-sensitivity", str(cb_sensitivity),
        "--value-buy-threshold", str(value_buy_threshold),
        "--cash-fragility", str(cash_fragility),
        "--market-maker-resilience", str(market_maker_resilience),
        "--ticks", "200",
        "--agents", "5000",
    ]
    
    try:
        res_zig = subprocess.run(cmd, capture_output=True, text=True, check=True)
        metrics_line = res_zig.stdout.strip().split("\n")[-1]
        m = metrics_line.split(",")
        actual_dd, actual_kurt, actual_vol, actual_cascade = (
            float(m[0]),
            float(m[1]),
            float(m[2]),
            float(m[3]),
        )
    except Exception as e:
        return 99999.0

    err_dd = abs((actual_dd - TARGET_DRAWDOWN) / TARGET_DRAWDOWN)
    err_kurt = abs((actual_kurt - TARGET_KURTOSIS) / TARGET_KURTOSIS)
    err_vol = abs((actual_vol - TARGET_VOL_CLUSTERING) / TARGET_VOL_CLUSTERING)
    
    # If target cascade depth is 0, just use absolute difference, else percentage
    if TARGET_CASCADE_DEPTH == 0:
        err_cascade = abs(actual_cascade)
    else:
        err_cascade = abs((actual_cascade - TARGET_CASCADE_DEPTH) / TARGET_CASCADE_DEPTH)

    return (0.5 * err_dd) + (0.1 * err_kurt) + (0.1 * err_vol) + (0.3 * err_cascade)


def main():
    print("Starting Optuna Bayesian Calibration against actual Physics Engine...")
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=100)

    print("\n--- OPTUNA CALIBRATION COMPLETED ---")
    best_params = study.best_params
    
    with open("data/calibrated_params.json", "w") as f:
        json.dump(best_params, f, indent=4)
        
    print(f"Best Loss: {study.best_value:.4f}")
    print("Best Params:", best_params)

if __name__ == "__main__":
    main()
