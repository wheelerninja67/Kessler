const std = @import("std");

comptime {
    _ = @import("stash_test.zig");
    _ = @import("mail_test.zig");
    _ = @import("determinism_test.zig");
}
