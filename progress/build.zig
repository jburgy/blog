const std = @import("std");

pub fn build(b: *std.Build) !void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    if (b.option(std.Build.LazyPath, "include", "sysconfig.get_path('include')")) |include| {
        const lib_mod = b.createModule(.{
            .root_source_file = b.path("binding.zig"),
            .target = target,
            .optimize = optimize,
        });
        lib_mod.addIncludePath(include);

        const py = b.addTranslateC(.{
            .root_source_file = try include.join(b.allocator, "Python.h"),
            .target = target,
            .optimize = optimize,
        });
        py.addIncludePath(include);
        const py_mod = py.createModule();

        if (b.option(std.Build.LazyPath, "stdlib", "sysconfig.get_path('stdlib')")) |stdlib| {
            py_mod.addLibraryPath(stdlib);
            lib_mod.addImport("python", py_mod);

            const lib = b.addLibrary(.{
                .name = "binding",
                .root_module = lib_mod,
            });
            b.getInstallStep().dependOn(&b.addInstallFileWithDir(
                lib.getEmittedBin(),
                .prefix,
                "binding.abi3.so",
            ).step);
        } else {
            b.getInstallStep().dependOn(&b.addFail("The -Dstdlib=... option is required for this step").step);
        }

        const unit_tests = b.addTest(.{ .root_module = lib_mod });
        const run_unit_tests = b.addRunArtifact(unit_tests);
        const test_step = b.step("test", "Run unit tests");
        test_step.dependOn(&run_unit_tests.step);
    } else {
        b.getInstallStep().dependOn(&b.addFail("The -Dinclude=... option is required for this step").step);
    }
}
