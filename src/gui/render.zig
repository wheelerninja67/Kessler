const std = @import("std");
const ring_buffer = @import("ring_buffer.zig");

const c = @cImport({
    @cInclude("gui/wrapper.h");
});

pub const AnimationState = struct {
    last_time: f64 = 0.0,
    frozen_frames: [36]f32 = [_]f32{0.0} ** 36,
    
    current_word: [:0]const u8 = "drift",
    target_word: [:0]const u8 = "drift",
    word_transition_timer: f32 = 0.0,
    
    vignette_progress: f32 = 0.0,
};

var g_state = AnimationState{};

pub fn renderAll(snapshot: *const ring_buffer.TickSnapshot, window_width: f32, window_height: f32) void {
    const draw_list = c.w_igGetBackgroundDrawList() orelse unreachable;

    if (!snapshot.engine_running) {
        renderOffline(draw_list, window_width, window_height);
        return;
    }

    const current_time = c.w_igGetTime();
    if (g_state.last_time == 0.0) g_state.last_time = current_time;
    const dt = @as(f32, @floatCast(current_time - g_state.last_time));
    g_state.last_time = current_time;

    renderWaveform(draw_list, snapshot, window_width, window_height);
    renderConstellation(draw_list, snapshot, window_width, window_height);
    renderVignette(draw_list, snapshot, window_width, window_height, dt);
    renderCascadeSeed(draw_list, snapshot, window_width, window_height, @as(f32, @floatCast(current_time)));
    renderWord(draw_list, snapshot, window_width, window_height, dt, @as(f32, @floatCast(current_time)));
    renderAnchor(draw_list, snapshot, window_width, window_height);
}

fn renderWaveform(draw_list: *c.ImDrawList, snapshot: *const ring_buffer.TickSnapshot, window_width: f32, window_height: f32) void {
    const height = window_height * 0.25;
    const count = snapshot.market_prices.len;
    
    const dx = window_width / @as(f32, @floatFromInt(count - 1));
    var points: [200]c.MyImVec2 = undefined;
    var min_p: f32 = 999999.0;
    var max_p: f32 = -999999.0;
    
    for (0..count) |i| {
        const idx = (snapshot.price_write_idx + i) % count;
        const p = @as(f32, @floatCast(snapshot.market_prices[idx]));
        if (p < min_p) min_p = p;
        if (p > max_p) max_p = p;
    }
    
    if (max_p == min_p) max_p = min_p + 1.0;
    
    for (0..count) |i| {
        const idx = (snapshot.price_write_idx + i) % count;
        const p = @as(f32, @floatCast(snapshot.market_prices[idx]));
        const norm = (p - min_p) / (max_p - min_p);
        
        points[i].x = @as(f32, @floatFromInt(i)) * dx;
        points[i].y = height - (norm * height * 0.8) - (height * 0.1);
    }
    
    for (0..count - 1) |i| {
        const p1 = points[i];
        const p2 = points[i + 1];
        
        const progress = @as(f32, @floatFromInt(i)) / @as(f32, @floatFromInt(count));
        
        var r: f32 = 0; var g: f32 = 0; var b: f32 = 0;
        if (progress < 0.33) {
            const t = progress / 0.33;
            r = std.math.lerp(0.0, 1.0, t);
            g = std.math.lerp(0.5, 1.0, t);
            b = std.math.lerp(1.0, 1.0, t);
        } else if (progress < 0.66) {
            const t = (progress - 0.33) / 0.33;
            r = std.math.lerp(1.0, 1.0, t);
            g = std.math.lerp(1.0, 0.7, t);
            b = std.math.lerp(1.0, 0.0, t);
        } else {
            const t = (progress - 0.66) / 0.34;
            r = std.math.lerp(1.0, 0.6, t);
            g = std.math.lerp(0.7, 0.0, t);
            b = std.math.lerp(0.0, 0.0, t);
        }
        
        const color = c.w_igGetColorU32(.{ .x = r, .y = g, .z = b, .w = 1.0 });
        c.w_ImDrawList_AddLine(draw_list, p1, p2, color, 2.0);
    }
}

fn renderConstellation(draw_list: *c.ImDrawList, snapshot: *const ring_buffer.TickSnapshot, window_width: f32, window_height: f32) void {
    const spacing: f32 = 60.0;
    const grid_size: f32 = 5.0 * spacing;
    
    const start_x = (window_width - grid_size) / 2.0;
    const start_y = (window_height - grid_size) / 2.0;
    
    for (0..36) |i| {
        const row = i / 6;
        const col = i % 6;
        
        const cx = start_x + @as(f32, @floatFromInt(col)) * spacing;
        const cy = start_y + @as(f32, @floatFromInt(row)) * spacing;
        
        if (snapshot.asset_frozen[i]) {
            if (g_state.frozen_frames[i] < 30.0) {
                g_state.frozen_frames[i] += 1.0;
            }
        } else {
            g_state.frozen_frames[i] = 0.0;
        }
        
        const depth = snapshot.base_depths[i];
        
        // Target radius
        var radius = @as(f32, @floatCast(depth)) * 26.0 + 4.0;
        if (radius < 4.0) radius = 4.0;
        if (radius > 30.0) radius = 30.0;
        
        // Shrink to 0 over 30 frames if frozen
        const shrink_factor = 1.0 - (g_state.frozen_frames[i] / 30.0);
        radius *= shrink_factor;
        
        if (radius <= 0.0) continue;
        
        var r: f32 = 1.0; var g: f32 = 1.0; var b: f32 = 1.0;
        if (depth < 0.3) {
            r = 1.0; g = 0.0; b = 0.0;
        } else if (depth < 0.7) {
            r = 1.0; g = 0.69; b = 0.0;
        }
        
        var alpha = @as(f32, @floatCast(snapshot.volatilities[i]));
        if (alpha < 0.1) alpha = 0.1;
        if (alpha > 1.0) alpha = 1.0;
        
        const color = c.w_igGetColorU32(.{ .x = r, .y = g, .z = b, .w = alpha });
        c.w_ImDrawList_AddCircleFilled(draw_list, .{ .x = cx, .y = cy }, radius, color);
    }
}

fn renderCascadeSeed(draw_list: *c.ImDrawList, snapshot: *const ring_buffer.TickSnapshot, window_width: f32, window_height: f32, current_time: f32) void {
    if (snapshot.cascade_depth == 0) return;
    
    const font = c.w_GetFont(3) orelse unreachable;
    
    var r: f32 = 1.0; var g: f32 = 0.69; var b: f32 = 0.0;
    var scale: f32 = 1.0;
    var glow_layers: u32 = 0;
    var glow_alpha: f32 = 0.0;
    var glow_radius: f32 = 0.0;
    
    if (snapshot.cascade_depth >= 5) {
        r = 1.0; g = 0.0; b = 0.0;
        const pulse = @as(f32, @floatCast((std.math.sin(current_time * std.math.pi) + 1.0) / 2.0));
        scale = 1.0 + 0.08 * pulse;
        glow_layers = 5;
        glow_alpha = 0.3 * pulse;
        glow_radius = 8.0 + 4.0 * pulse;
    } else if (snapshot.cascade_depth >= 3) {
        r = 1.0; g = 0.2; b = 0.2;
        glow_layers = 4;
        glow_alpha = 0.2;
        glow_radius = 6.0;
    } else {
        glow_layers = 2;
        glow_alpha = 0.1;
        glow_radius = 3.0;
    }
    
    var buf: [16]u8 = undefined;
    const text = std.fmt.bufPrintZ(&buf, "{d}", .{snapshot.cascade_depth}) catch return;
    
    const font_size = 96.0 * scale;
    const text_size = c.w_CalcTextSize(font, font_size, text.ptr);
    
    const center_x = (window_width - text_size.x) / 2.0;
    const center_y = (window_height - text_size.y) / 2.0;
    
    // Draw Glow
    if (glow_layers > 0) {
        const g_color = c.w_igGetColorU32(.{ .x = r, .y = g, .z = b, .w = glow_alpha });
        for (0..glow_layers) |layer| {
            const offset = glow_radius * @as(f32, @floatFromInt(layer + 1)) / @as(f32, @floatFromInt(glow_layers));
            // Top Left
            c.w_ImDrawList_AddText(draw_list, font, font_size, .{ .x = center_x - offset, .y = center_y - offset }, g_color, text.ptr);
            // Top Right
            c.w_ImDrawList_AddText(draw_list, font, font_size, .{ .x = center_x + offset, .y = center_y - offset }, g_color, text.ptr);
            // Bottom Left
            c.w_ImDrawList_AddText(draw_list, font, font_size, .{ .x = center_x - offset, .y = center_y + offset }, g_color, text.ptr);
            // Bottom Right
            c.w_ImDrawList_AddText(draw_list, font, font_size, .{ .x = center_x + offset, .y = center_y + offset }, g_color, text.ptr);
        }
    }
    
    // Draw Text
    const color = c.w_igGetColorU32(.{ .x = r, .y = g, .z = b, .w = 1.0 });
    c.w_ImDrawList_AddText(draw_list, font, font_size, .{ .x = center_x, .y = center_y }, color, text.ptr);
}

fn renderWord(draw_list: *c.ImDrawList, snapshot: *const ring_buffer.TickSnapshot, window_width: f32, window_height: f32, dt: f32, current_time: f32) void {
    const font = c.w_GetFont(2) orelse unreachable;
    const font_size = 28.0;
    
    var word: [:0]const u8 = undefined;
    var r: f32 = undefined; var g: f32 = undefined; var b: f32 = undefined;
    
    if (snapshot.theta_avg > 0.7) {
        word = "calm"; r = 0.0; g = 1.0; b = 0.0;
    } else if (snapshot.theta_avg > 0.3) {
        word = "drift"; r = 0.5; g = 0.5; b = 0.5;
    } else if (snapshot.theta_avg > 0.1) {
        word = "fear"; r = 1.0; g = 0.69; b = 0.0;
    } else {
        word = "panic"; r = 1.0; g = 0.0; b = 0.0;
    }

    if (!std.mem.eql(u8, word, g_state.target_word)) {
        g_state.current_word = g_state.target_word;
        g_state.target_word = word;
        g_state.word_transition_timer = 0.0;
    }
    
    if (g_state.word_transition_timer < 0.5) {
        g_state.word_transition_timer += dt;
        if (g_state.word_transition_timer > 0.5) {
            g_state.word_transition_timer = 0.5;
        }
    }
    
    const progress = g_state.word_transition_timer / 0.5;
    
    // If not panic, use solid. If panic, pulse.
    var alpha1: f32 = 1.0 - progress;
    var alpha2: f32 = progress;
    
    if (std.mem.eql(u8, g_state.current_word, "panic")) {
        alpha1 *= @as(f32, @floatCast((std.math.sin(current_time * std.math.pi * 2.0) + 1.0) / 2.0 * 0.5 + 0.5));
    }
    if (std.mem.eql(u8, g_state.target_word, "panic")) {
        alpha2 *= @as(f32, @floatCast((std.math.sin(current_time * std.math.pi * 2.0) + 1.0) / 2.0 * 0.5 + 0.5));
    }
    
    if (progress < 1.0) {
        // Draw current_word fading out
        var cr: f32 = 0.5; var cg: f32 = 0.5; var cb: f32 = 0.5;
        if (std.mem.eql(u8, g_state.current_word, "calm")) { cr = 0.0; cg = 1.0; cb = 0.0; }
        else if (std.mem.eql(u8, g_state.current_word, "fear")) { cr = 1.0; cg = 0.69; cb = 0.0; }
        else if (std.mem.eql(u8, g_state.current_word, "panic")) { cr = 1.0; cg = 0.0; cb = 0.0; }
        
        const color1 = c.w_igGetColorU32(.{ .x = cr, .y = cg, .z = cb, .w = alpha1 });
        const ts1 = c.w_CalcTextSize(font, font_size, g_state.current_word.ptr);
        const p1 = c.MyImVec2{ .x = (window_width - ts1.x) / 2.0, .y = window_height * 0.6 };
        c.w_ImDrawList_AddText(draw_list, font, font_size, p1, color1, g_state.current_word.ptr);
    }
    
    const color2 = c.w_igGetColorU32(.{ .x = r, .y = g, .z = b, .w = alpha2 });
    const ts2 = c.w_CalcTextSize(font, font_size, g_state.target_word.ptr);
    const p2 = c.MyImVec2{ .x = (window_width - ts2.x) / 2.0, .y = window_height * 0.6 };
    c.w_ImDrawList_AddText(draw_list, font, font_size, p2, color2, g_state.target_word.ptr);
}

fn renderVignette(draw_list: *c.ImDrawList, snapshot: *const ring_buffer.TickSnapshot, window_width: f32, window_height: f32, dt: f32) void {
    if (snapshot.cascade_depth > 0) {
        g_state.vignette_progress += dt / 3.0; // Fade in over 3s
        if (g_state.vignette_progress > 1.0) g_state.vignette_progress = 1.0;
    } else {
        g_state.vignette_progress -= dt / 10.0; // Fade out over 10s
        if (g_state.vignette_progress < 0.0) g_state.vignette_progress = 0.0;
    }
    
    if (g_state.vignette_progress <= 0.0) return;
    
    var intensity: f32 = 1.0;
    if (snapshot.cascade_depth > 0) {
        intensity = @min(1.0, @as(f32, @floatFromInt(snapshot.cascade_depth)) / 5.0);
    }
    
    const alpha = intensity * g_state.vignette_progress * 0.5; // Max 0.5 alpha
    
    const color_out = c.w_igGetColorU32(.{ .x = 0.5, .y = 0.0, .z = 0.0, .w = alpha });
    const color_in = c.w_igGetColorU32(.{ .x = 0.5, .y = 0.0, .z = 0.0, .w = 0.0 });
    
    const w = window_width;
    const h = window_height;
    const thick = 150.0;
    
    c.w_ImDrawList_AddRectFilledMultiColor(draw_list, .{ .x = 0, .y = 0 }, .{ .x = w, .y = thick }, color_out, color_out, color_in, color_in);
    c.w_ImDrawList_AddRectFilledMultiColor(draw_list, .{ .x = 0, .y = h - thick }, .{ .x = w, .y = h }, color_in, color_in, color_out, color_out);
    c.w_ImDrawList_AddRectFilledMultiColor(draw_list, .{ .x = 0, .y = 0 }, .{ .x = thick, .y = h }, color_out, color_in, color_in, color_out);
    c.w_ImDrawList_AddRectFilledMultiColor(draw_list, .{ .x = w - thick, .y = 0 }, .{ .x = w, .y = h }, color_in, color_out, color_out, color_in);
}

fn renderAnchor(draw_list: *c.ImDrawList, snapshot: *const ring_buffer.TickSnapshot, window_width: f32, window_height: f32) void {
    const font = c.w_GetFont(0) orelse unreachable;
    const font_size = 11.0;
    
    var buf: [64]u8 = undefined;
    const text = std.fmt.bufPrintZ(&buf, "t:{d} h:{x:0>2}{x:0>2}{x:0>2}{x:0>2}{x:0>2}{x:0>2}{x:0>2}{x:0>2}", .{
        snapshot.tick_number,
        snapshot.hash_first8[0], snapshot.hash_first8[1], snapshot.hash_first8[2], snapshot.hash_first8[3],
        snapshot.hash_first8[4], snapshot.hash_first8[5], snapshot.hash_first8[6], snapshot.hash_first8[7]
    }) catch return;
    
    const color = c.w_igGetColorU32(.{ .x = 0.31, .y = 0.31, .z = 0.31, .w = 1.0 }); // #505050
    const text_size = c.w_CalcTextSize(font, font_size, text.ptr);
    
    const pos = c.MyImVec2{
        .x = window_width - text_size.x - 20.0,
        .y = window_height - text_size.y - 15.0,
    };
    
    c.w_ImDrawList_AddText(draw_list, font, font_size, pos, color, text.ptr);
}

fn renderOffline(draw_list: *c.ImDrawList, window_width: f32, window_height: f32) void {
    const font = c.w_GetFont(1) orelse unreachable;
    const font_size = 24.0;
    
    const text = "ENGINE OFFLINE";
    const color = c.w_igGetColorU32(.{ .x = 0.545, .y = 0.58, .z = 0.62, .w = 1.0 });
    
    const text_size = c.w_CalcTextSize(font, font_size, text);
    
    const pos = c.MyImVec2{
        .x = (window_width - text_size.x) / 2.0,
        .y = (window_height - text_size.y) / 2.0,
    };
    
    c.w_ImDrawList_AddText(draw_list, font, font_size, pos, color, text);
}
