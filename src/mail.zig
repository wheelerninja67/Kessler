const std = @import("std");
const stash = @import("stash.zig");
const Atomic = std.atomic.Value;

pub const Intent = struct {
    agent_id: u32,
    asset_id: u32,
    quantity: f64,
    limit_price: f64,
    order_type: u8,
    side: u8,
    __pad: [6]u8 = [_]u8{0} ** 6,
};

pub const Mailbox = struct {
    buffer: []Intent,
    head: Atomic(u32),
    tail: Atomic(u32),
    _pad: [40]u8 = [_]u8{0} ** 40,

    pub fn push(self: *Mailbox, intent: Intent) bool {
        const t = self.tail.load(.monotonic);
        const h = self.head.load(.acquire);
        const next = (t + 1) % @as(u32, @intCast(self.buffer.len));
        if (next == h) return false;
        self.buffer[t] = intent;
        self.tail.store(next, .release);
        return true;
    }
};

pub fn init(arena: *stash.Stash, num_threads: u32, capacity: u32) ![]Mailbox {
    const mailboxes = try arena.stashAlloc(Mailbox, num_threads);
    for (mailboxes) |*mb| {
        mb.buffer = try arena.stashAlloc(Intent, capacity);
        mb.head = Atomic(u32).init(0);
        mb.tail = Atomic(u32).init(0);
    }
    return mailboxes;
}

/// Drains all intents from all mailboxes and processes them
pub fn drainAll(mailboxes: []Mailbox, context: anytype, callback: fn (@TypeOf(context), *const Intent) void) void {
    for (mailboxes) |*mb| {
        var h = mb.head.load(.monotonic);
        const t = mb.tail.load(.acquire);
        while (h != t) {
            callback(context, &mb.buffer[h]);
            h = (h + 1) % @as(u32, @intCast(mb.buffer.len));
        }
        mb.head.store(h, .release);
    }
}
