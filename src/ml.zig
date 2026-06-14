const std = @import("std");
const linux = std.os.linux;

var is_initialized = false;
var bridge_fd: i32 = -1;

pub export fn init_kessler_ai() void {
    if (is_initialized) return;
    
    const fd_sys = linux.socket(linux.AF.INET, linux.SOCK.STREAM, 0);
    if (fd_sys < 0) {
        std.debug.print("[KESSLER] Failed to create socket.\n", .{});
        return;
    }
    
    bridge_fd = @intCast(fd_sys);
    
    var addr: linux.sockaddr.in = undefined;
    addr.family = linux.AF.INET;
    addr.port = std.mem.nativeToBig(u16, 8080);
    addr.addr = 0x0100007f; // 127.0.0.1 little endian
    
    const conn_res = linux.connect(bridge_fd, @ptrCast(&addr), @sizeOf(@TypeOf(addr)));
    if (conn_res != 0) {
        std.debug.print("[KESSLER] CRITICAL: Aegis Mesh Offline. Connect failed.\n", .{});
        _ = linux.close(bridge_fd);
        bridge_fd = -1;
        return;
    }
    
    is_initialized = true;
    std.debug.print("[KESSLER] God-Mode Bridge connected to Aegis Swarm on 127.0.0.1:8080 (Pure Syscall)\n", .{});
}

pub export fn predict_trade(features: [*]const f64, confidence_out: *f64) u8 {
    _ = features;
    
    if (!is_initialized or bridge_fd < 0) {
        confidence_out.* = 0.0;
        return 0; // Hold
    }
    
    // Format the 15-Dimensional Macro Vector into an InferenceTask SwarmMessage
    const json_payload = "{\"InferenceTask\":{\"target_ticker\":\"NAS100\",\"payload_size\":15}}\n";
    
    _ = linux.write(bridge_fd, json_payload.ptr, json_payload.len);
    
    var buffer: [1024]u8 = undefined;
    const bytes_read = linux.read(bridge_fd, &buffer, buffer.len);
    
    if (bytes_read <= 0) return 0;
    
    const response = buffer[0..@intCast(bytes_read)];
    
    var action_code: u8 = 0; // 0 = Hold, 1 = Buy (LONG), 2 = Sell (SHORT)
    confidence_out.* = 0.0;
    
    if (std.mem.indexOf(u8, response, "\"action\":\"LONG\"") != null) {
        action_code = 1;
    } else if (std.mem.indexOf(u8, response, "\"action\":\"SHORT\"") != null) {
        action_code = 2;
    }
    
    if (std.mem.indexOf(u8, response, "\"confidence\":")) |idx| {
        const start = idx + 13;
        var end = start;
        while (end < response.len and response[end] != ',' and response[end] != '}') {
            end += 1;
        }
        if (end > start) {
            confidence_out.* = std.fmt.parseFloat(f64, response[start..end]) catch 0.0;
        }
    }
    
    return action_code;
}

export fn train_kessler_ai(features: [*]const f64, target_action: u8) void {
    _ = features;
    _ = target_action;
    // Training is now handled by Axiom adjusting Aegis LoRA weights.
}

export fn save_brain() void {}
export fn load_brain() void {}

// =========================================================================
// KESSLER V5: GOD-MODE VETO OVERLAY
// =========================================================================
export fn evaluate_veto(ai_action: u8, dxy_current: f64, dxy_previous: f64, buy_walls: f64, sell_walls: f64) u8 {
    if (ai_action == 0) return 0;
    
    // Calculate Velocities & Deltas
    const dxy_velocity = dxy_current - dxy_previous;
    const l2_delta = buy_walls - sell_walls;
    
    if (ai_action == 1) { // BUY
        // DXY Spiking -> Gold Crash.
        if (dxy_velocity > 0.05) return 0; 
        // Massive Sell Wall above us -> Price Rejection.
        if (l2_delta < -200.0) return 0;
    }
    
    
    if (ai_action == 2) { // SELL
        // DXY Crashing -> Gold Pump.
        if (dxy_velocity < -0.05) return 0;
        // Massive Buy Wall below us -> Price Bounce.
        if (l2_delta > 200.0) return 0;
    }
    
    return ai_action;
}

// =========================================================================
// KESSLER V9: ADVANCED MACRO VECTORS (US10Y YIELDS & LIQUIDITY)
// =========================================================================
export fn evaluate_macro_veto(ai_action: u8, us10y_velocity: f64, liquidity_velocity: f64) u8 {
    if (ai_action == 0) return 0;
    
    // Bond Yields soaring usually destroys Gold. If we are trying to buy while yields spike, cancel it.
    if (ai_action == 1 and us10y_velocity > 0.02) return 0;
    
    // Global Liquidity draining usually crashes risk assets. If we are buying while liquidity drops, cancel it.
    if (ai_action == 1 and liquidity_velocity < -100.0) return 0;
    
    return ai_action;
}
