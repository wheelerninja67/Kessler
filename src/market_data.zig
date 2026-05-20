const std = @import("std");
const stash = @import("stash.zig");

// FUSE DATA DIRECTLY INTO THE BINARY AT COMPILE TIME (Bypasses 0.16.0 fs limits)
const meta_file = @embedFile("data/metadata.json");
const prices_file = @embedFile("data/prices.csv");
const returns_file = @embedFile("data/returns.csv");

pub const MarketData = struct {
    num_tickers: u32,
    num_days: u32,
    prices: []f64, // [ticker * num_days + day]
    returns: []f64, // [ticker * num_days + day]
    ticker_names: [][]const u8,

    pub fn init(s: *stash.Stash, data_dir: []const u8) !MarketData {
        _ = data_dir; // Ignored. Data is fused into the executable.

        // Temporary arena for parsing overhead. Completely freed before the tick loop.
        var temp_arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
        defer temp_arena.deinit();
        const temp_alloc = temp_arena.allocator();

        // 1. Parse metadata.json from embedded memory string
        const parsed_json = try std.json.parseFromSlice(std.json.Value, temp_alloc, meta_file, .{});
        const root = parsed_json.value.object;
        const num_tickers = @as(u32, @intCast(root.get("num_tickers").?.integer));
        const tickers_array = root.get("tickers").?.array;

        // 2. Allocate ticker_names pool using the permanent stash arena
        var total_name_len: usize = 0;
        for (tickers_array.items) |t| {
            total_name_len += t.string.len + 1; // +1 for null separator
        }

        const name_block = try s.stashAlloc(u8, total_name_len);
        const ticker_names = try s.stashAlloc([]const u8, num_tickers);

        var offset: usize = 0;
        for (tickers_array.items, 0..) |t, i| {
            const len = t.string.len;
            @memcpy(name_block[offset .. offset + len], t.string);
            name_block[offset + len] = 0; // Null separator
            ticker_names[i] = name_block[offset .. offset + len];
            offset += len + 1;
        }

        // 3. Determine num_days by scanning the embedded prices string
        var num_days: u32 = 0;
        var line_it = std.mem.splitScalar(u8, prices_file, '\n');
        while (line_it.next()) |raw_line| {
            const line = std.mem.trim(u8, raw_line, "\r ");
            if (line.len == 0 or !std.ascii.isDigit(line[0])) continue; // Skip headers/empty lines
            num_days += 1;
        }

        // 4. Allocate highly optimized, flat arrays using the public stashAlloc interface
        const prices = try s.stashAlloc(f64, num_tickers * num_days);
        const returns = try s.stashAlloc(f64, num_tickers * num_days);

        // 5. Parse CSVs from embedded memory strings
        try parseCsv(prices_file, prices, num_tickers, num_days);
        try parseCsv(returns_file, returns, num_tickers, num_days);

        return MarketData{
            .num_tickers = num_tickers,
            .num_days = num_days,
            .prices = prices,
            .returns = returns,
            .ticker_names = ticker_names,
        };
    }

    // High-speed manual character parser (Zero external dependencies)
    fn parseCsv(csv_data: []const u8, dest: []f64, num_tickers: u32, num_days: u32) !void {
        var day: u32 = 0;
        var line_it = std.mem.splitScalar(u8, csv_data, '\n');

        while (line_it.next()) |raw_line| {
            const line = std.mem.trim(u8, raw_line, "\r ");
            if (line.len == 0 or !std.ascii.isDigit(line[0])) continue; // Skip headers
            if (day >= num_days) break;

            var col_it = std.mem.splitScalar(u8, line, ',');
            _ = col_it.next(); // Skip the Date column

            var t: u32 = 0;
            while (col_it.next()) |raw_val| {
                if (t >= num_tickers) break;

                const val_str = std.mem.trim(u8, raw_val, " \"\r");
                var val: f64 = 0.0;

                if (val_str.len == 0) {
                    // Forward-fill missing values
                    val = if (day > 0) dest[t * num_days + (day - 1)] else 0.0;
                } else {
                    val = std.fmt.parseFloat(f64, val_str) catch |err| {
                        std.debug.print("[!] PARSE ERROR: Float conversion failed on day {d}, ticker {d} ('{s}')\n", .{ day, t, val_str });
                        return err;
                    };
                }

                dest[t * num_days + day] = val;
                t += 1;
            }

            // Forward-fill any trailing missing columns for this row
            while (t < num_tickers) {
                dest[t * num_days + day] = if (day > 0) dest[t * num_days + (day - 1)] else 0.0;
                t += 1;
            }
            day += 1;
        }
    }

    pub fn getPrice(self: *const MarketData, ticker: u32, day: u32) f64 {
        return self.prices[ticker * self.num_days + day];
    }

    pub fn getReturn(self: *const MarketData, ticker: u32, day: u32) f64 {
        return self.returns[ticker * self.num_days + day];
    }

    pub fn getTickerName(self: *const MarketData, ticker: u32) []const u8 {
        return self.ticker_names[ticker];
    }
};
