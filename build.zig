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

    // ==========================================
    // 3. THE GUI VIEWER (zig build kessler-gui)
    // ==========================================
    const gui_exe = b.addExecutable(.{
        .name = "kessler-gui",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/gui_main.zig"),
            .target = target,
            .optimize = optimize,
            .link_libc = true,
        }),
    });

    gui_exe.root_module.link_libcpp = true;

    gui_exe.root_module.addCSourceFiles(.{
        .files = &.{
            "libs/imgui/imgui.cpp",
            "libs/imgui/imgui_draw.cpp",
            "libs/imgui/imgui_tables.cpp",
            "libs/imgui/imgui_widgets.cpp",
            "libs/imgui/imgui_demo.cpp",
            "libs/imgui/backends/imgui_impl_glfw.cpp",
            "libs/imgui/backends/imgui_impl_opengl3.cpp",
            "src/gui/wrapper.cpp",
        },
        .flags = &.{"-fno-sanitize=undefined"},
    });

    gui_exe.root_module.addIncludePath(b.path("libs/imgui"));
    gui_exe.root_module.addIncludePath(b.path("libs/imgui/backends"));
    gui_exe.root_module.addIncludePath(b.path("src"));

    gui_exe.root_module.linkSystemLibrary("glfw", .{});
    gui_exe.root_module.linkSystemLibrary("GL", .{});

    b.installArtifact(gui_exe);

    const gui_run = b.addRunArtifact(gui_exe);
    gui_run.step.dependOn(b.getInstallStep());
    const gui_step = b.step("kessler-gui", "Run the Kessler GUI viewer");
    gui_step.dependOn(&gui_run.step);


}
