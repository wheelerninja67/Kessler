const std = @import("std");
const stash = @import("stash.zig");
const market_data = @import("market_data.zig");
const crowd = @import("crowd.zig");
const bazaar = @import("bazaar.zig");
const gossip = @import("gossip.zig");
const diary = @import("diary.zig");
const pulse = @import("pulse.zig");

pub fn main() !void {
    // ====================================================================
    // HARDWIRED ORACLE CONFIGURATION
    // Completely bypassed broken Zig 0.16.0 CLI parsers to guarantee execution.
    // Equivalent to running: zig build run -- --replay --seed 42 --ticks 200 --csv
    // ====================================================================
    var config = pulse.Config{
        .agents = 1000,
        .assets = 37,
        .ticks = 200, // <-- Hardwired
        .seed = 42, // <-- Hardwired
        .start_tick = 0,
    };

    const use_calibrated = true;
    const do_replay = true; // <-- Hardwired
    const do_csv = true; // <-- Hardwired

    // Initialize the master memory arena
    var arena = try stash.Stash.stashCreate(256 * 1024 * 1024);
    defer arena.stashDestroy();

    std.debug.print("==================================================\n", .{});
    std.debug.print("PROJECT KESSLER: APEX ORACLE ENGINE\n", .{});
    std.debug.print("SEED: {d} (HARDWIRED)\n", .{config.seed});
    std.debug.print("FORWARD TICKS: {d} (HARDWIRED)\n", .{config.ticks});
    std.debug.print("CSV EXPORT: ENABLED\n", .{});
    std.debug.print("==================================================\n", .{});

    std.debug.print("[*] Ingesting frozen historical market data...\n", .{});
    const market = try market_data.MarketData.init(&arena, "data");

    config.assets = market.num_tickers;

    std.debug.print("[*] Allocating Struct-of-Arrays (SoA) topology...\n", .{});

    var c: crowd.Crowd = undefined;
    var b: bazaar.Bazaar = undefined;

    if (use_calibrated) {
        c = try crowd.Crowd.initCalibrated(&arena, config.agents, config.assets, &market, config.seed);
        b = try bazaar.Bazaar.initCalibrated(&arena, config.assets, &market, config.seed);
    } else {
        c = try crowd.Crowd.init(&arena, config.agents, config.assets, config.seed);
        b = try bazaar.Bazaar.init(&arena, config.assets, config.seed);
    }

    var net = try gossip.Network.init(&arena, config.agents, config.seed);

    const total_diary_ticks = if (do_replay) market.num_days + config.ticks else config.ticks;
    var d = try diary.Diary.init(&arena, total_diary_ticks, config.assets);

    if (do_replay) {
        std.debug.print("\n[*] Commencing Historical Replay Mode...\n", .{});
        config.start_tick = try pulse.replayHistory(&c, &b, &d, &market);
    }

    std.debug.print("[*] Igniting Gai-Kapadia execution loop (Forward Stress Testing)...\n\n", .{});
    try pulse.runSimulation(&c, &b, &net, &d, config);

    d.printStylizedFacts();
    d.printVolatilitySurface(&b);
    d.printTailRisk();
    net.printNetworkHealth(&c);
    d.printCROReport(config.seed, config.agents, config.ticks);
    d.printHash();

    if (do_csv) {
        d.exportCSV();
    }

    std.debug.print("\n[SUCCESS] Execution complete.\n", .{});
}
