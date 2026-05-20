const std = @import("std");
const stash = @import("stash.zig");
const market_data = @import("market_data.zig");

pub const Crowd = struct {
    count: u32,
    assets: u32,
    cash: []f64,
    theta: []f64,
    is_defaulted: []bool,
    is_bank: []bool,
    portfolio: []f64,
    equity: []f64,
    intensity: []f64,
    centrality: []f64,
    neighbors: []u32,
    cooldown: []u32,
    last_pnl: []f64,
    sigma: []f64, // NEW: Volatility estimate
    leverage: []f64, // NEW: Leverage ratio

    pub fn init(arena: *stash.Stash, count: u32, assets: u32, seed: u64) !Crowd {
        var prng = std.Random.DefaultPrng.init(seed);
        const random = prng.random();

        const c = Crowd{
            .count = count,
            .assets = assets,
            .cash = try arena.stashAlloc(f64, count),
            .theta = try arena.stashAlloc(f64, count),
            .is_defaulted = try arena.stashAlloc(bool, count),
            .is_bank = try arena.stashAlloc(bool, count),
            .portfolio = try arena.stashAlloc(f64, count * assets),
            .equity = try arena.stashAlloc(f64, count),
            .intensity = try arena.stashAlloc(f64, count),
            .centrality = try arena.stashAlloc(f64, count),
            .neighbors = try arena.stashAlloc(u32, count * 8),
            .cooldown = try arena.stashAlloc(u32, count),
            .last_pnl = try arena.stashAlloc(f64, count),
            .sigma = try arena.stashAlloc(f64, count),
            .leverage = try arena.stashAlloc(f64, count),
        };

        for (0..count) |i| {
            c.cash[i] = 100_000.0;
            c.theta[i] = random.float(f64);
            c.is_bank[i] = (i < count / 10);
            c.intensity[i] = 0.01;
            c.is_defaulted[i] = false;
            c.centrality[i] = random.float(f64) * 0.1;
            c.cooldown[i] = 0;
            c.last_pnl[i] = 0.0;
            c.sigma[i] = 0.05;
            c.leverage[i] = 1.0;

            for (0..8) |n| {
                c.neighbors[i * 8 + n] = random.int(u32) % count;
            }
            for (0..assets) |a| {
                c.portfolio[i * assets + a] = 1000.0 * (1.0 + c.centrality[i]);
            }
        }
        return c;
    }

    pub fn initCalibrated(arena: *stash.Stash, count: u32, assets: u32, md: *const market_data.MarketData, seed: u64) !Crowd {
        var prng = std.Random.DefaultPrng.init(seed);
        const rand = prng.random();

        const c = try init(arena, count, assets, seed); // Allocate buffers

        // 1. Compute SP500 (Ticker 0) trailing 20-day volatility for global Theta
        var sp500_mean: f64 = 0;
        const start_day = if (md.num_days > 20) md.num_days - 20 else 0;
        const days_to_calc = md.num_days - start_day;

        for (start_day..md.num_days) |d| {
            sp500_mean += md.getReturn(0, @intCast(d));
        }
        sp500_mean /= @as(f64, @floatFromInt(days_to_calc));

        var sp500_var: f64 = 0;
        for (start_day..md.num_days) |d| {
            const ret = md.getReturn(0, @intCast(d));
            sp500_var += (ret - sp500_mean) * (ret - sp500_mean);
        }
        sp500_var /= @as(f64, @floatFromInt(days_to_calc));
        const sp500_vol = std.math.sqrt(sp500_var);

        for (0..count) |i| {
            // 2. Assign Primary Asset (Home Bias)
            const primary_asset = rand.int(u32) % assets;

            // 3. Compute Sigma (Primary Asset 20-day vol)
            var p_mean: f64 = 0;
            for (start_day..md.num_days) |d| p_mean += md.getReturn(primary_asset, @intCast(d));
            p_mean /= @as(f64, @floatFromInt(days_to_calc));

            var p_var: f64 = 0;
            for (start_day..md.num_days) |d| {
                const ret = md.getReturn(primary_asset, @intCast(d));
                p_var += (ret - p_mean) * (ret - p_mean);
            }
            p_var /= @as(f64, @floatFromInt(days_to_calc));
            c.sigma[i] = std.math.sqrt(p_var);

            // 4. Compute Theta (Risk appetite drops as global vol spikes)
            c.theta[i] = @max(0.1, @min(0.9, 1.0 - (sp500_vol * 5.0)));

            // 5. Assign Leverage (10% Hedge Funds)
            if (rand.float(f64) < 0.10) {
                c.leverage[i] = 3.0 + (rand.float(f64) * 5.0);
            } else {
                c.leverage[i] = 1.0;
            }

            // 6. Portfolio Allocation
            c.cash[i] = 0; // Fully deployed
            c.equity[i] = 100_000.0;
            c.last_pnl[i] = 0.0;

            const initial_cash = 100_000.0;
            for (0..assets) |a| {
                const price = @max(0.01, md.getPrice(@intCast(a), md.num_days - 1));
                if (a == primary_asset) {
                    c.portfolio[i * assets + a] = (initial_cash * 0.8) / price;
                } else {
                    const spread = (initial_cash * 0.2) / @as(f64, @floatFromInt(assets - 1));
                    c.portfolio[i * assets + a] = spread / price;
                }
            }
        }
        return c;
    }

    pub fn applyMemoryAndHerdBehavior(self: *Crowd, prng_seed: u64) void {
        var prng = std.Random.DefaultPrng.init(prng_seed);
        const rand = prng.random();
        for (0..self.count) |i| {
            if (self.is_defaulted[i]) continue;
            var herd_theta: f64 = 0;
            for (0..8) |n| {
                herd_theta += self.theta[self.neighbors[i * 8 + n]];
            }

            const memory_bias: f64 = if (self.last_pnl[i] < 0) -0.05 else 0.02;

            self.theta[i] = (self.theta[i] * 0.7) + ((herd_theta / 8.0) * 0.2) + memory_bias + (rand.float(f64) * 0.01 - 0.005);
            self.theta[i] = @max(0.01, @min(1.0, self.theta[i]));

            self.intensity[i] *= 0.90;
        }
    }
};
