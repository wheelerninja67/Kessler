const std = @import("std");
const stash = @import("memory.zig");

/// Deep Learning Matrix: Proximal Policy Optimization (PPO) Base
/// Upgraded to 10-Dimensional Renaissance-Style Feature Processing.
pub const NeuralNet = struct {
    input_size: usize,
    hidden_size: usize,
    output_size: usize,
    
    w1: []f64, // Input -> Hidden Matrix
    w2: []f64, // Hidden -> Output Matrix
    
    // Pre-allocated buffers for zero-allocation forward/backward passes
    input_layer: []f64,
    hidden_layer: []f64,
    output_layer: []f64,
    
    learning_rate: f64,
    
    pub fn init(arena: *stash.Stash, in_sz: usize, hid_sz: usize, out_sz: usize, prng: *std.Random.DefaultPrng) !NeuralNet {
        var nn = NeuralNet{
            .input_size = in_sz,
            .hidden_size = hid_sz,
            .output_size = out_sz,
            .w1 = try arena.stashAlloc(f64, in_sz * hid_sz),
            .w2 = try arena.stashAlloc(f64, hid_sz * out_sz),
            .input_layer = try arena.stashAlloc(f64, in_sz),
            .hidden_layer = try arena.stashAlloc(f64, hid_sz),
            .output_layer = try arena.stashAlloc(f64, out_sz),
            .learning_rate = 0.01,
        };
        
        var random = prng.random();
        
        // Xavier Initialization
        const bound1 = @sqrt(6.0 / @as(f64, @floatFromInt(in_sz + hid_sz)));
        for (0..nn.w1.len) |i| nn.w1[i] = (random.float(f64) * 2.0 - 1.0) * bound1;
        
        const bound2 = @sqrt(6.0 / @as(f64, @floatFromInt(hid_sz + out_sz)));
        for (0..nn.w2.len) |i| nn.w2[i] = (random.float(f64) * 2.0 - 1.0) * bound2;
        
        return nn;
    }

    inline fn relu(x: f64) f64 { return @max(0.0, x); }
    inline fn relu_deriv(x: f64) f64 { return if (x > 0.0) 1.0 else 0.0; }
    
    /// Forward pass generating Agent Probability Policies
    pub fn forward(self: *NeuralNet, inputs: []const f64) []f64 {
        for (0..self.input_size) |i| self.input_layer[i] = inputs[i];
        
        // Input -> Hidden
        for (0..self.hidden_size) |i| {
            var sum: f64 = 0.0;
            for (0..self.input_size) |j| {
                sum += self.input_layer[j] * self.w1[j * self.hidden_size + i];
            }
            self.hidden_layer[i] = relu(sum);
        }
        
        // Hidden -> Output (Logits)
        for (0..self.output_size) |i| {
            var sum: f64 = 0.0;
            for (0..self.hidden_size) |j| {
                sum += self.hidden_layer[j] * self.w2[j * self.output_size + i];
            }
            self.output_layer[i] = sum;
        }
        
        // Softmax Activation
        var max_val: f64 = self.output_layer[0];
        for (0..self.output_size) |i| {
            if (self.output_layer[i] > max_val) max_val = self.output_layer[i];
        }
        
        var sum_exp: f64 = 0.0;
        for (0..self.output_size) |i| {
            self.output_layer[i] = @exp(self.output_layer[i] - max_val);
            sum_exp += self.output_layer[i];
        }
        for (0..self.output_size) |i| {
            self.output_layer[i] /= sum_exp;
        }
        
        return self.output_layer;
    }

    /// Backpropagation utilizing Cross-Entropy Loss gradient calculations
    pub fn backward(self: *NeuralNet, target_action: u8) void {
        var d_output = [_]f64{0.0} ** 3;
        for (0..self.output_size) |i| {
            const target: f64 = if (i == target_action) 1.0 else 0.0;
            d_output[i] = self.output_layer[i] - target;
        }

        var d_hidden = [_]f64{0.0} ** 64; 
        for (0..self.hidden_size) |j| {
            var error_sum: f64 = 0.0;
            for (0..self.output_size) |i| {
                error_sum += d_output[i] * self.w2[j * self.output_size + i];
                self.w2[j * self.output_size + i] -= self.learning_rate * d_output[i] * self.hidden_layer[j];
            }
            d_hidden[j] = error_sum * relu_deriv(self.hidden_layer[j]);
        }

        for (0..self.input_size) |j| {
            for (0..self.hidden_size) |i| {
                self.w1[j * self.hidden_size + i] -= self.learning_rate * d_hidden[i] * self.input_layer[j];
            }
        }
    }
};

// =========================================================================
// C FFI EXPORTS (For Python Bridge)
// =========================================================================

var global_arena: stash.Stash = undefined;
var global_nn: NeuralNet = undefined;
var is_initialized = false;
var global_prng: std.Random.DefaultPrng = undefined;

export fn init_kessler_ai() void {
    if (is_initialized) return;
    global_prng = std.Random.DefaultPrng.init(1337);
    global_arena = stash.Stash.stashCreate(std.heap.page_allocator, 1024 * 1024 * 10) catch return;
    
    // RENAISSANCE MATRIX: 15-Dimensional Vector Input (Macro Upgraded) -> 64 Hidden Node Deep Layer -> 3 Output Actions
    global_nn = NeuralNet.init(&global_arena, 15, 64, 3, &global_prng) catch return;
    is_initialized = true;
}

export fn predict_trade(features: [*]const f64, confidence_out: *f64) u8 {
    if (!is_initialized) return 0;
    
    // Unpack C-Array into Zig memory (15-Dimensional Macro State)
    var inputs = [_]f64{0.0} ** 15;
    for (0..15) |i| inputs[i] = features[i];
    
    const outputs = global_nn.forward(&inputs);
    
    var best_action: u8 = 0;
    var max_p: f64 = outputs[0];
    if (outputs[1] > max_p) { max_p = outputs[1]; best_action = 1; }
    if (outputs[2] > max_p) { max_p = outputs[2]; best_action = 2; }
    
    // V7 Institutional Upgrade: 
    // Force the network to be hyper-selective by imposing a base confidence penalty
    // This stops it from taking thousands of random trades in choppy markets.
    max_p = max_p * 0.85; // 15% flat reduction to confidence
    
    confidence_out.* = max_p;
    return best_action;
}

export fn train_kessler_ai(features: [*]const f64, target_action: u8) void {
    if (!is_initialized) return;
    
    var inputs = [_]f64{0.0} ** 15;
    for (0..15) |i| inputs[i] = features[i];
    
    _ = global_nn.forward(&inputs);
    global_nn.backward(target_action);
}

const c = @cImport({
    @cInclude("stdio.h");
});

export fn save_brain() void {
    if (!is_initialized) return;
    const file = c.fopen("kessler_brain.bin", "wb");
    if (file == null) return;
    defer _ = c.fclose(file);
    
    _ = c.fwrite(global_nn.w1.ptr, @sizeOf(f64), global_nn.w1.len, file);
    _ = c.fwrite(global_nn.w2.ptr, @sizeOf(f64), global_nn.w2.len, file);
}

export fn load_brain() void {
    if (!is_initialized) return;
    const file = c.fopen("kessler_brain.bin", "rb");
    if (file == null) return;
    defer _ = c.fclose(file);
    
    _ = c.fread(global_nn.w1.ptr, @sizeOf(f64), global_nn.w1.len, file);
    _ = c.fread(global_nn.w2.ptr, @sizeOf(f64), global_nn.w2.len, file);
}

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
