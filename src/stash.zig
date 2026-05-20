const std = @import("std");

pub const Stash = struct {
    ptr: [*]align(64) u8,
    total_size: usize,
    offset: usize,

    pub fn stashCreate(size: usize) !Stash {
        // Fix: Zig 0.16.0 uses @"64" as the enum member name for 64-byte alignment
        const slice = try std.heap.page_allocator.alignedAlloc(u8, .@"64", size);
        return Stash{
            .ptr = slice.ptr,
            .total_size = size,
            .offset = 0,
        };
    }

    pub fn stashAlloc(self: *Stash, comptime T: type, count: usize) ![]T {
        const size = @sizeOf(T) * count;

        // Manual 64-byte alignment adjustment for the current offset
        const alignment = 64;
        const adjustment = (alignment - (self.offset % alignment)) % alignment;
        const start = self.offset + adjustment;

        if (start + size > self.total_size) return error.OutOfMemory;

        self.offset = start + size;
        const raw_ptr = self.ptr + start;

        // @alignCast ensures the compiler knows this pointer is 64-byte aligned
        const aligned_ptr: [*]align(64) T = @ptrCast(@alignCast(raw_ptr));
        return aligned_ptr[0..count];
    }

    pub fn stashDestroy(self: *Stash) void {
        std.heap.page_allocator.free(self.ptr[0..self.total_size]);
    }

    pub fn stashBytesRemaining(self: *const Stash) usize {
        return self.total_size - self.offset;
    }
};
