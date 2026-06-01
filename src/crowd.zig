const std = @import("std");
const stash = @import("stash.zig");

pub const Config = struct {
    leverage_cap: f64 = 15.0,
    base_depth: u32 = 5000,
    decay_rate: f64 = 0.05,
    value_buy_threshold: f64 = 0.5,
    cash_fragility: f64 = 1.0,
};

pub const Crowd = struct {
    num_assets: usize,
    cash: []f64,
    equity: []f64,
    leverage: []f64,
    positions: []f64,
    is_defaulted: []bool,
    target_leverage: []f64,

    config: Config,
    initial_price: f64 = 100.0,

    pub fn init(arena: *stash.Stash, num_agents: usize, num_assets: usize, config: Config, seed: u64) !Crowd {
        var prng = std.Random.DefaultPrng.init(seed);
        const rand = prng.random();

        const cash = try arena.stashAlloc(f64, num_agents);
        const equity = try arena.stashAlloc(f64, num_agents);
        const leverage = try arena.stashAlloc(f64, num_agents);
        const positions = try arena.stashAlloc(f64, num_agents * num_assets);
        const is_defaulted = try arena.stashAlloc(bool, num_agents);
        const target_leverage = try arena.stashAlloc(f64, num_agents);

        for (0..num_agents) |i| {
            cash[i] = 10000.0 * config.cash_fragility * (0.8 + rand.float(f64) * 0.4);
            var total_asset_value: f64 = 0.0;
            for (0..num_assets) |j| {
                const pos = 100.0 / @as(f64, @floatFromInt(num_assets));
                positions[i * num_assets + j] = pos;
                total_asset_value += pos * 100.0;
            }
            target_leverage[i] = config.leverage_cap * 0.8;
            equity[i] = cash[i] + total_asset_value;
            leverage[i] = total_asset_value / equity[i];
            is_defaulted[i] = false;
        }

        return Crowd{
            .num_assets = num_assets,
            .cash = cash,
            .equity = equity,
            .leverage = leverage,
            .positions = positions,
            .is_defaulted = is_defaulted,
            .target_leverage = target_leverage,
            .config = config,
        };
    }

    pub fn deinit(self: *Crowd, allocator: std.mem.Allocator) void {
        _ = self;
        _ = allocator;
    }

    pub fn evaluateValueInvestors(self: *Crowd, current_price: f64) f64 {
        var buy_pressure: f64 = 0.0;
        const trigger_price = self.initial_price * self.config.value_buy_threshold;
        if (current_price < trigger_price) {
            buy_pressure += (trigger_price - current_price) * 10.0;
        }
        return buy_pressure;
    }
};