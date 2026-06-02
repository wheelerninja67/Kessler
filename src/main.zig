const std = @import("std");
const bazaar = @import("bazaar.zig");
const crowd = @import("crowd.zig");
const pulse = @import("pulse.zig");
const stash = @import("stash.zig");
const gossip = @import("gossip.zig");
const scenario = @import("scenario.zig");
const diary = @import("diary.zig");
const oracle = @import("oracle.zig");

const CalibratedParams = struct {
    leverage_cap: f64,
    base_depth: u32,
    decay_rate: f64,
    freeze_threshold: f64,
    freeze_duration: u32,
    cb_sensitivity: f64,
    value_buy_threshold: f64,
    cash_fragility: f64,
    market_maker_resilience: f64,
};

pub fn main(init: std.process.Init) !void {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const allocator = arena.allocator();

    var bazaar_config = bazaar.Config{};
    var crowd_config = crowd.Config{};
    var is_validate = false;
    var is_cli = false;
    var is_oracle = false;
    var scenario_path: ?[]const u8 = null;
    var cli_seed: ?u64 = null;
    var cli_ticks: ?u32 = null;
    var cli_agents: ?usize = null;
    // Parse CLI Arguments natively in Zig 0.16.0
    const args = try init.minimal.args.toSlice(allocator);
    var i: usize = 1;
    while (i < args.len) {
        const arg = args[i];

        if (std.mem.eql(u8, arg, "--validate")) {
            is_validate = true;
            i += 1;
        } else if (std.mem.eql(u8, arg, "--cli")) {
            is_cli = true;
            i += 1;
        } else if (std.mem.eql(u8, arg, "--oracle")) {
            is_oracle = true;
            i += 1;
        } else if (std.mem.eql(u8, arg, "--scenario")) {
            i += 1;
            if (i < args.len) {
                scenario_path = args[i];
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--seed")) {
            i += 1;
            if (i < args.len) {
                cli_seed = try std.fmt.parseInt(u64, args[i], 10);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--agents")) {
            i += 1;
            if (i < args.len) {
                cli_agents = try std.fmt.parseInt(usize, args[i], 10);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--ticks")) {
            i += 1;
            if (i < args.len) {
                cli_ticks = try std.fmt.parseInt(u32, args[i], 10);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--freeze-threshold")) {
            i += 1;
            if (i < args.len) {
                bazaar_config.freeze_threshold = try std.fmt.parseFloat(f64, args[i]);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--freeze-duration")) {
            i += 1;
            if (i < args.len) {
                bazaar_config.freeze_duration = try std.fmt.parseInt(u32, args[i], 10);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--cb-sensitivity")) {
            i += 1;
            if (i < args.len) {
                bazaar_config.cb_sensitivity = try std.fmt.parseFloat(f64, args[i]);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--market-maker-resilience")) {
            i += 1;
            if (i < args.len) {
                bazaar_config.market_maker_resilience = try std.fmt.parseFloat(f64, args[i]);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--leverage-cap")) {
            i += 1;
            if (i < args.len) {
                crowd_config.leverage_cap = try std.fmt.parseFloat(f64, args[i]);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--base-depth")) {
            i += 1;
            if (i < args.len) {
                crowd_config.base_depth = try std.fmt.parseInt(u32, args[i], 10);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--decay-rate")) {
            i += 1;
            if (i < args.len) {
                crowd_config.decay_rate = try std.fmt.parseFloat(f64, args[i]);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--value-buy-threshold")) {
            i += 1;
            if (i < args.len) {
                crowd_config.value_buy_threshold = try std.fmt.parseFloat(f64, args[i]);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--cash-fragility")) {
            i += 1;
            if (i < args.len) {
                crowd_config.cash_fragility = try std.fmt.parseFloat(f64, args[i]);
                i += 1;
            }
        } else {
            i += 1;
        }
    }

    var parsed_scenario: ?scenario.ScenarioConfig = null;
    if (scenario_path) |path| {
        const sc = try scenario.loadScenario(allocator, init.io, path);
        parsed_scenario = sc;

        crowd_config.leverage_cap = sc.leverage_cap;
        crowd_config.base_depth = @intFromFloat(sc.base_depth);
        crowd_config.decay_rate = sc.decay_rate;
        crowd_config.cash_fragility = 1.0;

        bazaar_config.freeze_threshold = sc.cb_threshold;
        bazaar_config.market_maker_resilience = sc.resilience;

        std.debug.print("SCENARIO: {s}\n", .{sc.name});
    }

    if (is_validate) {
        var buffer: [4096]u8 = undefined;
        const json_data = std.Io.Dir.readFile(std.Io.Dir.cwd(), init.io, "data/calibrated_params.json", &buffer) catch |err| {
            std.debug.print("Error: Could not read data/calibrated_params.json. Ensure the sweep has run.\n", .{});
            return err;
        };

        const parsed = try std.json.parseFromSlice(CalibratedParams, allocator, json_data, .{ .ignore_unknown_fields = true });
        defer parsed.deinit();

        const p = parsed.value;
        crowd_config.leverage_cap = p.leverage_cap;
        crowd_config.base_depth = p.base_depth;
        crowd_config.decay_rate = p.decay_rate;
        crowd_config.value_buy_threshold = p.value_buy_threshold;
        crowd_config.cash_fragility = p.cash_fragility;

        bazaar_config.freeze_threshold = p.freeze_threshold;
        bazaar_config.freeze_duration = p.freeze_duration;
        bazaar_config.cb_sensitivity = p.cb_sensitivity;
        bazaar_config.market_maker_resilience = p.market_maker_resilience;
    }

    if (is_cli) {
        diary.is_cli_mode = true;
    }

    const num_assets: usize = 7;
    var market = try bazaar.Bazaar.init(allocator, num_assets, bazaar_config);
    defer market.deinit(allocator);

    const agent_count = if (cli_agents != null) cli_agents.? else if (parsed_scenario != null) parsed_scenario.?.agent_count else 1000;
    const ticks = if (cli_ticks != null) cli_ticks.? else if (parsed_scenario != null) parsed_scenario.?.forward_ticks else 1000;
    const seed = if (cli_seed != null) cli_seed.? else 42;

    const CROWD_MEMORY = 1024 * 1024 * 1024; // 1 GB bump arena
    var crowd_stash = try stash.Stash.stashCreate(allocator, CROWD_MEMORY);
    defer crowd_stash.stashDestroy(allocator);

    var agents = try crowd.Crowd.init(&crowd_stash, agent_count, num_assets, crowd_config, seed);
    defer agents.deinit(allocator);

    var net = try gossip.Network.init(&crowd_stash, @intCast(agent_count), seed);

    // =========================================================================
    // SIMULATION EXECUTION
    // =========================================================================
    const shocks = if (parsed_scenario) |sc| sc.shocks else &[_]scenario.Shock{};
    const stats = try pulse.runTickLoop(ticks, &market, &agents, &net, shocks, allocator);

    // Print Telemetry telemetry CRO Report
    diary.printReport();

    if (is_oracle) {
        var active_defaults: usize = 0;
        for (agents.is_defaulted) |def| {
            if (def) active_defaults += 1;
        }
        
        const initial_mbs = 100.0;
        const final_mbs = market.assets[0].price;
        
        const prediction = oracle.Oracle.computeSignals(&market, initial_mbs, final_mbs, active_defaults, agents.cash.len);
        oracle.Oracle.printPrediction(prediction);
    } else if (is_validate) {
        const target = -56.8;
        const diff = @abs(stats.max_drawdown - target);

        const status = if (diff <= 15.0) "CALIBRATED" else if (diff <= 30.0) "PARTIAL" else "NEEDS TUNING";

        std.debug.print("Tolerance Bands: CALIBRATED (<= ±15%), PARTIAL (<= ±30%)\n", .{});
        std.debug.print("VALIDATION: Drawdown {d:.2}% (target {d:.1}%) — [{s}]\n", .{ stats.max_drawdown, target, status });
        std.debug.print("Metrics -> Kurtosis: {d:.2} | Vol Clustering: {d:.3} | Cascade Depth: {d:.1}\n", .{ stats.excess_kurtosis, stats.vol_clustering, stats.cascade_depth });
    } else if (!is_cli) {
        // Output CSV for the sweep script using the extracted metrics
        const output_csv = try std.fmt.allocPrint(allocator, "{d:.2},{d:.2},{d:.3},{d:.1}\n", .{ stats.max_drawdown, stats.excess_kurtosis, stats.vol_clustering, stats.cascade_depth });

        try std.Io.File.stdout().writeStreamingAll(init.io, output_csv);
    }
}
