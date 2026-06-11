const std = @import("std");

pub const MarketData = struct {
    allocator: std.mem.Allocator,
    prices: [][]f64, // [tick][asset_idx]
    num_ticks: usize,
    num_assets: usize,

    pub fn loadCsv(allocator: std.mem.Allocator, io: anytype, file_path: []const u8) !MarketData {
        const buffer = try allocator.alloc(u8, 1024 * 1024 * 50); // 50MB max file size
        defer allocator.free(buffer);
        const content = try std.Io.Dir.readFile(std.Io.Dir.cwd(), io, file_path, buffer);

        var lines = std.mem.splitScalar(u8, content, '\n');
        
        // Count lines and columns to allocate properly
        var line_count: usize = 0;
        var col_count: usize = 0;
        
        if (lines.next()) |header| {
            var cols = std.mem.splitScalar(u8, header, ',');
            while (cols.next()) |_| {
                col_count += 1;
            }
        }
        
        if (col_count <= 1) return error.InvalidCsvFormat;
        col_count -= 1; // Subtract 1 for the Date column

        const text_to_parse = content;
        var it_lines = std.mem.splitScalar(u8, text_to_parse, '\n');
        _ = it_lines.next(); // Skip header

        while (it_lines.next()) |raw_line| {
            const line = std.mem.trim(u8, raw_line, " \r");
            if (line.len == 0) continue;
            line_count += 1;
        }

        var prices = try allocator.alloc([]f64, line_count);
        
        it_lines = std.mem.splitScalar(u8, text_to_parse, '\n');
        _ = it_lines.next(); // Skip header
        
        var row_idx: usize = 0;
        while (it_lines.next()) |raw_line| {
            const line = std.mem.trim(u8, raw_line, " \r");
            if (line.len == 0) continue;
            
            var row = try allocator.alloc(f64, col_count);
            var cols = std.mem.splitScalar(u8, line, ',');
            _ = cols.next(); // Skip Date
            
            var c_idx: usize = 0;
            while (cols.next()) |col_str| {
                if (c_idx < col_count) {
                    const clean_col = std.mem.trim(u8, col_str, " \r");
                    if (clean_col.len > 0) {
                        row[c_idx] = try std.fmt.parseFloat(f64, clean_col);
                    } else {
                        row[c_idx] = 100.0; // default/fallback
                    }
                    c_idx += 1;
                }
            }
            prices[row_idx] = row;
            row_idx += 1;
        }

        return MarketData{
            .allocator = allocator,
            .prices = prices,
            .num_ticks = line_count,
            .num_assets = col_count,
        };
    }

    pub fn deinit(self: *MarketData) void {
        for (self.prices) |row| {
            self.allocator.free(row);
        }
        self.allocator.free(self.prices);
    }
};
