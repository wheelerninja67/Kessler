#!/bin/bash
set -e

# 1. Fix pulse.zig (prev_price and num_ticks)
sed -i 's/var min_price: f64 = market.assets\[0\].price;/var min_price: f64 = market.assets[0].price;\n    var max_price: f64 = market.assets[0].price;\n    var prev_price: f64 = market.assets[0].price;/' src/pulse.zig
sed -i 's/var max_price: f64 = market.assets\[0\].price;//' src/pulse.zig
sed -i 's/const num_ticks: u32 = 1000;//' src/pulse.zig
sed -i 's/pub fn runTickLoop(market: \*bazaar.Bazaar, agents: \*crowd.Crowd, net: \*gossip.Network, shocks: \[\]const scenario.Shock) !Stats {/pub fn runTickLoop(num_ticks: u32, market: *bazaar.Bazaar, agents: *crowd.Crowd, net: *gossip.Network, shocks: []const scenario.Shock, allocator: std.mem.Allocator) !Stats {/' src/pulse.zig
sed -i 's/var returns: \[num_ticks\]f64 = undefined;/var returns = try allocator.alloc(f64, num_ticks);\n    defer allocator.free(returns);/' src/pulse.zig
sed -i 's/const prev_price = current_price;//' src/pulse.zig
sed -i 's/valid_ticks += 1;\n            }\n        }/valid_ticks += 1;\n            }\n        }\n        prev_price = new_price;/' src/pulse.zig
sed -i 's/const cascade_depth = if (max_frozen_volume > 0) @log10(max_frozen_volume) else 0.0;/const cascade_final_depth = if (max_frozen_volume > 0) @log10(max_frozen_volume) else 0.0;/' src/pulse.zig
sed -i 's/\.cascade_depth = cascade_/.cascade_depth = cascade_final_depth,/' src/pulse.zig

# 2. Fix scenario.zig (fopen -> readFileAlloc, and nested keys)
sed -i 's/extern "c" fn fopen.*//' src/scenario.zig
sed -i 's/extern "c" fn fclose.*//' src/scenario.zig
sed -i 's/extern "c" fn fread.*//' src/scenario.zig
sed -i 's/fn readFileSync(allocator: std.mem.Allocator, path: \[\]const u8) !\[\]u8 {/fn readFileSync(allocator: std.mem.Allocator, path: []const u8) ![]u8 {\n    return std.fs.cwd().readFileAlloc(allocator, path, 1024 * 1024 * 10);/' src/scenario.zig
sed -i '/const path_z = try allocator.dupeZ(u8, path);/,/return buffer\[0..bytes\];/d' src/scenario.zig

