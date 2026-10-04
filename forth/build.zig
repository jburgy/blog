const std = @import("std");
const Build = std.Build;
const OptimizeMode = std.builtin.OptimizeMode;

pub fn build(b: *Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    if (target.result.os.tag == .wasi) {
        try buildWasi(b, target, optimize);
    } else {
        try buildNative(b, target, optimize);
    }
}

/// Invoke using
/// zig build -Dtarget=wasm32-wasi -Dcpu=baseline+tail_call
///
/// Zig's own linker produces a standalone `_start` command directly, the
/// same shape 5th.wasm (wasi-sdk) and jonesforth.wasm (hand-written) already
/// are. `openFlags` already has a `.wasi` branch and `key()` already exits
/// cleanly on end-of-stream (see 6th.zig), so this needed no source changes
/// — only a build target. Drive the result with `runWasiCommand`
/// (forth/wasm/wasi-worker.js), the same shared WASI/stdin plumbing 5th.wasm
/// and jonesforth.wasm use.
///
/// Installs under `web/wasi/`, not `web/`: keeps the layout consistent with
/// a possible future wasm target sharing the `6th.wasm` basename.
fn buildWasi(b: *Build, target: Build.ResolvedTarget, optimize: OptimizeMode) !void {
    const exe = b.addExecutable(.{
        .name = "6th",
        .root_module = b.createModule(.{
            .root_source_file = b.path("6th.zig"),
            .target = target,
            .optimize = optimize,
            .link_libc = true,
        }),
    });

    const install = b.addInstallArtifact(exe, .{
        .dest_dir = .{ .override = .{ .custom = "web/wasi" } },
    });
    b.getInstallStep().dependOn(&install.step);
}

fn buildNative(b: *Build, target: Build.ResolvedTarget, optimize: OptimizeMode) !void {
    const test_step = b.step("test", "Run 6th.zig/jansforth.zig/labeled.zig/hybrid.zig tests");

    // (executable name, root source file, test description)
    const sources = [_][2][]const u8{
        .{ "6th", "6th.zig" },
        .{ "jansforth-zig", "jansforth.zig" },
        .{ "labeled-zig", "labeled.zig" },
        .{ "hybrid-zig", "hybrid.zig" },
    };
    for (sources) |entry| {
        const name, const source_file = entry;

        const exe = b.addExecutable(.{
            .name = name,
            .root_module = b.createModule(.{
                .root_source_file = b.path(source_file),
                .target = target,
                .optimize = optimize,
                .link_libc = true,
            }),
            .use_llvm = true,
        });
        b.installArtifact(exe);

        const tests = b.addTest(.{
            .name = b.fmt("{s}-tests", .{name}),
            .root_module = b.createModule(.{
                .root_source_file = b.path(source_file),
                .target = target,
                .optimize = optimize,
                .link_libc = true,
            }),
            .use_llvm = true,
        });
        const run_tests = b.addRunArtifact(tests);
        test_step.dependOn(&run_tests.step);
    }
}
