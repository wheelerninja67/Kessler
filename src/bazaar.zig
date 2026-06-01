const std = @import("std");

pub const Config = struct {
    freeze_threshold: f64 = 0.8,
    freeze_duration: u32 = 10,
    cb_sensitivity: f64 = 1.0,
    market_maker_resilience: f64 = 0.1,
};

pub const Asset = struct {
    id: u32,
    price: f64 = 100.0,
    last_price: f64 = 100.0,
    kyle_lambda: f64 = 0.001,
    book_depth: f64 = 1000.0,

    is_frozen: bool = false,
    freeze_ticks_remaining: u32 = 0,
    
    // Magnet accumulators
    frozen_buy_vol: f64 = 0.0,
    frozen_sell_vol: f64 = 0.0,
};

pub const Bazaar = struct {
    assets: []Asset,
    config: Config,

    pub fn init(allocator: std.mem.Allocator, num_assets: usize, config: Config) !Bazaar {
        const assets = try allocator.alloc(Asset, num_assets);
        @memset(assets, std.mem.zeroes(Asset));
        
        for (assets, 0..) |*asset, i| {
            asset.id = @intCast(i);
            asset.price = 100.0;
            asset.last_price = 100.0;
            asset.kyle_lambda = 0.001;
            asset.book_depth = 1000.0;
        }
        
        return Bazaar{
            .assets = assets,
            .config = config,
        };
    }

    pub fn deinit(self: *Bazaar, allocator: std.mem.Allocator) void {
        allocator.free(self.assets);
    }

    pub fn submitOrder(self: *Bazaar, asset_id: u32, is_buy: bool, volume: f64) void {
        var asset = &self.assets[asset_id];
        
        if (asset.is_frozen) {
            // Magnet Effect: Orders pile up in the dark pool
            if (is_buy) {
                asset.frozen_buy_vol += volume;
            } else {
                asset.frozen_sell_vol += volume;
            }
        } else {
            const direction: f64 = if (is_buy) 1.0 else -1.0;
            asset.price += direction * volume * asset.kyle_lambda;
            if (asset.price < 0.01) asset.price = 0.01;
        }
    }

    pub fn updateMarketMicrostructure(self: *Bazaar) void {
        const safe_sensitivity = if (self.config.cb_sensitivity > 0.001) self.config.cb_sensitivity else 0.001;
        const effective_threshold = self.config.freeze_threshold / safe_sensitivity;

        for (self.assets) |*asset| {
            // Market Maker Resilience: depth recovery logic
            // Lower resilience means it recovers much slower, worsening price impact
            const target_depth = 1000.0;
            asset.book_depth += (target_depth - asset.book_depth) * self.config.market_maker_resilience;

            if (asset.is_frozen) {
                asset.freeze_ticks_remaining -= 1;

                if (asset.freeze_ticks_remaining == 0) {
                    // Batch execution unfreeze (Magnet Effect triggers)
                    asset.is_frozen = false;
                    const net_imbalance = asset.frozen_buy_vol - asset.frozen_sell_vol;
                    
                    asset.price += net_imbalance * asset.kyle_lambda; 
                    if (asset.price < 0.01) asset.price = 0.01;
                    
                    asset.frozen_buy_vol = 0.0;
                    asset.frozen_sell_vol = 0.0;
                    asset.last_price = asset.price;
                }
            } else {
                const drop = (asset.last_price - asset.price) / asset.last_price;

                if (drop > effective_threshold and drop > 0) {
                    asset.is_frozen = true;
                    asset.freeze_ticks_remaining = self.config.freeze_duration;
                }
                asset.last_price = asset.price;
            }
        }
    }
};