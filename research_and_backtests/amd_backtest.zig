const std = @import("std");

const Candle = struct {
    time: i64,
    open: f64,
    high: f64,
    low: f64,
    close: f64,
};

pub fn main() !void {
    const allocator = std.heap.page_allocator;

    const file = try std.fs.cwd().openFile("xauusd_clean.csv", .{});
    defer file.close();

    var reader = file.reader();
    var buf: [1024]u8 = undefined;
    
    var candles = std.ArrayList(Candle).init(allocator);
    defer candles.deinit();

    while (try reader.readUntilDelimiterOrEof(&buf, '\n')) |line| {
        if (line.len == 0) continue;
        var it = std.mem.split(u8, line, ",");
        
        const t_str = it.next() orelse continue;
        const o_str = it.next() orelse continue;
        const h_str = it.next() orelse continue;
        const l_str = it.next() orelse continue;
        const c_str = it.next() orelse continue;

        const time = try std.fmt.parseInt(i64, t_str, 10);
        const o = try std.fmt.parseFloat(f64, o_str);
        const h = try std.fmt.parseFloat(f64, h_str);
        const l = try std.fmt.parseFloat(f64, l_str);
        const c = try std.fmt.parseFloat(f64, c_str);

        try candles.append(.{ .time = time, .open = o, .high = h, .low = l, .close = c });
    }

    std.debug.print("=========================================================\n", .{});
    std.debug.print("[*] ZIG ENGINE: Loaded {} M5 Candles (60 Days)\n", .{candles.items.len});

    // AMD Backtest Logic
    var balance: f64 = 10750.0; // ~$10,750 USD = 9 Lakh INR
    var max_balance: f64 = balance;
    var total_trades: i32 = 0;
    var wins: i32 = 0;
    
    var in_trade: bool = false;
    var trade_dir: i32 = 0; // 1 = buy, -1 = sell
    var entry_price: f64 = 0;
    var sl: f64 = 0;
    var tp: f64 = 0;
    var trade_volume: f64 = 0;

    var asian_high: f64 = 0.0;
    var asian_low: f64 = 99999.0;
    var has_traded_today: bool = false;
    var current_day: i64 = 0;

    for (candles.items) |c| {
        // Unix time approximation (seconds)
        const day = @divFloor(c.time, 86400);
        const hour = @mod(@divFloor(c.time, 3600), 24);

        if (day != current_day) {
            current_day = day;
            asian_high = 0.0;
            asian_low = 99999.0;
            has_traded_today = false;
            
            // Close trades overnight to avoid massive gap risk
            if (in_trade) {
                if (trade_dir == 1) {
                    balance += (c.open - entry_price) * trade_volume;
                } else {
                    balance += (entry_price - c.open) * trade_volume;
                }
                in_trade = false;
            }
        }

        // Asian Session (00:00 to 06:00 UTC) Accumulation
        if (hour >= 0 and hour < 6) {
            if (c.high > asian_high) asian_high = c.high;
            if (c.low < asian_low) asian_low = c.low;
        }

        // London/NY Session Manipulation & Distribution
        if (hour >= 6 and hour < 18 and !in_trade and !has_traded_today) {
            const range_size = asian_high - asian_low;
            
            // Only trade if Asian range is relatively tight (accumulation occurred)
            if (range_size > 2.0 and range_size < 15.0) {
                // Liquidity Sweep (Fakeout)
                if (c.high > asian_high and c.close < asian_high) {
                    // Sell Signal: Buy stops swept, reversing down
                    in_trade = true;
                    trade_dir = -1;
                    entry_price = c.close;
                    sl = c.high + 0.5; // Micro stop above the sweep wick
                    const risk_distance = sl - entry_price;
                    tp = entry_price - (risk_distance * 4.0); // 1:4 R/R Expansion
                    
                    // Kamikaze-Adjacent Risk: 2.5% per trade (safely under 3% limit)
                    const risk_amount = balance * 0.025;
                    trade_volume = risk_amount / risk_distance; 
                    has_traded_today = true;
                } else if (c.low < asian_low and c.close > asian_low) {
                    // Buy Signal: Sell stops swept, reversing up
                    in_trade = true;
                    trade_dir = 1;
                    entry_price = c.close;
                    sl = c.low - 0.5; // Micro stop below the sweep wick
                    const risk_distance = entry_price - sl;
                    tp = entry_price + (risk_distance * 4.0); // 1:4 R/R Expansion
                    
                    const risk_amount = balance * 0.025;
                    trade_volume = risk_amount / risk_distance;
                    has_traded_today = true;
                }
            }
        }

        // Manage Trade
        if (in_trade) {
            if (trade_dir == 1) { // Buy
                if (c.low <= sl) {
                    balance -= (entry_price - sl) * trade_volume;
                    in_trade = false;
                    total_trades += 1;
                } else if (c.high >= tp) {
                    balance += (tp - entry_price) * trade_volume;
                    in_trade = false;
                    total_trades += 1;
                    wins += 1;
                }
            } else if (trade_dir == -1) { // Sell
                if (c.high >= sl) {
                    balance -= (sl - entry_price) * trade_volume;
                    in_trade = false;
                    total_trades += 1;
                } else if (c.low <= tp) {
                    balance += (entry_price - tp) * trade_volume;
                    in_trade = false;
                    total_trades += 1;
                    wins += 1;
                }
            }
        }
        
        if (balance > max_balance) max_balance = balance;
    }

    std.debug.print("=========================================================\n", .{});
    std.debug.print("          [KESSLER V1.1] ZIG BARE-METAL BACKTEST         \n", .{});
    std.debug.print("               EDGE: ASIAN LIQUIDITY SWEEP (AMD)         \n", .{});
    std.debug.print("=========================================================\n", .{});
    std.debug.print("Starting Equity: $10,750.00 (₹9 Lakh INR)\n", .{});
    std.debug.print("Ending Equity:   ${d:.2}\n", .{balance});
    std.debug.print("Total Profit:    ${d:.2}\n", .{balance - 10750.0});
    std.debug.print("Max Equity:      ${d:.2}\n", .{max_balance});
    std.debug.print("Total Sweeps:    {}\n", .{total_trades});
    if (total_trades > 0) {
        const win_rate: f64 = @as(f64, @floatFromInt(wins)) / @as(f64, @floatFromInt(total_trades)) * 100.0;
        std.debug.print("Sniper Win Rate: {d:.1}%\n", .{win_rate});
    }
    std.debug.print("=========================================================\n", .{});
}
