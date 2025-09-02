const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    if (b.option([]const u8, "include", "sysconfig.get_path('include')")) |include| {
        const lib_mod = b.createModule(.{
            .root_source_file = b.path("binding.zig"),
            .target = target,
            .optimize = optimize,
        });
        lib_mod.addIncludePath(.{ .cwd_relative = include });

        if (b.option([]const u8, "stdlib", "sysconfig.get_path('stdlib')")) |stdlib| {
            var it = std.mem.splitBackwardsScalar(u8, stdlib, '/');

            const lib = b.addLibrary(.{
                .name = "binding",
                .root_module = lib_mod,
            });
            lib.linkSystemLibrary(it.first());
            lib.addLibraryPath(.{ .cwd_relative = it.rest() });
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
