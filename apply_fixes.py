import os
import re

def read_file(path):
    with open(path, 'r') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w') as f:
        f.write(content)

# 1. oracle.zig
# Remove the file
if os.path.exists("src/oracle.zig"):
    os.remove("src/oracle.zig")

# 2. main.zig
main_code = read_file("src/main.zig")
main_code = main_code.replace('const oracle = @import("oracle.zig");\n', "")
main_code = main_code.replace('var is_oracle = false;\n', "")
main_code = main_code.replace('} else if (std.mem.eql(u8, arg, "--oracle")) {\n            is_oracle = true;\n            i += 1;\n        ', "")

oracle_block = """    if (is_oracle) {
        var active_defaults: usize = 0;
        for (agents.is_defaulted) |def| {
            if (def) active_defaults += 1;
        }
        
        const initial_mbs = 100.0;
        const final_mbs = market.assets[0].price;
        
        const prediction = oracle.Oracle.computeSignals(&market, initial_mbs, final_mbs, active_defaults, agents.cash.len);
        oracle.Oracle.printPrediction(prediction);
    } else if (is_validate) {"""
main_code = main_code.replace(oracle_block, "    if (is_validate) {")

# Fix 6: ASLR Entropy in main.zig
seed_logic_old = "const seed = if (cli_seed != null) cli_seed.? else 42;"
seed_logic_new = """var dummy: u8 = 0;
    const aslr_harvest = @intFromPtr(&dummy) ^ @as(u64, @bitCast(std.time.milliTimestamp()));
    const seed = if (cli_seed != null) cli_seed.? else aslr_harvest;
    std.debug.print("SEED: {d}\\n", .{seed});"""
main_code = main_code.replace(seed_logic_old, seed_logic_new)

# Fix 5: Telemetry Overflow in main.zig
stash_alloc_tick_history = """    var crowd_stash = try stash.Stash.stashCreate(allocator, CROWD_MEMORY);
    defer crowd_stash.stashDestroy(allocator);

    diary.tick_history = try crowd_stash.stashAlloc(diary.TickRecord, ticks);"""
main_code = main_code.replace("""    var crowd_stash = try stash.Stash.stashCreate(allocator, CROWD_MEMORY);
    defer crowd_stash.stashDestroy(allocator);""", stash_alloc_tick_history)

# Fix 8: deinit stub in main.zig
main_code = main_code.replace("defer agents.deinit(allocator);\n\n", "\n")
write_file("src/main.zig", main_code)


# 3. pulse.zig (Fix 2: Volatility Clustering)
pulse_code = read_file("src/pulse.zig")
vol_old = """        // Compute valid Log-Returns, discarding zero-movement ticks
        if (prev_price > 0.01 and tick > 50) {
            if (@abs(new_price - prev_price) > 1e-6) {
                const tick_return = @log(new_price / prev_price);
                returns[valid_ticks] = tick_return;
                valid_ticks += 1;
            }
        }"""
vol_new = """        // Compute valid Log-Returns, DO NOT discard zero-movement ticks
        if (prev_price > 0.01 and tick > 50) {
            var tick_return: f64 = 0.0;
            if (@abs(new_price - prev_price) > 1e-6) {
                tick_return = @log(new_price / prev_price);
            }
            returns[valid_ticks] = tick_return;
            valid_ticks += 1;
        }"""
pulse_code = pulse_code.replace(vol_old, vol_new)

# Fix 3: Implement Hawkes and Herd in pulse.zig
herd_code = """        // 4. Gai-Kapadia Network Contagion Cascade"""
herd_new = """        // 3.5 Hawkes Intensity Decay & Herd Behavior
        for (0..agents.cash.len) |i| {
            if (agents.is_defaulted[i]) continue;
            agents.intensity[i] *= 0.95;
            
            const start_idx = net.row_ptrs[i];
            const end_idx = net.row_ptrs[i + 1];
            var neighbor_theta_sum: f64 = 0.0;
            var neighbor_count: f64 = 0.0;
            for (start_idx..end_idx) |edge_idx| {
                const j = net.col_indices[edge_idx];
                neighbor_theta_sum += agents.theta[j];
                neighbor_count += 1.0;
            }
            if (neighbor_count > 0.0) {
                const avg_theta = neighbor_theta_sum / neighbor_count;
                agents.theta[i] = 0.8 * agents.theta[i] + 0.2 * avg_theta;
            }
        }

        // 4. Gai-Kapadia Network Contagion Cascade"""
pulse_code = pulse_code.replace(herd_code, herd_new)
write_file("src/pulse.zig", pulse_code)


# 4. crowd.zig
crowd_code = read_file("src/crowd.zig")
crowd_code = crowd_code.replace("    target_leverage: []f64,\n", "    target_leverage: []f64,\n    intensity: []f64,\n    theta: []f64,\n")

alloc_code = """        const target_leverage = try arena.stashAlloc(f64, num_agents);"""
alloc_new = """        const target_leverage = try arena.stashAlloc(f64, num_agents);
        const intensity = try arena.stashAlloc(f64, num_agents);
        const theta = try arena.stashAlloc(f64, num_agents);"""
crowd_code = crowd_code.replace(alloc_code, alloc_new)

init_code = """            target_leverage[i] = config.leverage_cap * 0.8;"""
init_new = """            target_leverage[i] = config.leverage_cap * 0.8;
            intensity[i] = 0.0;
            theta[i] = 0.5;"""
crowd_code = crowd_code.replace(init_code, init_new)

ret_code = """            .target_leverage = target_leverage,
            .config = config,
        };"""
ret_new = """            .target_leverage = target_leverage,
            .intensity = intensity,
            .theta = theta,
            .config = config,
        };"""
crowd_code = crowd_code.replace(ret_code, ret_new)

deinit_code = """    pub fn deinit(self: *Crowd, allocator: std.mem.Allocator) void {
        _ = self;
        _ = allocator;
    }

"""
crowd_code = crowd_code.replace(deinit_code, "")
write_file("src/crowd.zig", crowd_code)


# 5. bazaar.zig
bazaar_code = read_file("src/bazaar.zig")
bazaar_code = bazaar_code.replace("    config: Config,\n", "    config: Config,\n    vpin_buy_history: [50]f64 = [_]f64{0.0} ** 50,\n    vpin_sell_history: [50]f64 = [_]f64{0.0} ** 50,\n    vpin_idx: usize = 0,\n")

submit_old = """        if (asset.is_frozen) {"""
submit_new = """        self.vpin_buy_history[self.vpin_idx] += if (is_buy) volume else 0.0;
        self.vpin_sell_history[self.vpin_idx] += if (!is_buy) volume else 0.0;
        
        if (asset.is_frozen) {"""
bazaar_code = bazaar_code.replace(submit_old, submit_new)

price_impact_old = """            const direction: f64 = if (is_buy) 1.0 else -1.0;
            asset.price += direction * volume * asset.kyle_lambda;"""
price_impact_new = """            const direction: f64 = if (is_buy) 1.0 else -1.0;
            const initial_depth = 1000.0;
            var depth_factor: f64 = 1.0;
            if (asset.book_depth < initial_depth * 0.5) {
                depth_factor = 1.0 + (1.0 - (asset.book_depth / initial_depth)) * 2.0;
            }
            const effective_lambda = asset.kyle_lambda * depth_factor;
            asset.price += direction * volume * effective_lambda;"""
bazaar_code = bazaar_code.replace(price_impact_old, price_impact_new)

vpin_old = """    pub fn updateMarketMicrostructure(self: *Bazaar) void {"""
vpin_new = """    pub fn updateMarketMicrostructure(self: *Bazaar) void {
        var total_buy: f64 = 0.0;
        var total_sell: f64 = 0.0;
        for (self.vpin_buy_history) |v| total_buy += v;
        for (self.vpin_sell_history) |v| total_sell += v;
        const total_vol = total_buy + total_sell;
        
        if (total_vol > 0.0) {
            const vpin = @abs(total_buy - total_sell) / total_vol;
            if (vpin > 0.8) {
                std.debug.print("VPIN TOXICITY: {d:.4}\\n", .{vpin});
            }
        }
        
        self.vpin_idx = (self.vpin_idx + 1) % 50;
        self.vpin_buy_history[self.vpin_idx] = 0.0;
        self.vpin_sell_history[self.vpin_idx] = 0.0;
"""
bazaar_code = bazaar_code.replace(vpin_old, vpin_new)
write_file("src/bazaar.zig", bazaar_code)


# 6. gossip.zig
gossip_code = read_file("src/gossip.zig")
gossip_code = gossip_code.replace("    severed_edges: u32,\n", "    severed_edges: u32,\n    prng: std.Random.Xoshiro256,\n")
gossip_code = gossip_code.replace("        var prng = std.Random.DefaultPrng.init(seed);\n        const rand = prng.random();", "        var prng = std.Random.DefaultPrng.init(seed);\n        const rand = prng.random();")

ret_net_old = """            .severed_edges = 0,
        };"""
ret_net_new = """            .severed_edges = 0,
            .prng = prng,
        };"""
gossip_code = gossip_code.replace(ret_net_old, ret_net_new)

rewire_old = """                            if (c.equity[j] <= 0.0) {
                                c.is_defaulted[j] = true;
                                default_triggered_this_round = true;
                                new_defaults = true;
                            }"""
rewire_new = """                            if (c.equity[j] <= 0.0) {
                                c.is_defaulted[j] = true;
                                default_triggered_this_round = true;
                                new_defaults = true;

                                // Increase intensity of neighbors of j
                                const start_j = self.row_ptrs[j];
                                const end_j = self.row_ptrs[j + 1];
                                for (start_j..end_j) |n_idx| {
                                    const neighbor = self.col_indices[n_idx];
                                    c.intensity[neighbor] += 0.2;
                                }

                                // Contagion rewiring
                                const rand = self.prng.random();
                                if (rand.float(f64) < 0.10) {
                                    const new_target = rand.int(u32) % self.count;
                                    if (!c.is_defaulted[new_target] and new_target != i) {
                                        self.col_indices[edge_idx] = new_target;
                                        self.exposures[edge_idx] = 1000.0;
                                    }
                                }
                            }"""
gossip_code = gossip_code.replace(rewire_old, rewire_new)
write_file("src/gossip.zig", gossip_code)


# 7. diary.zig
diary_code = read_file("src/diary.zig")
diary_old = """pub var tick_history: [1000]TickRecord = undefined;"""
diary_new = """pub var tick_history: []TickRecord = &[_]TickRecord{};"""
diary_code = diary_code.replace(diary_old, diary_new)

diary_limit_old = """    if (tick < 1000) {"""
diary_limit_new = """    if (tick < tick_history.len) {"""
diary_code = diary_code.replace(diary_limit_old, diary_limit_new)
write_file("src/diary.zig", diary_code)


# 8. stash.zig
stash_code = read_file("src/stash.zig")
stash_dead = """    pub fn stashBytesRemaining(self: *const Stash) usize {
        return self.total_size - self.offset;
    }
"""
stash_code = stash_code.replace(stash_dead, "")
write_file("src/stash.zig", stash_code)


# 9. scenario.zig
scenario_code = read_file("src/scenario.zig")
scenario_comment = """// WARNING: This is a strict flat key-value parser.
// Nested YAML, trailing comments, or varying indentation will BREAK parsing.

"""
if not "WARNING" in scenario_code:
    scenario_code = scenario_comment + scenario_code
write_file("src/scenario.zig", scenario_code)

print("Applied all fixes to zig source files.")
