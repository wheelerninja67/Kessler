# Dependencies: pip install pandas matplotlib seaborn numpy
import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Global styling config for terminal-like dark theme
BG_COLOR = "#0d1117"
TEXT_COLOR = "#c9d1d9"
plt.rcParams.update(
    {
        "figure.facecolor": BG_COLOR,
        "axes.facecolor": BG_COLOR,
        "axes.edgecolor": "#30363d",
        "axes.labelcolor": TEXT_COLOR,
        "text.color": TEXT_COLOR,
        "xtick.color": TEXT_COLOR,
        "ytick.color": TEXT_COLOR,
        "grid.color": "#21262d",
        "legend.facecolor": BG_COLOR,
        "legend.edgecolor": "#30363d",
        "font.family": "sans-serif",
    }
)


def remove_spines(ax):
    """Removes top and right spines for a clean aesthetic."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def main():
    data_dir = os.path.join("src", "data")
    prices_path = os.path.join(data_dir, "prices.csv")
    returns_path = os.path.join(data_dir, "returns.csv")
    meta_path = os.path.join(data_dir, "metadata.json")

    if not os.path.exists(prices_path):
        print(
            f"[!] Error: {prices_path} not found. Ensure you are in the project root."
        )
        sys.exit(1)

    print("[*] Loading metadata and datasets...")
    with open(meta_path, "r") as f:
        meta = json.load(f)

    tickers = meta.get("tickers", [])

    # ---------------------------------------------------------
    # BULLETPROOF DATA LOADING
    # ---------------------------------------------------------
    def load_and_clean(filepath):
        df = pd.read_csv(filepath, low_memory=False)

        # The first column contains the dates but is incorrectly named 'Price' in the CSV
        first_col = df.columns[0]
        df.rename(columns={first_col: "Date"}, inplace=True)

        # Filter out the garbage metadata rows that got mixed into the data
        df = df[~df["Date"].astype(str).isin(["Ticker", "Date", "Price"])]

        # Convert the Date column to actual datetime objects and set as index
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df.dropna(subset=["Date"], inplace=True)
        df.set_index("Date", inplace=True)

        # Force all columns to numeric. Turns any remaining rogue strings into NaN.
        df = df.apply(pd.to_numeric, errors="coerce")

        # Drop columns that are completely empty/NaN
        df.dropna(axis=1, how="all", inplace=True)

        # Forward fill gaps, then fill any remaining with 0
        df.ffill(inplace=True)
        df.fillna(0, inplace=True)

        return df

    prices = load_and_clean(prices_path)
    returns = load_and_clean(returns_path)

    # ---------------------------------------------------------
    # CHART 1: PRICE HISTORY
    # ---------------------------------------------------------
    print("[*] Generating price_history.png...")
    fig, ax = plt.subplots(figsize=(12, 6))

    final_prices = prices.iloc[-1].sort_values(ascending=False)
    top_5 = final_prices.head(5).index.tolist()

    for col in prices.columns:
        if col == "^GSPC":
            continue
        alpha = 0.8 if col in top_5 else 0.2
        lw = 1.5 if col in top_5 else 0.8
        color = None if col in top_5 else "#484f58"

        label = col if col in top_5 else None
        ax.plot(
            prices.index,
            prices[col],
            alpha=alpha,
            linewidth=lw,
            color=color,
            label=label,
        )

    if "^GSPC" in prices.columns:
        ax.plot(
            prices.index,
            prices["^GSPC"],
            color="white",
            linewidth=2.5,
            label="^GSPC (S&P 500)",
        )
    else:
        print("[!] Warning: ^GSPC not found in tickers.")

    ax.set_yscale("log")
    ax.set_title("Historical Asset Prices (Log Scale)", pad=15, fontweight="bold")
    ax.set_ylabel("Price")
    ax.legend(loc="upper left", frameon=True)
    remove_spines(ax)
    plt.tight_layout()
    plt.savefig(
        os.path.join(data_dir, "price_history.png"), dpi=300, bbox_inches="tight"
    )
    plt.close()

    # ---------------------------------------------------------
    # CHART 2: RETURNS HEATMAP
    # ---------------------------------------------------------
    print("[*] Generating returns_heatmap.png...")
    # Limit to first 12 assets to maintain readability
    heat_cols = prices.columns[:12]
    corr_matrix = returns[heat_cols].corr()

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        corr_matrix,
        annot=True,
        fmt=".2f",
        cmap="coolwarm",
        center=0,
        cbar_kws={"label": "Correlation Coefficient"},
        ax=ax,
        annot_kws={"size": 9},
        linecolor=BG_COLOR,
        linewidths=0.5,
    )

    ax.set_title("Asset Cross-Correlation (Top 12)", pad=15, fontweight="bold")
    plt.tight_layout()
    plt.savefig(
        os.path.join(data_dir, "returns_heatmap.png"), dpi=300, bbox_inches="tight"
    )
    plt.close()

    # ---------------------------------------------------------
    # CHART 3: VOLATILITY TIMELINE
    # ---------------------------------------------------------
    print("[*] Generating volatility_timeline.png...")
    if "^GSPC" in returns.columns and "^VIX" in prices.columns:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

        gspc_vol = returns["^GSPC"].rolling(window=20).std() * np.sqrt(252) * 100

        ax1.plot(gspc_vol.index, gspc_vol, color="#58a6ff", linewidth=1.5)
        ax1.set_title("^GSPC 20-Day Realized Volatility (%)", fontweight="bold")
        ax1.set_ylabel("Realized Vol (%)")
        remove_spines(ax1)

        ax2.plot(prices.index, prices["^VIX"], color="#ff7b72", linewidth=1.5)
        ax2.set_title("^VIX Implied Volatility Index", fontweight="bold")
        ax2.set_ylabel("VIX Level")
        ax2.set_xlabel("Date")
        remove_spines(ax2)

        # Highlight COVID Crash (March 2020) if it exists in the data
        try:
            covid_date = pd.to_datetime("2020-03-16")
            if len(prices) > 0 and prices.index[0] < covid_date < prices.index[-1]:
                for axis in [ax1, ax2]:
                    axis.axvline(
                        covid_date,
                        color=TEXT_COLOR,
                        linestyle="--",
                        alpha=0.5,
                        linewidth=1,
                    )
                    axis.text(
                        covid_date,
                        axis.get_ylim()[1] * 0.9,
                        " COVID-19\n Crash",
                        color=TEXT_COLOR,
                        fontsize=9,
                        verticalalignment="top",
                    )
        except Exception:
            pass  # Fail gracefully if dates aren't perfectly aligned

        plt.tight_layout()
        plt.savefig(
            os.path.join(data_dir, "volatility_timeline.png"),
            dpi=300,
            bbox_inches="tight",
        )
        plt.close()
    else:
        print("[!] Warning: ^GSPC or ^VIX missing. Skipping volatility timeline.")

    print("[SUCCESS] All visualizations generated in src/data/ directory.")


if __name__ == "__main__":
    main()
