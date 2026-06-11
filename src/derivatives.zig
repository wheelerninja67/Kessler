const std = @import("std");

pub const OptionType = enum {
    Call,
    Put,
};

pub const Greeks = struct {
    delta: f64,
    gamma: f64,
    vega: f64,
    theta: f64,
    rho: f64,
};

// Standard normal cumulative distribution function (CDF)
pub fn normCDF(x: f64) f64 {
    const a1 = 0.254829592;
    const a2 = -0.284496736;
    const a3 = 1.421413741;
    const a4 = -1.453152027;
    const a5 = 1.061405429;
    const p  = 0.3275911;

    const sign = if (x < 0) -1.0 else 1.0;
    const x_abs = @abs(x);
    
    const t = 1.0 / (1.0 + p * x_abs);
    const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * @exp(-x_abs * x_abs / 2.0);
    
    return 0.5 * (1.0 + sign * y);
}

// Standard normal probability density function (PDF)
pub fn normPDF(x: f64) f64 {
    const pi = std.math.pi;
    return @exp(-0.5 * x * x) / @sqrt(2.0 * pi);
}

pub fn blackScholes(S: f64, K: f64, T: f64, r: f64, sigma: f64, opt_type: OptionType) f64 {
    if (T <= 0.0) {
        return switch (opt_type) {
            .Call => @max(S - K, 0.0),
            .Put => @max(K - S, 0.0),
        };
    }

    const d1 = (@log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * @sqrt(T));
    const d2 = d1 - sigma * @sqrt(T);

    return switch (opt_type) {
        .Call => S * normCDF(d1) - K * @exp(-r * T) * normCDF(d2),
        .Put  => K * @exp(-r * T) * normCDF(-d2) - S * normCDF(-d1),
    };
}

pub fn calculateGreeks(S: f64, K: f64, T: f64, r: f64, sigma: f64, opt_type: OptionType) Greeks {
    if (T <= 0.0) return Greeks{ .delta = 0, .gamma = 0, .vega = 0, .theta = 0, .rho = 0 };

    const d1 = (@log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * @sqrt(T));
    const d2 = d1 - sigma * @sqrt(T);

    var delta: f64 = 0;
    var theta: f64 = 0;
    var rho: f64 = 0;

    const gamma = normPDF(d1) / (S * sigma * @sqrt(T));
    const vega = S * normPDF(d1) * @sqrt(T);

    switch (opt_type) {
        .Call => {
            delta = normCDF(d1);
            theta = -(S * normPDF(d1) * sigma) / (2.0 * @sqrt(T)) - r * K * @exp(-r * T) * normCDF(d2);
            rho = K * T * @exp(-r * T) * normCDF(d2);
        },
        .Put => {
            delta = normCDF(d1) - 1.0;
            theta = -(S * normPDF(d1) * sigma) / (2.0 * @sqrt(T)) + r * K * @exp(-r * T) * normCDF(-d2);
            rho = -K * T * @exp(-r * T) * normCDF(-d2);
        }
    }

    return Greeks{
        .delta = delta,
        .gamma = gamma,
        .vega = vega,
        .theta = theta,
        .rho = rho,
    };
}
