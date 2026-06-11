const std = @import("std");
const memory = @import("memory.zig");
const agents_mod = @import("agents.zig");
const exchange = @import("exchange.zig");

const stash = memory;
const crowd = agents_mod;
const bazaar = exchange;

pub const Network = struct {
    count: u32,
    row_ptrs: []u32,
    col_indices: []u32,
    repo_haircut: f64, // Repo market haircut
    
    pub fn init(arena: *stash.Stash, count: u32, seed: u64) !Network {
        var prng = std.Random.DefaultPrng.init(seed);
        var random = prng.random();

        var row_ptrs = try arena.stashAlloc(u32, count + 1);
        
        // Dynamic Core-Periphery Topology
        const core_nodes = if (count > 50) 50 else count;
        
        var total_edges: usize = 0;
        var edges_per_node = try arena.stashAlloc(u32, count);
        // We don't free intermediate arrays in a bump arena

        for (0..count) |i| {
            var edges: u32 = 0;
            if (i < core_nodes) {
                edges = @intCast(random.uintAtMost(u32, if (count > 100) 100 else count - 1) + 20); // Core highly connected
            } else {
                edges = @intCast(random.uintAtMost(u32, 5) + 1); // Periphery loosely connected
            }
            if (edges >= count) edges = count - 1;
            edges_per_node[i] = edges;
            total_edges += edges;
        }

        var col_indices = try arena.stashAlloc(u32, total_edges);

        var current_edge: u32 = 0;
        for (0..count) |i| {
            row_ptrs[i] = current_edge;
            for (0..edges_per_node[i]) |_| {
                // Preferential attachment towards core nodes
                var target = random.uintAtMost(u32, count - 1);
                if (random.float(f64) < 0.7 and core_nodes > 0) {
                    target = random.uintAtMost(u32, core_nodes - 1);
                }
                
                if (target == i) target = (target + 1) % count;
                col_indices[current_edge] = target;
                current_edge += 1;
            }
        }
        row_ptrs[count] = current_edge;

        return Network{
            .count = count,
            .row_ptrs = row_ptrs,
            .col_indices = col_indices,
            .repo_haircut = 0.02, // 2% initial haircut
        };
    }

    pub fn propagateDefaults(self: *Network, agents: *crowd.Crowd, market: *bazaar.Bazaar) u32 {
        var cascade_depth: u32 = 0;
        var new_defaults = true;
        
        // 1. Repo Market Contagion
        // If market drops, repo haircuts increase, squeezing periphery liquidity
        if (market.assets[0].last_price > 0 and market.assets[0].price < market.assets[0].last_price) {
            self.repo_haircut += 0.001; 
        } else if (self.repo_haircut > 0.02) {
            self.repo_haircut -= 0.001;
        }

        while (new_defaults) {
            new_defaults = false;
            
            for (0..self.count) |i| {
                if (agents.is_defaulted[i]) continue;
                
                var exposure: f64 = 0.0;
                const start = self.row_ptrs[i];
                const end = self.row_ptrs[i + 1];
                
                // CDO/Counterparty exposure mapping
                for (start..end) |edge| {
                    const j = self.col_indices[edge];
                    if (agents.is_defaulted[j]) {
                        exposure += 1500.0; // Toxic counterparty exposure
                    }
                }

                // Apply repo squeeze
                const collateral_penalty = agents.equity[i] * self.repo_haircut;
                agents.cash[i] -= collateral_penalty;

                if (agents.cash[i] - exposure <= 0) {
                    agents.is_defaulted[i] = true;
                    agents.cash[i] = 0;
                    agents.equity[i] = 0;
                    new_defaults = true;
                    cascade_depth += 1;
                }
            }
        }

        return cascade_depth;
    }
};
