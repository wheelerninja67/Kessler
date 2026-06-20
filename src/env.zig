const std = @import("std");
const math = std.math;

// ──────────────────────────── Constants ────────────────────────────
pub const N_FEATURES: usize = 9;
pub const WINDOW_SIZE: usize = 100;
pub const SL_POINTS: f32 = 50.0;
pub const TP_POINTS: f32 = 100.0;
pub const SPREAD: f32 = 0.5;
pub const COMMISSION: f32 = 5.0;
pub const STARTING_BALANCE: f32 = 100000.0;
pub const POINT_VALUE: f32 = 20.0; // NAS100 $20 per point per lot
pub const BARS_PER_DAY: u32 = 78; // 6.5h * 12 five-min bars/h

// ──────────────────────────── Bar ──────────────────────────────────
pub const Bar = struct {
    open: f32,
    high: f32,
    low: f32,
    close: f32,
    volume: f32,
};

// ──────────────────────────── Env ──────────────────────────────────
pub const Env = struct {
    bars: []Bar,
    n_bars: usize,
    current_bar: usize,
    in_trade: bool,
    trade_direction: i8, // 1=long, -1=short, 0=none
    entry_price: f32,
    sl_price: f32,
    tp_price: f32,
    episode_pnl: f32,
    total_trades: u32,
    winning_trades: u32,
    balance: f32,
    peak_balance: f32,
    day_start_balance: f32,
    bars_since_day_start: u32,
    raw_feature_buf: [WINDOW_SIZE]f32,
};

// ──────────────────────────── Init / Reset ─────────────────────────
pub fn envInit(bars: []Bar) Env {
    return Env{
        .bars = bars,
        .n_bars = bars.len,
        .current_bar = WINDOW_SIZE,
        .in_trade = false,
        .trade_direction = 0,
        .entry_price = 0.0,
        .sl_price = 0.0,
        .tp_price = 0.0,
        .episode_pnl = 0.0,
        .total_trades = 0,
        .winning_trades = 0,
        .balance = STARTING_BALANCE,
        .peak_balance = STARTING_BALANCE,
        .day_start_balance = STARTING_BALANCE,
        .bars_since_day_start = 0,
        .raw_feature_buf = [_]f32{0.0} ** WINDOW_SIZE,
    };
}

pub fn envReset(self: *Env) void {
    self.current_bar = WINDOW_SIZE;
    self.in_trade = false;
    self.trade_direction = 0;
    self.entry_price = 0.0;
    self.sl_price = 0.0;
    self.tp_price = 0.0;
    self.episode_pnl = 0.0;
    self.total_trades = 0;
    self.winning_trades = 0;
    self.balance = STARTING_BALANCE;
    self.peak_balance = STARTING_BALANCE;
    self.day_start_balance = STARTING_BALANCE;
    self.bars_since_day_start = 0;
}

// ──────────────────────────── Indicators ───────────────────────────

fn computeEMA(bars: []Bar, end_idx: usize, period: usize) f32 {
    const warmup = period * 3;
    var start: usize = 0;
    if (end_idx >= warmup) {
        start = end_idx - warmup;
    }
    const mult: f32 = 2.0 / (@as(f32, @floatFromInt(period)) + 1.0);

    // Seed EMA with first close in range
    var ema: f32 = bars[start].close;
    var idx: usize = start + 1;
    while (idx <= end_idx) : (idx += 1) {
        ema = bars[idx].close * mult + ema * (1.0 - mult);
    }
    return ema;
}

fn computeRSI(bars: []Bar, end_idx: usize, period: usize) f32 {
    const p = period;
    if (end_idx < p + 1) return 50.0;

    // Initial average gain/loss over first `period` bars
    var avg_gain: f32 = 0.0;
    var avg_loss: f32 = 0.0;
    const first_bar = end_idx - p * 2; // extra warmup
    const start = if (end_idx >= p * 2) first_bar else 1;

    // Seed over [start .. start + period]
    {
        var i: usize = start + 1;
        const seed_end = start + p;
        const actual_end = if (seed_end <= end_idx) seed_end else end_idx;
        while (i <= actual_end) : (i += 1) {
            const diff = bars[i].close - bars[i - 1].close;
            if (diff > 0.0) {
                avg_gain += diff;
            } else {
                avg_loss += -diff;
            }
        }
        const pf: f32 = @floatFromInt(p);
        avg_gain /= pf;
        avg_loss /= pf;
    }

    // Wilder's smoothing for remaining bars
    {
        const seed_end = start + p;
        const smooth_start = if (seed_end <= end_idx) seed_end + 1 else end_idx + 1;
        var i: usize = smooth_start;
        const pf: f32 = @floatFromInt(p);
        while (i <= end_idx) : (i += 1) {
            const diff = bars[i].close - bars[i - 1].close;
            if (diff > 0.0) {
                avg_gain = (avg_gain * (pf - 1.0) + diff) / pf;
                avg_loss = (avg_loss * (pf - 1.0)) / pf;
            } else {
                avg_gain = (avg_gain * (pf - 1.0)) / pf;
                avg_loss = (avg_loss * (pf - 1.0) + (-diff)) / pf;
            }
        }
    }

    if (avg_loss < 1e-10) return 100.0;
    const rs = avg_gain / avg_loss;
    return 100.0 - 100.0 / (1.0 + rs);
}

fn computeATR(bars: []Bar, end_idx: usize, period: usize) f32 {
    const p = period;
    if (end_idx < p + 1) return 1.0;

    const start = if (end_idx >= p * 2) end_idx - p * 2 else 1;
    const pf: f32 = @floatFromInt(p);

    // Seed ATR
    var atr: f32 = 0.0;
    {
        var i: usize = start + 1;
        const seed_end = start + p;
        const actual_end = if (seed_end <= end_idx) seed_end else end_idx;
        while (i <= actual_end) : (i += 1) {
            const tr = trueRange(bars, i);
            atr += tr;
        }
        atr /= pf;
    }

    // Wilder's smoothing
    {
        const seed_end = start + p;
        const smooth_start = if (seed_end <= end_idx) seed_end + 1 else end_idx + 1;
        var i: usize = smooth_start;
        while (i <= end_idx) : (i += 1) {
            const tr = trueRange(bars, i);
            atr = (atr * (pf - 1.0) + tr) / pf;
        }
    }

    return atr;
}

fn trueRange(bars: []Bar, i: usize) f32 {
    const hl = bars[i].high - bars[i].low;
    const hc = @abs(bars[i].high - bars[i - 1].close);
    const lc = @abs(bars[i].low - bars[i - 1].close);
    return @max(hl, @max(hc, lc));
}

fn computeCumulativeDelta(bars: []Bar, end_idx: usize, lookback: usize) f32 {
    var delta: f32 = 0.0;
    const start = if (end_idx + 1 >= lookback) end_idx + 1 - lookback else 0;
    var i: usize = start;
    while (i <= end_idx) : (i += 1) {
        if (bars[i].close >= bars[i].open) {
            delta += bars[i].volume;
        } else {
            delta -= bars[i].volume;
        }
    }
    return delta;
}

// ──────────────────────────── Z-score ──────────────────────────────

fn rollingZscore(value: f32, buf: []const f32, count: usize) f32 {
    if (count == 0) return 0.0;
    var sum: f32 = 0.0;
    var sum_sq: f32 = 0.0;
    for (0..count) |i| {
        sum += buf[i];
        sum_sq += buf[i] * buf[i];
    }
    const n: f32 = @floatFromInt(count);
    const mean = sum / n;
    const variance = sum_sq / n - mean * mean;
    const stdev = @sqrt(@max(variance, 0.0));
    return (value - mean) / (stdev + 1e-8);
}

// ──────────────────────────── Observations ─────────────────────────

pub fn envGetObs(self: *Env, obs: []f32) void {
    const cur = self.current_bar;
    const bars = self.bars;

    // We fill raw_feature_buf for each feature, then Z-score the current value.
    // Window spans [cur - WINDOW_SIZE + 1 .. cur] = 100 bars

    // ---------- F0: Log Return ----------
    {
        var k: usize = 0;
        while (k < WINDOW_SIZE) : (k += 1) {
            const idx = cur - WINDOW_SIZE + 1 + k;
            if (idx >= 1) {
                self.raw_feature_buf[k] = @log(bars[idx].close / bars[idx - 1].close);
            } else {
                self.raw_feature_buf[k] = 0.0;
            }
        }
        const current_val = self.raw_feature_buf[WINDOW_SIZE - 1];
        obs[0] = rollingZscore(current_val, &self.raw_feature_buf, WINDOW_SIZE);
    }

    // ---------- F1: HL Range ----------
    {
        var k: usize = 0;
        while (k < WINDOW_SIZE) : (k += 1) {
            const idx = cur - WINDOW_SIZE + 1 + k;
            obs[1] = 0.0; // placeholder
            self.raw_feature_buf[k] = (bars[idx].high - bars[idx].low) / bars[idx].close;
        }
        const current_val = self.raw_feature_buf[WINDOW_SIZE - 1];
        obs[1] = rollingZscore(current_val, &self.raw_feature_buf, WINDOW_SIZE);
    }

    // ---------- F2: Close Position ----------
    {
        var k: usize = 0;
        while (k < WINDOW_SIZE) : (k += 1) {
            const idx = cur - WINDOW_SIZE + 1 + k;
            const hl = bars[idx].high - bars[idx].low + 1e-8;
            self.raw_feature_buf[k] = (bars[idx].close - bars[idx].low) / hl;
        }
        const current_val = self.raw_feature_buf[WINDOW_SIZE - 1];
        obs[2] = rollingZscore(current_val, &self.raw_feature_buf, WINDOW_SIZE);
    }

    // ---------- F3: Volume Ratio ----------
    {
        var k: usize = 0;
        while (k < WINDOW_SIZE) : (k += 1) {
            const idx = cur - WINDOW_SIZE + 1 + k;
            // Mean of last 20 bars' volume relative to idx
            var vol_sum: f32 = 0.0;
            var vol_count: f32 = 0.0;
            const vol_start = if (idx >= 20) idx - 19 else 0;
            var vi: usize = vol_start;
            while (vi <= idx) : (vi += 1) {
                vol_sum += bars[vi].volume;
                vol_count += 1.0;
            }
            const mean_vol = vol_sum / (vol_count + 1e-8);
            self.raw_feature_buf[k] = bars[idx].volume / (mean_vol + 1e-8);
        }
        const current_val = self.raw_feature_buf[WINDOW_SIZE - 1];
        obs[3] = rollingZscore(current_val, &self.raw_feature_buf, WINDOW_SIZE);
    }

    // ---------- F4: EMA Ratio ----------
    {
        var k: usize = 0;
        while (k < WINDOW_SIZE) : (k += 1) {
            const idx = cur - WINDOW_SIZE + 1 + k;
            const ema9 = computeEMA(bars, idx, 9);
            const ema21 = computeEMA(bars, idx, 21);
            self.raw_feature_buf[k] = ema9 / ema21 - 1.0;
        }
        const current_val = self.raw_feature_buf[WINDOW_SIZE - 1];
        obs[4] = rollingZscore(current_val, &self.raw_feature_buf, WINDOW_SIZE);
    }

    // ---------- F5: RSI ----------
    {
        var k: usize = 0;
        while (k < WINDOW_SIZE) : (k += 1) {
            const idx = cur - WINDOW_SIZE + 1 + k;
            self.raw_feature_buf[k] = computeRSI(bars, idx, 14) / 100.0;
        }
        const current_val = self.raw_feature_buf[WINDOW_SIZE - 1];
        obs[5] = rollingZscore(current_val, &self.raw_feature_buf, WINDOW_SIZE);
    }

    // ---------- F6: ATR Ratio ----------
    {
        var k: usize = 0;
        while (k < WINDOW_SIZE) : (k += 1) {
            const idx = cur - WINDOW_SIZE + 1 + k;
            self.raw_feature_buf[k] = computeATR(bars, idx, 14) / bars[idx].close;
        }
        const current_val = self.raw_feature_buf[WINDOW_SIZE - 1];
        obs[6] = rollingZscore(current_val, &self.raw_feature_buf, WINDOW_SIZE);
    }

    // ---------- F7: OC Ratio ----------
    {
        var k: usize = 0;
        while (k < WINDOW_SIZE) : (k += 1) {
            const idx = cur - WINDOW_SIZE + 1 + k;
            const hl = bars[idx].high - bars[idx].low + 1e-8;
            self.raw_feature_buf[k] = (bars[idx].close - bars[idx].open) / hl;
        }
        const current_val = self.raw_feature_buf[WINDOW_SIZE - 1];
        obs[7] = rollingZscore(current_val, &self.raw_feature_buf, WINDOW_SIZE);
    }

    // ---------- F8: Cumulative Delta ----------
    {
        var k: usize = 0;
        while (k < WINDOW_SIZE) : (k += 1) {
            const idx = cur - WINDOW_SIZE + 1 + k;
            self.raw_feature_buf[k] = computeCumulativeDelta(bars, idx, 10);
        }
        const current_val = self.raw_feature_buf[WINDOW_SIZE - 1];
        obs[8] = rollingZscore(current_val, &self.raw_feature_buf, WINDOW_SIZE);
    }
}

// ──────────────────────────── Step ─────────────────────────────────

pub fn envStep(self: *Env, action: u8, obs: []f32, reward: *f32, done: *bool) void {
    reward.* = 0.0;
    done.* = false;

    // Day rollover
    if (self.bars_since_day_start >= BARS_PER_DAY) {
        self.day_start_balance = self.balance;
        self.bars_since_day_start = 0;
    }

    // ── Open new trade ──
    if (!self.in_trade) {
        if (action == 0) {
            // LONG: buy at ask
            self.entry_price = self.bars[self.current_bar].close + SPREAD;
            self.sl_price = self.entry_price - SL_POINTS;
            self.tp_price = self.entry_price + TP_POINTS;
            self.in_trade = true;
            self.trade_direction = 1;
            self.balance -= COMMISSION;
        } else if (action == 1) {
            // SHORT: sell at bid
            self.entry_price = self.bars[self.current_bar].close - SPREAD;
            self.sl_price = self.entry_price + SL_POINTS;
            self.tp_price = self.entry_price - TP_POINTS;
            self.in_trade = true;
            self.trade_direction = -1;
            self.balance -= COMMISSION;
        }
    }

    // ── Check SL / TP on current bar for existing trade ──
    if (self.in_trade) {
        const bar = self.bars[self.current_bar];

        var sl_hit = false;
        var tp_hit = false;

        if (self.trade_direction == 1) {
            // LONG
            if (bar.low <= self.sl_price) sl_hit = true;
            if (bar.high >= self.tp_price) tp_hit = true;
        } else {
            // SHORT
            if (bar.high >= self.sl_price) sl_hit = true;
            if (bar.low <= self.tp_price) tp_hit = true;
        }

        // If both hit, assume SL first (conservative)
        if (sl_hit) {
            reward.* = -0.15;
            self.balance -= SL_POINTS * POINT_VALUE;
            self.balance -= COMMISSION;
            self.in_trade = false;
            self.trade_direction = 0;
            self.total_trades += 1;
        } else if (tp_hit) {
            reward.* = 0.30;
            self.balance += TP_POINTS * POINT_VALUE;
            self.balance -= COMMISSION;
            self.in_trade = false;
            self.trade_direction = 0;
            self.total_trades += 1;
            self.winning_trades += 1;
        }
    }

    // ── Drawdown protection ──
    if (self.in_trade) {
        const peak_dd = if (self.peak_balance > 0.0)
            (self.peak_balance - self.balance) / self.peak_balance
        else
            0.0;

        const day_dd = if (self.day_start_balance > 0.0)
            (self.day_start_balance - self.balance) / self.day_start_balance
        else
            0.0;

        if (peak_dd > 0.05 or day_dd > 0.03) {
            // Force close
            reward.* = -1.0;
            self.in_trade = false;
            self.trade_direction = 0;
        }
    }

    // Update peak balance
    if (self.balance > self.peak_balance) {
        self.peak_balance = self.balance;
    }

    // Advance
    self.current_bar += 1;
    self.bars_since_day_start += 1;

    if (self.current_bar >= self.n_bars - 1) {
        done.* = true;
    }

    // Fill observation
    if (!done.*) {
        envGetObs(self, obs);
    } else {
        for (0..N_FEATURES) |i| {
            obs[i] = 0.0;
        }
    }
}

// ──────────────────────────── Winrate ──────────────────────────────

pub fn envWinrate(self: *Env) f32 {
    if (self.total_trades == 0) return 0.0;
    return @as(f32, @floatFromInt(self.winning_trades)) / @as(f32, @floatFromInt(self.total_trades));
}
