const std = @import("std");

pub const Config = struct {
    freeze_threshold: f64 = 0.80,
    freeze_duration: u32 = 5,
    cb_sensitivity: f64 = 1.0,
    market_maker_resilience: f64 = 0.05,
    kappa_heston: f64 = 2.0,     // Mean reversion speed of volatility
    theta_heston: f64 = 0.04,    // Long term mean volatility (20% annualized -> 0.04 variance)
    xi_heston: f64 = 0.1,        // Volatility of volatility (Vol of vol)
    rho_heston: f64 = -0.7,      // Correlation between price and volatility
    vasicek_a: f64 = 0.1,        // Mean reversion speed of interest rate
    vasicek_b: f64 = 0.05,       // Long term mean interest rate (5%)
    vasicek_sigma: f64 = 0.01,   // Volatility of interest rate
};

pub const Asset = struct {
    price: f64,
    last_price: f64,
    variance: f64,             // Heston stochastic variance
    base_price: f64,
    book_depth: f64,
    kyle_lambda: f64,
    is_frozen: bool,
    freeze_timer: u32,
    frozen_sell_vol: f64,
    
    // Statistical LOB properties
    bid_ask_spread: f64,
    resting_bids: f64,
    resting_asks: f64,
};

pub const Bazaar = struct {
    assets: []Asset,
    config: Config,
    prng: std.Random.DefaultPrng,
    risk_free_rate: f64,
    money_supply_m2: f64,

    pub fn init(allocator: std.mem.Allocator, num_assets: usize, config: Config) !Bazaar {
        var assets = try allocator.alloc(Asset, num_assets);
        for (0..num_assets) |i| {
            assets[i] = Asset{
                .price = 100.0,
                .last_price = 100.0,
                .variance = config.theta_heston, // Start at long term mean
                .base_price = 100.0,
                .book_depth = 50000.0,
                .kyle_lambda = 0.0001,
                .is_frozen = false,
                .freeze_timer = 0,
                .frozen_sell_vol = 0.0,
                .bid_ask_spread = 0.01,
                .resting_bids = 25000.0,
                .resting_asks = 25000.0,
            };
        }
        
        return Bazaar{
            .assets = assets,
            .config = config,
            .prng = std.Random.DefaultPrng.init(0), // Seeded later if needed
            .risk_free_rate = config.vasicek_b,
            .money_supply_m2 = 1_000_000_000.0, // 1 Billion synthetic M2 base
        };
    }

    pub fn deinit(self: *Bazaar, allocator: std.mem.Allocator) void {
        allocator.free(self.assets);
    }

    pub fn submitOrder(self: *Bazaar, asset_idx: u32, is_buy: bool, volume: f64) void {
        if (asset_idx >= self.assets.len) return;
        var asset = &self.assets[asset_idx];

        if (asset.is_frozen) {
            if (!is_buy) {
                asset.frozen_sell_vol += volume;
            }
            return;
        }

        // 1. Limit Order Book (LOB) Execution via Cont-Stoikov model abstraction
        // Instead of instantaneous Kyle's Lambda, we eat into resting liquidity
        var executed_volume: f64 = 0.0;
        var slippage: f64 = 0.0;
        
        if (is_buy) {
            if (volume <= asset.resting_asks) {
                asset.resting_asks -= volume;
                executed_volume = volume;
            } else {
                executed_volume = asset.resting_asks;
                slippage = (volume - asset.resting_asks) * asset.kyle_lambda;
                asset.resting_asks = 0;
            }
            asset.price += (asset.bid_ask_spread / 2.0) + slippage;
        } else {
            if (volume <= asset.resting_bids) {
                asset.resting_bids -= volume;
                executed_volume = volume;
            } else {
                executed_volume = asset.resting_bids;
                slippage = (volume - asset.resting_bids) * asset.kyle_lambda;
                asset.resting_bids = 0;
            }
            asset.price -= (asset.bid_ask_spread / 2.0) + slippage;
        }

        if (asset.price < 0.01) asset.price = 0.01;

        // Spread widens based on slippage (Market Makers retreating)
        asset.bid_ask_spread += slippage * 0.1;
    }

    pub fn updateMarketMicrostructure(self: *Bazaar) void {
        const dt = 1.0 / 252.0; // 1 trading day as time step
        var random = self.prng.random();

        // 1. Vasicek Interest Rate Model (Stochastic Yield)
        const dW_r = random.floatNorm(f64) * @sqrt(dt);
        const dr = self.config.vasicek_a * (self.config.vasicek_b - self.risk_free_rate) * dt + self.config.vasicek_sigma * dW_r;
        self.risk_free_rate += dr;
        if (self.risk_free_rate < 0.0) self.risk_free_rate = 0.0; // Zero lower bound

        for (self.assets) |*asset| {
            if (asset.is_frozen) {
                asset.freeze_timer -= 1;
                if (asset.freeze_timer == 0) {
                    asset.is_frozen = false;
                    asset.price *= 0.95; // Gap down on unfreeze
                    asset.frozen_sell_vol = 0;
                }
                continue;
            }

            // 2. Heston Stochastic Volatility Model
            // Generate two correlated Wiener processes
            const dW1 = random.floatNorm(f64) * @sqrt(dt);
            const dZ = random.floatNorm(f64) * @sqrt(dt);
            const dW2 = self.config.rho_heston * dW1 + @sqrt(1.0 - self.config.rho_heston * self.config.rho_heston) * dZ;

            // Variance process (CIR)
            const vol_drift = self.config.kappa_heston * (self.config.theta_heston - asset.variance) * dt;
            const vol_diffusion = self.config.xi_heston * @sqrt(@max(asset.variance, 0.0)) * dW2;
            asset.variance += vol_drift + vol_diffusion;
            if (asset.variance < 0.0001) asset.variance = 0.0001; // Reflective boundary

            // Asset price process (Heston geometric brownian motion component)
            // Note: Endogenous drift is driven by agents, we only add the Heston stochastic diffusion
            const price_diffusion = @sqrt(asset.variance) * asset.price * dW1;
            asset.price += price_diffusion;
            if (asset.price < 0.01) asset.price = 0.01;

            // Circuit Breaker Logic
            const drop = (asset.last_price - asset.price) / asset.last_price;
            if (drop > self.config.freeze_threshold * self.config.cb_sensitivity) {
                asset.is_frozen = true;
                asset.freeze_timer = self.config.freeze_duration;
            }

            // Market Makers replenish LOB resting liquidity (Mean reverting spread and depth)
            asset.bid_ask_spread = asset.bid_ask_spread * 0.9 + 0.01 * 0.1;
            asset.resting_bids += self.config.market_maker_resilience * 10000.0;
            asset.resting_asks += self.config.market_maker_resilience * 10000.0;
            if (asset.resting_bids > asset.book_depth) asset.resting_bids = asset.book_depth;
            if (asset.resting_asks > asset.book_depth) asset.resting_asks = asset.book_depth;

            asset.last_price = asset.price;
        }
    }
};