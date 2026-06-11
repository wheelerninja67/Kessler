// WARNING: This is a strict flat key-value parser.
// Nested YAML, trailing comments, or varying indentation will BREAK parsing.

const std = @import("std");





fn readFileSync(allocator: std.mem.Allocator, io: anytype, path: []const u8) ![]u8 {
    const buffer = try allocator.alloc(u8, 1024 * 1024 * 10);
    defer allocator.free(buffer);
    const content = try std.Io.Dir.readFile(std.Io.Dir.cwd(), io, path, buffer);
    return try allocator.dupe(u8, content);
}

pub const StrategyDist = struct {
    momentum: f64 = 0.25,
    mean_reversion: f64 = 0.25,
    value: f64 = 0.25,
    random: f64 = 0.25,
};

pub const Shock = struct {
    tick: []const u8,
    type_name: []const u8,
    agent_ids: []const u32 = &[_]u32{},
    asset_id: ?usize = null,
    magnitude: ?f64 = null,
    fraction: ?f64 = null,
    description: []const u8 = "",
};

pub const ScenarioConfig = struct {
    name: []const u8 = "Default",
    description: []const u8 = "",
    assets: usize = 37,
    start_date: []const u8 = "",
    end_date: []const u8 = "",
    agent_count: usize = 1000000,
    leverage_cap: f64 = 5.0,
    strategy: StrategyDist = .{},
    base_depth: f64 = 1000.0,
    decay_rate: f64 = 0.01,
    resilience: f64 = 0.1,
    cb_threshold: f64 = 0.5,
    shocks: []const Shock = &[_]Shock{},
    forward_ticks: u32 = 200,

    pub fn parseYaml(allocator: std.mem.Allocator, io: anytype, file_path: []const u8) !ScenarioConfig {
        const content = try readFileSync(allocator, io, file_path);
        var config = ScenarioConfig{};

        var shock_buffer: [16]Shock = undefined;
        var shock_count: usize = 0;
        var current_shock: ?Shock = null;

        var text_to_parse = content;

        if (std.mem.startsWith(u8, text_to_parse, "\xEF\xBB\xBF")) {
            text_to_parse = text_to_parse[3..];
        }

        var lines = std.mem.splitScalar(u8, text_to_parse, '\n');

        while (lines.next()) |raw_line| {
            const line = std.mem.trim(u8, raw_line, " \r\t");
            if (line.len == 0 or line[0] == '#') continue;

            if (std.mem.startsWith(u8, line, "name:")) {
                config.name = extractString(line);
            } else if (std.mem.startsWith(u8, line, "count:")) {
                config.agent_count = try std.fmt.parseInt(usize, extractValue(line), 10);
            } else if (std.mem.startsWith(u8, line, "leverage_cap:")) {
                config.leverage_cap = try std.fmt.parseFloat(f64, extractValue(line));
            } else if (std.mem.startsWith(u8, line, "base_depth:")) {
                config.base_depth = try std.fmt.parseFloat(f64, extractValue(line));
            } else if (std.mem.startsWith(u8, line, "decay_rate:")) {
                config.decay_rate = try std.fmt.parseFloat(f64, extractValue(line));
            } else if (std.mem.startsWith(u8, line, "resilience:")) {
                config.resilience = try std.fmt.parseFloat(f64, extractValue(line));
            } else if (std.mem.startsWith(u8, line, "cb_threshold:")) {
                config.cb_threshold = try std.fmt.parseFloat(f64, extractValue(line));
            } else if (std.mem.startsWith(u8, line, "forward_ticks:")) {
                config.forward_ticks = try std.fmt.parseInt(u32, extractValue(line), 10);
            } else if (std.mem.startsWith(u8, line, "- tick:")) {
                if (current_shock != null and shock_count < shock_buffer.len) {
                    shock_buffer[shock_count] = current_shock.?;
                    shock_count += 1;
                }
                current_shock = Shock{ .tick = extractString(line), .type_name = "" };
            } else if (current_shock) |*shock| {
                if (std.mem.startsWith(u8, line, "type:")) {
                    shock.type_name = extractString(line);
                } else if (std.mem.startsWith(u8, line, "magnitude:")) {
                    shock.magnitude = try std.fmt.parseFloat(f64, extractValue(line));
                } else if (std.mem.startsWith(u8, line, "asset_id:")) {
                    shock.asset_id = try std.fmt.parseInt(usize, extractValue(line), 10);
                } else if (std.mem.startsWith(u8, line, "agent_ids:")) {
                    const val = extractValue(line);
                    const trimmed = std.mem.trim(u8, val, " []\r");
                    var it = std.mem.splitScalar(u8, trimmed, ',');

                    var ids_buf: [128]u32 = undefined;
                    var ids_cnt: usize = 0;

                    while (it.next()) |id_str| {
                        const clean_id = std.mem.trim(u8, id_str, " \r");
                        if (clean_id.len > 0) {
                            const id = std.fmt.parseInt(u32, clean_id, 10) catch continue;
                            if (ids_cnt < ids_buf.len) {
                                ids_buf[ids_cnt] = id;
                                ids_cnt += 1;
                            }
                        }
                    }
                    if (ids_cnt > 0) {
                        const final_ids = try allocator.alloc(u32, ids_cnt);
                        @memcpy(final_ids, ids_buf[0..ids_cnt]);
                        shock.agent_ids = final_ids;
                    }
                }
            }
        }

        if (current_shock != null and shock_count < shock_buffer.len) {
            shock_buffer[shock_count] = current_shock.?;
            shock_count += 1;
        }

        if (shock_count > 0) {
            const final_shocks = try allocator.alloc(Shock, shock_count);
            @memcpy(final_shocks, shock_buffer[0..shock_count]);
            config.shocks = final_shocks;
        }
        return config;
    }
};

pub fn loadScenario(allocator: std.mem.Allocator, io: anytype, file_path: []const u8) !ScenarioConfig {
    return try ScenarioConfig.parseYaml(allocator, io, file_path);
}

fn extractValue(line: []const u8) []const u8 {
    const colon_idx = std.mem.indexOfScalar(u8, line, ':') orelse return line;
    return std.mem.trim(u8, line[colon_idx + 1 ..], " \"'\r\t");
}

fn extractString(line: []const u8) []const u8 {
    return extractValue(line);
}
