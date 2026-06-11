#include <stdio.h>
#include <stdlib.h>
#include <omp.h>
#include <math.h>

typedef struct {
    float open;
    float high;
    float low;
    float close;
    float ema_50;
    float ema_100;
    float atr_14;
    float avg_atr_daily;
} Candle;

int main() {
    FILE *f = fopen("/home/mid/Projects/kessler/data/nasdaq_physics.bin", "rb");
    if (!f) {
        printf("Failed to open nasdaq_physics.bin\n");
        return 1;
    }

    fseek(f, 0, SEEK_END);
    long file_size = ftell(f);
    rewind(f);

    int num_candles = file_size / sizeof(Candle);
    Candle *candles = malloc(file_size);
    fread(candles, sizeof(Candle), num_candles, f);
    fclose(f);

    printf("[*] Loaded %d Nasdaq NQ=F physics state vectors into C Engine.\n", num_candles);
    printf("[*] Engaging MULTI-THREADED OpenMP Brute Force over 1.7 Million Wyckoff permutations...\n");

    float global_best_balance = 0.0;
    float b_sl = 0, b_tp = 0, b_gap = 0, b_stoic = 0;
    int b_win = 0;

    int sl_steps = 21; // 1.5 to 3.5 (0.1)
    int tp_steps = 41; // 2.5 to 6.5 (0.1)
    int gap_steps = 31; // 0.001 to 0.004 (0.0001)
    int win_steps = 13; // 8 to 20 (1)
    int stoic_steps = 5; // 0.4 to 0.8 (0.1)

    #pragma omp parallel
    {
        float local_best_balance = 0.0;
        float l_sl = 0, l_tp = 0, l_gap = 0, l_stoic = 0;
        int l_win = 0;

        #pragma omp for collapse(4) nowait
        for (int i = 0; i < sl_steps; i++) {
            for (int j = 0; j < tp_steps; j++) {
                for (int k = 0; k < gap_steps; k++) {
                    for (int w = 0; w < win_steps; w++) {
                        for (int s = 0; s < stoic_steps; s++) {
                            
                            float sl_mult = 1.5 + (i * 0.1);
                            float tp_mult = 2.5 + (j * 0.1);
                            float gap_thresh = 0.001 + (k * 0.0001);
                            int window = 8 + (w * 1);
                            float stoic_mult = 0.4 + (s * 0.1);
                            
                            // Prop Firm Account Setup
                            float balance = 10000.0;
                            float risk_pct = 2.0; 
                            float max_drawdown = 10000.0 * 0.10; // 10% max trailing drawdown
                            float peak_balance = 10000.0;

                            int in_trade = 0;
                            int dir = 0;
                            float entry_price = 0;
                            float position_size = 0;
                            float sl_price = 0;
                            float tp_price = 0;

                            for (int c = window; c < num_candles; c++) {
                                if (balance < (peak_balance - max_drawdown) || balance <= 0) break; // Blown account
                                if (balance > peak_balance) peak_balance = balance;

                                float close = candles[c].close;

                                if (in_trade) {
                                    int hit_sl = 0, hit_tp = 0;
                                    float high = candles[c].high;
                                    float low = candles[c].low;

                                    if (dir == 1) { // LONG
                                        if (low <= sl_price) hit_sl = 1;
                                        else if (high >= tp_price) hit_tp = 1;
                                    } else { // SHORT
                                        if (high >= sl_price) hit_sl = 1;
                                        else if (low <= tp_price) hit_tp = 1;
                                    }

                                    if (hit_sl) {
                                        float loss_amount = balance * (risk_pct / 100.0);
                                        balance -= loss_amount;
                                        in_trade = 0;
                                        continue;
                                    }

                                    if (hit_tp) {
                                        float risk_amount = balance * (risk_pct / 100.0);
                                        float rr = (tp_mult / sl_mult);
                                        float profit = risk_amount * rr;
                                        balance += profit;
                                        in_trade = 0;
                                    }
                                } else {
                                    // STOIC PATIENCE FILTER
                                    if (candles[c].atr_14 < (candles[c].avg_atr_daily * stoic_mult)) continue;

                                    // EMA TREND FILTER
                                    int trend = 0; // 0=FLAT, 1=BULL, 2=BEAR
                                    float gap = fabs(candles[c].ema_50 - candles[c].ema_100) / candles[c].ema_100;
                                    if (gap > gap_thresh) {
                                        if (candles[c].ema_50 > candles[c].ema_100) trend = 1;
                                        else trend = 2;
                                    }

                                    if (trend == 0) continue;

                                    // CALCULATE HIGHEST/LOWEST
                                    float highest = 0, lowest = 9999999.0;
                                    for (int prev = c - window; prev < c; prev++) {
                                        if (candles[prev].high > highest) highest = candles[prev].high;
                                        if (candles[prev].low < lowest) lowest = candles[prev].low;
                                    }

                                    float prev_close = candles[c-1].close;

                                    if (trend == 1 && close > highest) {
                                        in_trade = 1; dir = 1;
                                        entry_price = close;
                                        sl_price = entry_price - (candles[c].atr_14 * sl_mult);
                                        tp_price = entry_price + (candles[c].atr_14 * tp_mult);
                                    } else if (trend == 2 && close < lowest) {
                                        in_trade = 1; dir = 2;
                                        entry_price = close;
                                        sl_price = entry_price + (candles[c].atr_14 * sl_mult);
                                        tp_price = entry_price - (candles[c].atr_14 * tp_mult);
                                    }
                                }
                            }

                            if (balance > local_best_balance) {
                                local_best_balance = balance;
                                l_sl = sl_mult; l_tp = tp_mult; l_gap = gap_thresh; l_win = window; l_stoic = stoic_mult;
                            }
                        }
                    }
                }
            }
        }

        #pragma omp critical
        {
            if (local_best_balance > global_best_balance) {
                global_best_balance = local_best_balance;
                b_sl = l_sl; b_tp = l_tp; b_gap = l_gap; b_win = l_win; b_stoic = l_stoic;
            }
        }
    }

    printf("\n=================================================================\n");
    printf("  [*] MAXIMUM PROP-FIRM WYCKOFF COMPOUNDING FOUND (C OPENMP)\n");
    printf("=================================================================\n");
    printf("Starting Balance: $10,000.00\n");
    printf("Final Balance:    $%.2f\n", global_best_balance);
    printf("ATR Stop-Loss:    %.1fx\n", b_sl);
    printf("ATR Take-Profit:  %.1fx\n", b_tp);
    printf("EMA Gap Thresh:   %.4f\n", b_gap);
    printf("Breakout Window:  %d Candles\n", b_win);
    printf("Stoic Reject:     %.1fx ATR\n", b_stoic);
    printf("=================================================================\n");
    return 0;
}
