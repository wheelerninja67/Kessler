const std = @import("std");
const stash = @import("stash.zig");
const crowd = @import("crowd.zig");

pub const Network = struct {
    count: u32,
    credit_matrix: []f64,
    initial_edges: u32,
    severed_edges: u32,

    pub fn init(arena: *stash.Stash, count: u32, seed: u64) !Network {
        var prng = std.Random.DefaultPrng.init(seed);
        const rand = prng.random();

        var net = Network{
            .count = count,
            .credit_matrix = try arena.stashAlloc(f64, count * count),
            .initial_edges = 0,
            .severed_edges = 0,
        };

        var edges: u32 = 0;
        for (0..count) |i| {
            for (0..count) |j| {
                if (i != j and rand.float(f64) < 0.05) {
                    net.credit_matrix[i * count + j] = rand.float(f64) * 5000.0;
                    edges += 1;
                } else {
                    net.credit_matrix[i * count + j] = 0;
                }
            }
        }
        net.initial_edges = edges;
        return net;
    }

    pub fn rewire(self: *Network, defaulted_agent: u32, rand: std.Random) void {
        for (0..self.count) |j| {
            if (self.credit_matrix[defaulted_agent * self.count + j] > 0) {
                self.credit_matrix[defaulted_agent * self.count + j] = 0;
                self.severed_edges += 1; // Track contagion damage
                const new_counterparty = rand.int(u32) % self.count;
                self.credit_matrix[defaulted_agent * self.count + new_counterparty] = rand.float(f64) * 2000.0;
            }
        }
    }

    pub fn printNetworkHealth(self: *Network, c: *crowd.Crowd) void {
        var survivors: u32 = 0;
        var total_degree: u32 = 0;
        var max_centrality: f64 = -1.0;
        var most_central_id: u32 = 0;

        for (0..self.count) |i| {
            if (!c.is_defaulted[i]) {
                survivors += 1;
                if (c.centrality[i] > max_centrality) {
                    max_centrality = c.centrality[i];
                    most_central_id = @intCast(i);
                }
                var degree: u32 = 0;
                for (0..self.count) |j| {
                    if (self.credit_matrix[i * self.count + j] > 0) degree += 1;
                    if (self.credit_matrix[j * self.count + i] > 0) degree += 1;
                }
                total_degree += degree;
            }
        }
        const avg_degree = if (survivors > 0) @as(f64, @floatFromInt(total_degree)) / @as(f64, @floatFromInt(survivors)) else 0.0;

        std.debug.print("\n=== NETWORK HEALTH REPORT ===\n", .{});
        std.debug.print("Total Initial Edges: {d}\n", .{self.initial_edges});
        std.debug.print("Edges Severed (Defaults): {d}\n", .{self.severed_edges});
        std.debug.print("Avg Survivor Degree: {d:.2}\n", .{avg_degree});
        std.debug.print("Most Central Survivor: Agent {d} (Centrality: {d:.4})\n", .{ most_central_id, max_centrality });
    }
};
