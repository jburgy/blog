const std = @import("std");

pub fn build(b: *std.Build) !void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const version = b.option([]const u8, "version", "sysconfig.get_python_version()") orelse b.run(&.{ "python", "-c", "import sysconfig; print(sysconfig.get_python_version(), end='')" });
    const include: std.Build.LazyPath = b.option(std.Build.LazyPath, "include", "sysconfig.get_path('include')") orelse .{ .cwd_relative = b.run(&.{ "python", "-c", "import sysconfig; print(sysconfig.get_path('include'), end='')" }) };
    const stdlib: std.Build.LazyPath = b.option(std.Build.LazyPath, "stdlib", "sysconfig.get_path('stdlib')") orelse .{ .cwd_relative = b.run(&.{ "python", "-c", "import sysconfig; print(sysconfig.get_path('stdlib'), end='')" }) };

    const py = b.addTranslateC(.{
        .root_source_file = try include.join(b.allocator, "Python.h"),
        .target = target,
        .optimize = optimize,
    });
    py.addIncludePath(include);

    const py_mod = py.createModule();
    py_mod.addLibraryPath(stdlib.dirname());
    py_mod.linkSystemLibrary(b.fmt("python{s}", .{version}), .{});

    const lib_mod = b.createModule(.{
        .root_source_file = b.path("binding.zig"),
        .target = target,
        .optimize = optimize,
    });
    lib_mod.addImport("python", py_mod);

    const lib = b.addLibrary(.{
        .linkage = .dynamic,
        .name = "binding",
        .root_module = lib_mod,
    });
    b.getInstallStep().dependOn(&b.addInstallFileWithDir(
        lib.getEmittedBin(),
        .prefix,
        "binding.abi3.so",
    ).step);

    const unit_tests = b.addTest(.{ .root_module = lib_mod });
    const run_unit_tests = b.addRunArtifact(unit_tests);
    const test_step = b.step("test", "Run unit tests");
    test_step.dependOn(&run_unit_tests.step);
}
