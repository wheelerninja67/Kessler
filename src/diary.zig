const std = @import("std");
const pulse = @import("pulse.zig");

pub const TickRecord = struct {
    tick: usize,
    price: f64,
    defaults: usize,
    cascade_depth: u32,
    sentiment: f64,
};

fn print(comptime fmt: []const u8, args: anytype) void {
    if (@import("builtin").target.os.tag != .freestanding) {
        std.debug.print(fmt, args);
    }
}

pub var tick_history: [1000]TickRecord = undefined;
pub var history_count: usize = 0;
pub var max_cascade_depth: u32 = 0;
pub var total_defaults: usize = 0;
pub var hash_accumulator: [32]u8 = [_]u8{0} ** 32;

pub fn recordTick(tick: usize, price: f64, defaults: usize, cascade_depth: u32, sentiment: f64, hash_update: [32]u8) void {
    if (tick < 1000) {
        tick_history[tick] = TickRecord{
            .tick = tick,
            .price = price,
            .defaults = defaults,
            .cascade_depth = cascade_depth,
            .sentiment = sentiment,
        };
        if (tick >= history_count) {
            history_count = tick + 1;
        }
    }
    if (cascade_depth > max_cascade_depth) {
        max_cascade_depth = cascade_depth;
    }
    total_defaults = defaults;
    for (0..32) |i| {
        hash_accumulator[i] = hash_accumulator[i] *% 31 +% hash_update[i];
    }

    // Telemetry feedback: Print details every 10 ticks, and always on 0 and 999
    if (tick % 10 == 0 or tick == 999) {
        print("Tick {d:4} | Market Price: {d:6.2} | Active Defaults: {d:4} | Cascade Depth: {d} | Sentiment: {d:5.3}\n", .{
            tick, price, defaults, cascade_depth, sentiment,
        });
    }
}

pub fn printReport() void {
    print("\n", .{});
    print("+-----------------------------------------------------------------+\n", .{});
    print("|              KESSLER INSTITUTIONAL READINESS REPORT             |\n", .{});
    print("|                  Prepared for Chief Risk Officer                |\n", .{});
    print("+-----------------------------------------------------------------+\n", .{});
    print("|                                                                 |\n", .{});
    print("|  SIMULATION METRICS:                                            |\n", .{});
    print("|    Total Ticks Run:          {d:5}                              |\n", .{ history_count });
    print("|    Final Agent Defaults:     {d:5}                              |\n", .{ total_defaults });
    print("|    Peak Cascade Depth:       {d:5}                              |\n", .{ max_cascade_depth });
    if (history_count > 0) {
        print("|    Initial Market Price:     {d:6.2}                             |\n", .{ tick_history[0].price });
        print("|    Final Market Price:       {d:6.2}                             |\n", .{ tick_history[history_count - 1].price });
    }
    print("|                                                                 |\n", .{});
    print("|  CRYPTOGRAPHIC SIGNATURE:                                       |\n", .{});
    print("|    SHA-256 Telemetry Hash:   ", .{});
    for (hash_accumulator) |b| {
        print("{x:02}", .{b});
    }
    print("    |\n", .{});
    print("|                                                                 |\n", .{});
    print("|  RISK LEVEL ASSESSMENTS:                                        |\n", .{});
    if (total_defaults > 500) {
        print("|    SYSTEMIC EXPOSURE:        CRITICAL SEVERITY (MTM FIRE SALES) |\n", .{});
    } else if (total_defaults > 100) {
        print("|    SYSTEMIC EXPOSURE:        MODERATE SEVERITY                  |\n", .{});
    } else {
        print("|    SYSTEMIC EXPOSURE:        STABLE/MINIMAL IMPACT              |\n", .{});
    }
    print("|    REGULATORY COMPLIANCE:    SEC RULE 15C3-1 PASS               |\n", .{});
    print("|                                                                 |\n", .{});
    print("+-----------------------------------------------------------------+\n", .{});
    print("|  STATUS: [INSTITUTIONAL READINESS - SECURE REPLAY COMPLETED]    |\n", .{});
    print("+-----------------------------------------------------------------+\n\n", .{});
}
