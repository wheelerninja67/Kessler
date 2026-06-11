const std = @import("std");

const Candle = struct {
    close: f32,
    z_score: f32,
};

const Params = struct {
    risk_pct: f32,
    entry_sigma: f32,
    exit_sigma: f32,
    sl_pct: f32,
};

pub fn simulate(candles: []const Candle, params: Params) struct { balance: f32, wins: u32, losses: u32 } {
    var balance: f32 = 100.0;
    const fee_pct: f32 = 0.00055;
    
    var in_trade = false;
    var direction: u8 = 0; // 1 = LONG, 2 = SHORT
    var entry_price: f32 = 0;
    var position_size: f32 = 0;
    var sl: f32 = 0;
    
    var wins: u32 = 0;
    var losses: u32 = 0;

    for (candles) |candle| {
        if (balance <= 1.0) break;

        if (in_trade) {
            var hit_sl = false;
            if (direction == 1 and candle.close <= sl) hit_sl = true;
            if (direction == 2 and candle.close >= sl) hit_sl = true;

            if (hit_sl) {
                const loss_amount = balance * (params.risk_pct / 100.0);
                const fee = (position_size * candle.close) * fee_pct;
                balance -= (loss_amount + fee);
                losses += 1;
                in_trade = false;
                continue;
            }

            var hit_tp = false;
            if (direction == 1 and candle.z_score >= params.exit_sigma) hit_tp = true;
            if (direction == 2 and candle.z_score <= -params.exit_sigma) hit_tp = true;

            if (hit_tp) {
                var price_diff: f32 = 0;
                if (direction == 1) {
                    price_diff = candle.close - entry_price;
                } else {
                    price_diff = entry_price - candle.close;
                }
                const profit = position_size * price_diff;
                const fee = (position_size * candle.close) * fee_pct;
                balance += (profit - fee);
                wins += 1;
                in_trade = false;
            }
        } else {
            if (candle.z_score <= -params.entry_sigma) {
                in_trade = true;
                direction = 1;
                entry_price = candle.close;
                sl = entry_price * (1.0 - params.sl_pct);
            } else if (candle.z_score >= params.entry_sigma) {
                in_trade = true;
                direction = 2;
                entry_price = candle.close;
                sl = entry_price * (1.0 + params.sl_pct);
            }

            if (in_trade) {
                const risk_amount = balance * (params.risk_pct / 100.0);
                var price_distance = entry_price - sl;
                if (price_distance < 0) price_distance = -price_distance;
                if (price_distance == 0) {
                    in_trade = false;
                    continue;
                }
                position_size = risk_amount / price_distance;
                const entry_fee = (position_size * entry_price) * fee_pct;
                balance -= entry_fee;
            }
        }
    }

    return .{ .balance = balance, .wins = wins, .losses = losses };
}

pub fn main() !void {
    const allocator = std.heap.page_allocator;

    // In a real system we read physics.bin, but for now we read pre-processed data
    var dir = try std.fs.openDirAbsolute("/home/mid/Projects/kessler/data", .{});
    defer dir.close();
    var file = try dir.openFile("physics.bin", .{});
    defer file.close();

    const file_size = try file.getEndPos();
    const num_candles = file_size / (2 * @sizeOf(f32));
    
    var candles = try allocator.alloc(Candle, num_candles);
    defer allocator.free(candles);

    var reader = file.reader();
    for (0..num_candles) |i| {
        candles[i].close = try reader.readFloatLittle(f32);
        candles[i].z_score = try reader.readFloatLittle(f32);
    }

    std.debug.print("[*] Loaded {d} Solana physics state vectors into Zig Engine.\n", .{num_candles});
    std.debug.print("[*] Engaging Hyper-Compounding Brute Force over 2.4 Million permutations...\n", .{});

    var best_balance: f32 = 0;
    var best_params: Params = undefined;

    // Loop ranges
    // risk_pct: 5 to 35 (step 0.5) => 60 steps
    // entry_sigma: 1.5 to 5.0 (step 0.1) => 35 steps
    // exit_sigma: -3.0 to 3.0 (step 0.1) => 60 steps
    // sl_pct: 0.01 to 0.20 (step 0.01) => 19 steps

    var risk_idx: u32 = 0;
    while (risk_idx < 60) : (risk_idx += 1) {
        const risk = 5.0 + @as(f32, @floatFromInt(risk_idx)) * 0.5;
        
        var entry_idx: u32 = 0;
        while (entry_idx < 35) : (entry_idx += 1) {
            const entry = 1.5 + @as(f32, @floatFromInt(entry_idx)) * 0.1;
            
            var exit_idx: u32 = 0;
            while (exit_idx < 60) : (exit_idx += 1) {
                const exit_s = -3.0 + @as(f32, @floatFromInt(exit_idx)) * 0.1;
                
                var sl_idx: u32 = 0;
                while (sl_idx < 19) : (sl_idx += 1) {
                    const sl = 0.01 + @as(f32, @floatFromInt(sl_idx)) * 0.01;
                    
                    const p = Params{
                        .risk_pct = risk,
                        .entry_sigma = entry,
                        .exit_sigma = exit_s,
                        .sl_pct = sl,
                    };
                    
                    const res = simulate(candles, p);
                    if (res.balance > best_balance) {
                        best_balance = res.balance;
                        best_params = p;
                    }
                }
            }
        }
    }

    std.debug.print("\n=================================================================\n", .{});
    std.debug.print("  [*] MAXIMUM STAT-ARB COMPOUNDING FOUND (ZIG MEV ENGINE)\n", .{});
    std.debug.print("=================================================================\n", .{});
    std.debug.print("Starting Balance: $100.00\n", .{});
    std.debug.print("Final Balance:    ${d}\n", .{best_balance});
    std.debug.print("Risk Per Trade:   {d}%\n", .{best_params.risk_pct});
    std.debug.print("Entry Sigma:      {d}\n", .{best_params.entry_sigma});
    std.debug.print("Exit Sigma:       {d}\n", .{best_params.exit_sigma});
    std.debug.print("Stop-Loss Pct:    {d}%\n", .{best_params.sl_pct * 100.0});
    std.debug.print("=================================================================\n", .{});
}
