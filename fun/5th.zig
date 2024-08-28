const std = @import("std");
const io = std.io;
const fmt = std.fmt;
const mem = std.mem;
const os = std.os;
const linux = os.linux;
const syscalls = linux.syscalls;
const posix = std.posix;

const stdin = io.getStdIn().reader();
const stdout = io.getStdOut().writer();

const Flag = enum(u8) { IMMED = 0x80, HIDDEN = 0x20, LENMASK = 0x1F, ZERO = 0x0 };

const Word = extern struct {
    link: ?*const Word,
    flag: u8,
    name: [31]u8 align(1),
};

const offset = @divTrunc(@sizeOf(Word), @sizeOf(Instr));

inline fn codeFieldAddress(w: [*]const Instr) [*]const Instr {
    return w + offset;
}

const Interp = struct {
    state: isize,
    latest: *Word,
    s0: [*]const isize,
    base: isize,
    r0: [*]const [*]Instr,
    buffer: [32]u8,
    alloc: mem.Allocator,
    here: [*]u8,
    code: []Instr,

    pub inline fn next(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
        _ = target;
        const tgt = ip[0].word;
        return @call(.always_tail, tgt[0].code, .{ self, sp, rsp, ip[1..], tgt });
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
        while (node != null and ((node.?.flag & mask) != name.len or !mem.eql(u8, node.?.name[0..name.len], name)))
            node = @constCast(node.?.link);

        return node;
    }

    pub fn index(self: *Interp) usize {
        return @divTrunc(@intFromPtr(self.here) - @intFromPtr(self.code.ptr), @sizeOf(Instr));
    }

    fn ensureCapacity(self: *Interp) error{OutOfMemory}!usize {
        var n = self.code.len;
        const i = self.index();
        while (i >= n)
            n *|= 2;
        if (n > self.code.len) {
            if (self.alloc.resize(self.code, n)) {
                self.code.len = n;
            } else {
                return error.OutOfMemory;
            }
        }
        return i;
    }

    pub fn append(self: *Interp, instr: Instr) mem.Allocator.Error!void {
        const i = try self.ensureCapacity();
        self.here = @ptrCast(self.code.ptr + (i + 1));
        self.code[i] = instr;
    }
};

const Instr = packed union {
    code: *const fn (*Interp, []isize, [][*]Instr, [*]Instr, [*]const Instr) anyerror!void,
    literal: isize,
    word: [*]const Instr,
};

const Source = union(enum) {
    self: []const u8,
    literal: isize,
};

fn key() u8 {
    const b = stdin.readByte() catch std.process.exit(0);
    return b;
}

fn defword_(
    comptime last: ?[]const Instr,
    comptime flag: Flag,
    comptime name: []const u8,
    comptime code: []const Instr,
) [offset + code.len]Instr {
    var instrs: [offset + code.len]Instr = undefined;
    const p: *Word = @ptrCast(&instrs[0]);
    p.link = if (last == null) null else @ptrCast(last.?.ptr);
    p.flag = name.len | @intFromEnum(flag);
    @memcpy(p.name[0..name.len], name);
    @memset(p.name[name.len..31], 0);
    @memcpy(instrs[offset..], code);
    return instrs;
}

fn defcode_(
    comptime last: ?[]const Instr,
    comptime name: []const u8,
    comptime code: fn (*Interp, []isize, [][*]Instr, [*]Instr, [*]const Instr) anyerror!void,
) [offset + 1]Instr {
    return defword_(last, Flag.ZERO, name, &[_]Instr{.{ .code = code }});
}

fn defcode(
    comptime last: ?[]const Instr,
    comptime name: []const u8,
    comptime stack: fn ([]isize) callconv(.Inline) anyerror![]isize,
) [offset + 1]Instr {
    const wrap = struct {
        pub fn code(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
            self.next(try stack(sp), rsp, ip, target);
        }
    };
    return defcode_(last, name, wrap.code);
}

fn defconst(
    comptime last: ?[]const Instr,
    comptime name: []const u8,
    comptime value: Source,
) [offset + 1]Instr {
    const wrap = struct {
        pub fn code(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
            const s: []isize = (sp.ptr - 1)[0 .. sp.len + 1];
            s[0] = switch (value) {
                .self => |f| @intCast(@intFromPtr(&@field(self, f))),
                .literal => |i| i,
            };
            self.next(s, rsp, ip, target);
        }
    };
    return defcode_(last, name, wrap.code);
}

fn defword(
    comptime last: ?[]const Instr,
    comptime flag: Flag,
    comptime name: []const u8,
    comptime data: []const []const Instr,
) [offset + data.len + 1]Instr {
    const code = [_]Instr{.{ .code = docol_ }} ++ comptime init: {
        var code: [data.len]Instr = undefined;
        for (&code, data) |*d, s| {
            d.* = .{ .word = codeFieldAddress(s.ptr) };
        }
        break :init &code;
    };
    return defword_(last, flag, name, code);
}

inline fn _drop(sp: []isize) anyerror![]isize {
    return sp[1..];
}
const drop = defcode(null, "DROP", _drop);

inline fn _swap(sp: []isize) anyerror![]isize {
    const temp = sp[1];
    sp[1] = sp[0];
    sp[0] = temp;
    return sp;
}
const swap = defcode(&drop, "SWAP", _swap);

inline fn _dup(sp: []isize) anyerror![]isize {
    const s = (sp.ptr - 1)[0 .. sp.len + 1];
    s[0] = sp[0];
    return s;
}
const dup = defcode(&swap, "DUP", _dup);

inline fn _over(sp: []isize) anyerror![]isize {
    const s = (sp.ptr - 1)[0 .. sp.len + 1];
    s[0] = sp[1];
    return s;
}
const over = defcode(&dup, "OVER", _over);

inline fn _rot(sp: []isize) anyerror![]isize {
    const a = sp[0];
    const b = sp[1];
    const c = sp[2];
    sp[2] = b;
    sp[1] = a;
    sp[0] = c;
    return sp;
}
const rot = defcode(&over, "ROT", _rot);

inline fn _nrot(sp: []isize) anyerror![]isize {
    const a = sp[0];
    const b = sp[1];
    const c = sp[2];
    sp[2] = a;
    sp[1] = c;
    sp[0] = b;
    return sp;
}
const nrot = defcode(&rot, "-ROT", _nrot);

inline fn _twodrop(sp: []isize) anyerror![]isize {
    return sp[2..];
}
const twodrop = defcode(&nrot, "2DROP", _twodrop);

inline fn _twodup(sp: []isize) anyerror![]isize {
    const s = (sp.ptr - 2)[0 .. sp.len + 2];
    s[1] = sp[1];
    s[0] = sp[0];
    return s;
}
const twodup = defcode(&twodrop, "2DUP", _twodup);

inline fn _twoswap(sp: []isize) anyerror![]isize {
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

inline fn _qdup(sp: []isize) anyerror![]isize {
    if (sp[0] != 0) {
        const s = (sp.ptr - 1)[0 .. sp.len + 1];
        s[0] = sp[0];
        return s;
    }
    return sp;
}
const qdup = defcode(&twoswap, "?DUP", _qdup);

inline fn _incr(sp: []isize) anyerror![]isize {
    sp[0] += 1;
    return sp;
}
const incr = defcode(&qdup, "1+", _incr);

inline fn _decr(sp: []isize) anyerror![]isize {
    sp[0] -= 1;
    return sp;
}
const decr = defcode(&incr, "1-", _decr);

inline fn _incrp(sp: []isize) anyerror![]isize {
    sp[0] += @sizeOf(usize);
    return sp;
}
const incrp = defcode(&decr, &[_]u8{ '0' + @sizeOf(usize), '+' }, _incrp);

inline fn _decrp(sp: []isize) anyerror![]isize {
    sp[0] -= @sizeOf(usize);
    return sp;
}
const decrp = defcode(&incrp, &[_]u8{ '0' + @sizeOf(usize), '-' }, _decrp);

inline fn _add(sp: []isize) anyerror![]isize {
    sp[1] += sp[0];
    return sp[1..];
}
const add = defcode(&decrp, "+", _add);

inline fn _sub(sp: []isize) anyerror![]isize {
    sp[1] -= sp[0];
    return sp[1..];
}
const sub = defcode(&add, "-", _sub);

inline fn _mul(sp: []isize) anyerror![]isize {
    sp[1] *= sp[0];
    return sp[1..];
}
const mul = defcode(&sub, "*", _mul);

inline fn _divmod(sp: []isize) anyerror![]isize {
    const a = sp[1];
    const b = sp[0];
    sp[1] = @rem(a, b);
    sp[0] = @divTrunc(a, b);
    return sp;
}
const divmod = defcode(&mul, "/MOD", _divmod);

inline fn _equ(sp: []isize) anyerror![]isize {
    sp[1] = if (sp[1] == sp[0]) -1 else 0;
    return sp[1..];
}
const equ = defcode(&divmod, "=", _equ);

inline fn _nequ(sp: []isize) anyerror![]isize {
    sp[1] = if (sp[1] == sp[0]) 0 else -1;
    return sp[1..];
}
const nequ = defcode(&equ, "<>", _nequ);

inline fn _lt(sp: []isize) anyerror![]isize {
    sp[1] = if (sp[1] < sp[0]) -1 else 0;
    return sp[1..];
}
const lt = defcode(&nequ, "<", _lt);

inline fn _gt(sp: []isize) anyerror![]isize {
    sp[1] = if (sp[1] > sp[0]) -1 else 0;
    return sp[1..];
}
const gt = defcode(&lt, ">", _gt);

inline fn _le(sp: []isize) anyerror![]isize {
    sp[1] = if (sp[1] <= sp[0]) -1 else 0;
    return sp[1..];
}
const le = defcode(&gt, "<=", _le);

inline fn _ge(sp: []isize) anyerror![]isize {
    sp[1] = if (sp[1] >= sp[0]) -1 else 0;
    return sp[1..];
}
const ge = defcode(&le, ">=", _ge);

inline fn _zequ(sp: []isize) anyerror![]isize {
    sp[0] = if (sp[0] == 0) -1 else 0;
    return sp;
}
const zequ = defcode(&ge, "0=", _zequ);

inline fn _znequ(sp: []isize) anyerror![]isize {
    sp[0] = if (sp[0] != 0) -1 else 0;
    return sp;
}
const znequ = defcode(&zequ, "0<>", _znequ);

inline fn _zlt(sp: []isize) anyerror![]isize {
    sp[0] = if (sp[0] < 0) -1 else 0;
    return sp;
}
const zlt = defcode(&znequ, "0<", _zlt);

inline fn _zgt(sp: []isize) anyerror![]isize {
    sp[0] = if (sp[0] > 0) -1 else 0;
    return sp;
}
const zgt = defcode(&zlt, "0>", _zgt);

inline fn _zle(sp: []isize) anyerror![]isize {
    sp[0] = if (sp[0] <= 0) -1 else 0;
    return sp;
}
const zle = defcode(&zgt, "0<=", _zle);

inline fn _zge(sp: []isize) anyerror![]isize {
    sp[0] = if (sp[0] >= 0) -1 else 0;
    return sp;
}
const zge = defcode(&zle, "0>=", _zge);

inline fn _and(sp: []isize) anyerror![]isize {
    sp[1] &= sp[0];
    return sp[1..];
}
const and_ = defcode(&zge, "AND", _and);

inline fn _or(sp: []isize) anyerror![]isize {
    sp[1] |= sp[0];
    return sp[1..];
}
const or_ = defcode(&and_, "OR", _or);

inline fn _xor(sp: []isize) anyerror![]isize {
    sp[1] ^= sp[0];
    return sp[1..];
}
const xor = defcode(&or_, "XOR", _xor);

inline fn _invert(sp: []isize) anyerror![]isize {
    sp[0] = ~sp[0];
    return sp;
}
const invert = defcode(&xor, "INVERT", _invert);

fn _exit(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    _ = ip;
    self.next(sp, rsp[1..], rsp[0], target);
}
const exit = defcode_(&invert, "EXIT", _exit);

fn _lit(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const s = (sp.ptr - 1)[0 .. sp.len + 1];
    s[0] = ip[0].literal;
    self.next(s, rsp, ip[1..], target);
}
const lit = defcode_(&exit, "LIT", _lit);

inline fn _store(sp: []isize) anyerror![]isize {
    const u: usize = @intCast(sp[0]);
    const p: *isize = @ptrFromInt(u);
    p.* = sp[1];
    return sp[2..];
}
const store = defcode(&lit, "!", _store);

inline fn _fetch(sp: []isize) anyerror![]isize {
    const u: usize = @intCast(sp[0]);
    const p: *isize = @ptrFromInt(u);
    sp[0] = p.*;
    return sp;
}
const fetch = defcode(&store, "@", _fetch);

inline fn _addstore(sp: []isize) anyerror![]isize {
    const u: usize = @intCast(sp[0]);
    const p: *[*]u8 = @ptrFromInt(u);
    const v: usize = @intCast(sp[1]);
    p.* += v;
    return sp[2..];
}
const addstore = defcode(&fetch, "+!", _addstore);

inline fn _substore(sp: []isize) anyerror![]isize {
    const u: usize = @intCast(sp[0]);
    const p: *[*]u8 = @ptrFromInt(u);
    const v: usize = @intCast(sp[1]);
    p.* -= v;
    return sp[2..];
}
const substore = defcode(&addstore, "-!", _substore);

inline fn _storebyte(sp: []isize) anyerror![]isize {
    const u: usize = @intCast(sp[0]);
    const v: u8 = @intCast(sp[1]);
    const p: [*]u8 = @ptrFromInt(u);
    p[0] = v;
    return sp[2..];
}
const storebyte = defcode(&substore, "C!", _storebyte);

inline fn _fetchbyte(sp: []isize) anyerror![]isize {
    const u: usize = @intCast(sp[0]);
    const p: [*]u8 = @ptrFromInt(u);
    sp[0] = p[0];
    return sp;
}
const fetchbyte = defcode(&storebyte, "C@", _fetchbyte);

inline fn _ccopy(sp: []isize) anyerror![]isize {
    const u: usize = @intCast(sp[0]);
    const v: usize = @intCast(sp[1]);
    const p: [*]u8 = @ptrFromInt(u);
    const q: [*]u8 = @ptrFromInt(v);
    q[0] = p[0];
    return sp[2..];
}
const ccopy = defcode(&fetchbyte, "C@C!", _ccopy);

inline fn _cmove(sp: []isize) anyerror![]isize {
    const n: usize = @intCast(sp[0]);
    @memcpy(dest: {
        const u: usize = @intCast(sp[1]);
        const p: [*]u8 = @ptrFromInt(u);
        break :dest p[0..n];
    }, source: {
        const v: usize = @intCast(sp[2]);
        const q: [*]u8 = @ptrFromInt(v);
        break :source q[0..n];
    });
    return sp[2..];
}
const cmove = defcode(&ccopy, "CMOVE", _cmove);

const state = defconst(&cmove, "STATE", .{ .self = "state" });

fn _here(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const s = (sp.ptr - 1)[0 .. sp.len + 1];
    _ = try self.ensureCapacity();
    const u = @intFromPtr(&self.here);
    s[0] = @intCast(u);
    self.next(s, rsp, ip, target);
}
const here = defcode_(&state, "HERE", _here);
const latest = defconst(&here, "LATEST", .{ .self = "latest" });
const sz = defconst(&latest, "S0", .{ .self = "s0" });
const base = defconst(&sz, "BASE", .{ .self = "base" });

inline fn _argc(sp: []isize) anyerror![]isize {
    const s = (sp.ptr - 1)[0 .. sp.len + 1];
    const u = @intFromPtr(os.argv.ptr - 1);
    s[0] = @intCast(u);
    return s;
}
const argc = defcode(&base, "(ARGC)", _argc);
const version = defconst(&argc, "VERSION", .{ .literal = 47 });
fn _rz(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const s = (sp.ptr - 1)[0 .. sp.len + 1];
    const u = @intFromPtr(self.r0);
    s[0] = @intCast(u);
    self.next(s, rsp, ip, target);
}
const rz = defcode_(&version, "R0", _rz);

fn docol_(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const r = (rsp.ptr - 1)[0 .. rsp.len + 1];
    r[0] = @constCast(ip);
    self.next(sp, r, @constCast(target[1..]), target);
}

inline fn _docol(sp: []isize) anyerror![]isize {
    const s = (sp.ptr - 1)[0 .. sp.len + 1];
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
const o_rdonly = defconst(&sys_brk, "O_RDONLY", .{ .literal = @intFromEnum(posix.ACCMODE.RDONLY) });
const o_wronly = defconst(&o_rdonly, "O_WRONLY", .{ .literal = @intFromEnum(posix.ACCMODE.WRONLY) });
const o_rdwr = defconst(&o_wronly, "O_RDWR", .{ .literal = @intFromEnum(posix.ACCMODE.RDWR) });
const o_creat = defconst(&o_rdwr, "O_CREAT", .{ .literal = 0x100 });
const o_excl = defconst(&o_creat, "O_EXCL", .{ .literal = 0x200 });
const o_trunc = defconst(&o_excl, "O_TRUNC", .{ .literal = 0x1000 });
const o_append = defconst(&o_trunc, "O_APPEND", .{ .literal = 0x2000 });
const o_nonblock = defconst(&o_append, "O_NONBLOCK", .{ .literal = 0x4000 });

fn _tor(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const r = (rsp.ptr - 1)[0 .. rsp.len + 1];
    const s: usize = @intCast(sp[0]);
    const t: *[*]Instr = @ptrFromInt(s);
    r[0] = t.*;
    self.next(sp[1..], r, ip, target);
}
const tor = defcode_(&o_nonblock, ">R", _tor);

fn _fromr(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const s = (sp.ptr - 1)[0 .. sp.len + 1];
    sp[0] = @intCast(@intFromPtr(&rsp[0]));
    self.next(s, rsp[1..], ip, target);
}
const fromr = defcode_(&tor, "R>", _fromr);

fn _rspfetch(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const s = (sp.ptr - 1)[0 .. sp.len + 1];
    sp[0] = @intCast(@intFromPtr(rsp.ptr));
    self.next(s, rsp, ip, target);
}
const rspfetch = defcode_(&fromr, "RSP@", _rspfetch);

fn _rspstore(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const s: usize = @intCast(sp[0]);
    const t: [*][*]Instr = @ptrFromInt(s);
    const n = @divTrunc(@intFromPtr(rsp.ptr + rsp.len) - s, @sizeOf([*][*]Instr));
    self.next(sp[1..], t[0..n], ip, target);
}
const rspstore = defcode_(&rspfetch, "RSP!", _rspstore);

fn _rdrop(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    self.next(sp, rsp[1..], ip, target);
}
const rdrop = defcode_(&rspstore, "RDROP", _rdrop);

inline fn _dspfetch(sp: []isize) anyerror![]isize {
    const s = (sp.ptr - 1)[0 .. sp.len + 1];
    s[0] = @intCast(@intFromPtr(sp.ptr));
    return s;
}
const dspfetch = defcode(&rdrop, "DSP@", _dspfetch);

inline fn _dspstore(sp: []isize) anyerror![]isize {
    const u: usize = @intCast(sp[0]);
    const p: [*]isize = @ptrFromInt(u);
    const n = @divTrunc(@intFromPtr(sp.ptr + sp.len) - u, @sizeOf([*]Instr));
    return p[0..n];
}
const dspstore = defcode(&dspfetch, "DSP!", _dspstore);

inline fn _key(sp: []isize) anyerror![]isize {
    const s = (sp.ptr - 1)[0 .. sp.len + 1];
    s[0] = @as(isize, key());
    return s;
}
const key_ = defcode(&dspstore, "KEY", _key);

inline fn _emit(sp: []isize) anyerror![]isize {
    const u: usize = @intCast(sp[0]);
    const c: u8 = @truncate(u);
    try stdout.print("{c}", .{c});
    return sp[1..];
}
const emit = defcode(&key_, "EMIT", _emit);

fn _word(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const s = (sp.ptr - 2)[0 .. sp.len + 2];
    const u = @intFromPtr(&self.buffer);
    s[1] = @intCast(u);
    s[0] = @intCast(self.word());
    self.next(s, rsp, ip, target);
}
const word_ = defcode_(&emit, "WORD", _word);

fn _number(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
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
const number = defcode_(&word_, "NUMBER", _number);

fn _find(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const c: usize = @intCast(sp[0]);
    const u: usize = @intCast(sp[1]);
    const s: [*]u8 = @ptrFromInt(u);
    const v = self.find(s[0..c]);

    sp[1] = @intCast(@intFromPtr(v));
    self.next(sp[1..], rsp, ip, target);
}
const find_ = defcode_(&number, "FIND", _find);

inline fn _tcfa(sp: []isize) anyerror![]isize {
    const u: usize = @intCast(sp[0]);
    const w: [*]const Instr = @ptrFromInt(u);
    sp[0] = @intCast(@intFromPtr(codeFieldAddress(w)));
    return sp;
}
const tcfa = defcode(&find_, ">CFA", _tcfa);
const tdfa = defword(
    &tcfa,
    Flag.ZERO,
    ">DFA",
    &[_][]const Instr{ &tcfa, &incrp, &exit, &exit },
);

fn _create(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const c: usize = @intCast(sp[0]);
    const u: usize = @intCast(sp[1]);
    const s: [*]u8 = @ptrFromInt(u);
    if (self.code.len > 0 and self.alloc.resize(self.code, self.index()) == false)
        return error.IndexOutOfBounds;
    const code = try self.alloc.alloc(Instr, offset + 4);
    var new: *Word = @ptrCast(code.ptr);
    new.link = self.latest;
    new.flag = @truncate(c);
    @memset(new.name[0..31], 0);
    @memcpy(new.name[0..c], s[0..c]);
    self.latest = new;
    self.here = @ptrCast(&code[offset]);
    self.code = code;
    self.next(sp[2..], rsp, ip, target);
}
const create = defcode_(&tdfa, "CREATE", _create);

fn _comma(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const s: isize = sp[0];
    const instr: Instr = if (s < 0x1000) .{ .literal = s } else if (s == @intFromPtr(&docol_)) .{ .code = docol_ } else .{ .word = blk: {
        const u: usize = @intCast(s);
        const p: [*]Instr = @ptrFromInt(u);
        break :blk p;
    } };
    try self.append(instr);
    self.next(sp[1..], rsp, ip, target);
}
const comma = defcode_(&create, ",", _comma);

fn _lbrac(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    self.state = 0;
    self.next(sp, rsp, ip, target);
}
const lbrac = defword_(
    &comma,
    Flag.IMMED,
    "[",
    &[_]Instr{.{ .code = _lbrac }},
);

fn _rbrac(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    self.state = 1;
    self.next(sp, rsp, ip, target);
}
const rbrac = defcode_(&lbrac, "]", _rbrac);

fn _immediate(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    self.latest.flag ^= @intFromEnum(Flag.IMMED);
    self.next(sp, rsp, ip, target);
}
const immediate = defword_(
    &rbrac,
    Flag.IMMED,
    "IMMEDIATE",
    &[_]Instr{.{ .code = _immediate }},
);

inline fn _hidden(sp: []isize) anyerror![]isize {
    const u: usize = @intCast(sp[0]);
    const w: *Word = @ptrFromInt(u);
    w.flag ^= @intFromEnum(Flag.HIDDEN);
    return sp[1..];
}
const hidden = defcode(&immediate, "HIDDEN", _hidden);

const hide = defword(
    &hidden,
    Flag.ZERO,
    "HIDE",
    &[_][]const Instr{ &word_, &find_, &hidden, &exit },
);
const colon = defword(
    &hide,
    Flag.ZERO,
    ":",
    &[_][]const Instr{ &word_, &create, &docol, &comma, &latest, &fetch, &hidden, &rbrac, &exit, &exit },
);

fn _tick(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const s = (sp.ptr - 1)[0 .. sp.len + 1];
    const u = @intFromPtr(ip[0].word);
    s[0] = @intCast(u);
    self.next(s, rsp, ip[1..], target);
}
const tick = defcode_(&colon, "'", _tick);

const semicolon = defword(
    &tick,
    Flag.IMMED,
    ";",
    &[_][]const Instr{ &tick, &exit, &comma, &latest, &fetch, &hidden, &lbrac, &exit },
);

fn _branch(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const n = @divTrunc(ip[0].literal, @sizeOf(Instr));
    const a = @abs(n);
    const p = if (n < 0) ip - a else ip + a;
    self.next(sp, rsp, p, target);
}
const branch = defcode_(&semicolon, "BRANCH", _branch);

fn _zbranch(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    if (sp[0] == 0)
        return @call(.always_tail, _branch, .{ self, sp[1..], rsp, ip, target });
    self.next(sp[1..], rsp, ip[1..], target);
}
const zbranch = defcode_(&branch, "0BRANCH", _zbranch);

fn _litstring(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const c: usize = @intCast(ip[0].literal);
    const s = (sp.ptr - 2)[0 .. sp.len + 2];
    s[1] = @intCast(@intFromPtr(&ip[1]));
    s[0] = @intCast(c);
    const n: usize = 1 + @divTrunc(c + @sizeOf(Instr), @sizeOf(Instr));
    self.next(s, rsp, ip[n..], target);
}
const litstring = defcode_(&zbranch, "LITSTRING", _litstring);

inline fn _tell(sp: []isize) anyerror![]isize {
    const u: usize = @intCast(sp[0]);
    const v: usize = @intCast(sp[1]);
    const p: [*]u8 = @ptrFromInt(v);
    _ = try stdout.write(p[0..u]);
    return sp[2..];
}
const tell = defcode(&litstring, "TELL", _tell);

fn _interpret(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const c = self.word();
    var s = sp;

    if (self.find(self.buffer[0..c])) |new| {
        const tgt = codeFieldAddress(@ptrCast(new));
        if ((new.flag & @intFromEnum(Flag.IMMED)) != 0 or self.state == 0) {
            return @call(.always_tail, tgt[0].code, .{ self, sp, rsp, ip, tgt });
        } else {
            try self.append(.{ .word = tgt });
        }
    } else if (fmt.parseInt(isize, self.buffer[0..c], blk: {
        const ubase: usize = @intCast(self.base);
        const bbase: u8 = @intCast(ubase);

        break :blk bbase;
    })) |a| {
        if (self.state == 1) {
            try self.append(.{ .word = codeFieldAddress(&lit) });
            try self.append(.{ .literal = a });
        } else {
            s = (sp.ptr - 1)[0 .. sp.len + 1];
            s[0] = a;
        }
    } else |_| {
        std.debug.panic("PARSE ERROR: {s}\n", .{self.buffer[0..c]});
    }
    self.next(s, rsp, ip, target);
}
const interpret = defcode_(&tell, "INTERPRET", _interpret);

const quit = defword_(
    &interpret,
    Flag.ZERO,
    "QUIT",
    &[_]Instr{
        .{ .code = docol_ },
        .{ .word = codeFieldAddress(&rz) },
        .{ .word = codeFieldAddress(&rspstore) },
        .{ .word = codeFieldAddress(&interpret) },
        .{ .word = codeFieldAddress(&branch) },
        .{ .literal = -2 * @sizeOf(Instr) },
        .{ .word = codeFieldAddress(&exit) },
    },
);

fn _char(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const s = (sp.ptr - 1)[0 .. sp.len + 1];
    _ = self.word();
    s[0] = self.buffer[0];
    self.next(s, rsp, ip, target);
}
const char = defcode_(&quit, "CHAR", _char);

fn _execute(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    _ = target;
    const u: usize = @intCast(sp[0]);
    const target_: *Instr = @ptrFromInt(u);
    return @call(.always_tail, target_.code, .{ self, sp[1..], rsp, ip, target_[0..0] });
}
const execute = defcode_(&char, "EXECUTE", _execute);

inline fn _syscall3(sp: []isize) ![]isize {
    const number_: syscalls.X64 = @enumFromInt(sp[0]);
    const arg1: usize = @intCast(sp[1]);
    const arg2: usize = @intCast(sp[2]);
    const arg3: usize = @intCast(sp[3]);

    sp[3] = @intCast(linux.syscall3(number_, arg1, arg2, arg3));
    return sp[3..];
}
const syscall3 = defcode(&execute, "SYSCALL3", _syscall3);

inline fn _syscall2(sp: []isize) ![]isize {
    const number_: syscalls.X64 = @enumFromInt(sp[0]);
    const arg1: usize = @intCast(sp[1]);
    const arg2: usize = @intCast(sp[2]);

    sp[2] = @intCast(linux.syscall2(number_, arg1, arg2));
    return sp[2..];
}
const syscall2 = defcode(&syscall3, "SYSCALL2", _syscall2);

fn _syscall1(self: *Interp, sp: []isize, rsp: [][*]Instr, ip: [*]Instr, target: [*]const Instr) anyerror!void {
    const number_: syscalls.X64 = @enumFromInt(sp[0]);
    const arg1: usize = @intCast(sp[1]);

    sp[1] = if (number_ == syscalls.X64.brk and arg1 == 0) blk: {
        const p: *std.heap.FixedBufferAllocator = @alignCast(@ptrCast(self.alloc.ptr));
        break :blk @intCast(@intFromPtr(p.buffer.ptr + p.buffer.len));
    } else @intCast(linux.syscall1(number_, arg1));
    self.next(sp[1..], rsp, ip, target);
}
const syscall1 = defcode_(&syscall2, "SYSCALL1", _syscall1);

inline fn _syscall0(sp: []isize) ![]isize {
    const number_: syscalls.X64 = @enumFromInt(sp[0]);

    sp[0] = @intCast(linux.syscall0(number_));
    return sp;
}
const syscall0 = defcode(&syscall1, "SYSCALL0", _syscall0);

pub fn main() anyerror!void {
    const N = 0x20;
    var stack: [N]isize = [_]isize{undefined} ** N;
    const sp: []isize = stack[N..];
    const return_stack: [N][*]Instr = [_][*]Instr{undefined} ** N;
    const rsp: [][*]Instr = return_stack[N..];
    var memory: [0x800000]u8 = undefined;
    var fba = std.heap.FixedBufferAllocator.init(&memory);
    const allocator = fba.allocator();
    var env = Interp{
        .state = 0,
        .latest = @constCast(@ptrCast(&syscall0)),
        .s0 = sp.ptr,
        .base = 10,
        .r0 = rsp.ptr,
        .buffer = undefined,
        .alloc = allocator,
        .here = undefined,
        .code = undefined,
    };
    const self = &env;
    const target = codeFieldAddress(&quit);
    const cold_start = [_]Instr{.{ .word = target }};
    const ip: [*]Instr = @constCast(&cold_start);

    try docol_(self, sp, rsp, ip, target);
}
