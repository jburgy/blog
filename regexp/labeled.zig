//! Zig transcription of switched.c's Thompson-construction compiler and
//! matcher, but dispatched with Zig 0.14's labeled `switch`/`continue`
//! instead of a plain `while (true) switch (...)` or GCC's labels as
//! values -- see https://simonklee.dk/labeled-switch. A labeled `switch`
//! lets each case `continue` straight to another case by value, which
//! LLVM lowers to one indirect jump per case (its own entry in a jump
//! table) rather than one shared dispatch site the way `switched.c`'s
//! `for (;;) switch (...)` does, so it sits between `switched.c` and
//! `threaded.c` in spirit: portable standard Zig, but with per-case
//! computed jumps like `threaded.c`'s computed goto.
//!
//! `union cell`'s `.link` field is a raw pointer in switched.c/threaded.c
//! (and a byte/word offset in jit.py's X86_64/Arm64 encoders, since Python
//! has no pointer arithmetic either). Cell here borrows that same idea from
//! jansforth.rs, whose Forth VM addresses its whole flat `memory` array by
//! plain integer index rather than by native pointer: `Cell.link` is a
//! `u16` index into the `code` slice, so `study`/`compile` can be ordinary,
//! separate functions -- Zig has no computed-goto restriction tying them to
//! `search`'s own labels the way threaded.c's `op[]` is tied to `search`.
//!
//! See also Thompson, Ken. Regular Expression Search Algorithm,
//! Communications of the ACM 11(6) (June 1968), pp. 419-422.

const std = @import("std");
const Allocator = std.mem.Allocator;
const testing = std.testing;

/// switched.c/threaded.c size their `stack`/`lambda`/`clist`/`nlist` at C's
/// `BUFSIZ` (glibc: 8192) and never check it -- an overflowing pattern or
/// subject just corrupts memory there. Zig's bounds-checked arrays fail
/// loudly instead of silently, but they still need the same headroom to
/// avoid failing *at all* on inputs no bigger than what BUFSIZ tolerates.
const BUFSIZ = 8192;

const LPAREN: u8 = 128;
const RPAREN: u8 = 129;
const ALTERN: u8 = 130;
const CONCAT: u8 = 131;
const KLEENE: u8 = 132;

/// One cell of a compiled program: either an opcode, a link (index of
/// another cell in the same slice), or a literal character. Which field is
/// meaningful is determined purely by position, exactly as in switched.c's
/// `union cell` -- there is no runtime tag.
pub const Cell = union {
    op: Op,
    link: u16,
    chr: u8,
};

/// `xchg` never appears in a compiled program; it is search()'s own
/// starting state, played by value rather than by a sentinel cell.
pub const Op = enum(u8) { jump, char, fork, stop, fail, xchg };

fn prepare(allocator: Allocator, src: []const u8) ![]u8 {
    var escape = [_]u8{0} ** 128;
    escape['a'] = 7; // '\a'
    escape['b'] = 8; // '\b'
    escape['f'] = 12; // '\f'
    escape['n'] = 10; // '\n'
    escape['r'] = 13; // '\r'
    escape['t'] = 9; // '\t'
    escape['v'] = 11; // '\v'
    for ("\"()*\\|") |c| escape[c] = c;

    const dest = try allocator.alloc(u8, 2 * (src.len + 1));
    var j: usize = 0;
    var concat = false;
    var nparen: i32 = 0;
    var i: usize = 0;
    while (i < src.len) : (i += 1) {
        var c = src[i];
        switch (c) {
            '(' => {
                if (concat) {
                    dest[j] = CONCAT;
                    j += 1;
                }
                dest[j] = LPAREN;
                j += 1;
                concat = false;
                nparen += 1;
                continue;
            },
            ')' => {
                dest[j] = RPAREN;
                j += 1;
                nparen -= 1;
            },
            '*' => {
                dest[j] = KLEENE;
                j += 1;
            },
            '|' => {
                dest[j] = ALTERN;
                j += 1;
                concat = false;
                continue;
            },
            '\\' => {
                const next = if (i + 1 < src.len) src[i + 1] else 0;
                const mapped = escape[next];
                if (mapped != 0) {
                    c = mapped;
                    i += 1;
                } else {
                    c = '\\';
                }
                if (concat) {
                    dest[j] = CONCAT;
                    j += 1;
                }
                dest[j] = c;
                j += 1;
            },
            else => {
                if (concat) {
                    dest[j] = CONCAT;
                    j += 1;
                }
                dest[j] = c;
                j += 1;
            },
        }
        concat = true;
        if (nparen < 0) std.debug.print("unbalanced parentheses\n", .{});
    }
    dest[j] = RPAREN;
    j += 1;
    return dest[0..j];
}

/// http://cs.lasierra.edu/~ehwang/cptg454/postfix.pdf
fn convert(allocator: Allocator, re: []const u8) ![]u8 {
    const src = try prepare(allocator, re);
    var stack: [BUFSIZ]u8 = undefined;
    stack[0] = LPAREN;
    var top: usize = 1;

    const dest = try allocator.alloc(u8, 2 * (src.len + 1));
    var j: usize = 0;

    for (src) |c| {
        switch (c) {
            LPAREN => {
                stack[top] = c;
                top += 1;
            },
            RPAREN, ALTERN, CONCAT, KLEENE => {
                while (c <= stack[top - 1]) {
                    top -= 1;
                    dest[j] = stack[top];
                    j += 1;
                }
                if (c == RPAREN) {
                    top -= 1; // discard LPAREN
                } else {
                    stack[top] = c;
                    top += 1;
                }
            },
            else => {
                dest[j] = c;
                j += 1;
            },
        }
    }
    return dest[0..j];
}

// Node layouts, mirroring switched.c's 4/8/6-cell encodings.  The leading
// JUMP of a node doubles as the successor link of the node before it,
// which is what makes concatenation free.
//
//   char  JUMP <body>  CHAR <c>              entry = body, exit = the cell after
//   *     FORK <body>  JUMP <exit>
//         FORK <body>  JUMP <exit>           entry = the second FORK, whose JUMP recognizes lambda
//   |     JUMP <exit>  FORK <b>  JUMP <a>    entry = the FORK, exit = the cell after
//
// lambda[] is Thompson's revision from the Notes of his paper: it points
// at the JUMP taken when a fragment matches the empty string, or is null.
// Starring a fragment turns that JUMP into FAIL so that a** cannot loop.
fn codelen(src: []const u8) usize {
    var n: usize = 1; // one cell for the trailing STOP
    for (src) |c| {
        switch (c) {
            CONCAT => {},
            KLEENE => n += 8,
            ALTERN => n += 6,
            else => n += 4,
        }
    }
    return n;
}

fn compile(allocator: Allocator, src: []const u8) ![]Cell {
    var stack: [BUFSIZ]u16 = undefined;
    var lambda: [BUFSIZ]?u16 = undefined;
    var top: usize = 0;

    const code = try allocator.alloc(Cell, codelen(src));
    var pc: u16 = 0;

    for (src) |c| {
        switch (c) {
            CONCAT => {
                if (lambda[top - 1] == null) lambda[top - 2] = null;
                top -= 1;
            },
            KLEENE => {
                code[pc + 0] = .{ .op = .fork };
                code[pc + 1] = .{ .link = code[stack[top - 1]].link };
                code[pc + 2] = .{ .op = .jump };
                code[pc + 3] = .{ .link = pc + 8 };
                code[pc + 4] = .{ .op = .fork };
                code[pc + 5] = .{ .link = code[stack[top - 1]].link };
                code[pc + 6] = .{ .op = .jump };
                code[pc + 7] = .{ .link = pc + 8 };
                code[stack[top - 1]].link = pc + 4;
                if (lambda[top - 1]) |l| code[l].op = .fail;
                lambda[top - 1] = pc + 6;
                pc += 8;
            },
            ALTERN => {
                code[pc + 0] = .{ .op = .jump };
                code[pc + 1] = .{ .link = pc + 6 };
                code[pc + 2] = .{ .op = .fork };
                code[pc + 3] = .{ .link = code[stack[top - 1]].link };
                code[pc + 4] = .{ .op = .jump };
                code[pc + 5] = .{ .link = code[stack[top - 2]].link };
                code[stack[top - 1]].link = pc + 6;
                code[stack[top - 2]].link = pc + 2;
                if (lambda[top - 2] == null) {
                    lambda[top - 2] = lambda[top - 1];
                } else if (lambda[top - 1]) |l| {
                    code[l + 1].link = lambda[top - 2].?;
                }
                pc += 6;
                top -= 1;
            },
            else => {
                lambda[top] = null;
                stack[top] = pc + 1;
                top += 1;
                code[pc + 0] = .{ .op = .jump };
                code[pc + 1] = .{ .link = pc + 2 };
                code[pc + 2] = .{ .op = .char };
                code[pc + 3] = .{ .chr = c };
                pc += 4;
            },
        }
    }
    code[pc] = .{ .op = .stop };
    return code;
}

pub fn study(allocator: Allocator, re: []const u8) ![]Cell {
    var arena = std.heap.ArenaAllocator.init(allocator);
    defer arena.deinit();
    const postfix = try convert(arena.allocator(), re);
    return compile(allocator, postfix);
}

/// `code[pc].op`, then advance pc past it -- the labeled-switch equivalent
/// of switched.c's `(pc++)->op` used at every dispatch site.
fn fetch(code: []const Cell, pc: *u16) Op {
    const op = code[pc.*].op;
    pc.* += 1;
    return op;
}

/// Leftmost, unanchored search: end of the match, or null. Mirrors
/// switched.c's search() cell for cell; `si` plays the role of `s - text`,
/// and a `null` clist entry plays the role of switched.c's `&xchg`
/// sentinel (a cell address outside `code` itself).
pub fn search(code: []const Cell, s: []const u8) ?usize {
    var clist: [BUFSIZ]?u16 = undefined;
    var nlist: [BUFSIZ]u16 = undefined;
    var cnode: usize = 0;
    var nnode: usize = 0;
    var si: usize = 0;
    var c: ?u8 = null; // null primes the first exchange, like switched.c's `c = EOF`
    var pc: u16 = 0;

    dispatch: switch (Op.xchg) {
        .xchg => {
            if (c) |ch| {
                if (ch == 0) return null;
            }
            clist[cnode] = null;
            cnode += 1;
            while (nnode > 0) {
                nnode -= 1;
                clist[cnode] = nlist[nnode];
                cnode += 1;
            }
            // read the current char and advance, like C's `c = *s++` --
            // that post-increment fires even when reading the trailing
            // NUL, so `si` must too, or STOP's `si - 1` is off by one.
            c = if (si < s.len) s[si] else 0;
            si += 1;
            pc = 0;
            continue :dispatch fetch(code, &pc);
        },
        .jump => {
            pc = code[pc].link;
            continue :dispatch fetch(code, &pc);
        },
        .char => {
            const chr = code[pc].chr;
            pc += 1;
            if (chr == c.?) {
                // skip duplicates, or (a|a)* doubles nlist on every character
                var dup = false;
                var i: usize = 0;
                while (i < nnode) : (i += 1) {
                    if (nlist[i] == pc) {
                        dup = true;
                        break;
                    }
                }
                if (!dup) {
                    nlist[nnode] = pc;
                    nnode += 1;
                }
            }
            continue :dispatch .fail;
        },
        .fail => {
            // this thread is done for this character: run the next one on clist
            cnode -= 1;
            if (clist[cnode]) |idx| {
                pc = idx;
                continue :dispatch fetch(code, &pc);
            }
            continue :dispatch .xchg;
        },
        .fork => {
            clist[cnode] = pc + 1; // run the fall-through later, the branch now
            cnode += 1;
            pc = code[pc].link;
            continue :dispatch fetch(code, &pc);
        },
        .stop => return si - 1,
    }
}

const cases = .{
    .{ "abcdefg", "abcdefg", 7 },
    .{ "(a|b)*a", "ababababab", 1 },
    .{ "(a|b)*a", "aaaaaaaaba", 1 },
    .{ "(a|b)*a", "aaaaaabac", 1 },
    .{ "a(b|c)*d", "abccbcccd", 9 },
    .{ "a(b|c)*d", "abccbcccde", 9 },
    .{ "(a|a)*", "aaaaaaaaaaaaaaaaaaaaaaaaaaaa", 0 },
    .{ "(a|a)*b", "aaaaaaaaaaaaaaaab", 17 },
    .{ "a(b|c)*d", "abccccccccd", 11 },
    .{ "a*", "aaab", 0 },
    .{ "a(b|c)*d", "abcd", 4 },
    .{ "a**", "b", 0 },
    .{ "(a*b*)*c", "abbac", 5 },
    .{ "(a*|b*)*c", "abac", 4 },
    .{ "b*(c|d)", "c", 1 },
};

test "search matches switched.c/threaded.c on the same table" {
    inline for (cases) |case| {
        const code = try study(testing.allocator, case[0]);
        defer testing.allocator.free(code);
        try testing.expectEqual(@as(?usize, case[2]), search(code, case[1]));
    }
}

test "search reports null when nothing matches" {
    const code = try study(testing.allocator, "xyz");
    defer testing.allocator.free(code);
    try testing.expectEqual(@as(?usize, null), search(code, "abc"));
}
