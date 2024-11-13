const std = @import("std");
const Build = std.Build;
const OptimizeMode = std.builtin.OptimizeMode;

pub fn build(b: *Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    if (target.result.isWasm()) {
        try buildWasm(b, target, optimize);
    } else {
        try buildNative(b, target, optimize);
    }
}

/// Invoke using
/// zig build -Dtarget=wasm32-emscripten -Dcpu=baseline+atomics+bulk_memory+tail_call
fn buildWasm(b: *Build, target: Build.ResolvedTarget, optimize: OptimizeMode) !void {
    const lib = b.addStaticLibrary(.{
        .name = "zorth",
        .root_source_file = b.path("5th.zig"),
        .target = target,
        .optimize = optimize,
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
    const out_file = emcc.addOutputFileArg("zorth.mjs");
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
        .name = "5th",
        .root_source_file = b.path("5th.zig"),
        .target = target,
        .optimize = optimize,
    });
    b.installArtifact(exe);
}
