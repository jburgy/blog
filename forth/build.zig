const std = @import("std");
const Build = std.Build;
const OptimizeMode = std.builtin.OptimizeMode;

/// wasm32-wasi target: zig build -Dtarget=wasm32-wasi -Dcpu=baseline+tail_call
///
/// Zig's own linker produces a standalone `_start` command directly, the
/// same shape 5th.wasm (wasi-sdk) and jonesforth.wasm (hand-written) already
/// are. Each source's `openFlags` has a `.wasi` branch and `key()` already
/// exits cleanly on end-of-stream (see 6th.zig), so none needed source
/// changes beyond that — only a build target. Drive the result with
/// `runWasiCommand` (forth/wasm/wasi-worker.js), the same shared WASI/stdin
/// plumbing 5th.wasm and jonesforth.wasm use.
pub fn build(b: *Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});
    const wasi = target.result.os.tag == .wasi;

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
            // stage2_x86_64 can't guarantee @call(.always_tail, ...) (used
            // throughout the dispatch loop); aarch64 can, but CI runs on
            // ubuntu-latest (x86_64), so force LLVM for every native target.
            .use_llvm = true,
        });
        // Installs under `web/wasi/`, not `web/`: keeps the layout consistent
        // with a possible future wasm target sharing the `.wasm` basenames.
        const install = b.addInstallArtifact(exe, if (wasi) .{
            .dest_dir = .{ .override = .{ .custom = "web/wasi" } },
        } else .{});
        b.getInstallStep().dependOn(&install.step);

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
