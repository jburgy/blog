const std = @import("std");
const Build = std.Build;
const OptimizeMode = std.builtin.OptimizeMode;

pub fn build(b: *Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    if (target.result.cpu.arch.isWasm()) {
        try buildWasm(b, target, optimize);
    } else {
        try buildNative(b, target, optimize);
    }
}

/// Invoke using
/// zig build -Dtarget=wasm32-emscripten -Dcpu=baseline+atomics+bulk_memory+tail_call
fn buildWasm(b: *Build, target: Build.ResolvedTarget, optimize: OptimizeMode) !void {
    const lib = b.addLibrary(.{
        .name = "zorth",
        .root_module = b.createModule(.{
            .root_source_file = b.path("6th.zig"),
            .target = target,
            .optimize = optimize,
        }),
        .linkage = .static,
    });
    lib.rdynamic = true;
    lib.linkLibC();

    const emcc = b.addSystemCommand(&.{"emcc"});
    emcc.addArg("-mtail-call");
    emcc.addArg("-pthread");
    emcc.addArg("-sPROXY_TO_PTHREAD");
    emcc.addArg("-sEXPORTED_FUNCTIONS=_malloc,_main");
    emcc.addArg("-sUSE_OFFSET_CONVERTER");
    emcc.addArg("-sASSERTIONS=2");
    emcc.addArg("--js-library=node_modules/xterm-pty/emscripten-pty.js");
    emcc.addArg("-o");
    const out_file = emcc.addOutputFileArg("6th.mjs");
    emcc.addArtifactArg(lib);

    const install = b.addInstallDirectory(.{
        .source_dir = out_file.dirname(),
        .install_dir = .prefix,
        .install_subdir = "web",
    });
    install.step.dependOn(&emcc.step);

    b.getInstallStep().dependOn(&install.step);
}

fn buildNative(b: *Build, target: Build.ResolvedTarget, optimize: OptimizeMode) !void {
    const exe = b.addExecutable(.{
        .name = "6th",
        .root_module = b.createModule(.{
            .root_source_file = b.path("6th.zig"),
            .target = target,
            .optimize = optimize,
        }),
        .use_llvm = true,
    });
    b.installArtifact(exe);
}
