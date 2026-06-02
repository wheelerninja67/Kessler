const std = @import("std");
const bazaar = @import("bazaar.zig");
const crowd = @import("crowd.zig");
const gossip = @import("gossip.zig");
const scenario = @import("scenario.zig");
const diary = @import("diary.zig");

pub const Stats = struct {
    max_drawdown: f64,
    excess_kurtosis: f64,
    vol_clustering: f64,
    cascade_depth: f64,
};

pub const Config = struct {
    agents: usize,
    assets: usize,
    ticks: u32,
    seed: u64,
    threads: u32 = 1,
};

pub const EngineAsset = struct {
    name: []const u8,
    hist_max_drawdown: f64,
    synth_max_drawdown: f64,
    is_volatility: bool,
};

pub const Engine = struct {
    assets: []EngineAsset,
};

pub fn runTickLoop(num_ticks: u32, market: *bazaar.Bazaar, agents: *crowd.Crowd, net: *gossip.Network, shocks: []const scenario.Shock, allocator: std.mem.Allocator) !Stats {
    

    var min_price: f64 = market.assets[0].price;
    var max_price: f64 = market.assets[0].price;
    var prev_price: f64 = market.assets[0].price;
    

    var returns = try allocator.alloc(f64, num_ticks);
    defer allocator.free(returns);
    var valid_ticks: usize = 0;

    var max_frozen_volume: f64 = 0.0;

    for (0..num_ticks) |tick| {
        

        // 1. Trigger Scenario Shocks
        for (shocks) |shock| {
            const shock_tick = std.fmt.parseInt(u32, shock.tick, 10) catch continue;
            if (shock_tick == tick) {
                // If the shock targets specific agents, default them instantly
                if (shock.agent_ids.len > 0) {
                    for (shock.agent_ids) |agent_id| {
                        if (agent_id < agents.cash.len) {
                            agents.is_defaulted[agent_id] = true;
                            agents.cash[agent_id] = 0.0;
                            agents.equity[agent_id] = 0.0;
                        }
                    }
                }
                // Execute structural shock based on type
                if (std.mem.eql(u8, shock.type_name, "forced_liquidation")) {
                    const pct = shock.magnitude orelse 0.1;
                    const victims = @as(usize, @intFromFloat(@as(f64, @floatFromInt(agents.cash.len)) * pct));
                    for (0..victims) |i| {
                        agents.is_defaulted[i] = true;
                        agents.cash[i] = 0.0;
                        agents.equity[i] = 0.0;
                    }
                } else {
                    // Standard liquidity withdrawal or selling pressure
                    const magnitude = shock.magnitude orelse 25000.0;
                    market.submitOrder(@intCast(shock.asset_id orelse 0), false, magnitude);
                }
            }
        }

        // Placeholder fallback shock if no scenario shocks are defined
        if (shocks.len == 0 and tick == 50) {
            market.submitOrder(0, false, 85000.0);
            const shock_victims = agents.cash.len / 10; // 10% of market wiped out
            for (0..shock_victims) |i| {
                agents.is_defaulted[i] = true;
                agents.cash[i] = 0;
                agents.equity[i] = 0;
            }
        }

        // 2. Value Investor orders
        for (0..agents.num_assets) |j| {
            const buy_vol = agents.evaluateValueInvestors(market.assets[j].price);
            if (buy_vol > 0) {
                market.submitOrder(@as(u32, @intCast(j)), true, buy_vol);
            }
        }

        // 3. Mark-to-Market & Margin Call / Forced Selling
        for (0..agents.cash.len) |i| {
            if (agents.is_defaulted[i]) continue;

            var asset_value: f64 = 0.0;
            for (0..agents.num_assets) |j| {
                asset_value += agents.positions[i * agents.num_assets + j] * market.assets[j].price;
            }

            const equity = agents.cash[i] + asset_value;
            agents.equity[i] = equity;

            if (equity <= 0) {
                agents.is_defaulted[i] = true;
                continue;
            }

            const current_leverage = asset_value / equity;
            agents.leverage[i] = current_leverage;

            if (current_leverage > agents.config.leverage_cap) {
                const excess_leverage = current_leverage - agents.target_leverage[i];
                const value_to_sell = excess_leverage * equity;

                if (value_to_sell > 0) {
                    for (0..agents.num_assets) |j| {
                        const amount_to_sell = (value_to_sell / @as(f64, @floatFromInt(agents.num_assets))) / market.assets[j].price;
                        if (amount_to_sell > 0 and agents.positions[i * agents.num_assets + j] >= amount_to_sell) {
                            agents.positions[i * agents.num_assets + j] -= amount_to_sell;
                            agents.cash[i] += amount_to_sell * market.assets[j].price;
                            market.submitOrder(@as(u32, @intCast(j)), false, amount_to_sell);
                        }
                    }
                }
            }

            for (0..agents.num_assets) |j| {
                if (market.assets[j].price < 90.0) {
                    const panic_sell = agents.positions[i * agents.num_assets + j] * agents.config.decay_rate * 0.05;
                    if (panic_sell > 0) {
                        agents.positions[i * agents.num_assets + j] -= panic_sell;
                        agents.cash[i] += panic_sell * market.assets[j].price;
                        market.submitOrder(@as(u32, @intCast(j)), false, panic_sell);
                    }
                }
            }
        }

        // 4. Gai-Kapadia Network Contagion Cascade
        const cascade_depth = net.propagateDefaults(agents, market);

        // 5. Update Market Microstructure
        market.updateMarketMicrostructure();

        const new_price = market.assets[0].price;

        if (market.assets[0].is_frozen) {
            if (market.assets[0].frozen_sell_vol > max_frozen_volume) {
                max_frozen_volume = market.assets[0].frozen_sell_vol;
            }
        }

        if (new_price < min_price) min_price = new_price;
        if (new_price > max_price) max_price = new_price;

        // Compute valid Log-Returns, discarding zero-movement ticks
        if (prev_price > 0.01 and tick > 50) {
            if (@abs(new_price - prev_price) > 1e-6) {
                const tick_return = @log(new_price / prev_price);
                returns[valid_ticks] = tick_return;
                valid_ticks += 1;
            }
        }
        
        prev_price = new_price;

        // 6. Record telemetry metrics and update hash accumulator
        var active_defaults: usize = 0;
        for (agents.is_defaulted) |def| {
            if (def) active_defaults += 1;
        }
        
        var prices: [7]f64 = undefined;
        for (0..7) |j| {
            prices[j] = market.assets[j].price;
        }

        const total_sentiment: f64 = 0.0;
        const avg_sentiment = if (agents.cash.len > 0) total_sentiment / @as(f64, @floatFromInt(agents.cash.len)) else 0.0;

        var hash_update: [32]u8 = [_]u8{0} ** 32;
        var hasher = std.crypto.hash.sha2.Sha256.init(.{});
        hasher.update(&std.mem.toBytes(tick));
        hasher.update(&std.mem.toBytes(prices[0]));
        hasher.update(&std.mem.toBytes(active_defaults));
        hasher.update(&std.mem.toBytes(cascade_depth));
        hasher.final(&hash_update);

        diary.recordTick(tick, &prices, active_defaults, cascade_depth, avg_sentiment, hash_update);
    }

    // =========================================================================
    // COMPILE FINAL METRICS
    // =========================================================================
    const max_drawdown = ((min_price - 100.0) / 100.0) * 100.0;

    var kurtosis: f64 = 0.0;
    var vol_clustering: f64 = 0.0;

    if (valid_ticks > 4) {
        const n: f64 = @floatFromInt(valid_ticks);

        // 1. Compute Mean of Log-Returns & Absolute Log-Returns
        var mean_r: f64 = 0.0;
        var mean_abs_r: f64 = 0.0;
        for (0..valid_ticks) |i| {
            mean_r += returns[i];
            mean_abs_r += @abs(returns[i]);
        }
        mean_r /= n;
        mean_abs_r /= n;

        // 2. Compute Variance, 4th Moment, and Lag-1 Autocovariance
        var m2: f64 = 0.0;
        var m4: f64 = 0.0;
        var var_abs_r: f64 = 0.0;
        var cov_abs_r: f64 = 0.0;

        for (0..valid_ticks) |i| {
            const r = returns[i];
            const dev = r - mean_r;
            const dev2 = dev * dev;
            m2 += dev2;
            m4 += dev2 * dev2;

            const dev_abs = @abs(r) - mean_abs_r;
            var_abs_r += dev_abs * dev_abs;

            if (i > 0) {
                const prev_dev_abs = @abs(returns[i - 1]) - mean_abs_r;
                cov_abs_r += dev_abs * prev_dev_abs;
            }
        }

        // 3. Excess Kurtosis = (m4 / var^2) - 3
        const var_est = m2 / n;
        if (var_est > 1e-12) {
            const moment_4 = m4 / n;
            kurtosis = (moment_4 / (var_est * var_est)) - 3.0;

            if (kurtosis > 50.0) kurtosis = 50.0;
            if (kurtosis < -2.0) kurtosis = -2.0;
        }

        // 4. Volatility Clustering = lag-1 autocorrelation of absolute returns
        const var_abs_est = var_abs_r / n;
        if (var_abs_est > 1e-12) {
            const cov_est = cov_abs_r / (n - 1.0);
            vol_clustering = cov_est / var_abs_est;

            if (vol_clustering > 1.0) vol_clustering = 1.0;
            if (vol_clustering < -1.0) vol_clustering = -1.0;
        }
    }

    const cascade_final_depth = if (max_frozen_volume > 0) @log10(max_frozen_volume) else 0.0;

    return Stats{
        .max_drawdown = max_drawdown,
        .excess_kurtosis = kurtosis,
        .vol_clustering = vol_clustering,
        .cascade_depth = cascade_final_depth,
    };
}
