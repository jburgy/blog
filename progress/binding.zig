const std = @import("std");
const py = @import("pydust");

const root = @This();

pub const Progress = py.class(struct {
    const Self = @This();
    index: std.Progress.Node.OptionalIndex,

    pub fn __init__(self: *Self) !void {
        self.index = std.Progress.start(.{}).index;
    }

    pub fn start(
        self: *const Self,
        args: struct { name: py.PyString(root), estimated_total_items: usize = 0 },
    ) !*const Self {
        const parent: std.Progress.Node = .{ .index = self.index };
        const node = parent.start(try args.name.asSlice(), args.estimated_total_items);
        return py.init(root, Self, .{ .index = node.index });
    }

    pub fn increase_estimate(self: *const Self, args: struct { count: usize }) void {
        const node: std.Progress.Node = .{ .index = self.index };
        node.increaseEstimatedTotalItems(args.count);
    }

    pub fn end(self: *const Self) void {
        const node: std.Progress.Node = .{ .index = self.index };
        node.end();
    }

    pub fn completeOne(self: *const Self) void {
        const node: std.Progress.Node = .{ .index = self.index };
        node.completeOne();
    }
});

comptime {
    py.rootmodule(root);
}
