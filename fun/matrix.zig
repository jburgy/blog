const std = @import("std");

fn matrix(T: type, rows: usize, cols: usize, allocator: std.mem.Allocator) ![][]T {
    const n = rows * (@sizeOf([]T) + cols * @sizeOf(T));
    const m = try allocator.allocWithOptions(u8, n, .of([]T), null);

    const rowSlices = std.mem.bytesAsSlice([]T, m);
    const data: []T = @alignCast(std.mem.bytesAsSlice(T, m[rows * @sizeOf([]T) ..]));

    for (0..rows) |rowIndex| {
        rowSlices[rowIndex] = data[rowIndex * cols ..][0..cols];
    }
    return rowSlices;
}

test matrix {
    const testing = std.testing;
    const M = 4;
    const N = 6;

    const m = try matrix(u32, M, N, testing.allocator);
    defer testing.allocator.free(m);

    m[2][4] = 123;
    try testing.expectEqual(123, m[2][4]);
}
