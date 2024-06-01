const std = @import("std");

pub fn build(b: *std.Build) void {
    const exe = b.addExecutable(.{
        .name = "5th",
        .root_source_file = .{ .path = "5th.zig" },
        .target = b.host,
    });
    b.installArtifact(exe);
}
