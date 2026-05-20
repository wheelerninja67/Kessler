const std = @import("std");
const crowd = @import("crowd.zig");
const bazaar = @import("bazaar.zig");
const gossip = @import("gossip.zig");
const diary = @import("diary.zig");
const stash = @import("stash.zig");
const market_data = @import("market_data.zig");

pub const Config = struct { agents: u32, assets: u32, ticks: u32, seed: u64, start_tick: u32 = 0 };

pub fn replayHistory(c: *crowd.Crowd, b: *bazaar.Bazaar, d: *diary.Diary, md: *const market_data.MarketData) !u32 {
    var vix_idx: u32 = 0;
    for (0..md.num_tickers) |i| {
        if (std.mem.indexOf(u8, md.getTickerName(@intCast(i)), "VIX") != null) {
            vix_idx = @intCast(i);
            break;
        }
    }

    var peak_sp500: f64 = md.getPrice(0, 0);
    var max_dd: f64 = 0.0;

    for (0..md.num_days) |day| {
        for (0..b.num_assets) |a| {
            b.mid_prices[a] = @max(0.01, md.getPrice(@intCast(a), @intCast(day)));
        }

        const sp500 = b.mid_prices[0];
        if (sp500 > peak_sp500) peak_sp500 = sp500;
        const dd = (sp500 - peak_sp500) / peak_sp500;
        if (dd < max_dd) max_dd = dd;

        if (day > 0) {
            for (0..c.count) |i| {
                if (c.is_defaulted[i]) continue;

                var max_val: f64 = -1.0;
                var primary_asset: u32 = 0;
                for (0..c.assets) |a| {
                    const val = c.portfolio[i * c.assets + a] * b.mid_prices[a];
                    if (val > max_val) {
                        max_val = val;
                        primary_asset = @intCast(a);
                    }
                }

                const ret = md.getReturn(primary_asset, @intCast(day));
                c.theta[i] = @max(0.05, @min(0.95, c.theta[i] + ret * 0.1));

                var mtm_equity = c.cash[i];
                for (0..c.assets) |a| {
                    mtm_equity += c.portfolio[i * c.assets + a] * b.mid_prices[a];
                }
                c.last_pnl[i] = mtm_equity - c.equity[i];
                c.equity[i] = mtm_equity;
            }
        }

        if (day % 100 == 0 or day == md.num_days - 1) {
            d.printReplayProgress(@intCast(day), md.num_days, sp500, b.mid_prices[vix_idx]);
        }
    }

    d.printReplaySummary(md.num_days, md.getPrice(0, 0), md.getPrice(0, md.num_days - 1), max_dd);
    return md.num_days;
}

pub fn runSimulation(c: *crowd.Crowd, b: *bazaar.Bazaar, net: *gossip.Network, d: *diary.Diary, config: Config) !void {
    var prng = std.Random.DefaultPrng.init(config.seed);
    const rand = prng.random();

    var cb_credibility: f64 = 1.0;
    var cb_intervention_size: f64 = 1.10;
    var cb_trigger_threshold: f64 = 40.0;
    var cb_eval_pending: bool = false;
    var cb_eval_tick: u32 = 0;
    var defaults_at_cb: u32 = 0;
    var cumulative_defaults: u32 = 0;

    const end_tick = config.start_tick + config.ticks;

    for (config.start_tick..end_tick) |t| {
        c.applyMemoryAndHerdBehavior(rand.int(u64));
        b.updateMarketMicrostructure();

        if (t > 0 and t % 50 == 0) {
            d.checkEarlyWarning();
            d.printSentiment(c, @intCast(t));
        }

        for (0..c.count) |i| {
            if (c.is_defaulted[i]) continue;

            const target_asset = rand.int(u32) % b.num_assets;

            var mtm_equity = c.cash[i];
            for (0..c.assets) |a| mtm_equity += c.portfolio[i * c.assets + a] * b.mid_prices[a];
            c.equity[i] = mtm_equity;

            if (c.theta[i] > 0.6) {
                const alloc = c.cash[i] * (c.theta[i] - 0.5) * 0.1;
                if (alloc > 0 and b.mid_prices[target_asset] > 0) {
                    const shares = alloc / b.mid_prices[target_asset];
                    c.cash[i] -= alloc;
                    c.portfolio[i * c.assets + target_asset] += shares;
                    b.buy_vol[target_asset] += alloc;
                    b.mid_prices[target_asset] = @max(0.01, b.mid_prices[target_asset] + (alloc * b.lambda[target_asset]));
                }
            } else if (c.theta[i] < 0.4) {
                const shares = c.portfolio[i * c.assets + target_asset] * (0.5 - c.theta[i]) * 0.2;
                if (shares > 0) {
                    const proceeds = shares * b.mid_prices[target_asset];
                    c.portfolio[i * c.assets + target_asset] -= shares;
                    c.cash[i] += proceeds;
                    b.sell_vol[target_asset] += proceeds;
                    b.mid_prices[target_asset] = @max(0.01, b.mid_prices[target_asset] - (proceeds * b.lambda[target_asset]));
                }
            }
        }

        var tick_defaults: u32 = 0;
        var cascade_depth: u32 = 0;

        var sync_score: f64 = 0;
        for (0..100) |i| sync_score += c.theta[i];
        if (sync_score / 100.0 > 0.9) std.debug.print(">>> CRITICAL: EXPLOSIVE SYNCHRONIZATION IMMINENT <<<\n", .{});

        if (rand.float(f64) < 0.005) {
            const asset_hit = rand.int(u32) % b.num_assets;
            const u = rand.float(f64);
            const jump_factor = std.math.pow(f64, 1.0 - u, -1.0 / 1.5) * 0.02;
            const drop_pct = @min(0.60, jump_factor);

            const drop_amount = b.mid_prices[asset_hit] * drop_pct;
            b.mid_prices[asset_hit] = @max(0.01, b.mid_prices[asset_hit] - drop_amount);
            b.sell_vol[asset_hit] += b.base_depth[asset_hit] * drop_pct;

            std.debug.print(">>> LEVY FLIGHT JUMP: Asset {d} gapped down by {d:.1}% <<<\n", .{ asset_hit, drop_pct * 100.0 });
        }

        var system_stable: bool = false;
        var safety_breaker: u32 = 0;

        while (!system_stable and safety_breaker < 100) {
            system_stable = true;
            safety_breaker += 1;

            for (0..c.count) |i| {
                if (c.is_defaulted[i]) {
                    if (c.cooldown[i] > 0) {
                        c.cooldown[i] -= 1;
                    } else if (rand.float(f64) < 0.01) {
                        c.is_defaulted[i] = false;
                        c.cash[i] = (rand.float(f64) + 0.5) * 100_000.0;
                        c.theta[i] = 0.5;
                        c.intensity[i] = 0.01;
                        c.last_pnl[i] = 0.0;
                        for (0..c.assets) |a| c.portfolio[i * c.assets + a] = 1000.0;
                    }
                    continue;
                }

                var mtm_equity = c.cash[i];
                for (0..c.assets) |a| mtm_equity += c.portfolio[i * c.assets + a] * b.mid_prices[a];

                c.last_pnl[i] = mtm_equity - c.equity[i];
                c.equity[i] = mtm_equity;

                const min_capital = if (c.is_bank[i]) 50_000.0 * (1.0 + c.centrality[i]) else 0;

                if (c.is_bank[i] and c.equity[i] < min_capital) {
                    system_stable = false;
                    for (0..c.assets) |a| {
                        const fire_sale = c.portfolio[i * c.assets + a] * 0.1;
                        c.portfolio[i * c.assets + a] -= fire_sale;
                        b.sell_vol[a] += fire_sale;
                        const impact = fire_sale * b.lambda[a];
                        b.mid_prices[a] = @max(0.01, b.mid_prices[a] - impact);
                    }
                }

                const panic_default = (c.intensity[i] > 2.0 and rand.float(f64) < 0.1);

                if (c.equity[i] < 0 or panic_default) {
                    c.is_defaulted[i] = true;
                    c.cooldown[i] = 100 + (rand.int(u32) % 100);
                    tick_defaults += 1;
                    system_stable = false;

                    const shock_multiplier = 1.0 + c.centrality[i];

                    for (0..c.assets) |a| {
                        if (b.frozen_ticks[a] > 0) continue;

                        const fire_sale = c.portfolio[i * c.assets + a];
                        c.portfolio[i * c.assets + a] = 0;
                        b.sell_vol[a] += fire_sale;
                        const impact = fire_sale * b.lambda[a] * shock_multiplier;
                        b.mid_prices[a] = @max(0.01, b.mid_prices[a] - impact);

                        for (0..c.assets) |other| {
                            if (a != other) {
                                const corr = b.correlation_matrix[a * c.assets + other];
                                b.mid_prices[other] = @max(0.01, b.mid_prices[other] - (impact * corr * 0.5));
                            }
                        }
                    }

                    for (0..c.count) |creditor| {
                        const exposure = net.credit_matrix[i * c.count + creditor];
                        if (exposure > 0) {
                            c.cash[creditor] -= exposure * 0.5;
                        }
                    }

                    net.rewire(@as(u32, @intCast(i)), rand);
                    for (0..8) |n| c.intensity[c.neighbors[i * 8 + n]] += 0.8 * shock_multiplier;
                }
            }
            if (!system_stable) cascade_depth += 1;
        }

        cumulative_defaults += tick_defaults;

        var mkt_avg: f64 = 0;
        for (b.mid_prices) |p| mkt_avg += p;
        mkt_avg /= @as(f64, @floatFromInt(b.num_assets));

        if (cb_eval_pending and t >= cb_eval_tick) {
            const defaults_since = cumulative_defaults - defaults_at_cb;
            if (defaults_since > 0) {
                cb_intervention_size *= 1.20;
                cb_trigger_threshold *= 0.90;
            } else {
                cb_intervention_size = @max(1.01, cb_intervention_size * 0.90);
                cb_trigger_threshold *= 1.05;
            }
            std.debug.print(">>> CB LEARNING: Intervention size adjusted to {d:.1}%, trigger threshold lowered to {d:.1}% <<<\n", .{ (cb_intervention_size - 1.0) * 100.0, cb_trigger_threshold });
            cb_eval_pending = false;
        }

        if (mkt_avg < cb_trigger_threshold) {
            if (cb_credibility > 0.3) {
                std.debug.print(">>> CB INTERVENTION (Size: +{d:.1}%, Credibility: {d:.2}) <<<\n", .{ (cb_intervention_size - 1.0) * 100.0, cb_credibility });
                for (0..b.num_assets) |a| b.mid_prices[a] *= cb_intervention_size;
                cb_credibility *= 0.8;
                d.cb_interventions += 1;

                cb_eval_pending = true;
                cb_eval_tick = @intCast(t + 5);
                defaults_at_cb = cumulative_defaults;
            } else {
                std.debug.print(">>> CB FAILED. OUT OF AMMO. <<<\n", .{});
            }
        } else {
            cb_credibility = @min(1.0, cb_credibility + 0.01);
        }

        d.record(@as(u32, @intCast(t)), b, tick_defaults, cascade_depth);
    }
}

