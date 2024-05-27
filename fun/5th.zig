const std = @import("std");
const io = std.io;
const fmt = std.fmt;
const mem = std.mem;
const os = std.os;
const linux = os.linux;
const syscalls = linux.syscalls;

const libc = @cImport({
    @cInclude("fcntl.h");
});

const stdin = io.getStdIn().reader();
const stdout = io.getStdOut().writer();

const Flag = enum(u8) { IMMED = 0x80, HIDDEN = 0x20, LENMASK = 0x1F, ZERO = 0x0 };

const Word = struct {
    link: ?*const Word,
    flag: u8,
    name: []const u8,
    code: []const Instr,
};

const Interp = struct {
    state: isize,
    latest: *Word,
    s0: [*]isize,
    base: i32,
    r0: [*][]Instr,
    buffer: [32]u8,
    here: [*]u8,

    pub inline fn next(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
        _ = target;
        try @call(.always_tail, ip[0].word[0].code, .{ self, sp, rsp, ip[1..], ip[0].word });
    }

    pub fn word(self: *Interp) usize {
        var ch: u8 = 0;
        var i: usize = 0;

        while (ch <= ' ') {
            ch = key();
            if (ch == '\\') { // comment ⇒ skip line
                while (ch != '\n') ch = key();
            }
        }
        while (ch > ' ') {
            self.buffer[i] = ch;
            i += 1;
            ch = key();
        }
        return i;
    }

    pub fn find(self: *Interp, name: []u8) ?*Word {
        const mask = @intFromEnum(Flag.HIDDEN) | @intFromEnum(Flag.LENMASK);
        var node: ?*Word = self.latest;
        while (node != null and ((node.?.flag & mask) != name.len or !mem.eql(u8, node.?.name, name)))
            node = @constCast(node.?.link);

        return node;
    }
};

const Instr = union {
    code: *const fn (*Interp, [*]isize, [*][]Instr, []Instr, []const Instr) anyerror!void,
    literal: isize,
    word: []const Instr,
};

const Type = enum {
    self,
    rsp,
    ip,
    literal,
};

const Source = union(Type) {
    self: []const u8,
    rsp: fn ([*][]Instr) callconv(.Inline) isize,
    ip: fn ([*]Instr) callconv(.Inline) isize,
    literal: isize,
};

fn key() u8 {
    const b = stdin.readByte() catch std.process.exit(0);
    return b;
}

fn defcode(
    comptime last: ?*const Word,
    comptime name: []const u8,
    comptime stack: fn ([*]isize) callconv(.Inline) anyerror![*]isize,
) Word {
    const wrap = struct {
        pub fn code(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
            self.next(try stack(sp), rsp, ip, target);
        }
    };
    return Word{
        .link = last,
        .flag = name.len,
        .name = name,
        .code = &[_]Instr{.{ .code = wrap.code }},
    };
}

fn defconst(
    comptime last: ?*const Word,
    comptime name: []const u8,
    comptime value: Source,
) Word {
    const wrap = struct {
        pub fn code(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
            const s = sp - 1;
            sp[0] = switch (value) {
                Type.self => |f| @intCast(@intFromPtr(&@field(self, f))),
                Type.rsp => |g| g(rsp),
                Type.ip => |h| h(ip),
                Type.literal => |i| i,
            };
            self.next(s, rsp, ip, target);
        }
    };
    return Word{
        .link = last,
        .flag = name.len,
        .name = name,
        .code = &[_]Instr{.{ .code = wrap.code }},
    };
}

fn defword(
    comptime last: ?*const Word,
    comptime flag: Flag,
    comptime name: []const u8,
    comptime data: []const Word,
) Word {
    return Word{
        .link = last,
        .flag = name.len | @intFromEnum(flag),
        .name = name,
        .code = [_]Instr{.{ .code = docol_ }} ++ comptime init: {
            var code: [data.len]Instr = undefined;
            for (&code, data) |*d, s| {
                d.* = .{ .word = s.code };
            }
            break :init &code;
        },
    };
}

inline fn _drop(sp: [*]isize) anyerror![*]isize {
    return sp + 1;
}
const drop = defcode(null, "DROP", _drop);

inline fn _swap(sp: [*]isize) anyerror![*]isize {
    const temp = sp[1];
    sp[1] = sp[0];
    sp[0] = temp;
    return sp;
}
const swap = defcode(&drop, "SWAP", _swap);

inline fn _dup(sp: [*]isize) anyerror![*]isize {
    const s = sp - 1;
    s[0] = sp[0];
    return s;
}
const dup = defcode(&swap, "DUP", _dup);

inline fn _over(sp: [*]isize) anyerror![*]isize {
    const s = sp - 1;
    s[0] = sp[1];
    return s;
}
const over = defcode(&dup, "OVER", _over);

inline fn _rot(sp: [*]isize) anyerror![*]isize {
    const a = sp[0];
    const b = sp[1];
    const c = sp[2];
    sp[2] = b;
    sp[1] = a;
    sp[0] = c;
    return sp;
}
const rot = defcode(&over, "ROT", _rot);

inline fn _nrot(sp: [*]isize) anyerror![*]isize {
    const a = sp[0];
    const b = sp[1];
    const c = sp[2];
    sp[2] = a;
    sp[1] = c;
    sp[0] = b;
    return sp;
}
const nrot = defcode(&rot, "-ROT", _nrot);

inline fn _twodrop(sp: [*]isize) anyerror![*]isize {
    return sp + 2;
}
const twodrop = defcode(&nrot, "2DROP", _twodrop);

inline fn _twodup(sp: [*]isize) anyerror![*]isize {
    const s = sp - 2;
    s[1] = sp[1];
    s[0] = sp[0];
    return s;
}
const twodup = defcode(&twodrop, "2DUP", _twodup);

inline fn _twoswap(sp: [*]isize) anyerror![*]isize {
    const a = sp[0];
    const b = sp[1];
    const c = sp[2];
    const d = sp[3];
    sp[3] = b;
    sp[2] = a;
    sp[1] = d;
    sp[0] = c;
    return sp;
}
const twoswap = defcode(&twodup, "2SWAP", _twoswap);

inline fn _qdup(sp: [*]isize) anyerror![*]isize {
    if (sp[0] != 0) {
        const s = sp - 1;
        s[0] = sp[0];
        return s;
    }
    return sp;
}
const qdup = defcode(&twoswap, "?DUP", _qdup);

inline fn _incr(sp: [*]isize) anyerror![*]isize {
    sp[0] += 1;
    return sp;
}
const incr = defcode(&qdup, "1+", _incr);

inline fn _decr(sp: [*]isize) anyerror![*]isize {
    sp[0] -= 1;
    return sp;
}
const decr = defcode(&incr, "1-", _decr);

inline fn _incrp(sp: [*]isize) anyerror![*]isize {
    sp[0] += @sizeOf(usize);
    return sp;
}
const incrp = defcode(&decr, &[_]u8{ '0' + @sizeOf(usize), '+' }, _incrp);

inline fn _decrp(sp: [*]isize) anyerror![*]isize {
    sp[0] -= @sizeOf(usize);
    return sp;
}
const decrp = defcode(&incrp, &[_]u8{ '0' + @sizeOf(usize), '-' }, _incrp);

inline fn _add(sp: [*]isize) anyerror![*]isize {
    sp[1] += sp[0];
    return sp + 1;
}
const add = defcode(&decrp, "+", _add);

inline fn _sub(sp: [*]isize) anyerror![*]isize {
    sp[1] -= sp[0];
    return sp + 1;
}
const sub = defcode(&add, "-", _sub);

inline fn _mul(sp: [*]isize) anyerror![*]isize {
    sp[1] *= sp[0];
    return sp + 1;
}
const mul = defcode(&sub, "*", _mul);

inline fn _divmod(sp: [*]isize) anyerror![*]isize {
    const a = sp[1];
    const b = sp[0];
    sp[1] = @rem(a, b);
    sp[0] = @divTrunc(a, b);
    return sp;
}
const divmod = defcode(&mul, "/MOD", _divmod);

inline fn _equ(sp: [*]isize) anyerror![*]isize {
    sp[1] = if (sp[0] == sp[1]) -1 else 0;
    return sp + 1;
}
const equ = defcode(&divmod, "=", _equ);

inline fn _nequ(sp: [*]isize) anyerror![*]isize {
    sp[1] = if (sp[0] == sp[1]) 0 else -1;
    return sp + 1;
}
const nequ = defcode(&equ, "<>", _nequ);

inline fn _lt(sp: [*]isize) anyerror![*]isize {
    sp[1] = if (sp[0] < sp[1]) -1 else 0;
    return sp + 1;
}
const lt = defcode(&nequ, "<", _lt);

inline fn _gt(sp: [*]isize) anyerror![*]isize {
    sp[1] = if (sp[0] > sp[1]) -1 else 0;
    return sp + 1;
}
const gt = defcode(&lt, ">", _gt);

inline fn _le(sp: [*]isize) anyerror![*]isize {
    sp[1] = if (sp[0] <= sp[1]) -1 else 0;
    return sp + 1;
}
const le = defcode(&nequ, "<=", _le);

inline fn _ge(sp: [*]isize) anyerror![*]isize {
    sp[1] = if (sp[0] >= sp[1]) -1 else 0;
    return sp + 1;
}
const ge = defcode(&le, "=>", _ge);

inline fn _zequ(sp: [*]isize) anyerror![*]isize {
    sp[0] = if (sp[0] != 0) 0 else -1;
    return sp;
}
const zequ = defcode(&ge, "0=", _zequ);

inline fn _znequ(sp: [*]isize) anyerror![*]isize {
    sp[0] = if (sp[0] != 0) -1 else 0;
    return sp;
}
const znequ = defcode(&zequ, "0<>", _znequ);

inline fn _zlt(sp: [*]isize) anyerror![*]isize {
    sp[0] = if (sp[0] < 0) -1 else 0;
    return sp;
}
const zlt = defcode(&znequ, "0<", _zlt);

inline fn _zgt(sp: [*]isize) anyerror![*]isize {
    sp[0] = if (sp[0] > 0) -1 else 0;
    return sp;
}
const zgt = defcode(&zlt, "0>", _zgt);

inline fn _zle(sp: [*]isize) anyerror![*]isize {
    sp[0] = if (sp[0] <= 0) -1 else 0;
    return sp;
}
const zle = defcode(&znequ, "0<", _zle);

inline fn _zge(sp: [*]isize) anyerror![*]isize {
    sp[0] = if (sp[0] >= 0) -1 else 0;
    return sp;
}
const zge = defcode(&zle, "0>", _zge);

inline fn _and(sp: [*]isize) anyerror![*]isize {
    sp[1] &= sp[0];
    return sp + 1;
}
const and_ = defcode(&zge, "AND", _and);

inline fn _or(sp: [*]isize) anyerror![*]isize {
    sp[1] |= sp[0];
    return sp + 1;
}
const or_ = defcode(&and_, "OR", _or);

inline fn _xor(sp: [*]isize) anyerror![*]isize {
    sp[1] ^= sp[0];
    return sp + 1;
}
const xor = defcode(&or_, "XOR", _xor);

inline fn _invert(sp: [*]isize) anyerror![*]isize {
    sp[0] = ~sp[0];
    return sp;
}
const invert = defcode(&xor, "INVERT", _invert);

inline fn _exit(sp: [*]isize) anyerror![*]isize {
    // FIXME: exit
    return sp;
}
const exit = defcode(&invert, "EXIT", _exit);

inline fn _lit(sp: [*]isize) anyerror![*]isize {
    // FIXME: lit
    return sp;
}
const lit = defcode(&exit, "LIT", _lit);

inline fn _store(sp: [*]isize) anyerror![*]isize {
    const u: usize = @intCast(sp[0]);
    const p: *isize = @ptrFromInt(u);
    p.* = sp[1];
    return sp + 2;
}
const store = defcode(&lit, "!", _store);

inline fn _fetch(sp: [*]isize) anyerror![*]isize {
    const u: usize = @intCast(sp[0]);
    const p: *isize = @ptrFromInt(u);
    sp[0] = p.*;
    return sp;
}
const fetch = defcode(&store, "@", _fetch);

inline fn _addstore(sp: [*]isize) anyerror![*]isize {
    const u: usize = @intCast(sp[0]);
    const p: *isize = @ptrFromInt(u);
    p.* += sp[1];
    return sp + 2;
}
const addstore = defcode(&fetch, "+!", _addstore);

inline fn _substore(sp: [*]isize) anyerror![*]isize {
    const u: usize = @intCast(sp[0]);
    const p: *[*]u8 = @ptrFromInt(u);
    const v: usize = @intCast(sp[1]);
    p.* -= v;
    return sp + 2;
}
const substore = defcode(&addstore, "-!", _substore);

inline fn _storebyte(sp: [*]isize) anyerror![*]isize {
    const u: usize = @intCast(sp[0]);
    const v: u8 = @intCast(sp[1]);
    const p: [*]u8 = @ptrFromInt(u);
    p[0] = v;
    return sp + 2;
}
const storebyte = defcode(&substore, "C!", _storebyte);

inline fn _fetchbyte(sp: [*]isize) anyerror![*]isize {
    const u: usize = @intCast(sp[0]);
    const p: [*]u8 = @ptrFromInt(u);
    sp[0] = p[0];
    return sp;
}
const fetchbyte = defcode(&storebyte, "C@", _fetchbyte);

inline fn _ccopy(sp: [*]isize) anyerror![*]isize {
    const u: usize = @intCast(sp[0]);
    const v: usize = @intCast(sp[1]);
    const p: [*]u8 = @ptrFromInt(u);
    const q: [*]u8 = @ptrFromInt(v);
    q[0] = p[0];
    return sp + 2;
}
const ccopy = defcode(&fetchbyte, "C@C!", _ccopy);

inline fn _cmove(sp: [*]isize) anyerror![*]isize {
    const n: usize = @intCast(sp[0]);
    const u: usize = @intCast(sp[1]);
    const v: usize = @intCast(sp[2]);
    const p: [*]u8 = @ptrFromInt(u);
    const q: [*]u8 = @ptrFromInt(v);
    mem.copyForwards(u8, p[0..n], q[0..n]);
    return sp + 2;
}
const cmove = defcode(&ccopy, "CMOVE", _cmove);

const state = defconst(&cmove, "STATE", .{ .self = "state" });
const here = defconst(&state, "HERE", .{ .self = "here" });
const latest = defconst(&here, "LATEST", .{ .self = "latest" });
const sz = defconst(&latest, "S0", .{ .self = "s0" });
const base = defconst(&sz, "BASE", .{ .self = "base" });
const version = defconst(&base, "VERSION", .{ .literal = 47 });
const rz = defconst(&version, "R0", .{ .self = "r0" });

fn docol_(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    const r = rsp - 1;
    r[0] = @constCast(ip);
    self.next(sp, r, @constCast(target[1..]), target[0].word);
}

inline fn _docol(sp: [*]isize) anyerror![*]isize {
    const s = sp - 1;
    s[0] = @intCast(@intFromPtr(&docol_));
    return s;
}
const docol = defcode(&rz, "DOCOL", _docol);
const f_immed = defconst(&docol, "F_IMMED", .{ .literal = @intFromEnum(Flag.IMMED) });
const f_hidden = defconst(&f_immed, "F_HIDDEN", .{ .literal = @intFromEnum(Flag.HIDDEN) });
const f_lenmask = defconst(&f_hidden, "F_LENMASK", .{ .literal = @intFromEnum(Flag.LENMASK) });
const sys_exit = defconst(&f_lenmask, "SYS_EXIT", .{ .literal = @intFromEnum(syscalls.X64.exit) });
const sys_open = defconst(&sys_exit, "SYS_OPEN", .{ .literal = @intFromEnum(syscalls.X64.open) });
const sys_close = defconst(&sys_open, "SYS_CLOSE", .{ .literal = @intFromEnum(syscalls.X64.close) });
const sys_read = defconst(&sys_close, "SYS_READ", .{ .literal = @intFromEnum(syscalls.X64.read) });
const sys_write = defconst(&sys_read, "SYS_WRITE", .{ .literal = @intFromEnum(syscalls.X64.write) });
const sys_brk = defconst(&sys_write, "SYS_BRK", .{ .literal = @intFromEnum(syscalls.X64.brk) });
const o_rdonly = defconst(&sys_brk, "O_RDONLY", .{ .literal = libc.O_RDONLY });
const o_wronly = defconst(&o_rdonly, "O_WRONLY", .{ .literal = libc.O_WRONLY });
const o_rdwr = defconst(&o_wronly, "O_RDWR", .{ .literal = libc.O_RDWR });
const o_creat = defconst(&o_rdwr, "O_CREAT", .{ .literal = libc.O_CREAT });
const o_excl = defconst(&o_creat, "O_EXCL", .{ .literal = libc.O_EXCL });
const o_trunc = defconst(&o_excl, "O_TRUNC", .{ .literal = libc.O_TRUNC });
const o_append = defconst(&o_trunc, "O_APPEND", .{ .literal = libc.O_APPEND });
const o_nonblock = defconst(&o_append, "O_NONBLOCK", .{ .literal = libc.O_NONBLOCK });

fn _tor(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    const r = rsp - 1;
    const s: usize = @intCast(sp[0]);
    const t: *Instr = @ptrFromInt(s);
    r[0] = t[0..0];
    self.next(sp + 1, r, ip, target);
}
const tor = Word{
    .link = &o_nonblock,
    .flag = ">R".len,
    .name = ">R",
    .code = &[_]Instr{.{ .code = _tor }},
};

fn _fromr(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    const s = sp - 1;
    sp[0] = @intCast(@intFromPtr(&rsp[0]));
    self.next(s, rsp + 1, ip, target);
}
const fromr = Word{
    .link = &tor,
    .flag = "R>".len,
    .name = "R>",
    .code = &[_]Instr{.{ .code = _fromr }},
};

fn _rspfetch(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    const s = sp - 1;
    sp[0] = @intCast(@intFromPtr(rsp));
    self.next(s, rsp, ip, target);
}
const rspfetch = Word{
    .link = &fromr,
    .flag = "RSP@".len,
    .name = "RSP@",
    .code = &[_]Instr{.{ .code = _rspfetch }},
};

fn _rspstore(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    _ = rsp;
    const s: usize = @intCast(sp[0]);
    const t: [*][]Instr = @ptrFromInt(s);
    self.next(sp + 1, t, ip, target);
}
const rspstore = Word{
    .link = &rspfetch,
    .flag = "RSP!".len,
    .name = "RSP!",
    .code = &[_]Instr{.{ .code = _rspstore }},
};

fn _rdrop(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    self.next(sp, rsp + 1, ip, target);
}
const rdrop = Word{
    .link = &rspstore,
    .flag = "RDROP!".len,
    .name = "RDROP!",
    .code = &[_]Instr{.{ .code = _rdrop }},
};

inline fn _dspfetch(sp: [*]isize) anyerror![*]isize {
    const s = sp - 1;
    s[0] = @intCast(@intFromPtr(sp));
    return s;
}
const dspfetch = defcode(&rdrop, "DSP@", _dspfetch);

inline fn _dspstore(sp: [*]isize) anyerror![*]isize {
    const u: usize = @intCast(sp[0]);
    return @ptrFromInt(u);
}
const dspstore = defcode(&dspfetch, "DSP!", _dspstore);

inline fn _key(sp: [*]isize) anyerror![*]isize {
    const s = sp - 1;
    s[0] = @as(isize, key());
    return s;
}
const key_ = defcode(&dspstore, "KEY", _key);

inline fn _emit(sp: [*]isize) anyerror![*]isize {
    return sp + 1;
}
const emit = defcode(&key_, "EMIT", _emit);

fn _word(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    const s = sp - 2;
    const u = @intFromPtr(&self.buffer);
    s[1] = @intCast(u);
    s[0] = @intCast(self.word());
    self.next(s, rsp, ip, target);
}
const word_ = Word{
    .link = &key_,
    .flag = "WORD".len,
    .name = "WORD",
    .code = &[_]Instr{.{ .code = _word }},
};

fn _number(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    if (fmt.parseInt(isize, buf: {
        const c: usize = @intCast(sp[0]);
        const u: usize = @intCast(sp[1]);
        const s: [*]u8 = @ptrFromInt(u);
        break :buf s[0..c];
    }, blk: {
        const ubase: usize = @intCast(self.base);
        const bbase: u8 = @intCast(ubase);

        break :blk bbase;
    })) |num| {
        sp[0] = num;
        sp[1] = 0;
    } else |_| {}
    self.next(sp, rsp, ip, target);
}
const number = Word{
    .link = &word_,
    .flag = "NUMBER".len,
    .name = "NUMBER",
    .code = &[_]Instr{.{ .code = _number }},
};

fn _find(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    const c: usize = @intCast(sp[0]);
    const u: usize = @intCast(sp[1]);
    const s: [*]u8 = @ptrFromInt(u);
    const v = self.find(s[0..c]);

    sp[1] = @intCast(@intFromPtr(v));
    self.next(sp + 1, rsp, ip, target);
}
const find_ = Word{
    .link = &number,
    .flag = "FIND".len,
    .name = "FIND",
    .code = &[_]Instr{.{ .code = _find }},
};

inline fn _tcfa(sp: [*]isize) anyerror![*]isize {
    const u: usize = @intCast(sp[0]);
    const w: *Word = @ptrFromInt(u);
    sp[0] = @intCast(@intFromPtr(&w.code));
    return sp;
}
const tcfa = defcode(&find_, ">CFA", _tcfa);

const tdfa = Word{
    .link = &tcfa,
    .flag = ">DFA".len,
    .name = ">DFA",
    .code = &[_]Instr{
        .{ .code = docol_ },
        .{ .word = tcfa.code },
        .{ .word = incrp.code },
        .{ .word = exit.code },
    },
};

fn _create(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    const c: usize = @intCast(sp[0]);
    const u: usize = @intCast(sp[1]);
    const s: [*]u8 = @ptrFromInt(u);
    const new: *Word = @alignCast(@ptrCast(self.here));
    new.link = self.latest;
    new.flag = @truncate(c);
    mem.copyForwards(u8, @constCast(new.name), s[0..c]);
    self.here = @constCast(@ptrCast(new.code));
    self.latest = new;
    self.next(sp + 2, rsp, ip, target);
}
const create = Word{
    .link = &tdfa,
    .flag = "CREATE".len,
    .name = "CREATE",
    .code = &[_]Instr{.{ .code = _create }},
};

fn _comma(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    const p: [*]Instr = @alignCast(@ptrCast(self.here));
    const u: usize = @intCast(sp[0]);
    const q: *Instr = @ptrFromInt(u);
    p[0].word = q[0..0];
    self.here = @ptrCast(p + 1);
    self.next(sp + 1, rsp, ip, target);
}
const comma = Word{
    .link = &create,
    .flag = ",".len,
    .name = ",",
    .code = &[_]Instr{.{
        .code = _comma,
    }},
};

fn _lbrac(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    self.state = 0;
    self.next(sp + 1, rsp, ip, target);
}
const lbrac = Word{
    .link = &comma,
    .flag = "[".len,
    .name = "[",
    .code = &[_]Instr{.{
        .code = _lbrac,
    }},
};

fn _rbrac(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    self.state = 1;
    self.next(sp + 1, rsp, ip, target);
}
const rbrac = Word{
    .link = &comma,
    .flag = "]".len,
    .name = "]",
    .code = &[_]Instr{.{
        .code = _rbrac,
    }},
};

fn _immediate(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    self.latest.flag ^= @intFromEnum(Flag.IMMED);
    self.next(sp + 1, rsp, ip, target);
}
const immediate = Word{
    .link = &rbrac,
    .flag = "IMMEDIATE".len,
    .name = "IMMEDIATE",
    .code = &[_]Instr{.{
        .code = _immediate,
    }},
};

inline fn _hidden(sp: [*]isize) anyerror![*]isize {
    const u: usize = @intCast(sp[0]);
    const w: *Word = @ptrFromInt(u);
    w.flag ^= @intFromEnum(Flag.HIDDEN);
    return sp + 1;
}
const hidden = defcode(&immediate, "HIDDEN", _hidden);

const hide = defword(&hidden, Flag.ZERO, "HIDE", &[_]Word{ word_, find_, hidden, exit });
const colon = defword(&hide, Flag.ZERO, ":", &[_]Word{ word_, create, docol, comma, latest, fetch, hidden, rbrac, exit });
const semicolon = defword(&colon, Flag.IMMED, ";", &[_]Word{ lit, exit, comma, latest, fetch, hidden, lbrac, exit });
const tick = defcode(&semicolon, "'", _lit);

fn _branch(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    const offset: usize = @intCast(ip[0].literal);
    self.next(sp, rsp, ip[offset..], target);
}
const branch = Word{
    .link = &tick,
    .flag = "BRANCH".len,
    .name = "BRANCH",
    .code = &[_]Instr{.{
        .code = _branch,
    }},
};

fn _zbranch(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    if (sp[0] == 0)
        @call(.always_tail, _branch, .{ self, sp + 1, rsp, ip, ip[0].word });
    self.next(sp + 1, rsp, ip[1..], target);
}
const zbranch = Word{
    .link = &branch,
    .flag = "0BRANCH".len,
    .name = "0BRANCH",
    .code = &[_]Instr{.{
        .code = _zbranch,
    }},
};

fn _litstring(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    const c: usize = @intCast(ip[0].literal);
    const s = sp - 2;
    s[1] = @intCast(@intFromPtr(&ip[1]));
    s[0] = @intCast(c);
    const offset: usize = (c + @sizeOf(usize)) / @sizeOf(usize);
    self.next(s, rsp, ip[offset..], target);
}
const litstring = Word{
    .link = &branch,
    .flag = "LITSTRING".len,
    .name = "LITSTRING",
    .code = &[_]Instr{.{
        .code = _litstring,
    }},
};

inline fn _tell(sp: [*]isize) anyerror![*]isize {
    const u: usize = @intCast(sp[0]);
    const v: u8 = @intCast(sp[1]);
    const p: [*]u8 = @ptrFromInt(v);
    _ = try stdout.write(p[0..u]);
    return sp + 2;
}
const tell = defcode(&litstring, "TELL", _tell);

fn _interpret(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    const c = self.word();
    const p: [*]Instr = @alignCast(@ptrCast(self.here));
    var n: usize = 0;

    if (self.find(self.buffer[0..c])) |new| {
        const tgt = new.code;
        if ((new.flag & @intFromEnum(Flag.IMMED)) != 0) {
            try @call(.always_tail, tgt[0].code, .{ self, sp, rsp, ip, tgt });
        } else {
            p[0] = .{ .word = target };
            n = 1;
        }
    } else if (fmt.parseInt(isize, self.buffer[0..c], blk: {
        const ubase: usize = @intCast(self.base);
        const bbase: u8 = @intCast(ubase);

        break :blk bbase;
    })) |a| {
        if (self.state == 1) {
            p[0] = .{ .word = @constCast(lit.code) };
            p[1] = .{ .literal = a };
            n = 2;
        } else {}
    } else |_| {
        std.debug.print("PARSE ERROR: {s}\n", .{self.buffer[0..c]});
    }
    self.here = @ptrCast(p + n);
    self.next(sp, rsp, ip, target);
}
const interpret = Word{ .link = &tell, .flag = "INTERPRET".len, .name = "INTERPRET", .code = &[_]Instr{.{ .code = _interpret }} };

const quit = Word{
    .link = &interpret,
    .flag = "QUIT".len,
    .name = "QUIT",
    .code = &[_]Instr{
        .{ .code = docol_ },
        .{ .word = rz.code },
        .{ .word = rspstore.code },
        .{ .word = interpret.code },
        .{ .word = branch.code },
        .{ .literal = -2 * @sizeOf(usize) },
        .{ .word = exit.code },
    },
};

fn _char(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    const s = sp - 1;
    _ = self.word();
    s[0] = self.buffer[0];
    self.next(s, rsp, ip, target);
}
const char = Word{ .link = &quit, .flag = "CHAR".len, .name = "CHAR", .code = &[_]Instr{.{ .code = _char }} };

fn _execute(self: *Interp, sp: [*]isize, rsp: [*][]Instr, ip: []Instr, target: []const Instr) anyerror!void {
    _ = target;
    const u: usize = @intCast(sp[0]);
    const target_: *Instr = @ptrFromInt(u);
    try @call(.always_tail, target_.code, .{ self, sp + 1, rsp, ip, target_[0..0] });
}
const execute = Word{ .link = &char, .flag = "EXECUTE".len, .name = "EXECUTE", .code = &[_]Instr{.{ .code = _execute }} };

inline fn _syscall3(sp: [*]isize) ![*]isize {
    const number_: syscalls.X64 = @enumFromInt(sp[0]);
    const arg1: usize = @intCast(sp[1]);
    const arg2: usize = @intCast(sp[2]);
    const arg3: usize = @intCast(sp[3]);

    sp[3] = @intCast(linux.syscall3(number_, arg1, arg2, arg3));
    return sp + 3;
}
const syscall3 = defcode(&execute, "SYSCALL3", _syscall3);

inline fn _syscall2(sp: [*]isize) ![*]isize {
    const number_: syscalls.X64 = @enumFromInt(sp[0]);
    const arg1: usize = @intCast(sp[1]);
    const arg2: usize = @intCast(sp[2]);

    sp[2] = @intCast(linux.syscall2(number_, arg1, arg2));
    return sp + 2;
}
const syscall2 = defcode(&execute, "SYSCALL2", _syscall2);

inline fn _syscall1(sp: [*]isize) ![*]isize {
    const number_: syscalls.X64 = @enumFromInt(sp[0]);
    const arg1: usize = @intCast(sp[1]);

    sp[1] = @intCast(linux.syscall1(number_, arg1));
    return sp + 1;
}
const syscall1 = defcode(&execute, "SYSCALL1", _syscall1);

inline fn _syscall0(sp: [*]isize) ![*]isize {
    const number_: syscalls.X64 = @enumFromInt(sp[0]);

    sp[0] = @intCast(linux.syscall0(number_));
    return sp;
}
const syscall0 = defcode(&execute, "SYSCALL0", _syscall0);

pub fn main() anyerror!void {
    const N = 0x20;
    var stack: [N]isize = [_]isize{undefined} ** N;
    const sp: [*]isize = &stack;
    const return_stack: [N][]Instr = [_][]Instr{undefined} ** N;
    const rsp: [*][]Instr = @constCast(&return_stack);
    const here_: [1000]u8 = undefined;
    const self = Interp{
        .state = 0,
        .latest = @constCast(&syscall0),
        .s0 = sp + N,
        .base = 10,
        .r0 = rsp + N,
        .buffer = undefined,
        .here = @constCast(&here_),
    };
    const cold_start = [_]Instr{.{ .word = @constCast(quit.code) }};
    const ip: []Instr = @constCast(&cold_start);

    try ip[0].word[0].code(@constCast(&self), sp, rsp, ip[1..], ip[0].word);
}
