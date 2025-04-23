//! See https://blog.jfo.click/how-zig-do/
const std = @import("std");
const testing = std.testing;
const expectEqualStrings = testing.expectEqualStrings;
const expectError = testing.expectError;

fn seekBack(src: []const u8, srcptr: u16) !u16 {
    var depth: u16 = 1;
    var ptr: u16 = srcptr;
    while (depth > 0) {
        const ov = @subWithOverflow(ptr, 1);
        if (ov[1] != 0) return error.OutOfBounds;
        ptr = ov[0];
        switch (src[ptr]) {
            '[' => depth -= 1,
            ']' => depth += 1,
            else => {},
        }
    }
    return ptr;
}

fn seekForward(src: []const u8, srcptr: u16) !u16 {
    var depth: u16 = 1;
    var ptr: u16 = srcptr;
    while (depth > 0) {
        ptr += 1;
        if (ptr >= src.len) return error.OutOfBounds;
        switch (src[ptr]) {
            '[' => depth += 1,
            ']' => depth -= 1,
            else => {},
        }
    }
    return ptr;
}

pub fn bf(src: []const u8, storage: []u8) !void {
    const stdout = std.io.getStdOut().writer();

    var memptr: u16 = 0;
    var srcptr: u16 = 0;
    while (srcptr < src.len) : (srcptr += 1) {
        switch (src[srcptr]) {
            '+' => storage[memptr] +%= 1,
            '-' => storage[memptr] -%= 1,
            '>' => memptr += 1,
            '<' => memptr -= 1,
            '[' => if (storage[memptr] == 0) {
                srcptr = try seekForward(src, srcptr);
            },
            ']' => if (storage[memptr] != 0) {
                srcptr = try seekBack(src, srcptr);
            },
            '.' => try stdout.print("{c}", .{storage[memptr]}),
            else => {},
        }
    }
}

test "+" {
    var storage = [_]u8{0};
    try bf("+++", storage[0..]);
    try expectEqualStrings("\x03", storage[0..]);
}

test "-" {
    var storage = [_]u8{0};
    try bf("---", storage[0..]);
    try expectEqualStrings("\xfd", storage[0..]);
}

test ">" {
    var storage = [_]u8{0} ** 5;
    try bf(">>>+++", storage[0..]);
    try expectEqualStrings("\x00\x00\x00\x03\x00", storage[0..]);
}

test "<" {
    var storage = [_]u8{0} ** 5;
    try bf(">>>+++<++<+", storage[0..]);
    try expectEqualStrings("\x00\x01\x02\x03\x00", storage[0..]);
}

test "[] skips execution and exits" {
    var storage = [_]u8{0} ** 3;
    try bf("+++++>[>+++++<-]", storage[0..]);
    try expectEqualStrings("\x05\x00\x00", storage[0..]);
}

test "[] executes and exits" {
    var storage = [_]u8{0} ** 2;
    try bf("+++++[>+++++<-]", storage[0..]);
    try expectEqualStrings("\x00\x19", storage[0..]);
}

test "[] skips execution with internal braces and exits" {
    var storage = [_]u8{0} ** 2;
    try bf("++>[>++[-]++<-]", storage[0..]);
    try expectEqualStrings("\x02\x00", storage[0..]);
}

test "[] executes with internal braces and exits" {
    var storage = [_]u8{0} ** 2;
    try bf("++[>++[-]++<-]", storage[0..]);
    try expectEqualStrings("\x00\x02", storage[0..]);
}

test "errors on mismatched brackets missing opening" {
    var storage = [_]u8{0} ** 2;
    try expectError(error.OutOfBounds, bf("++>++[-]++<-]", storage[0..]));
}

test "errors on mismatched brackets missing closing" {
    var storage = [_]u8{0} ** 2;
    try expectError(error.OutOfBounds, bf("+-[+>++[-]++<-", storage[0..]));
}
