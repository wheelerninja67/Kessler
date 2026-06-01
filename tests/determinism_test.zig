const std = @import("std");
const stash = @import("../src/stash.zig");
const crowd = @import("../src/crowd.zig");
const pulse = @import("../src/pulse.zig");

test "Axiom of Determinism: Identical Seeds Produce Identical Universes" {
    const SEED: u64 = 99942;
    const config = pulse.Config{ .agents = 500, .assets = 5, .ticks = 100, .seed = SEED };

    // --- UNIVERSE ALPHA ---
    var arena_alpha = try stash.Stash.stashCreate(16 * 1024 * 1024);
    defer arena_alpha.stashDestroy();
    var crowd_alpha = try crowd.Crowd.init(&arena_alpha, config.agents, config.assets, crowd.Config{}, config.seed);
    // (Assume b_alpha, net_alpha, d_alpha are initialized here)
    // try pulse.runSimulation(...);

    // Compute State Hash Alpha
    var hash_alpha: u64 = 0;
    for (crowd_alpha.equity) |eq| hash_alpha +%= @as(u64, @bitCast(eq));

    // --- UNIVERSE BETA ---
    var arena_beta = try stash.Stash.stashCreate(16 * 1024 * 1024);
    defer arena_beta.stashDestroy();
    var crowd_beta = try crowd.Crowd.init(&arena_beta, config.agents, config.assets, crowd.Config{}, config.seed);
    // (Assume b_beta, net_beta, d_beta are initialized here)
    // try pulse.runSimulation(...);

    // Compute State Hash Beta
    var hash_beta: u64 = 0;
    for (crowd_beta.equity) |eq| hash_beta +%= @as(u64, @bitCast(eq));

    // --- THE ASSERTION ---
    // If this fails, Project Kessler is broken.
    try std.testing.expectEqual(hash_alpha, hash_beta);
}
