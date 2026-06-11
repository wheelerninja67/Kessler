const std = @import("std");
const memory = @import("memory.zig");
const stash = memory;

pub const Config = struct {
    leverage_cap: f64 = 15.0,
    base_depth: u32 = 1000,
    decay_rate: f64 = 0.05,
    value_buy_threshold: f64 = 0.20,
    cash_fragility: f64 = 0.05,
    ising_temp: f64 = 1.2,       // Temperature for Ising Model
    ising_coupling: f64 = 1.0,   // Interaction strength
};

pub const AgentState = enum(u8) {
    Susceptible = 0,
    Infected = 1,
    Recovered = 2,
};

pub const Crowd = struct {
    config: Config,
    num_assets: usize,
    
    cash: []f64,
    positions: []f64,
    equity: []f64,
    leverage: []f64,
    target_leverage: []f64,
    
    // Ising Model & SIR Epidemiology
    spin: []i8,               // +1 (Bull) or -1 (Bear)
    viral_load: []f64,         // SIR infection probability
    state: []AgentState,       // S, I, or R
    
    is_defaulted: []bool,
    is_hft: []bool,            // High Frequency Trader flag
    
    prng: std.Random.DefaultPrng,

    pub fn init(arena: *stash.Stash, count: usize, num_assets: usize, config: Config, seed: u64) !Crowd {
        var crowd = Crowd{
            .config = config,
            .num_assets = num_assets,
            .cash = try arena.stashAlloc(f64, count),
            .positions = try arena.stashAlloc(f64, count * num_assets),
            .equity = try arena.stashAlloc(f64, count),
            .leverage = try arena.stashAlloc(f64, count),
            .target_leverage = try arena.stashAlloc(f64, count),
            .spin = try arena.stashAlloc(i8, count),
            .viral_load = try arena.stashAlloc(f64, count),
            .state = try arena.stashAlloc(AgentState, count),
            .is_defaulted = try arena.stashAlloc(bool, count),
            .is_hft = try arena.stashAlloc(bool, count),
            .prng = std.Random.DefaultPrng.init(seed),
        };

        var random = crowd.prng.random();
        for (0..count) |i| {
            crowd.cash[i] = random.float(f64) * 10000.0 + 1000.0;
            crowd.target_leverage[i] = random.float(f64) * 5.0 + 2.0;
            crowd.spin[i] = if (random.boolean()) 1 else -1;
            crowd.viral_load[i] = 0.0;
            crowd.state[i] = .Susceptible;
            crowd.is_defaulted[i] = false;
            crowd.is_hft[i] = if (random.float(f64) < 0.05) true else false; // 5% are HFTs
            
            for (0..num_assets) |j| {
                crowd.positions[i * num_assets + j] = random.float(f64) * 50.0;
            }
        }
        return crowd;
    }

    pub fn evaluateValueInvestors(self: *Crowd, price: f64) f64 {
        var total_buy: f64 = 0.0;
        var random = self.prng.random();
        
        for (0..self.cash.len) |i| {
            if (self.is_defaulted[i] or self.state[i] == .Infected) continue;
            
            // Value investors step in if price is heavily discounted and they have positive spin
            if (price < 80.0 and self.spin[i] == 1) {
                if (random.float(f64) < self.config.value_buy_threshold) {
                    const invest = self.cash[i] * 0.1;
                    self.cash[i] -= invest;
                    total_buy += invest;
                }
            }
        }
        return total_buy;
    }
};