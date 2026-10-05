//! [labeled.zig](labeled.zig)'s VM again, but the `continue :dispatch` is
//! replicated for only the *hot* opcodes; the other 63 prongs fall out of the
//! switch to a single shared `op = fetchOp(...)` at the bottom of the loop,
//! the way [jansforth.zig](jansforth.zig) dispatches everything.
//!
//! labeled.zig gives every one of its 100 `fetchOp` prongs its own dispatch
//! site, which makes each prong a predecessor of every other prong. LLVM
//! answers that with 104 copies of the jump table (+41 KB of `.rodata`) and,
//! worse, gives up on register-allocating the VM state: `ip`/`cfa`/`sp`/`rsp`
//! end up in stack slots that every primitive read-modify-writes. Replicating
//! only the prongs that actually run often keeps the branch-prediction benefit
//! where it pays and lets the rest share one site; see README.md for the
//! instruction counts.
//!
//! The hot set is every opcode reaching >=1% of executed instructions on at
//! least one workload in `benchmark.py`'s suite -- deliberately not just the
//! Fibonacci benchmark, which is a tight integer/stack loop and would have
//! nominated only 20 opcodes covering 40% of the compile-heavy workload.
//! Re-deriving it needs an opcode counter patched into the dispatch loop,
//! which is not committed.
//!
//! Everything else is a copy of labeled.zig, which is itself a copy of
//! jansforth.zig: the dictionary, every opcode's semantics, `main()` and the
//! tests are identical, so the benchmark only sees the dispatch shape.
const std = @import("std");
const builtin = @import("builtin");
const native = builtin.cpu.arch.endian();

const WORD_BUFFER: usize = 0x5014;
const STATE_ADDR: usize = 0x1400;
const HERE_ADDR: usize = 0x1401;
const LATEST_ADDR: usize = 0x1402;
const S0_ADDR: usize = 0x1403;
const BASE_ADDR: usize = 0x1404;
const LIT_CFA: i32 = 5251;

// jonesforth's own portable flag numbering (not the real platform O_* bits);
// translated to the host's real flags by `openFlags` below, exactly like
// 6th.zig does for the same reason: __O_CREAT etc. are Forth-visible
// integers a program can OR together, so they need one fixed meaning
// regardless of which OS actually runs the interpreter.
const O_RDONLY = 0o0;
const O_WRONLY = 0o1;
const O_RDWR = 0o2;
const O_CREAT = 0o100;
const O_EXCL = 0o200;
const O_TRUNC = 0o1_000;
const O_APPEND = 0o2_000;
const O_NONBLOCK = 0o4_000;

fn openFlags(flags: i32) std.c.O {
    const f: usize = @intCast(flags);
    return switch (builtin.os.tag) {
        .linux, .macos => .{
            // O_RDONLY/O_WRONLY/O_RDWR are 0/1/2: the access mode is the
            // low two bits, not just the O_RDWR bit alone (masking with
            // O_RDWR would fold plain O_WRONLY into O_RDONLY).
            .ACCMODE = @enumFromInt(f & 0x3),
            .CREAT = (f & O_CREAT) != 0,
            .EXCL = (f & O_EXCL) != 0,
            .TRUNC = (f & O_TRUNC) != 0,
            .APPEND = (f & O_APPEND) != 0,
            .NONBLOCK = (f & O_NONBLOCK) != 0,
        },
        else => @panic("unsupported OS"),
    };
}

// jonesforth's SYS_* opcodes only ever feed into our own `switch (n)` below
// (unlike jansforth.c, which hands them straight to a raw syscall(2)), so
// any distinct sentinel would do; these match jansforth.rs's real BSD/Linux
// syscall numbers for recognizability.
const SysNum = if (builtin.os.tag == .macos) struct {
    const EXIT: i32 = 0x2000001;
    const READ: i32 = 0x2000003;
    const WRITE: i32 = 0x2000004;
    const OPEN: i32 = 0x2000005;
    const CLOSE: i32 = 0x2000006;
    const BRK: i32 = 0x20000d6;
    const CREAT: i32 = 0x2000018;
} else struct {
    const EXIT: i32 = 1;
    const READ: i32 = 3;
    const WRITE: i32 = 4;
    const OPEN: i32 = 5;
    const CLOSE: i32 = 6;
    const BRK: i32 = 45;
    const CREAT: i32 = 8;
};

/// Enum values match jansforth.rs's `match` arms (0-100), *not* jansforth.c's
/// `enum Builtin` ordinals: the C enum also declares `TDFA`/`COLON`/
/// `SEMICOLON` as placeholders for words whose code field is always DOCOL,
/// which shifts every later ordinal. jansforth.rs's dictionary builder never
/// reserves opcode numbers for composite words, so its numbering (and this
/// one) skips straight over them instead.
pub const Op = enum(i32) {
    DOCOL = 0,
    DROP = 1,
    SWAP = 2,
    DUP = 3,
    OVER = 4,
    ROT = 5,
    NROT = 6,
    TWODROP = 7,
    TWODUP = 8,
    TWOSWAP = 9,
    QDUP = 10,
    INCR = 11,
    DECR = 12,
    INCR4 = 13,
    DECR4 = 14,
    ADD = 15,
    SUB = 16,
    MUL = 17,
    DIVMOD = 18,
    EQU = 19,
    NEQU = 20,
    LT = 21,
    GT = 22,
    LE = 23,
    GE = 24,
    ZEQU = 25,
    ZNEQU = 26,
    ZLT = 27,
    ZGT = 28,
    ZLE = 29,
    ZGE = 30,
    AND = 31,
    OR = 32,
    XOR = 33,
    INVERT = 34,
    EXIT = 35,
    LIT = 36,
    STORE = 37,
    FETCH = 38,
    ADDSTORE = 39,
    SUBSTORE = 40,
    STOREBYTE = 41,
    FETCHBYTE = 42,
    CCOPY = 43,
    CMOVE = 44,
    STATE = 45,
    HERE = 46,
    LATEST = 47,
    SZ = 48,
    BASE = 49,
    VERSION = 50,
    RZ = 51,
    __DOCOL = 52,
    F_IMMED = 53,
    F_HIDDEN = 54,
    F_LENMASK = 55,
    SYS_EXIT = 56,
    SYS_OPEN = 57,
    SYS_CLOSE = 58,
    SYS_READ = 59,
    SYS_WRITE = 60,
    SYS_CREAT = 61,
    SYS_BRK = 62,
    __O_RDONLY = 63,
    __O_WRONLY = 64,
    __O_RDWR = 65,
    __O_CREAT = 66,
    __O_EXCL = 67,
    __O_TRUNC = 68,
    __O_APPEND = 69,
    __O_NONBLOCK = 70,
    TOR = 71,
    FROMR = 72,
    RSPFETCH = 73,
    RSPSTORE = 74,
    RDROP = 75,
    DSPFETCH = 76,
    DSPSTORE = 77,
    KEY = 78,
    EMIT = 79,
    WORD = 80,
    NUMBER = 81,
    FIND = 82,
    TCFA = 83,
    CREATE = 84,
    COMMA = 85,
    LBRAC = 86,
    RBRAC = 87,
    IMMEDIATE = 88,
    HIDDEN = 89,
    TICK = 90,
    BRANCH = 91,
    ZBRANCH = 92,
    LITSTRING = 93,
    TELL = 94,
    INTERPRET = 95,
    CHAR = 96,
    EXECUTE = 97,
    SYSCALL3 = 98,
    SYSCALL2 = 99,
    SYSCALL1 = 100,
    _,
};

const NAMES =
    "DROP SWAP DUP OVER ROT -ROT 2DROP 2DUP 2SWAP ?DUP 1+ 1- 4+ 4- " ++
    "+ - * /MOD = <> < > <= >= 0= 0<> 0< 0> 0<= 0>= AND OR XOR INVERT " ++
    "EXIT LIT ! @ +! -! C! C@ C@C! CMOVE STATE HERE LATEST S0 BASE VERSION R0 DOCOL " ++
    "F_IMMED F_HIDDEN F_LENMASK SYS_EXIT SYS_OPEN SYS_CLOSE SYS_READ SYS_WRITE SYS_CREAT SYS_BRK " ++
    "O_RDONLY O_WRONLY O_RDWR O_CREAT O_EXCL O_TRUNC O_APPEND O_NONBLOCK " ++
    ">R R> RSP@ RSP! RDROP DSP@ DSP! KEY EMIT WORD NUMBER FIND >CFA >DFA CREATE , [ ] " ++
    "IMMEDIATE HIDDEN HIDE : ; ' BRANCH 0BRANCH LITSTRING TELL INTERPRET QUIT CHAR EXECUTE " ++
    "SYSCALL3 SYSCALL2 SYSCALL1";

const IMMEDIATE_WORDS = [_][]const u8{ "[", "IMMEDIATE", ";" };

const CompositeWord = struct { name: []const u8, body: []const u8 };

/// The five words whose code field is DOCOL (a colon-definition), spelled
/// out here instead of being typed into the static rodata table: `LATEST`,
/// `>CFA`, and friends are already primitives by the time these run, so
/// each body is just the sequence of words/literals jonesforth.f would
/// compile for the same definition.
const COMPOSITE_WORDS = [_]CompositeWord{
    .{ .name = ">DFA", .body = ">CFA 4+ EXIT" },
    .{ .name = ":", .body = "WORD CREATE LIT 0 , LATEST @ HIDDEN ] EXIT" },
    .{ .name = ";", .body = "LIT EXIT , LATEST @ HIDDEN [ EXIT" },
    .{ .name = "HIDE", .body = "WORD FIND HIDDEN EXIT" },
    .{ .name = "QUIT", .body = "R0 RSP! INTERPRET BRANCH -8" },
};

fn readI32At(bytes: []const u8, addr: usize) i32 {
    return std.mem.readInt(i32, bytes[addr..][0..4], native);
}

fn writeI32At(bytes: []u8, addr: usize, value: i32) void {
    std.mem.writeInt(i32, bytes[addr..][0..4], value, native);
}

fn alignUp4(len: usize) usize {
    return (len + 4) & ~@as(usize, 3);
}

fn findComposite(name: []const u8) ?[]const u8 {
    for (COMPOSITE_WORDS) |entry| {
        if (std.mem.eql(u8, entry.name, name)) return entry.body;
    }
    return null;
}

/// Builds the same dictionary as jansforth.c's static `rodata[]`, starting
/// at the same `5133 << 2` byte offset and walking `NAMES` in the same
/// order, so the resulting bytes are identical to the C table (validated
/// the same way jansforth.rs is, by comparison.rs).
fn buildRodata(bytes: []u8) void {
    var here: usize = 5133 << 2;
    var latest: usize = 0;
    var code: i32 = 1;

    var names_it = std.mem.tokenizeScalar(u8, NAMES, ' ');
    while (names_it.next()) |name| {
        writeI32At(bytes, here, @intCast(latest));
        latest = here;

        var flag: u8 = @intCast(name.len);
        for (IMMEDIATE_WORDS) |w| {
            if (std.mem.eql(u8, w, name)) {
                flag |= 0x80;
                break;
            }
        }
        bytes[here + 4] = flag;
        @memcpy(bytes[here + 5 ..][0..name.len], name);
        here += 4 + alignUp4(name.len);

        if (findComposite(name)) |body| {
            writeI32At(bytes, here, 0); // DOCOL
            here += 4;
            var body_it = std.mem.tokenizeScalar(u8, body, ' ');
            while (body_it.next()) |word| {
                if (std.fmt.parseInt(i32, word, 10)) |num| {
                    writeI32At(bytes, here, num);
                    here += 4;
                } else |_| {
                    var node = latest;
                    while (node != 0 and (bytes[node + 4] & 0x3F != word.len or
                        !std.mem.eql(u8, bytes[node + 5 ..][0..word.len], word)))
                    {
                        node = @intCast(readI32At(bytes, node));
                    }
                    node += 4 + alignUp4(word.len); // >CFA
                    writeI32At(bytes, here, @intCast(node));
                    here += 4;
                }
            }
        } else {
            writeI32At(bytes, here, code);
            here += 4;
            code += 1;
        }
    }

    writeI32At(bytes, STATE_ADDR * 4, 0);
    writeI32At(bytes, HERE_ADDR * 4, @intCast(here));
    writeI32At(bytes, LATEST_ADDR * 4, @intCast(latest));
    writeI32At(bytes, S0_ADDR * 4, 0x2000);
    writeI32At(bytes, BASE_ADDR * 4, 10);
}

const NumResult = struct { result: i32, remaining: i32 };

/// The VM state shared with labeled.zig: memory, I/O, and every
/// helper (`key`/`word`/`find`/`number`/`codeFieldAddress`) that `run()`
/// calls into but that has nothing to do with dispatch strategy.
pub const Forth = struct {
    memory: std.array_list.AlignedManaged(u8, .of(u32)),
    reader: *std.Io.Reader,
    writer: *std.Io.Writer,

    pub fn init(
        allocator: std.mem.Allocator,
        reader: *std.Io.Reader,
        writer: *std.Io.Writer,
    ) !Forth {
        const initial_size = 0x10000 * 4;
        var memory: std.array_list.AlignedManaged(u8, .of(u32)) = try .initCapacity(allocator, initial_size);
        try memory.appendNTimes(0, initial_size);
        buildRodata(memory.items);
        return .{ .memory = memory, .reader = reader, .writer = writer };
    }

    pub fn deinit(self: *Forth) void {
        self.memory.deinit();
    }

    /// `addr` is a *cell* (word) index, exactly like jansforth.c/rs's
    /// `memory[addr]`/`read_i32(addr)` -- multiplied by 4 to get the byte
    /// offset into `self.memory`.
    fn readI32(self: *const Forth, addr: usize) i32 {
        return readI32At(self.memory.items, addr * 4);
    }

    fn writeI32(self: *Forth, addr: usize, value: i32) void {
        writeI32At(self.memory.items, addr * 4, value);
    }

    /// `(byte_address >> 2)`, the same cast every `RSP!`/`DSP!`/`EXIT`/etc.
    /// case performs to turn a stored byte address back into a cell index.
    fn addrOf(value: i32) usize {
        return @intCast(value >> 2);
    }

    /// `NEXT`: read the next opcode out of `code[ip]`, advance `ip` past
    /// it, and land on `cfa` -- the labeled-switch equivalent of
    /// jansforth.zig's shared `cfa = addrOf(self.readI32(ip)); ip += 1;`
    /// tail, now run explicitly by every `continue :dispatch` instead of by
    /// falling out to one shared dispatch site. Mirrors regexp/labeled.zig's
    /// `fetch()`.
    fn fetchOp(self: *Forth, cfa: *usize, ip: *usize) Op {
        cfa.* = addrOf(self.readI32(ip.*));
        ip.* += 1;
        return @enumFromInt(self.readI32(cfa.*));
    }

    fn key(self: *Forth) !u8 {
        return self.reader.takeByte();
    }

    fn word(self: *Forth) !i32 {
        var ch = try self.key();
        while (true) {
            if (ch == '\\') { // comment ⇒ skip to end of line
                while (ch != '\n') ch = try self.key();
            }
            if (ch > ' ') break;
            ch = try self.key();
        }

        var pos = WORD_BUFFER;
        while (true) {
            self.memory.items[pos] = ch;
            pos += 1;
            ch = try self.key();
            if (ch <= ' ') break;
        }
        return @intCast(pos - WORD_BUFFER);
    }

    /// `& 0x3F` (not `F_LENMASK`'s `0x1F`) is deliberate: it folds the
    /// `HIDDEN` flag bit into the comparison so a hidden word's masked
    /// length never matches a real search length, exactly like
    /// jansforth.c/rs's `find()`.
    fn find(self: *const Forth, count: i32, name: usize) i32 {
        var word_addr = self.readI32(LATEST_ADDR);
        while (word_addr != 0) {
            const wa: usize = @intCast(word_addr);
            const len = self.memory.items[wa + 4] & 0x3F;
            if (len == @as(u8, @intCast(count))) {
                const n: usize = @intCast(count);
                if (std.mem.eql(u8, self.memory.items[wa + 5 ..][0..n], self.memory.items[name..][0..n]))
                    return word_addr;
            }
            word_addr = self.readI32(addrOf(word_addr));
        }
        return 0;
    }

    fn number(self: *const Forth, n: i32, s: usize) NumResult {
        const base = self.readI32(BASE_ADDR);
        var pos = s;
        var remaining = n;
        var sign: i32 = 1;

        switch (self.memory.items[pos]) {
            '-' => {
                sign = -1;
                remaining -= 1;
                pos += 1;
            },
            '+' => {
                remaining -= 1;
                pos += 1;
            },
            else => {},
        }

        var result: i32 = 0;
        while (remaining > 0) {
            result *%= base;
            const ch = self.memory.items[pos];
            pos += 1;
            var digit: i32 = @as(i32, ch) - @as(i32, '0');
            if (digit < 0) break;
            if (digit > 9) {
                digit -= 7; // 'A' - '0' - 10
                if (digit < 10) break;
            }
            if (digit >= base) break;
            result +%= digit;
            remaining -= 1;
        }

        return .{ .result = result *% sign, .remaining = remaining };
    }

    fn codeFieldAddress(self: *const Forth, w: i32) i32 {
        var word_addr = w + 4;
        word_addr += @as(i32, self.memory.items[@intCast(word_addr)] & 0x1F) + 4;
        word_addr &= ~@as(i32, 3);
        return word_addr;
    }

    fn doSyscall3(self: *Forth, n: i32, a: i32, b: i32, c: i32) i32 {
        return switch (n) {
            SysNum.READ => blk: {
                const buf = self.memory.items[@intCast(b)..][0..@intCast(c)];
                const got = std.posix.read(@intCast(a), buf) catch break :blk -1;
                break :blk @intCast(got);
            },
            SysNum.WRITE => blk: {
                const buf = self.memory.items[@intCast(b)..][0..@intCast(c)];
                const got = std.posix.write(@intCast(a), buf) catch break :blk -1;
                break :blk @intCast(got);
            },
            SysNum.OPEN => blk: { // (path, flags|O_CREAT, mode) -- SYSCALL3
                const path = std.mem.sliceTo(self.memory.items[@intCast(a)..], 0);
                const fd = std.posix.open(path, openFlags(b), @intCast(c)) catch break :blk -1;
                break :blk @intCast(fd);
            },
            SysNum.CREAT => blk: {
                const path = std.mem.sliceTo(self.memory.items[@intCast(a)..], 0);
                const flags: std.c.O = .{ .ACCMODE = .WRONLY, .CREAT = true, .TRUNC = true };
                const fd = std.posix.open(path, flags, @intCast(b)) catch break :blk -1;
                break :blk @intCast(fd);
            },
            else => -1,
        };
    }

    fn doSyscall2(self: *Forth, n: i32, a: i32, b: i32) i32 {
        return switch (n) {
            SysNum.OPEN => blk: { // (path, flags) -- SYSCALL2, no mode
                const path = std.mem.sliceTo(self.memory.items[@intCast(a)..], 0);
                const fd = std.posix.open(path, openFlags(b), 0o644) catch break :blk -1;
                break :blk @intCast(fd);
            },
            else => -1,
        };
    }

    fn doSyscall1(self: *Forth, n: i32, a: i32) i32 {
        switch (n) {
            // Truncate rather than @intCast: exit() wraps an out-of-u8-range
            // status the same way C's exit()/Rust's process::exit(i32) do,
            // instead of panicking on the common `-1 SYS_EXIT SYSCALL1` idiom.
            SysNum.EXIT => std.process.exit(@truncate(@as(u32, @bitCast(a)))),
            SysNum.CLOSE => {
                std.posix.close(@intCast(a));
                return 0;
            },
            SysNum.BRK => {
                // jonesforth's raw brk(2): 0 queries the current break, else
                // grows to it; self.memory's own length IS the break, since
                // every forth-visible address is already an offset from its
                // start. Only ever grows, matching jansforth.rs's guard.
                const current: i32 = @intCast(self.memory.items.len);
                if (a > current) {
                    const old_len = self.memory.items.len;
                    self.memory.resize(@intCast(a)) catch @panic("OOM growing memory");
                    @memset(self.memory.items[old_len..], 0);
                }
                return @intCast(self.memory.items.len);
            },
            else => return -1,
        }
    }

    pub fn run(self: *Forth) !void {
        var sp: usize = 0x0800;
        var rsp: usize = 0x1000;
        var cfa: usize = 5530;
        var ip: usize = 0;

        var op: Op = @enumFromInt(self.readI32(cfa));
        while (true) {
            dispatch: switch (op) {
                .DOCOL => {
                    rsp -= 1;
                    self.writeI32(rsp, @intCast(ip << 2));
                    ip = cfa + 1;
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .DROP => {
                    sp += 1;
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .SWAP => {
                    const a = self.readI32(sp);
                    const b = self.readI32(sp + 1);
                    self.writeI32(sp, b);
                    self.writeI32(sp + 1, a);
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .DUP => {
                    sp -= 1;
                    self.writeI32(sp, self.readI32(sp + 1));
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .OVER => {
                    sp -= 1;
                    self.writeI32(sp, self.readI32(sp + 2));
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .ROT => {
                    const a = self.readI32(sp);
                    const b = self.readI32(sp + 1);
                    const c = self.readI32(sp + 2);
                    self.writeI32(sp + 2, b);
                    self.writeI32(sp + 1, a);
                    self.writeI32(sp, c);
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .NROT => {
                    const a = self.readI32(sp);
                    const b = self.readI32(sp + 1);
                    const c = self.readI32(sp + 2);
                    self.writeI32(sp + 2, a);
                    self.writeI32(sp + 1, c);
                    self.writeI32(sp, b);
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .TWODROP => {
                    sp += 2;
                },
                .TWODUP => {
                    sp -= 2;
                    self.writeI32(sp, self.readI32(sp + 2));
                    self.writeI32(sp + 1, self.readI32(sp + 3));
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .TWOSWAP => {
                    const a = self.readI32(sp);
                    const b = self.readI32(sp + 1);
                    const c = self.readI32(sp + 2);
                    const d = self.readI32(sp + 3);
                    self.writeI32(sp + 3, b);
                    self.writeI32(sp + 2, a);
                    self.writeI32(sp + 1, d);
                    self.writeI32(sp, c);
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .QDUP => {
                    const a = self.readI32(sp);
                    if (a != 0) {
                        sp -= 1;
                        self.writeI32(sp, a);
                    }
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .INCR => {
                    self.writeI32(sp, self.readI32(sp) +% 1);
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .DECR => {
                    self.writeI32(sp, self.readI32(sp) -% 1);
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .INCR4 => {
                    self.writeI32(sp, self.readI32(sp) +% 4);
                },
                .DECR4 => {
                    self.writeI32(sp, self.readI32(sp) -% 4);
                },
                .ADD => {
                    self.writeI32(sp + 1, self.readI32(sp + 1) +% self.readI32(sp));
                    sp += 1;
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .SUB => {
                    self.writeI32(sp + 1, self.readI32(sp + 1) -% self.readI32(sp));
                    sp += 1;
                },
                .MUL => {
                    self.writeI32(sp + 1, self.readI32(sp + 1) *% self.readI32(sp));
                    sp += 1;
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .DIVMOD => {
                    const a = self.readI32(sp + 1);
                    const b = self.readI32(sp);
                    self.writeI32(sp + 1, @rem(a, b));
                    self.writeI32(sp, @divTrunc(a, b));
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .EQU => {
                    self.writeI32(sp + 1, if (self.readI32(sp + 1) == self.readI32(sp)) -1 else 0);
                    sp += 1;
                },
                .NEQU => {
                    self.writeI32(sp + 1, if (self.readI32(sp + 1) != self.readI32(sp)) -1 else 0);
                    sp += 1;
                },
                .LT => {
                    self.writeI32(sp + 1, if (self.readI32(sp + 1) < self.readI32(sp)) -1 else 0);
                    sp += 1;
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .GT => {
                    self.writeI32(sp + 1, if (self.readI32(sp + 1) > self.readI32(sp)) -1 else 0);
                    sp += 1;
                },
                .LE => {
                    self.writeI32(sp + 1, if (self.readI32(sp + 1) <= self.readI32(sp)) -1 else 0);
                    sp += 1;
                },
                .GE => {
                    self.writeI32(sp + 1, if (self.readI32(sp + 1) >= self.readI32(sp)) -1 else 0);
                    sp += 1;
                },
                .ZEQU => {
                    self.writeI32(sp, if (self.readI32(sp) == 0) -1 else 0);
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .ZNEQU => {
                    self.writeI32(sp, if (self.readI32(sp) != 0) -1 else 0);
                },
                .ZLT => {
                    self.writeI32(sp, if (self.readI32(sp) < 0) -1 else 0);
                },
                .ZGT => {
                    self.writeI32(sp, if (self.readI32(sp) > 0) -1 else 0);
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .ZLE => {
                    self.writeI32(sp, if (self.readI32(sp) <= 0) -1 else 0);
                },
                .ZGE => {
                    self.writeI32(sp, if (self.readI32(sp) >= 0) -1 else 0);
                },
                .AND => {
                    self.writeI32(sp + 1, self.readI32(sp + 1) & self.readI32(sp));
                    sp += 1;
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .OR => {
                    self.writeI32(sp + 1, self.readI32(sp + 1) | self.readI32(sp));
                    sp += 1;
                },
                .XOR => {
                    self.writeI32(sp + 1, self.readI32(sp + 1) ^ self.readI32(sp));
                    sp += 1;
                },
                .INVERT => {
                    self.writeI32(sp, ~self.readI32(sp));
                },
                .EXIT => {
                    ip = addrOf(self.readI32(rsp));
                    rsp += 1;
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .LIT => {
                    sp -= 1;
                    self.writeI32(sp, self.readI32(ip));
                    ip += 1;
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .STORE => {
                    self.writeI32(addrOf(self.readI32(sp)), self.readI32(sp + 1));
                    sp += 2;
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .FETCH => {
                    const addr = addrOf(self.readI32(sp));
                    self.writeI32(sp, self.readI32(addr));
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .ADDSTORE => {
                    const addr = addrOf(self.readI32(sp));
                    self.writeI32(addr, self.readI32(addr) +% self.readI32(sp + 1));
                    sp += 2;
                },
                .SUBSTORE => {
                    const addr = addrOf(self.readI32(sp));
                    self.writeI32(addr, self.readI32(addr) -% self.readI32(sp + 1));
                    sp += 2;
                },
                .STOREBYTE => {
                    const addr: usize = @intCast(self.readI32(sp));
                    self.memory.items[addr] = @truncate(@as(u32, @bitCast(self.readI32(sp + 1))));
                    sp += 2;
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .FETCHBYTE => {
                    const addr: usize = @intCast(self.readI32(sp));
                    self.writeI32(sp, self.memory.items[addr]);
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .CCOPY => {
                    // ( source dest -- source+1 dest+1 ), per jonesforth.S:
                    // dest is on top, source is one cell below; both
                    // addresses are left incremented.
                    const dest: usize = @intCast(self.readI32(sp));
                    const source: usize = @intCast(self.readI32(sp + 1));
                    self.memory.items[dest] = self.memory.items[source];
                    self.writeI32(sp, @intCast(dest + 1));
                    self.writeI32(sp + 1, @intCast(source + 1));
                },
                .CMOVE => {
                    const src: usize = @intCast(self.readI32(sp + 2));
                    const dst: usize = @intCast(self.readI32(sp + 1));
                    const len: usize = @intCast(self.readI32(sp));
                    const s = self.memory.items[src..][0..len];
                    const d = self.memory.items[dst..][0..len];
                    if (dst <= src) std.mem.copyForwards(u8, d, s) else std.mem.copyBackwards(u8, d, s);
                    sp += 3;
                },
                .STATE => {
                    sp -= 1;
                    self.writeI32(sp, @intCast(STATE_ADDR << 2));
                },
                .HERE => {
                    sp -= 1;
                    self.writeI32(sp, @intCast(HERE_ADDR << 2));
                },
                .LATEST => {
                    sp -= 1;
                    self.writeI32(sp, @intCast(LATEST_ADDR << 2));
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .SZ => {
                    sp -= 1;
                    self.writeI32(sp, @intCast(S0_ADDR << 2));
                },
                .BASE => {
                    sp -= 1;
                    self.writeI32(sp, @intCast(BASE_ADDR << 2));
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .VERSION => {
                    sp -= 1;
                    self.writeI32(sp, 47);
                },
                .RZ => {
                    sp -= 1;
                    self.writeI32(sp, 0x1000 << 2);
                },
                .__DOCOL => {
                    sp -= 1;
                    self.writeI32(sp, 0);
                },
                .F_IMMED => {
                    sp -= 1;
                    self.writeI32(sp, 0x80);
                },
                .F_HIDDEN => {
                    sp -= 1;
                    self.writeI32(sp, 0x20);
                },
                .F_LENMASK => {
                    sp -= 1;
                    self.writeI32(sp, 0x1F);
                },
                .SYS_EXIT => {
                    sp -= 1;
                    self.writeI32(sp, SysNum.EXIT);
                },
                .SYS_OPEN => {
                    sp -= 1;
                    self.writeI32(sp, SysNum.OPEN);
                },
                .SYS_CLOSE => {
                    sp -= 1;
                    self.writeI32(sp, SysNum.CLOSE);
                },
                .SYS_READ => {
                    sp -= 1;
                    self.writeI32(sp, SysNum.READ);
                },
                .SYS_WRITE => {
                    sp -= 1;
                    self.writeI32(sp, SysNum.WRITE);
                },
                .SYS_CREAT => {
                    sp -= 1;
                    self.writeI32(sp, SysNum.CREAT);
                },
                .SYS_BRK => {
                    sp -= 1;
                    self.writeI32(sp, SysNum.BRK);
                },
                .__O_RDONLY => {
                    sp -= 1;
                    self.writeI32(sp, O_RDONLY);
                },
                .__O_WRONLY => {
                    sp -= 1;
                    self.writeI32(sp, O_WRONLY);
                },
                .__O_RDWR => {
                    sp -= 1;
                    self.writeI32(sp, O_RDWR);
                },
                .__O_CREAT => {
                    sp -= 1;
                    self.writeI32(sp, O_CREAT);
                },
                .__O_EXCL => {
                    sp -= 1;
                    self.writeI32(sp, O_EXCL);
                },
                .__O_TRUNC => {
                    sp -= 1;
                    self.writeI32(sp, O_TRUNC);
                },
                .__O_APPEND => {
                    sp -= 1;
                    self.writeI32(sp, O_APPEND);
                },
                .__O_NONBLOCK => {
                    sp -= 1;
                    self.writeI32(sp, O_NONBLOCK);
                },
                .TOR => {
                    rsp -= 1;
                    self.writeI32(rsp, self.readI32(sp));
                    sp += 1;
                },
                .FROMR => {
                    sp -= 1;
                    self.writeI32(sp, self.readI32(rsp));
                    rsp += 1;
                },
                .RSPFETCH => {
                    sp -= 1;
                    self.writeI32(sp, @intCast(rsp << 2));
                },
                .RSPSTORE => {
                    rsp = addrOf(self.readI32(sp));
                    sp += 1;
                },
                .RDROP => {
                    rsp += 1;
                },
                .DSPFETCH => {
                    const a = sp;
                    sp -= 1;
                    self.writeI32(sp, @intCast(a << 2));
                },
                .DSPSTORE => {
                    sp = addrOf(self.readI32(sp));
                },
                .KEY => {
                    sp -= 1;
                    const ch = try self.key();
                    self.writeI32(sp, ch);
                },
                .EMIT => {
                    const ch: u8 = @truncate(@as(u32, @bitCast(self.readI32(sp))));
                    try self.writer.writeByte(ch);
                    try self.writer.flush();
                    sp += 1;
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .WORD => {
                    sp -= 1;
                    self.writeI32(sp, @intCast(WORD_BUFFER));
                    sp -= 1;
                    self.writeI32(sp, try self.word());
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .NUMBER => {
                    const num = self.number(self.readI32(sp), @intCast(self.readI32(sp + 1)));
                    self.writeI32(sp + 1, num.result);
                    self.writeI32(sp, num.remaining);
                },
                .FIND => {
                    const result = self.find(self.readI32(sp), @intCast(self.readI32(sp + 1)));
                    self.writeI32(sp + 1, result);
                    sp += 1;
                },
                .TCFA => {
                    self.writeI32(sp, self.codeFieldAddress(self.readI32(sp)));
                },
                .CREATE => {
                    const count: usize = @intCast(self.readI32(sp));
                    const name: usize = @intCast(self.readI32(sp + 1));
                    const here: usize = @intCast(self.readI32(HERE_ADDR));
                    self.writeI32(here >> 2, self.readI32(LATEST_ADDR));
                    self.memory.items[here + 4] = @truncate(count);
                    std.mem.copyForwards(u8, self.memory.items[here + 5 ..][0..count], self.memory.items[name..][0..count]);
                    self.writeI32(HERE_ADDR, self.codeFieldAddress(@intCast(here)));
                    self.writeI32(LATEST_ADDR, @intCast(here));
                    sp += 2;
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .COMMA => {
                    const here: usize = @intCast(self.readI32(HERE_ADDR));
                    self.writeI32(here >> 2, self.readI32(sp));
                    self.writeI32(HERE_ADDR, @intCast(here + 4));
                    sp += 1;
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .LBRAC => {
                    self.writeI32(STATE_ADDR, 0);
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .RBRAC => {
                    self.writeI32(STATE_ADDR, 1);
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .IMMEDIATE => {
                    const latest = addrOf(self.readI32(LATEST_ADDR));
                    self.writeI32(latest + 1, self.readI32(latest + 1) ^ 0x80);
                },
                .HIDDEN => {
                    const target = addrOf(self.readI32(sp));
                    self.writeI32(target + 1, self.readI32(target + 1) ^ 0x20);
                    sp += 1;
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .TICK => {
                    sp -= 1;
                    self.writeI32(sp, self.readI32(ip));
                    ip += 1;
                },
                .BRANCH => {
                    ip = @intCast(@as(i32, @intCast(ip)) + (self.readI32(ip) >> 2));
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .ZBRANCH => {
                    if (self.readI32(sp) != 0) {
                        ip += 1;
                    } else {
                        ip = @intCast(@as(i32, @intCast(ip)) + (self.readI32(ip) >> 2));
                    }
                    sp += 1;
                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .LITSTRING => {
                    sp -= 1;
                    self.writeI32(sp, @intCast((ip + 1) << 2));
                    sp -= 1;
                    const len = self.readI32(ip);
                    self.writeI32(sp, len);
                    ip += 1 + @as(usize, @intCast((len +% 3) >> 2));
                },
                .TELL => {
                    const len: usize = @intCast(self.readI32(sp));
                    const addr: usize = @intCast(self.readI32(sp + 1));
                    try self.writer.writeAll(self.memory.items[addr..][0..len]);
                    try self.writer.flush();
                    sp += 2;
                },
                .INTERPRET => {
                    const a = try self.word();
                    const b = self.find(a, WORD_BUFFER);
                    if (b != 0) {
                        cfa = @intCast(self.codeFieldAddress(b));
                        if ((self.memory.items[@intCast(b + 4)] & 0x80) != 0 or self.readI32(STATE_ADDR) == 0) {
                            cfa >>= 2;
                            continue :dispatch @enumFromInt(self.readI32(cfa));
                        }
                        const here = self.readI32(HERE_ADDR);
                        self.writeI32(@intCast(here >> 2), @intCast(cfa));
                        self.writeI32(HERE_ADDR, here + 4);
                    } else {
                        const num = self.number(a, WORD_BUFFER);
                        if (num.remaining != 0) {
                            try std.fs.File.stderr().writeAll("PARSE ERROR: ");
                            try std.fs.File.stderr().writeAll(self.memory.items[WORD_BUFFER..][0..@intCast(a)]);
                            try std.fs.File.stderr().writeAll("\n");
                        } else if (self.readI32(STATE_ADDR) != 0) {
                            var here = self.readI32(HERE_ADDR);
                            self.writeI32(@intCast(here >> 2), LIT_CFA << 2);
                            here += 4;
                            self.writeI32(HERE_ADDR, here);
                            self.writeI32(@intCast(here >> 2), num.result);
                            self.writeI32(HERE_ADDR, here + 4);
                        } else {
                            sp -= 1;
                            self.writeI32(sp, num.result);
                        }
                    }

                    continue :dispatch fetchOp(self, &cfa, &ip);
                },
                .CHAR => {
                    _ = try self.word();
                    sp -= 1;
                    self.writeI32(sp, self.memory.items[WORD_BUFFER]);
                },
                .EXECUTE => {
                    cfa = addrOf(self.readI32(sp));
                    sp += 1;
                    continue :dispatch @enumFromInt(self.readI32(cfa));
                },
                .SYSCALL3 => {
                    const n = self.readI32(sp);
                    const a = self.readI32(sp + 1);
                    const b = self.readI32(sp + 2);
                    const c = self.readI32(sp + 3);
                    self.writeI32(sp + 3, self.doSyscall3(n, a, b, c));
                    sp += 3;
                },
                .SYSCALL2 => {
                    const n = self.readI32(sp);
                    const a = self.readI32(sp + 1);
                    const b = self.readI32(sp + 2);
                    self.writeI32(sp + 2, self.doSyscall2(n, a, b));
                    sp += 2;
                },
                .SYSCALL1 => {
                    const n = self.readI32(sp);
                    const a = self.readI32(sp + 1);
                    self.writeI32(sp + 1, self.doSyscall1(n, a));
                    sp += 1;
                },
                _ => return error.UnknownOpcode,
            }
            op = fetchOp(self, &cfa, &ip);
        }
    }
};

pub fn main() !void {
    const gpa = std.heap.c_allocator;
    var stdin_buffer: [4096]u8 = undefined;
    var stdout_buffer: [4096]u8 = undefined;
    var stdin_reader = std.fs.File.stdin().reader(&stdin_buffer);
    var stdout_writer = std.fs.File.stdout().writer(&stdout_buffer);

    var forth = try Forth.init(gpa, &stdin_reader.interface, &stdout_writer.interface);
    defer forth.deinit();

    // Running out of input is jonesforth.S's _KEY hitting eax <= 0 and
    // exiting cleanly (code 0); only a genuine bug is a real error.
    forth.run() catch |err| {
        if (err != error.EndOfStream) {
            std.debug.print("Runtime error: {}\n", .{err});
            std.process.exit(1);
        }
    };
}

const testing = std.testing;

test "defwords" {
    var discard: std.Io.Writer.Discarding = .init(&.{});
    var reader: std.Io.Reader = .fixed(&.{});
    var forth = try Forth.init(testing.allocator, &reader, &discard.writer);
    defer forth.deinit();

    var node: usize = @intCast(forth.readI32(LATEST_ADDR));
    var names = std.array_list.Managed([]const u8).init(testing.allocator);
    defer names.deinit();
    while (node != 0) {
        const length: usize = @intCast(forth.memory.items[node + 4] & 0x3F);
        try names.append(forth.memory.items[node + 5 ..][0..length]);
        node = @intCast(forth.readI32(node >> 2));
    }
    std.mem.reverse([]const u8, names.items);

    try testing.expectEqual(0, forth.readI32(STATE_ADDR));
    try testing.expectEqual(10, forth.readI32(BASE_ADDR));
    try testing.expectEqualSlices(u8, "DROP", names.items[0]);
    try testing.expectEqualSlices(u8, "SWAP", names.items[1]);
    try testing.expectEqualSlices(u8, "DUP", names.items[2]);
    try testing.expectEqualSlices(u8, "OVER", names.items[3]);
    try testing.expectEqualSlices(u8, "ROT", names.items[4]);
    try testing.expectEqualSlices(u8, "R0", names.items[50]);
    try testing.expectEqualSlices(u8, "DOCOL", names.items[51]);
    try testing.expectEqualSlices(u8, ">DFA", names.items[83]);
    try testing.expectEqualSlices(u8, "SYSCALL1", names.items[names.items.len - 1]);
    try testing.expect(forth.readI32(HERE_ADDR) > forth.readI32(LATEST_ADDR));
}

test "interp" {
    const input =
        \\: / /MOD SWAP DROP ;
        \\: '\n' 10 ;
        \\: BL 32 ;
        \\: CR '\n' EMIT ;
        \\: SPACE BL EMIT ;
        \\: NEGATE 0 SWAP - ;
        \\: TRUE 1 ;
        \\: FALSE 0 ;
        \\: LITERAL IMMEDIATE ' LIT , , ;
        \\: ':' [ CHAR : ] LITERAL ;
        \\: ';' [ CHAR ; ] LITERAL ;
        \\: '"' [ CHAR " ] LITERAL ;
        \\: 'A' [ CHAR A ] LITERAL ;
        \\: '0' [ CHAR 0 ] LITERAL ;
        \\: '-' [ CHAR - ] LITERAL ;
        \\: [COMPILE] IMMEDIATE WORD FIND >CFA , ;
        \\: RECURSE IMMEDIATE LATEST @ >CFA , ;
        \\: IF IMMEDIATE ' 0BRANCH , HERE @ 0 , ;
        \\: THEN IMMEDIATE DUP HERE @ SWAP - SWAP ! ;
        \\: ELSE IMMEDIATE ' BRANCH , HERE @ 0 , SWAP DUP HERE @ SWAP - SWAP ! ;
        \\: BEGIN IMMEDIATE HERE @ ;
        \\: AGAIN IMMEDIATE ' BRANCH , HERE @ - , ;
        \\: WHILE IMMEDIATE ' 0BRANCH , HERE @ 0 , ;
        \\: REPEAT IMMEDIATE ' BRANCH , SWAP HERE @ - , DUP HERE @ SWAP - SWAP ! ;
        \\: NIP SWAP DROP ;
        \\: PICK 1+ 4 * DSP@ + @ ;
        \\: SPACES BEGIN DUP 0> WHILE SPACE 1- REPEAT DROP ;
        \\: U. BASE @ /MOD ?DUP IF RECURSE THEN DUP 10 < IF '0' ELSE 10 - 'A' THEN + EMIT ;
        \\: .S DSP@ BEGIN DUP S0 @ < WHILE DUP @ U. 4+ SPACE REPEAT DROP ;
        \\: UWIDTH BASE @ / ?DUP IF RECURSE 1+ ELSE 1 THEN ;
        \\: U.R SWAP DUP UWIDTH ROT SWAP - SPACES U. ;
        \\: .R SWAP DUP 0< IF NEGATE 1 SWAP ROT 1- ELSE 0 SWAP ROT THEN SWAP DUP UWIDTH ROT SWAP - SPACES SWAP IF '-' EMIT THEN U. ;
        \\: . 0 .R SPACE ;
        \\: U. U. SPACE ;
        \\: WITHIN -ROT OVER <= IF > IF TRUE ELSE FALSE THEN ELSE 2DROP FALSE THEN ;
        \\: ALIGNED 3 + -4 AND ;
        \\: ALIGN HERE @ ALIGNED HERE ! ;
        \\: C, HERE @ C! 1 HERE +! ;
        \\: S" IMMEDIATE STATE @ IF ' LITSTRING , HERE @ 0 , BEGIN KEY DUP '"' <> WHILE C, REPEAT DROP DUP HERE @ SWAP - 4- SWAP ! ALIGN ELSE HERE @ BEGIN KEY DUP '"' <> WHILE OVER C! 1+ REPEAT DROP HERE @ - HERE @ SWAP THEN ;
        \\: ." IMMEDIATE STATE @ IF [COMPILE] S" ' TELL , ELSE BEGIN KEY DUP '"' = IF DROP EXIT THEN EMIT AGAIN THEN ;
        \\: CELLS 4 * ;
        \\: ID. 4+ DUP C@ F_LENMASK AND BEGIN DUP 0> WHILE SWAP 1+ DUP C@ EMIT SWAP 1- REPEAT 2DROP ;
        \\: ?IMMEDIATE 4+ C@ F_IMMED AND ;
        \\: CASE IMMEDIATE 0 ;
        \\: OF IMMEDIATE ' OVER , ' = , [COMPILE] IF ' DROP , ;
        \\: ENDOF IMMEDIATE [COMPILE] ELSE ;
        \\: ENDCASE IMMEDIATE ' DROP , BEGIN ?DUP WHILE [COMPILE] THEN REPEAT ;
        \\: CFA> LATEST @ BEGIN ?DUP WHILE 2DUP SWAP < IF NIP EXIT THEN @ REPEAT DROP 0 ;
        \\: SEE WORD FIND HERE @ LATEST @ BEGIN 2 PICK OVER <> WHILE NIP DUP @ REPEAT DROP SWAP
        \\ ':' EMIT SPACE DUP ID. SPACE DUP ?IMMEDIATE IF ." IMMEDIATE " THEN >DFA
        \\ BEGIN 2DUP > WHILE DUP @
        \\     CASE
        \\         ' LIT OF 4+ DUP @ . ENDOF
        \\         ' LITSTRING OF [ CHAR S ] LITERAL EMIT '"' EMIT SPACE 4+ DUP @ SWAP 4+ SWAP 2DUP TELL '"' EMIT SPACE + ALIGNED 4- ENDOF
        \\         ' 0BRANCH OF ." 0BRANCH ( " 4+ DUP @ . ." ) " ENDOF
        \\         ' BRANCH OF ." BRANCH ( " 4+ DUP @ . ." ) " ENDOF
        \\         ' ' OF [ CHAR ' ] LITERAL EMIT SPACE 4+ DUP CFA> ID. SPACE ENDOF
        \\         ' EXIT OF 2DUP 4+ <> IF ." EXIT " THEN ENDOF
        \\         DUP CFA> ID. SPACE
        \\     ENDCASE
        \\     4+
        \\ REPEAT
        \\ ';' EMIT CR 2DROP ;
        \\: ['] IMMEDIATE ' LIT , ;
        \\: EXCEPTION-MARKER RDROP 0 ;
        \\: CATCH DSP@ 4+ >R ' EXCEPTION-MARKER 4+ >R EXECUTE ;
        \\: THROW ?DUP IF RSP@ BEGIN DUP R0 4- < WHILE DUP @ ' EXCEPTION-MARKER 4+ = IF 4+ RSP! DUP DUP DUP R> 4- SWAP OVER ! DSP! EXIT THEN 4+ REPEAT
        \\ DROP CASE 0 1- OF ." ABORTED" CR ENDOF ." UNCAUGHT THROW " DUP . CR ENDCASE QUIT THEN ;
        \\: STRLEN DUP BEGIN DUP C@ 0<> WHILE 1+ REPEAT SWAP - ;
        \\65 EMIT CR \ A
        \\777 65 EMIT DROP CR \ A
        \\32 DUP + 1+ EMIT CR \ A
        \\16 DUP 2DUP + + + 1+ EMIT CR \ A
        \\8 DUP * 1+ EMIT CR \ A
        \\CHAR A EMIT CR \ A
        \\: SLOW WORD FIND >CFA EXECUTE ; 65 SLOW EMIT CR \ A
        \\1179010630 DSP@ 4 TELL 2DROP CR \ FFFF
        \\1179010630 DSP@ HERE @ 4 CMOVE HERE @ 4 TELL DROP CR \ FFFF
        \\S0 @ DSP@ - HERE @ HERE @ 4 + 4 CMOVE S0 @ DSP@ - SWAP - . CR \ 4
        \\13622 DSP@ 2 NUMBER DROP EMIT CR \ A
        \\64 >R RSP@ 1 TELL RDROP CR \ @
        \\64 DSP@ RSP@ C@C! RSP@ 1 TELL 2DROP DROP CR \ @
        \\64 >R 1 RSP@ +! RSP@ 1 TELL RDROP CR \ A
        \\VERSION . CR \ 47
        \\LATEST @ ID. CR \ SLOW
        \\0 1 > . CR \ 0
        \\1 0 > . CR \ -1
        \\0 1 >= . CR \ 0
        \\0 0 >= . CR \ -1
        \\0 0<> . CR \ 0
        \\1 0<> . CR \ -1
        \\1 0<= . CR \ 0
        \\0 0 <= . CR \ -1
        \\-1 0>= . CR \ 0
        \\0 0>= . CR \ -1
        \\0 0 OR . CR \ 0
        \\0 -1 OR . CR \ -1
        \\-1 -1 XOR . CR \ 0
        \\0 -1 XOR . CR \ -1
        \\-1 INVERT . CR \ 0
        \\0 INVERT . CR \ -1
        \\F_IMMED F_HIDDEN .S 2DROP CR \ 32 128
        \\: CFA@ WORD FIND >CFA @ ; CFA@ >DFA DOCOL = . CR \ -1
        \\3 4 5 .S 2DROP DROP CR \ 5 4 3
        \\3 4 5 WITHIN . CR \ 0
        \\SEE >DFA \ : >DFA >CFA 4+ ;
        \\SEE HIDE \ : HIDE WORD FIND HIDDEN ;
        \\SEE QUIT \ : QUIT R0 RSP! INTERPRET BRANCH ( -8 ) ;
        \\: FOO THROW ;
        \\: TEST-EXCEPTIONS 25 ['] FOO CATCH ?DUP IF ." FOO threw exception: " . CR DROP THEN ;
        \\TEST-EXCEPTIONS \ FOO threw exception: 25
        \\: PAD4 ." ABCD" ; PAD4 CR \ ABCD
        \\HIDE (ARGC) WORD (ARGC) FIND 0= . CR \ -1
        \\
    ;

    var reader: std.Io.Reader = .fixed(input);
    var aw = std.Io.Writer.Allocating.init(testing.allocator);
    defer aw.deinit();

    var forth = try Forth.init(testing.allocator, &reader, &aw.writer);
    defer forth.deinit();

    try testing.expectError(error.EndOfStream, forth.run());

    const actual = aw.writer.buffer[0..aw.writer.end];
    var actual_lines = std.mem.splitScalar(u8, actual, '\n');
    var input_lines = std.mem.splitScalar(u8, input, '\n');
    while (input_lines.next()) |line| {
        const marker = std.mem.indexOf(u8, line, " \\ ") orelse continue;
        const expected = std.mem.trimRight(u8, line[marker + 3 ..], " ");
        const got = std.mem.trimRight(u8, actual_lines.next() orelse "", " \r");
        try testing.expectEqualStrings(expected, got);
    }
}
