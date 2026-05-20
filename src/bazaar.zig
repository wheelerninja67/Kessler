const std = @import("std");
const stash = @import("stash.zig");
const market_data = @import("market_data.zig");

pub const Bazaar = struct {
    num_assets: u32,
    mid_prices: []f64,
    lambda: []f64,
    base_depth: []f64,
    volatility: []f64,
    vpin: []f64,
    buy_vol: []f64,
    sell_vol: []f64,
    correlation_matrix: []f64,
    frozen_ticks: []u32,
    abs_ret_history: []f64,
    history_idx: u32,
    decay_rate: []f64,
    resilience: []f64,
    iv_surface: []f64, // NEW: Stores the calibrated ATM Implied Volatility

    pub fn init(arena: *stash.Stash, assets: u32, seed: u64) !Bazaar {
        _ = seed;
        const b = Bazaar{
            .num_assets = assets,
            .mid_prices = try arena.stashAlloc(f64, assets),
            .lambda = try arena.stashAlloc(f64, assets),
            .base_depth = try arena.stashAlloc(f64, assets),
            .volatility = try arena.stashAlloc(f64, assets),
            .vpin = try arena.stashAlloc(f64, assets),
            .buy_vol = try arena.stashAlloc(f64, assets),
            .sell_vol = try arena.stashAlloc(f64, assets),
            .correlation_matrix = try arena.stashAlloc(f64, assets * assets),
            .frozen_ticks = try arena.stashAlloc(u32, assets),
            .abs_ret_history = try arena.stashAlloc(f64, assets * 20),
            .history_idx = 0,
            .decay_rate = try arena.stashAlloc(f64, assets),
            .resilience = try arena.stashAlloc(f64, assets),
            .iv_surface = try arena.stashAlloc(f64, assets),
        };
        for (0..assets) |i| {
            b.mid_prices[i] = 100.0;
            b.lambda[i] = 0.001;
            b.base_depth[i] = 10000.0;
            b.frozen_ticks[i] = 0;
            b.decay_rate[i] = 0.01;
            b.resilience[i] = 0.1;
            b.iv_surface[i] = 0.20; // Default 20% IV
            for (0..assets) |j| {
                b.correlation_matrix[i * assets + j] = if (i == j) 1.0 else 0.3;
            }
            for (0..20) |lag| b.abs_ret_history[i * 20 + lag] = 0.0;
        }
        return b;
    }

    pub fn initCalibrated(arena: *stash.Stash, assets: u32, md: *const market_data.MarketData, seed: u64) !Bazaar {
        const b = try init(arena, assets, seed);

        for (0..assets) |a| {
            // Sync price to reality
            b.mid_prices[a] = md.getPrice(@intCast(a), md.num_days - 1);

            // Calculate trailing 20-day annualized volatility for the IV Surface
            const start_20 = if (md.num_days > 20) md.num_days - 20 else 0;
            var mean_ret: f64 = 0;
            const days_20 = md.num_days - start_20;
            for (start_20..md.num_days) |d| {
                mean_ret += md.getReturn(@intCast(a), @intCast(d));
            }
            mean_ret /= @as(f64, @floatFromInt(days_20));

            var var_ret: f64 = 0;
            for (start_20..md.num_days) |d| {
                const r = md.getReturn(@intCast(a), @intCast(d));
                var_ret += (r - mean_ret) * (r - mean_ret);
            }
            var_ret /= @as(f64, @floatFromInt(days_20));

            // Multiply daily vol by sqrt(252) to annualize it (~15.87)
            b.iv_surface[a] = std.math.sqrt(var_ret) * 15.8745;
            if (b.iv_surface[a] < 0.05) b.iv_surface[a] = 0.05; // Floor at 5% for safety

            // Scale Base Depth dynamically based on 100-day historical abs returns
            const start_100 = if (md.num_days > 100) md.num_days - 100 else 0;
            var abs_ret_sum: f64 = 0;
            const days_100 = md.num_days - start_100;
            for (start_100..md.num_days) |d| {
                abs_ret_sum += @abs(md.getReturn(@intCast(a), @intCast(d)));
            }
            const avg_abs_ret = abs_ret_sum / @as(f64, @floatFromInt(days_100));

            b.base_depth[a] = @max(1000.0, avg_abs_ret * 1_000_000.0);
            b.lambda[a] = 1.0 / b.base_depth[a];
        }
        return b;
    }

    pub fn updateMarketMicrostructure(self: *Bazaar) void {
        self.history_idx = (self.history_idx + 1) % 20;

        for (0..self.num_assets) |a| {
            if (self.frozen_ticks[a] > 0) {
                self.frozen_ticks[a] -= 1;
                continue;
            }

            const total_vol = self.buy_vol[a] + self.sell_vol[a] + 1.0;
            self.vpin[a] = @abs(self.buy_vol[a] - self.sell_vol[a]) / total_vol;

            var rough_vol: f64 = 0;
            const H: f64 = 0.15;
            for (0..20) |lag| {
                const idx = (self.history_idx + 20 - lag) % 20;
                const weight = 1.0 / std.math.pow(f64, @as(f64, @floatFromInt(lag + 1)), H);
                rough_vol += self.abs_ret_history[a * 20 + idx] * weight;
            }
            self.volatility[a] = rough_vol / 20.0;

            if (self.vpin[a] > 0.8 or self.volatility[a] > 0.05) {
                self.lambda[a] *= (1.0 + self.resilience[a] * 5.0);
                self.base_depth[a] *= 0.5;

                if (self.base_depth[a] < 1000.0 and self.lambda[a] > 0.02) {
                    self.frozen_ticks[a] = 10;
                    std.debug.print(">>> LIQUIDITY BLACK HOLE: Asset {d} frozen. <<<\n", .{a});
                }

                for (0..self.num_assets) |other| {
                    if (a != other) {
                        const corr = self.correlation_matrix[a * self.num_assets + other];
                        self.base_depth[other] -= (self.base_depth[other] * corr * 0.1);
                    }
                }
            } else {
                self.lambda[a] = @max(0.001, self.lambda[a] * (1.0 - self.decay_rate[a]));
                self.base_depth[a] = @min(100000.0, self.base_depth[a] * 1.05);
            }

            self.buy_vol[a] = 0;
            self.sell_vol[a] = 0;
        }
    }
};
