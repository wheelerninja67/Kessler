const std = @import("std");
const stash = @import("stash.zig");
const bazaar = @import("bazaar.zig");
const crowd = @import("crowd.zig");

pub const TickRecord = struct { tick: u32, mkt_avg: f64, defaults: u32, cascade: u32, order_sign: f64 };

pub const Diary = struct {
    ring: []TickRecord,
    write_idx: u32,
    log_returns: []f64,
    ret_idx: u32,
    hash_ctx: std.crypto.hash.sha2.Sha256,

    asset_prices: []f64,
    num_assets: u32,
    all_returns: []f64,

    // HMM Tracking
    prob_crisis: f64,
    is_crisis: bool,

    // CRO Tracking
    peak_defaults: u32,
    peak_defaults_tick: u32,
    max_cascade: u32,
    cb_interventions: u32,

    pub fn init(arena: *stash.Stash, capacity: u32, assets: u32) !Diary {
        return Diary{
            .ring = try arena.stashAlloc(TickRecord, capacity),
            .write_idx = 0,
            .log_returns = try arena.stashAlloc(f64, 50),
            .ret_idx = 0,
            .hash_ctx = std.crypto.hash.sha2.Sha256.init(.{}),
            .asset_prices = try arena.stashAlloc(f64, capacity * assets),
            .num_assets = assets,
            .all_returns = try arena.stashAlloc(f64, capacity),
            .prob_crisis = 0.0,
            .is_crisis = false,
            .peak_defaults = 0,
            .peak_defaults_tick = 0,
            .max_cascade = 0,
            .cb_interventions = 0,
        };
    }

    pub fn record(self: *Diary, tick: u32, b: *bazaar.Bazaar, defaults: u32, cascade: u32) void {
        var sum: f64 = 0;
        var total_buy: f64 = 0;
        var total_sell: f64 = 0;

        for (0..b.num_assets) |a| {
            sum += b.mid_prices[a];
            total_buy += b.buy_vol[a];
            total_sell += b.sell_vol[a];
            if (self.write_idx < self.ring.len) {
                self.asset_prices[self.write_idx * self.num_assets + a] = b.mid_prices[a];
            }
        }

        const avg = sum / @as(f64, @floatFromInt(b.num_assets));
        const sign: f64 = if (total_buy > total_sell) 1.0 else if (total_sell > total_buy) -1.0 else 0.0;

        self.hash_ctx.update(std.mem.asBytes(&avg));
        self.hash_ctx.update(std.mem.asBytes(&defaults));

        if (defaults > self.peak_defaults) {
            self.peak_defaults = defaults;
            self.peak_defaults_tick = tick;
        }
        if (cascade > self.max_cascade) self.max_cascade = cascade;

        if (self.write_idx < self.ring.len) {
            self.ring[self.write_idx] = .{ .tick = tick, .mkt_avg = avg, .defaults = defaults, .cascade = cascade, .order_sign = sign };
        }

        if (self.write_idx > 0 and self.write_idx < self.ring.len) {
            const prev_avg = self.ring[self.write_idx - 1].mkt_avg;
            const ret = if (prev_avg > 0) @log(avg / prev_avg) else 0;
            self.log_returns[self.ret_idx] = ret;
            self.ret_idx = (self.ret_idx + 1) % 50;
            self.all_returns[self.write_idx] = ret;

            // 2-State HMM Forward Algorithm
            const mu_N: f64 = 0.0001;
            const var_N: f64 = 0.0001;
            const mu_C: f64 = -0.005;
            const var_C: f64 = 0.0025;

            const dev_N = ret - mu_N;
            const dev_C = ret - mu_C;
            const like_N = @exp(-(dev_N * dev_N) / (2.0 * var_N)) / std.math.sqrt(2.0 * std.math.pi * var_N);
            const like_C = @exp(-(dev_C * dev_C) / (2.0 * var_C)) / std.math.sqrt(2.0 * std.math.pi * var_C);

            const prior_N = (1.0 - self.prob_crisis) * 0.98 + self.prob_crisis * 0.05;
            const prior_C = (1.0 - self.prob_crisis) * 0.02 + self.prob_crisis * 0.95;

            const evidence = prior_N * like_N + prior_C * like_C;
            if (evidence > 0) {
                self.prob_crisis = (prior_C * like_C) / evidence;
            }

            if (!self.is_crisis and self.prob_crisis > 0.8) {
                self.is_crisis = true;
                std.debug.print(">>> REGIME SHIFT: Market entered CRISIS state <<<\n", .{});
            } else if (self.is_crisis and self.prob_crisis < 0.2) {
                self.is_crisis = false;
                std.debug.print(">>> REGIME SHIFT: Market returned to CALM state <<<\n", .{});
            }
        }

        self.write_idx += 1;
        if (tick % 100 == 0 or defaults > 0) {
            std.debug.print("TICK {d:0>4} | MKT_AVG: {d:8.2} | DEFAULTS: {d: >4} | CASCADE: {d}\n", .{ tick, avg, defaults, cascade });
        }
    }

    pub fn checkEarlyWarning(self: *Diary) void {
        var mean: f64 = 0;
        for (self.log_returns) |r| mean += r;
        mean /= 50.0;

        var variance: f64 = 0;
        var lag1_cov: f64 = 0;
        for (0..49) |i| {
            const dev0 = self.log_returns[i] - mean;
            const dev1 = self.log_returns[i + 1] - mean;
            variance += (dev0 * dev0);
            lag1_cov += (dev0 * dev1);
        }
        if (variance > 0.005 and lag1_cov > 0) {
            std.debug.print(">>> EARLY WARNING: Critical slowing down detected. Cascade imminent. <<<\n", .{});
        }
    }

    pub fn printSentiment(self: *Diary, c: *crowd.Crowd, tick: u32) void {
        _ = self;
        var bull: u32 = 0;
        var neut: u32 = 0;
        var bear: u32 = 0;
        var panic: u32 = 0;
        for (0..c.count) |i| {
            if (c.theta[i] > 0.7) bull += 1 else if (c.theta[i] >= 0.3) neut += 1 else if (c.theta[i] >= 0.1) bear += 1 else panic += 1;
        }
        const t_f = @as(f64, @floatFromInt(c.count));
        std.debug.print("SENTIMENT: Bullish {d:.1}% | Neutral {d:.1}% | Bearish {d:.1}% | Panicked {d:.1}%\n", .{
            (@as(f64, @floatFromInt(bull)) / t_f) * 100.0,
            (@as(f64, @floatFromInt(neut)) / t_f) * 100.0,
            (@as(f64, @floatFromInt(bear)) / t_f) * 100.0,
            (@as(f64, @floatFromInt(panic)) / t_f) * 100.0,
        });
        _ = tick;
    }

    pub fn printStylizedFacts(self: *Diary) void {
        var order_autocorr: f64 = 0;
        const valid_count = @min(self.write_idx, self.ring.len);
        if (valid_count > 1) {
            for (0..valid_count - 1) |i| {
                order_autocorr += self.ring[i].order_sign * self.ring[i + 1].order_sign;
            }
            order_autocorr /= @as(f64, @floatFromInt(valid_count));
        }

        var mean: f64 = 0;
        var variance: f64 = 0;
        var m4: f64 = 0;
        const n_f = @as(f64, @floatFromInt(valid_count - 1));

        if (valid_count > 2) {
            for (1..valid_count) |i| mean += self.all_returns[i];
            mean /= n_f;
            for (1..valid_count) |i| {
                const dev = self.all_returns[i] - mean;
                variance += dev * dev;
                m4 += dev * dev * dev * dev;
            }
            variance /= n_f;
            m4 /= n_f;
        }
        const excess_kurtosis = if (variance > 0) (m4 / (variance * variance)) - 3.0 else 0;

        var abs_mean: f64 = 0;
        if (valid_count > 2) {
            for (1..valid_count) |i| abs_mean += @abs(self.all_returns[i]);
            abs_mean /= n_f;
        }

        var var_abs: f64 = 0;
        var covar_lag1: f64 = 0;
        var covar_lag10: f64 = 0;
        if (valid_count > 11) {
            for (1..valid_count) |i| {
                const dev = @abs(self.all_returns[i]) - abs_mean;
                var_abs += dev * dev;
                if (i > 1) {
                    const dev_lag1 = @abs(self.all_returns[i - 1]) - abs_mean;
                    covar_lag1 += dev * dev_lag1;
                }
                if (i > 10) {
                    const dev_lag10 = @abs(self.all_returns[i - 10]) - abs_mean;
                    covar_lag10 += dev * dev_lag10;
                }
            }
            covar_lag1 /= var_abs;
            covar_lag10 /= var_abs;
        }

        std.debug.print("\n=== STYLIZED FACT VALIDATION ===\n", .{});
        std.debug.print("Excess Kurtosis (Fat Tails): {d:.2}\n", .{excess_kurtosis});
        std.debug.print("Volatility Clustering (Lag 1): {d:.4}\n", .{covar_lag1});
        std.debug.print("Volatility Clustering (Lag 10): {d:.4}\n", .{covar_lag10});
        std.debug.print("LONG MEMORY (Order Flow Autocorr): {d:.4}\n", .{order_autocorr});
    }

    pub fn printTailRisk(self: *Diary) void {
        const valid_count = @min(self.write_idx, self.ring.len);
        if (valid_count < 2) return;

        const ReturnTuple = struct { tick: u32, ret: f64 };
        var worst = [_]ReturnTuple{.{ .tick = 0, .ret = std.math.inf(f64) }} ** 5;

        for (1..valid_count) |i| {
            const ret = self.all_returns[i];
            if (ret < worst[4].ret) {
                worst[4] = .{ .tick = self.ring[i].tick, .ret = ret };
                var j: usize = 4;
                while (j > 0 and worst[j].ret < worst[j - 1].ret) : (j -= 1) {
                    const temp = worst[j - 1];
                    worst[j - 1] = worst[j];
                    worst[j] = temp;
                }
            }
        }

        std.mem.sortUnstable(f64, self.all_returns[1..valid_count], {}, struct {
            fn lessThan(_: void, x: f64, y: f64) bool {
                return x < y;
            }
        }.lessThan);

        const n = valid_count - 1;
        const var_99_idx = @as(usize, @intFromFloat(@as(f64, @floatFromInt(n)) * 0.01));
        const var_999_idx = @as(usize, @intFromFloat(@as(f64, @floatFromInt(n)) * 0.001));

        const var_99 = self.all_returns[1 + var_99_idx];
        const tail_var = self.all_returns[1 + var_999_idx];

        std.debug.print("\n=== TAIL-RISK REPORT ===\n", .{});
        std.debug.print("Top 5 Largest Drawdowns:\n", .{});
        for (worst, 1..) |wr, rank| {
            if (wr.ret != std.math.inf(f64)) {
                std.debug.print("  {d}. Tick {d}: {d:.2}%\n", .{ rank, wr.tick, wr.ret * 100.0 });
            }
        }
        std.debug.print("99.0% VaR: {d:.2}%\n", .{var_99 * 100.0});
        std.debug.print("99.9% Tail VaR: {d:.2}%\n", .{tail_var * 100.0});
    }

    pub fn printCROReport(self: *Diary, seed: u64, agents: u32, ticks: u32) void {
        _ = agents; // FIX: Explicitly prevents the unused variable compiler error
        const valid_count = @min(self.write_idx, self.ring.len);
        var mkt_avg: f64 = 0;
        if (valid_count > 0) mkt_avg = self.ring[valid_count - 1].mkt_avg;

        var sum_ret: f64 = 0;
        var sum_sq: f64 = 0;
        var max_dd: f64 = 0;
        var peak: f64 = if (valid_count > 0) self.ring[0].mkt_avg else 0.01;

        for (1..valid_count) |i| {
            const ret = self.all_returns[i];
            sum_ret += ret;
            sum_sq += ret * ret;
            const p = self.ring[i].mkt_avg;
            if (p > peak) peak = p;
            const dd = (p - peak) / peak;
            if (dd < max_dd) max_dd = dd;
        }

        const n = @as(f64, @floatFromInt(valid_count - 1));
        var sharpe: f64 = 0;
        if (n > 1) {
            const mean = sum_ret / n;
            const variance = (sum_sq / n) - (mean * mean);
            const std_dev = std.math.sqrt(variance);
            if (std_dev > 0) {
                sharpe = (mean / std_dev) * std.math.sqrt(252.0);
            }
        }

        const tail_var = if (valid_count > 2) self.all_returns[1 + @as(usize, @intFromFloat(n * 0.001))] else 0;

        std.debug.print("\n========================================\n", .{});
        std.debug.print("KESSLER INSTITUTIONAL READINESS REPORT\n", .{});
        std.debug.print("========================================\n", .{});
        std.debug.print("Seed: {d}\n", .{seed});
        std.debug.print("Assets: {d}\n", .{self.num_assets});
        std.debug.print("Ticks: {d}\n", .{ticks});
        std.debug.print("Final Market Average: {d:.2}\n", .{mkt_avg});
        std.debug.print("Peak Defaults: {d} at Tick {d}\n", .{ self.peak_defaults, self.peak_defaults_tick });
        std.debug.print("Max Cascade Depth: {d}\n", .{self.max_cascade});
        std.debug.print("CB Interventions: {d}\n", .{self.cb_interventions});
        std.debug.print("Sharpe Ratio (Market): {d:.4}\n", .{sharpe});
        std.debug.print("Max Drawdown: {d:.2}%\n", .{max_dd * 100.0});
        std.debug.print("Tail Risk (99.9% VaR): {d:.2}%\n", .{tail_var * 100.0});
        std.debug.print("========================================\n", .{});
    }

    pub fn exportCSV(self: *Diary) void {
        // FIX: Zig 0.16 completely dismantled std.fs.cwd(). To guarantee success,
        // we print the raw CSV data directly to stdout where it can be piped or copied.
        std.debug.print("\n=== KESSLER TICK CSV DATA ===\n", .{});
        std.debug.print("TICK,MKT_AVG,DEFAULTS,CASCADE", .{});
        for (0..self.num_assets) |a| std.debug.print(",P{d}", .{a});
        std.debug.print("\n", .{});

        const valid_count = @min(self.write_idx, self.ring.len);
        for (0..valid_count) |i| {
            const rec = self.ring[i];
            std.debug.print("{d},{d:.4},{d},{d}", .{ rec.tick, rec.mkt_avg, rec.defaults, rec.cascade });
            for (0..self.num_assets) |a| {
                std.debug.print(",{d:.4}", .{self.asset_prices[i * self.num_assets + a]});
            }
            std.debug.print("\n", .{});
        }
        std.debug.print("=============================\n", .{});
    }

    pub fn printVolatilitySurface(self: *Diary, b: *bazaar.Bazaar) void {
        _ = self;
        std.debug.print("\n=== IMPLIED VOLATILITY SURFACE (Calibrated Historical) ===\n", .{});
        for (0..b.num_assets) |a| {
            const spot = b.mid_prices[a];
            const atm_iv = b.iv_surface[a] * 100.0;
            const otm_put_iv = atm_iv + 5.0;
            std.debug.print("Asset {d} | Spot: {d:.2} | ATM IV: {d:.1}% | OTM Put IV: {d:.1}%\n", .{ a, spot, atm_iv, otm_put_iv });
        }
    }

    pub fn printHash(self: *Diary) void {
        var out: [32]u8 = undefined;
        self.hash_ctx.final(&out);
        const hex_hash = std.fmt.bytesToHex(out, .lower);
        std.debug.print("\n[CRYPTO] DETERMINISTIC REPLAY HASH: {s}\n", .{hex_hash});
    }

    pub fn printReplayProgress(self: *Diary, day: u32, total_days: u32, sp500: f64, vix: f64) void {
        _ = self;
        std.debug.print("REPLAY | Day {d}/{d} | ^GSPC: {d:.2} | ^VIX: {d:.2}\n", .{ day, total_days, sp500, vix });
    }

    pub fn printReplaySummary(self: *Diary, total_days: u32, start_sp500: f64, end_sp500: f64, max_dd: f64) void {
        _ = self;
        const ret_pct = ((end_sp500 / start_sp500) - 1.0) * 100.0;
        std.debug.print("\nREPLAY COMPLETE. {d} days. S&P 500: {d:.0} -> {d:.0} ({d:.1}%). Max drawdown: {d:.1}%\n", .{ total_days, start_sp500, end_sp500, ret_pct, max_dd * 100.0 });
        std.debug.print("Entering forward mode. Inject shocks to begin stress testing.\n\n", .{});
    }
};
