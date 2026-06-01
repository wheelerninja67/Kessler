const std = @import("std");
const stash = @import("stash.zig");
const crowd = @import("crowd.zig");
const bazaar = @import("bazaar.zig");

pub const Network = struct {
    count: u32,
    row_ptrs: []u32,
    col_indices: []u32,
    exposures: []f64,
    initial_edges: u32,
    severed_edges: u32,

    pub fn init(arena: *stash.Stash, count: u32, seed: u64) !Network {
        var prng = std.Random.DefaultPrng.init(seed);
        const rand = prng.random();

        const max_degree = 40;
        const max_edges = @as(usize, count) * max_degree;

        var net = Network{
            .count = count,
            .row_ptrs = try arena.stashAlloc(u32, count + 1),
            .col_indices = try arena.stashAlloc(u32, max_edges),
            .exposures = try arena.stashAlloc(f64, max_edges),
            .initial_edges = 0,
            .severed_edges = 0,
        };

        var current_edge: u32 = 0;
        for (0..count) |i| {
            net.row_ptrs[i] = current_edge;
            
            const degree = (rand.int(usize) % 20) + 10; // 10 to 30 edges
            
            for (0..degree) |_| {
                if (current_edge >= max_edges) break;
                
                const creditor = rand.int(u32) % count;
                if (i == creditor) continue;
                
                net.col_indices[current_edge] = creditor;
                net.exposures[current_edge] = rand.float(f64) * 5000.0;
                current_edge += 1;
            }
        }
        net.row_ptrs[count] = current_edge;
        net.initial_edges = current_edge;
        return net;
    }

    pub fn propagateDefaults(self: *Network, c: *crowd.Crowd, market: *bazaar.Bazaar) u32 {
        var cascade_depth: u32 = 0;
        var new_defaults = true;

        while (new_defaults) {
            new_defaults = false;
            var default_triggered_this_round = false;

            for (0..self.count) |i| {
                if (c.is_defaulted[i]) {
                    const start_idx = self.row_ptrs[i];
                    const end_idx = self.row_ptrs[i + 1];
                    
                    for (start_idx..end_idx) |edge_idx| {
                        const j = self.col_indices[edge_idx];
                        if (c.is_defaulted[j]) continue;

                        const exposure = self.exposures[edge_idx];
                        if (exposure > 0) {
                            c.cash[j] -= exposure;
                            
                            var asset_value: f64 = 0.0;
                            for (0..c.num_assets) |a| {
                                asset_value += c.positions[j * c.num_assets + a] * market.assets[a].price;
                            }
                            c.equity[j] = c.cash[j] + asset_value;

                            self.exposures[edge_idx] = 0.0;
                            self.severed_edges += 1;

                            if (c.equity[j] <= 0.0) {
                                c.is_defaulted[j] = true;
                                default_triggered_this_round = true;
                                new_defaults = true;
                            }
                        }
                    }
                }
            }

            if (default_triggered_this_round) {
                cascade_depth += 1;
            }
        }

        return cascade_depth;
    }
};
