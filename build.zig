const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    // ==========================================
    // 1. THE CORE ENGINE (zig build run)
    // ==========================================
    const exe = b.addExecutable(.{
        .name = "kessler",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/main.zig"),
            .target = target,
            .optimize = optimize,
            .link_libc = true,
        }),
    });

    b.installArtifact(exe);
    const run_cmd = b.addRunArtifact(exe);
    run_cmd.step.dependOn(b.getInstallStep());
    const run_step = b.step("run", "Run the Kessler systemic risk oracle");
    run_step.dependOn(&run_cmd.step);

    // ==========================================
    // 2. THE TEST SUITE (zig build test)
    // ==========================================
    const tests = b.addTest(.{
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/determinism_test.zig"), // <--- UPDATE THIS LINE
            .target = target,
            .optimize = optimize,
            .link_libc = true,
        }),
    });

    const run_tests = b.addRunArtifact(tests);
    const test_step = b.step("test", "Run the Determinism and Math tests");
    test_step.dependOn(&run_tests.step);
}
