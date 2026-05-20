const std = @import("std");
const stash = @import("stash.zig");
const crowd = @import("crowd.zig");
const pulse = @import("pulse.zig");

test "Axiom of Determinism: Identical Seeds Produce Identical Universes" {
    const SEED: u64 = 99942;
    const config = pulse.Config{ .agents = 500, .assets = 5, .ticks = 100, .seed = SEED, .threads = 1 };

    // --- UNIVERSE ALPHA ---
    var arena_alpha = try stash.Stash.stashCreate(16 * 1024 * 1024);
    defer arena_alpha.stashDestroy();
    // CHANGED to const:
    const crowd_alpha = try crowd.Crowd.init(&arena_alpha, config.agents, config.assets, config.seed);

    var hash_alpha: u64 = 0;
    for (crowd_alpha.equity) |eq| hash_alpha +%= @as(u64, @bitCast(eq));

    // --- UNIVERSE BETA ---
    var arena_beta = try stash.Stash.stashCreate(16 * 1024 * 1024);
    defer arena_beta.stashDestroy();
    // CHANGED to const:
    const crowd_beta = try crowd.Crowd.init(&arena_beta, config.agents, config.assets, config.seed);

    var hash_beta: u64 = 0;
    for (crowd_beta.equity) |eq| hash_beta +%= @as(u64, @bitCast(eq));

    // --- THE ASSERTION ---
    // If this fails, Project Kessler is broken.
    try std.testing.expectEqual(hash_alpha, hash_beta);
}
