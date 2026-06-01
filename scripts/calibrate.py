import json
import os
import subprocess

import numpy as np
import pandas as pd
import xgboost as xgb
from skopt import gp_minimize
from skopt.space import Integer, Real

TARGET_DRAWDOWN = -56.8
TARGET_KURTOSIS = 3.0
TARGET_VOL_CLUSTERING = 0.15
TARGET_CASCADE_DEPTH = 3.0


def train_surrogate_models(df):
    features = [
        "leverage_cap",
        "base_depth",
        "decay_rate",
        "freeze_threshold",
        "freeze_duration",
        "cb_sensitivity",
        "value_buy_threshold",
        "cash_fragility",
        "market_maker_resilience",
    ]
    X = df[features]
    models = {}
    targets = ["max_drawdown", "excess_kurtosis", "vol_clustering", "cascade_depth"]

    for target in targets:
        y = df[target]
        model = xgb.XGBRegressor(
            n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42
        )
        model.fit(X, y)
        models[target] = model

    return models, features


def main():
    df = pd.read_csv("data/sweep_results.csv")
    models, features = train_surrogate_models(df)

    def objective(params):
        X_pred = pd.DataFrame([params], columns=features)

        pred_dd = models["max_drawdown"].predict(X_pred)[0]
        pred_kurt = models["excess_kurtosis"].predict(X_pred)[0]
        pred_vol = models["vol_clustering"].predict(X_pred)[0]
        pred_cascade = models["cascade_depth"].predict(X_pred)[0]

        err_dd = abs((pred_dd - TARGET_DRAWDOWN) / TARGET_DRAWDOWN)
        err_kurt = abs((pred_kurt - TARGET_KURTOSIS) / TARGET_KURTOSIS)
        err_vol = abs((pred_vol - TARGET_VOL_CLUSTERING) / TARGET_VOL_CLUSTERING)
        err_cascade = abs((pred_cascade - TARGET_CASCADE_DEPTH) / TARGET_CASCADE_DEPTH)

        # INCREASED CASCADE PENALTY: 30% weight for contagion, 50% for DD, 10% each for statistics
        return (0.5 * err_dd) + (0.1 * err_kurt) + (0.1 * err_vol) + (0.3 * err_cascade)

    # Expanded search space to match the sweep
    space = [
        Real(10.0, 75.0, name="leverage_cap"),
        Integer(200, 3000, name="base_depth"),
        Real(0.01, 0.1, name="decay_rate"),
        Real(0.3, 0.95, name="freeze_threshold"),
        Integer(1, 8, name="freeze_duration"),
        Real(0.3, 2.5, name="cb_sensitivity"),
        Real(0.05, 0.40, name="value_buy_threshold"),
        Real(0.01, 0.15, name="cash_fragility"),
        Real(0.01, 0.20, name="market_maker_resilience"),
    ]

    print("Running Bayesian Optimization via gp_minimize...")
    res = gp_minimize(
        objective,
        space,
        n_calls=200,
        n_initial_points=40,
        acq_func="LCB",
        kappa=3.0,
        random_state=42,
    )

    best_params = {
        dim.name: (float(val) if isinstance(dim, Real) else int(val))
        for dim, val in zip(space, res.x)
    }

    with open("data/calibrated_params.json", "w") as f:
        json.dump(best_params, f, indent=4)

    print("\n--- TOP 5 CONFIGURATIONS FOUND ---")
    sorted_indices = np.argsort(res.func_vals)
    for i in range(min(5, len(sorted_indices))):
        idx = sorted_indices[i]
        val = res.func_vals[idx]
        print(f"{i + 1}. Dist: {val:.4f} | Param set {idx}")

    exe_path = "zig-out/bin/kessler.exe" if os.name == "nt" else "./zig-out/bin/kessler"
    actual_dd, actual_kurt, actual_vol, actual_cascade = (
        float("nan"),
        float("nan"),
        float("nan"),
        float("nan"),
    )

    if os.path.exists(exe_path):
        cmd = [
            exe_path,
            "--leverage-cap",
            str(best_params["leverage_cap"]),
            "--base-depth",
            str(best_params["base_depth"]),
            "--decay-rate",
            str(best_params["decay_rate"]),
            "--freeze-threshold",
            str(best_params["freeze_threshold"]),
            "--freeze-duration",
            str(best_params["freeze_duration"]),
            "--cb-sensitivity",
            str(best_params["cb_sensitivity"]),
            "--value-buy-threshold",
            str(best_params["value_buy_threshold"]),
            "--cash-fragility",
            str(best_params["cash_fragility"]),
            "--market-maker-resilience",
            str(best_params["market_maker_resilience"]),
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
            print(f"Warning: Could not run Zig binary to get actual physics: {e}")

    X_best = pd.DataFrame([res.x], columns=features)

    print("\n--- CALIBRATION VALIDATION (Surrogate vs Actual) ---")
    print(
        f"Drawdown:        Target {TARGET_DRAWDOWN}% | Pred {models['max_drawdown'].predict(X_best)[0]:>6.2f}% | Actual {actual_dd:>6.2f}%"
    )
    print(
        f"Excess Kurtosis: Target {TARGET_KURTOSIS}    | Pred {models['excess_kurtosis'].predict(X_best)[0]:>6.2f}  | Actual {actual_kurt:>6.2f}"
    )
    print(
        f"Vol Clustering:  Target {TARGET_VOL_CLUSTERING}   | Pred {models['vol_clustering'].predict(X_best)[0]:>6.3f}  | Actual {actual_vol:>6.3f}"
    )
    print(
        f"Cascade Depth:   Target {TARGET_CASCADE_DEPTH}    | Pred {models['cascade_depth'].predict(X_best)[0]:>6.1f}   | Actual {actual_cascade:>6.1f}"
    )

    if actual_cascade == 0.0 or actual_kurt < 0.0:
        print("\n[!] WARNING: CALIBRATION UNRELIABLE [!]")
        print(
            "The surrogate model overfit. Actual physics simulation shows no agent defaults (cascade = 0.0) or invalid kurtosis."
        )
        print(
            "Recommendation: Check that cash_fragility sweep ranges are low enough to force defaults."
        )


if __name__ == "__main__":
    main()
