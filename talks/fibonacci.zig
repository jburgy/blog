const std = @import("std");

fn clsb(i: usize) usize {
    var n = i;
    while (true) {
        const m = n & (n - 1);
        if (m == 0)
            return n;
        n = m;
    }
}

fn fib(n: usize) usize {
    var m = clsb(n);
    var a: usize = 0;
    var b: usize = 1;

    while (m > 0) {
        const a2 = a * a;
        a = a * (a + b + b);
        b = a2 + b * b;
        if ((n & m) != 0) {
            const t = a + b;
            b = a;
            a = t;
        }
        m >>= 1;
    }
    return a;
}

pub fn main() void {
    std.debug.print("{d}\n", .{fib(92)});
}
