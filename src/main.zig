const std = @import("std");
const exchange = @import("exchange.zig");
const agents_mod = @import("agents.zig");
const engine = @import("engine.zig");
const memory = @import("memory.zig");
const network = @import("network.zig");
const config_parser = @import("config_parser.zig");
const telemetry = @import("telemetry.zig");
const data_loader = @import("data_loader.zig");
const derivatives = @import("derivatives.zig");
const ml = @import("ml.zig");

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

    var exchange_config = exchange.Config{};
    var agents_config = agents_mod.Config{};
    var is_validate = false;
    var is_cli = false;
    var scenario_path: ?[]const u8 = null;
    var market_data_path: ?[]const u8 = null;
    var cli_seed: ?u64 = null;
    var cli_ticks: ?u32 = null;
    var cli_agents: ?usize = null;
    
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
        } else if (std.mem.eql(u8, arg, "--scenario")) {
            i += 1;
            if (i < args.len) {
                scenario_path = args[i];
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--market-data")) {
            i += 1;
            if (i < args.len) {
                market_data_path = args[i];
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
                exchange_config.freeze_threshold = try std.fmt.parseFloat(f64, args[i]);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--freeze-duration")) {
            i += 1;
            if (i < args.len) {
                exchange_config.freeze_duration = try std.fmt.parseInt(u32, args[i], 10);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--cb-sensitivity")) {
            i += 1;
            if (i < args.len) {
                exchange_config.cb_sensitivity = try std.fmt.parseFloat(f64, args[i]);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--market-maker-resilience")) {
            i += 1;
            if (i < args.len) {
                exchange_config.market_maker_resilience = try std.fmt.parseFloat(f64, args[i]);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--leverage-cap")) {
            i += 1;
            if (i < args.len) {
                agents_config.leverage_cap = try std.fmt.parseFloat(f64, args[i]);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--base-depth")) {
            i += 1;
            if (i < args.len) {
                agents_config.base_depth = try std.fmt.parseInt(u32, args[i], 10);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--decay-rate")) {
            i += 1;
            if (i < args.len) {
                agents_config.decay_rate = try std.fmt.parseFloat(f64, args[i]);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--value-buy-threshold")) {
            i += 1;
            if (i < args.len) {
                agents_config.value_buy_threshold = try std.fmt.parseFloat(f64, args[i]);
                i += 1;
            }
        } else if (std.mem.eql(u8, arg, "--cash-fragility")) {
            i += 1;
            if (i < args.len) {
                agents_config.cash_fragility = try std.fmt.parseFloat(f64, args[i]);
                i += 1;
            }
        } else {
            i += 1;
        }
    }

    var parsed_scenario: ?config_parser.ScenarioConfig = null;
    if (scenario_path) |path| {
        const sc = try config_parser.loadScenario(allocator, init.io, path);
        parsed_scenario = sc;

        agents_config.leverage_cap = sc.leverage_cap;
        agents_config.base_depth = @intFromFloat(sc.base_depth);
        agents_config.decay_rate = sc.decay_rate;
        agents_config.cash_fragility = 1.0;

        exchange_config.freeze_threshold = sc.cb_threshold;
        exchange_config.market_maker_resilience = sc.resilience;

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
        agents_config.leverage_cap = p.leverage_cap;
        agents_config.base_depth = p.base_depth;
        agents_config.decay_rate = p.decay_rate;
        agents_config.value_buy_threshold = p.value_buy_threshold;
        agents_config.cash_fragility = p.cash_fragility;

        exchange_config.freeze_threshold = p.freeze_threshold;
        exchange_config.freeze_duration = p.freeze_duration;
        exchange_config.cb_sensitivity = p.cb_sensitivity;
        exchange_config.market_maker_resilience = p.market_maker_resilience;
    }

    if (is_cli) {
        telemetry.is_cli_mode = true;
    }

    var market_data: ?data_loader.MarketData = null;
    if (market_data_path) |path| {
        market_data = try data_loader.MarketData.loadCsv(allocator, init.io, path);
    }

    const num_assets: usize = if (market_data != null) market_data.?.num_assets else 7;
    var market = try exchange.Bazaar.init(allocator, num_assets, exchange_config);
    defer market.deinit(allocator);

    if (market_data) |md| {
        if (md.num_ticks > 0) {
            for (0..num_assets) |j| {
                const init_price = md.prices[0][j];
                market.assets[j].price = init_price;
                market.assets[j].last_price = init_price;
            }
        }
    }

    const agent_count = if (cli_agents != null) cli_agents.? else if (parsed_scenario != null) parsed_scenario.?.agent_count else 1000;
    const ticks = if (cli_ticks != null) cli_ticks.? else if (parsed_scenario != null) parsed_scenario.?.forward_ticks else 1000;
    var dummy: u8 = 0;
    const aslr_harvest = @intFromPtr(&dummy);
    const seed = if (cli_seed != null) cli_seed.? else aslr_harvest;
    std.debug.print("SEED: {d}\n", .{seed});

    const CROWD_MEMORY = 1024 * 1024 * 1024; // 1 GB bump arena
    var agent_memory = try memory.Stash.stashCreate(allocator, CROWD_MEMORY);
    defer agent_memory.stashDestroy(allocator);

    telemetry.tick_history = try agent_memory.stashAlloc(telemetry.TickRecord, ticks);

    var agents = try agents_mod.Crowd.init(&agent_memory, agent_count, num_assets, agents_config, seed);
    var net = try network.Network.init(&agent_memory, @intCast(agent_count), seed);

    const shocks = if (parsed_scenario) |sc| sc.shocks else &[_]config_parser.Shock{};
    const stats = try engine.runTickLoop(ticks, &market, &agents, &net, shocks, allocator, if (market_data != null) &(market_data.?) else null);

    telemetry.printReport();

    if (is_validate) {
        const target = -56.8;
        const diff = @abs(stats.max_drawdown - target);
        const status = if (diff <= 15.0) "CALIBRATED" else if (diff <= 30.0) "PARTIAL" else "NEEDS TUNING";
        std.debug.print("Tolerance Bands: CALIBRATED (<= ±15%), PARTIAL (<= ±30%)\n", .{});
        std.debug.print("VALIDATION: Drawdown {d:.2}% (target {d:.1}%) — [{s}]\n", .{ stats.max_drawdown, target, status });
        std.debug.print("Metrics -> Kurtosis: {d:.2} | Vol Clustering: {d:.3} | Cascade Depth: {d:.1}\n", .{ stats.excess_kurtosis, stats.vol_clustering, stats.cascade_depth });
    } else if (!is_cli) {
        const output_csv = try std.fmt.allocPrint(allocator, "{d:.2},{d:.2},{d:.3},{d:.1}\n", .{ stats.max_drawdown, stats.excess_kurtosis, stats.vol_clustering, stats.cascade_depth });
        try std.Io.File.stdout().writeStreamingAll(init.io, output_csv);
    }
}
