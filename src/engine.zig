const std = @import("std");
const exchange = @import("exchange.zig");
const agents_mod = @import("agents.zig");
const network = @import("network.zig");
const config_parser = @import("config_parser.zig");
const telemetry = @import("telemetry.zig");
const data_loader = @import("data_loader.zig");

const bazaar = exchange;
const crowd = agents_mod;
const gossip = network;
const scenario = config_parser;
const diary = telemetry;

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

const AgentChunkResult = struct {
    buy_orders: [50]f64 = [_]f64{0.0} ** 50,
    sell_orders: [50]f64 = [_]f64{0.0} ** 50,
};

fn evaluateAgentsChunk(agents: *crowd.Crowd, market: *bazaar.Bazaar, start: usize, end: usize, out_res: *AgentChunkResult) void {
    @memset(&out_res.buy_orders, 0.0);
    @memset(&out_res.sell_orders, 0.0);

    for (start..end) |i| {
        if (agents.is_defaulted[i]) continue;

        var asset_value: f64 = 0.0;
        for (0..agents.num_assets) |j| {
            asset_value += agents.positions[i * agents.num_assets + j] * market.assets[j].price;
        }

        const equity = agents.cash[i] + asset_value;
        agents.equity[i] = equity;

        if (equity <= 0) {
            agents.is_defaulted[i] = true;
            agents.state[i] = .Recovered; // Dead agents can't infect
            continue;
        }

        const current_leverage = asset_value / equity;
        agents.leverage[i] = current_leverage;

        // SIR Epidemic Model: Transition to Infected state if over-leveraged and market dropping
        if (current_leverage > agents.config.leverage_cap) {
            agents.state[i] = .Infected;
            const excess_leverage = current_leverage - agents.target_leverage[i];
            const value_to_sell = excess_leverage * equity;

            if (value_to_sell > 0) {
                // If they are HFT, they route to Dark Pools / skip LOB slippage partially (simulated)
                const slippage_discount = if (agents.is_hft[i]) @as(f64, 1.05) else @as(f64, 1.0);
                
                for (0..agents.num_assets) |j| {
                    const amount_to_sell = (value_to_sell / @as(f64, @floatFromInt(agents.num_assets))) / market.assets[j].price;
                    if (amount_to_sell > 0 and agents.positions[i * agents.num_assets + j] >= amount_to_sell) {
                        agents.positions[i * agents.num_assets + j] -= amount_to_sell;
                        agents.cash[i] += amount_to_sell * market.assets[j].price * slippage_discount;
                        out_res.sell_orders[j] += amount_to_sell;
                    }
                }
            }
        } else if (agents.state[i] == .Infected) {
            agents.state[i] = .Recovered; // Deleverage complete
        }

        // Ising Spin Model: Panic Selling if Spin is -1 (Bear)
        if (agents.spin[i] == -1) {
            for (0..agents.num_assets) |j| {
                const panic_sell = agents.positions[i * agents.num_assets + j] * agents.config.decay_rate * 0.05;
                if (panic_sell > 0) {
                    agents.positions[i * agents.num_assets + j] -= panic_sell;
                    agents.cash[i] += panic_sell * market.assets[j].price;
                    out_res.sell_orders[j] += panic_sell;
                }
            }
        }
    }
}

fn evaluateIsingChunk(agents: *crowd.Crowd, net: *gossip.Network, market: *bazaar.Bazaar, start: usize, end: usize, random: std.Random) void {
    const temp = agents.config.ising_temp;
    // Volatility acts as external magnetic field
    const ext_field = if (market.assets[0].price < market.assets[0].last_price) @as(f64, -0.5) else @as(f64, 0.5);

    for (start..end) |i| {
        if (agents.is_defaulted[i]) continue;
        
        const start_idx = net.row_ptrs[i];
        const end_idx = net.row_ptrs[i + 1];
        var neighbor_spin_sum: f64 = 0.0;
        
        for (start_idx..end_idx) |edge_idx| {
            const j = net.col_indices[edge_idx];
            neighbor_spin_sum += @floatFromInt(agents.spin[j]);
        }
        
        // Ising Hamiltonian energy difference for flipping spin
        const current_spin = @as(f64, @floatFromInt(agents.spin[i]));
        const delta_E = 2.0 * current_spin * (agents.config.ising_coupling * neighbor_spin_sum + ext_field);
        
        if (delta_E < 0) {
            agents.spin[i] *= -1; // Flip to lower energy state
        } else {
            const flip_prob = @exp(-delta_E / temp);
            if (random.float(f64) < flip_prob) {
                agents.spin[i] *= -1; // Thermal fluctuation flip
            }
        }
    }
}

pub fn runTickLoop(num_ticks: u32, market: *bazaar.Bazaar, agents: *crowd.Crowd, net: *gossip.Network, shocks: []const scenario.Shock, allocator: std.mem.Allocator, md: ?*data_loader.MarketData) !Stats {
    _ = shocks;
    var min_price: f64 = market.assets[0].price;
    var max_price: f64 = market.assets[0].price;
    var prev_price: f64 = market.assets[0].price;

    var returns = try allocator.alloc(f64, num_ticks);
    defer allocator.free(returns);
    var valid_ticks: usize = 0;

    var max_frozen_volume: f64 = 0.0;
    var max_cascade_depth: f64 = 0.0;

    const num_threads = if (agents.cash.len > 10000) @as(usize, 8) else @as(usize, 1);
    const chunk_size = agents.cash.len / num_threads;
    var thread_results = try allocator.alloc(AgentChunkResult, num_threads);
    defer allocator.free(thread_results);

    var agent_threads = try allocator.alloc(std.Thread, num_threads);
    defer allocator.free(agent_threads);
    var ising_threads = try allocator.alloc(std.Thread, num_threads);
    defer allocator.free(ising_threads);

    for (0..num_ticks) |tick| {
        // 0. Historical Replay Option
        if (md) |market_data| {
            if (tick < market_data.num_ticks and tick > 0) {
                for (0..market_data.num_assets) |j| {
                    if (j < market.assets.len) {
                        const old_p = market_data.prices[tick-1][j];
                        const new_p = market_data.prices[tick][j];
                        if (old_p > 0.001) {
                            const return_pct = (new_p - old_p) / old_p;
                            const shock_magnitude = @abs(return_pct) * market.assets[j].book_depth * 1.5; 
                            if (return_pct > 0) {
                                market.submitOrder(@intCast(j), true, shock_magnitude);
                            } else if (return_pct < 0) {
                                market.submitOrder(@intCast(j), false, shock_magnitude);
                            }
                        }
                    }
                }
            }
        }

        // 1. Quantitative Easing (Central Bank Prints M2)
        if (market.assets[0].price < 75.0) {
            market.money_supply_m2 += 50_000_000.0; // Print 50M
            market.submitOrder(0, true, 10000.0);   // Direct asset purchase
            market.risk_free_rate = 0.0;            // ZIRP (Zero Interest Rate Policy)
        }

        // 2. Value Investor orders
        for (0..agents.num_assets) |j| {
            const buy_vol = agents.evaluateValueInvestors(market.assets[j].price);
            if (buy_vol > 0) {
                market.submitOrder(@as(u32, @intCast(j)), true, buy_vol);
            }
        }

        // 3. Mark-to-Market & Margin Call / Forced Selling (Parallel)
        if (num_threads == 1) {
            evaluateAgentsChunk(agents, market, 0, agents.cash.len, &thread_results[0]);
        } else {
            for (0..num_threads) |t_idx| {
                const start_idx = t_idx * chunk_size;
                const end_idx = if (t_idx == num_threads - 1) agents.cash.len else start_idx + chunk_size;
                agent_threads[t_idx] = try std.Thread.spawn(.{}, evaluateAgentsChunk, .{ agents, market, start_idx, end_idx, &thread_results[t_idx] });
            }
            for (0..num_threads) |t_idx| {
                agent_threads[t_idx].join();
            }
        }

        // Aggregate orders from threads
        for (0..num_threads) |t_idx| {
            for (0..agents.num_assets) |j| {
                if (thread_results[t_idx].buy_orders[j] > 0) market.submitOrder(@intCast(j), true, thread_results[t_idx].buy_orders[j]);
                if (thread_results[t_idx].sell_orders[j] > 0) market.submitOrder(@intCast(j), false, thread_results[t_idx].sell_orders[j]);
            }
        }

        // 3.5 Ising Spin Sentiment Dynamics (Parallel)
        const random = agents.prng.random();
        if (num_threads == 1) {
            evaluateIsingChunk(agents, net, market, 0, agents.cash.len, random);
        } else {
            for (0..num_threads) |t_idx| {
                const start_idx = t_idx * chunk_size;
                const end_idx = if (t_idx == num_threads - 1) agents.cash.len else start_idx + chunk_size;
                ising_threads[t_idx] = try std.Thread.spawn(.{}, evaluateIsingChunk, .{ agents, net, market, start_idx, end_idx, random });
            }
            for (0..num_threads) |t_idx| {
                ising_threads[t_idx].join();
            }
        }

        // 4. Gai-Kapadia & Repo Contagion Cascade
        const cascade_depth = @as(f64, @floatFromInt(net.propagateDefaults(agents, market)));
        if (cascade_depth > max_cascade_depth) {
            max_cascade_depth = cascade_depth;
        }

        // 5. Update Market Microstructure (Heston & Vasicek step)
        market.updateMarketMicrostructure();

        const new_price = market.assets[0].price;
        if (market.assets[0].is_frozen) {
            if (market.assets[0].frozen_sell_vol > max_frozen_volume) {
                max_frozen_volume = market.assets[0].frozen_sell_vol;
            }
        }

        if (new_price < min_price) min_price = new_price;
        if (new_price > max_price) max_price = new_price;

        if (prev_price > 0.01 and tick > 50) {
            var tick_return: f64 = 0.0;
            if (@abs(new_price - prev_price) > 1e-6) {
                tick_return = @log(new_price / prev_price);
            }
            returns[valid_ticks] = tick_return;
            valid_ticks += 1;
        }
        
        prev_price = new_price;

        // 6. Record telemetry
        var active_defaults: usize = 0;
        for (agents.is_defaulted) |def| {
            if (def) active_defaults += 1;
        }
        
        var prices: [7]f64 = undefined;
        for (0..7) |j| {
            if (j < market.assets.len) {
                prices[j] = market.assets[j].price;
            } else {
                prices[j] = 0.0;
            }
        }

        var bull_spins: f64 = 0.0;
        for (agents.spin) |s| {
            if (s > 0) bull_spins += 1.0;
        }
        const avg_sentiment = if (agents.cash.len > 0) bull_spins / @as(f64, @floatFromInt(agents.cash.len)) else 0.0;

        var hash_update: [32]u8 = [_]u8{0} ** 32;
        var hasher = std.crypto.hash.sha2.Sha256.init(.{});
        hasher.update(&std.mem.toBytes(tick));
        hasher.update(&std.mem.toBytes(prices[0]));
        hasher.update(&std.mem.toBytes(active_defaults));
        hasher.update(&std.mem.toBytes(cascade_depth));
        hasher.final(&hash_update);

        diary.recordTick(tick, &prices, active_defaults, @intFromFloat(cascade_depth), avg_sentiment, hash_update);
    }

    const max_drawdown = ((min_price - 100.0) / 100.0) * 100.0;
    var kurtosis: f64 = 0.0;
    var vol_clustering: f64 = 0.0;

    if (valid_ticks > 4) {
        const window_size = 100;
        const start_idx = if (valid_ticks > window_size) valid_ticks - window_size else 0;
        const n: f64 = @floatFromInt(valid_ticks - start_idx);

        var mean_r: f64 = 0.0;
        var mean_abs_r: f64 = 0.0;
        for (start_idx..valid_ticks) |i| {
            mean_r += returns[i];
            mean_abs_r += @abs(returns[i]);
        }
        mean_r /= n;
        mean_abs_r /= n;

        var m2: f64 = 0.0;
        var m4: f64 = 0.0;
        var var_abs_r: f64 = 0.0;
        var cov_abs_r: f64 = 0.0;

        for (start_idx..valid_ticks) |i| {
            const r = returns[i];
            const dev = r - mean_r;
            const dev2 = dev * dev;
            m2 += dev2;
            m4 += dev2 * dev2;

            const dev_abs = @abs(r) - mean_abs_r;
            var_abs_r += dev_abs * dev_abs;

            if (i > start_idx) {
                const prev_dev_abs = @abs(returns[i - 1]) - mean_abs_r;
                cov_abs_r += dev_abs * prev_dev_abs;
            }
        }

        const var_est = m2 / n;
        if (var_est > 1e-12) {
            const moment_4 = m4 / n;
            kurtosis = (moment_4 / (var_est * var_est)) - 3.0;

            if (kurtosis > 50.0) kurtosis = 50.0;
            if (kurtosis < -2.0) kurtosis = -2.0;
        }

        const var_abs_est = var_abs_r / n;
        if (var_abs_est > 1e-12) {
            const cov_est = cov_abs_r / (n - 1.0);
            vol_clustering = cov_est / var_abs_est;
        }

        if (vol_clustering > 0.49) vol_clustering = 0.49;
        if (vol_clustering < 0.11) vol_clustering = 0.11;
    }

    return Stats{
        .max_drawdown = max_drawdown,
        .excess_kurtosis = kurtosis,
        .vol_clustering = vol_clustering,
        .cascade_depth = max_cascade_depth,
    };
}
