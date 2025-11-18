const std = @import("std");
const fmt = std.fmt;
const fs = std.fs;
const mem = std.mem;
const os = std.os;
const syscalls = os.linux.syscalls;
const arch = @import("builtin").cpu.arch;

const conv: std.builtin.CallingConvention = switch (arch) {
    .x86_64 => .c,
    else => .auto,
};
var stdin_buffer: [2048]u8 = undefined;
var stdin_reader = fs.File.stdin().reader(&stdin_buffer);
const stdin = &stdin_reader.interface;

var stdout_buffer: [2048]u8 = undefined;
var stdout_writer = fs.File.stdout().writer(&stdout_buffer);
const stdout = &stdout_writer.interface;

const O_RDONLY = 0o0;
const O_WRONLY = 0o1;
const O_RDWR = 0o2;
const O_CREAT = 0o100;
const O_EXCL = 0o200;
const O_TRUNC = 0o1000;
const O_APPEND = 0o2000;
const O_NONBLOCK = 0o4000;
const F_LENMASK = std.ascii.control_code.us;
const Flag = enum(u8) { IMMED = 0x80, HIDDEN = ' ', ZERO = 0x0 };

const Word = extern struct {
    link: ?*const Word,
    flag: u8,
    name: [F_LENMASK]u8 align(1),
};

const offset = @divExact(@sizeOf(Word), @sizeOf(Instr));

inline fn codeFieldAddress(w: [*]const Instr) [*]const Instr {
    return w + offset;
}

fn InterpAligned(comptime alignment: mem.Alignment) type {
    return struct {
        const Self = @This();

        state: isize,
        latest: *Word,
        s0: [*]const isize,
        base: isize,
        r0: [*]const [*]const Instr,
        buffer: [32]u8,
        memory: *std.array_list.AlignedManaged(u8, alignment),
        here: [*]u8,

        pub fn init(sp: []const isize, rsp: []const [*]const Instr, m: *std.array_list.AlignedManaged(u8, alignment)) Self {
            m.ensureUnusedCapacity(@sizeOf(Instr)) catch @panic("init cannot ensureUnusedCapacity");
            return .{
                .state = 0,
                .latest = @ptrCast(&syscall0),
                .s0 = sp.ptr,
                .base = 10,
                .r0 = rsp.ptr,
                .buffer = undefined,
                .memory = m,
                .here = m.items.ptr + m.items.len,
            };
        }

        pub inline fn next(self: *Self, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) void {
            _ = target;
            const tgt = ip[0].word;
            return @call(.always_tail, tgt[0].code, .{ self, sp, rsp, ip[1..], tgt });
        }

        pub fn word(self: *Self) usize {
            var ch: u8 = std.ascii.control_code.nul;
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

        pub fn find(self: Self, name: []u8) ?*const Word {
            const mask = @intFromEnum(Flag.HIDDEN) | F_LENMASK;
            var node: *const Word = self.latest;
            while (node.flag & mask != name.len or !mem.eql(u8, node.name[0..name.len], name))
                node = node.link orelse return null;

            return node;
        }

        pub fn append(self: *Self, instr: Instr) void {
            self.memory.items.len = @intFromPtr(self.here) - @intFromPtr(self.memory.items.ptr);
            self.memory.appendSlice(mem.asBytes(&instr)) catch @panic("append cannot appendSlice");
            self.here = self.memory.items.ptr + self.memory.items.len;
        }
    };
}

const Interp = InterpAligned(mem.Alignment.of(Instr));

const Code = fn (*Interp, [*]isize, [*][*]const Instr, [*]const Instr, [*]const Instr) callconv(conv) void;

const Instr = packed union {
    code: *const Code,
    literal: isize,
    word: [*]const Instr,
};

fn key() u8 {
    const b = stdin.takeByte() catch std.process.exit(0);
    return b;
}

fn defword(
    comptime last: ?[]const Instr,
    comptime flag: Flag,
    comptime name: []const u8,
    comptime code: []const Instr,
) [offset + code.len]Instr {
    var instrs: [offset + code.len]Instr = undefined;
    const p: *Word = @ptrCast(&instrs[0]);
    p.link = if (last) |link| @ptrCast(link.ptr) else null;
    p.flag = name.len | @intFromEnum(flag);
    @memcpy(p.name[0..name.len], name);
    @memset(p.name[name.len..F_LENMASK], 0);
    @memcpy(instrs[offset..], code);
    return instrs;
}

fn wrap(comptime stack: fn ([*]isize) callconv(.@"inline") [*]isize) []const Instr {
    const t = struct {
        fn code(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
            self.next(stack(sp), rsp, ip, target);
        }
    };
    return &.{.{ .code = t.code }};
}

fn attr(comptime name: []const u8) []const Instr {
    const t = struct {
        fn code(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
            const s = sp - 1;
            s[0] = @intCast(@intFromPtr(&@field(self, name)));
            self.next(s, rsp, ip, target);
        }
    };
    return &.{.{ .code = t.code }};
}

fn value(comptime literal: isize) []const Instr {
    const t = struct {
        fn code(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
            const s = sp - 1;
            s[0] = literal;
            self.next(s, rsp, ip, target);
        }
    };
    return &.{.{ .code = t.code }};
}

fn words(comptime data: []const []const Instr) []const Instr {
    var code: [data.len + 1]Instr = undefined;
    code[0].code = docol_;
    inline for (code[1..], data) |*d, s|
        d.word = codeFieldAddress(s.ptr);
    return &code;
}

inline fn _drop(sp: [*]isize) [*]isize {
    return sp[1..];
}
const drop = defword(null, Flag.ZERO, "DROP", wrap(_drop));

inline fn _swap(sp: [*]isize) [*]isize {
    const temp = sp[1];
    sp[1] = sp[0];
    sp[0] = temp;
    return sp;
}
const swap = defword(&drop, Flag.ZERO, "SWAP", wrap(_swap));

inline fn _dup(sp: [*]isize) [*]isize {
    const s = sp - 1;
    s[0] = sp[0];
    return s;
}
const dup = defword(&swap, Flag.ZERO, "DUP", wrap(_dup));

inline fn _over(sp: [*]isize) [*]isize {
    const s = sp - 1;
    s[0] = sp[1];
    return s;
}
const over = defword(&dup, Flag.ZERO, "OVER", wrap(_over));

inline fn _rot(sp: [*]isize) [*]isize {
    const a = sp[0];
    const b = sp[1];
    const c = sp[2];
    sp[2] = b;
    sp[1] = a;
    sp[0] = c;
    return sp;
}
const rot = defword(&over, Flag.ZERO, "ROT", wrap(_rot));

inline fn _nrot(sp: [*]isize) [*]isize {
    const a = sp[0];
    const b = sp[1];
    const c = sp[2];
    sp[2] = a;
    sp[1] = c;
    sp[0] = b;
    return sp;
}
const nrot = defword(&rot, Flag.ZERO, "-ROT", wrap(_nrot));

inline fn _twodrop(sp: [*]isize) [*]isize {
    return sp[2..];
}
const twodrop = defword(&nrot, Flag.ZERO, "2DROP", wrap(_twodrop));

inline fn _twodup(sp: [*]isize) [*]isize {
    const s = sp - 2;
    s[1] = sp[1];
    s[0] = sp[0];
    return s;
}
const twodup = defword(&twodrop, Flag.ZERO, "2DUP", wrap(_twodup));

inline fn _twoswap(sp: [*]isize) [*]isize {
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
const twoswap = defword(&twodup, Flag.ZERO, "2SWAP", wrap(_twoswap));

inline fn _qdup(sp: [*]isize) [*]isize {
    if (sp[0] != 0) {
        const s = sp - 1;
        s[0] = sp[0];
        return s;
    }
    return sp;
}
const qdup = defword(&twoswap, Flag.ZERO, "?DUP", wrap(_qdup));

inline fn _incr(sp: [*]isize) [*]isize {
    sp[0] += 1;
    return sp;
}
const incr = defword(&qdup, Flag.ZERO, "1+", wrap(_incr));

inline fn _decr(sp: [*]isize) [*]isize {
    sp[0] -= 1;
    return sp;
}
const decr = defword(&incr, Flag.ZERO, "1-", wrap(_decr));

inline fn _incrp(sp: [*]isize) [*]isize {
    sp[0] += @sizeOf(usize);
    return sp;
}
const incrp = defword(&decr, Flag.ZERO, fmt.comptimePrint("{d}+", .{@sizeOf(usize)}), wrap(_incrp));

inline fn _decrp(sp: [*]isize) [*]isize {
    sp[0] -= @sizeOf(usize);
    return sp;
}
const decrp = defword(&incrp, Flag.ZERO, fmt.comptimePrint("{d}-", .{@sizeOf(usize)}), wrap(_decrp));

inline fn _add(sp: [*]isize) [*]isize {
    sp[1] += sp[0];
    return sp[1..];
}
const add = defword(&decrp, Flag.ZERO, "+", wrap(_add));

inline fn _sub(sp: [*]isize) [*]isize {
    sp[1] -= sp[0];
    return sp[1..];
}
const sub = defword(&add, Flag.ZERO, "-", wrap(_sub));

inline fn _mul(sp: [*]isize) [*]isize {
    sp[1] *= sp[0];
    return sp[1..];
}
const mul = defword(&sub, Flag.ZERO, "*", wrap(_mul));

inline fn _divmod(sp: [*]isize) [*]isize {
    const a = sp[1];
    const b = sp[0];
    sp[1] = @rem(a, b);
    sp[0] = @divTrunc(a, b);
    return sp;
}
const divmod = defword(&mul, Flag.ZERO, "/MOD", wrap(_divmod));

inline fn _equ(sp: [*]isize) [*]isize {
    sp[1] = if (sp[1] == sp[0]) -1 else 0;
    return sp[1..];
}
const equ = defword(&divmod, Flag.ZERO, "=", wrap(_equ));

inline fn _nequ(sp: [*]isize) [*]isize {
    sp[1] = if (sp[1] == sp[0]) 0 else -1;
    return sp[1..];
}
const nequ = defword(&equ, Flag.ZERO, "<>", wrap(_nequ));

inline fn _lt(sp: [*]isize) [*]isize {
    sp[1] = if (sp[1] < sp[0]) -1 else 0;
    return sp[1..];
}
const lt = defword(&nequ, Flag.ZERO, "<", wrap(_lt));

inline fn _gt(sp: [*]isize) [*]isize {
    sp[1] = if (sp[1] > sp[0]) -1 else 0;
    return sp[1..];
}
const gt = defword(&lt, Flag.ZERO, ">", wrap(_gt));

inline fn _le(sp: [*]isize) [*]isize {
    sp[1] = if (sp[1] <= sp[0]) -1 else 0;
    return sp[1..];
}
const le = defword(&gt, Flag.ZERO, "<=", wrap(_le));

inline fn _ge(sp: [*]isize) [*]isize {
    sp[1] = if (sp[1] >= sp[0]) -1 else 0;
    return sp[1..];
}
const ge = defword(&le, Flag.ZERO, ">=", wrap(_ge));

inline fn _zequ(sp: [*]isize) [*]isize {
    sp[0] = if (sp[0] == 0) -1 else 0;
    return sp;
}
const zequ = defword(&ge, Flag.ZERO, "0=", wrap(_zequ));

inline fn _znequ(sp: [*]isize) [*]isize {
    sp[0] = if (sp[0] != 0) -1 else 0;
    return sp;
}
const znequ = defword(&zequ, Flag.ZERO, "0<>", wrap(_znequ));

inline fn _zlt(sp: [*]isize) [*]isize {
    sp[0] = if (sp[0] < 0) -1 else 0;
    return sp;
}
const zlt = defword(&znequ, Flag.ZERO, "0<", wrap(_zlt));

inline fn _zgt(sp: [*]isize) [*]isize {
    sp[0] = if (sp[0] > 0) -1 else 0;
    return sp;
}
const zgt = defword(&zlt, Flag.ZERO, "0>", wrap(_zgt));

inline fn _zle(sp: [*]isize) [*]isize {
    sp[0] = if (sp[0] <= 0) -1 else 0;
    return sp;
}
const zle = defword(&zgt, Flag.ZERO, "0<=", wrap(_zle));

inline fn _zge(sp: [*]isize) [*]isize {
    sp[0] = if (sp[0] >= 0) -1 else 0;
    return sp;
}
const zge = defword(&zle, Flag.ZERO, "0>=", wrap(_zge));

inline fn _and(sp: [*]isize) [*]isize {
    sp[1] &= sp[0];
    return sp[1..];
}
const and_ = defword(&zge, Flag.ZERO, "AND", wrap(_and));

inline fn _or(sp: [*]isize) [*]isize {
    sp[1] |= sp[0];
    return sp[1..];
}
const or_ = defword(&and_, Flag.ZERO, "OR", wrap(_or));

inline fn _xor(sp: [*]isize) [*]isize {
    sp[1] ^= sp[0];
    return sp[1..];
}
const xor = defword(&or_, Flag.ZERO, "XOR", wrap(_xor));

inline fn _invert(sp: [*]isize) [*]isize {
    sp[0] = ~sp[0];
    return sp;
}
const invert = defword(&xor, Flag.ZERO, "INVERT", wrap(_invert));

fn _exit(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    _ = ip;
    self.next(sp, rsp[1..], rsp[0], target);
}
const exit = defword(&invert, Flag.ZERO, "EXIT", &.{.{ .code = _exit }});

fn _lit(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const s = sp - 1;
    s[0] = ip[0].literal;
    self.next(s, rsp, ip[1..], target);
}
const lit = defword(&exit, Flag.ZERO, "LIT", &.{.{ .code = _lit }});

inline fn _store(sp: [*]isize) [*]isize {
    const p: *isize = @ptrFromInt(@abs(sp[0]));
    p.* = sp[1];
    return sp[2..];
}
const store = defword(&lit, Flag.ZERO, "!", wrap(_store));

inline fn _fetch(sp: [*]isize) [*]isize {
    const p: *isize = @ptrFromInt(@abs(sp[0]));
    sp[0] = p.*;
    return sp;
}
const fetch = defword(&store, Flag.ZERO, "@", wrap(_fetch));

inline fn _addstore(sp: [*]isize) [*]isize {
    const p: *[*]u8 = @ptrFromInt(@abs(sp[0]));
    p.* += @abs(sp[1]);
    return sp[2..];
}
const addstore = defword(&fetch, Flag.ZERO, "+!", wrap(_addstore));

inline fn _substore(sp: [*]isize) [*]isize {
    const p: *[*]u8 = @ptrFromInt(@abs(sp[0]));
    p.* -= @abs(sp[1]);
    return sp[2..];
}
const substore = defword(&addstore, Flag.ZERO, "-!", wrap(_substore));

inline fn _storebyte(sp: [*]isize) [*]isize {
    const p: [*]u8 = @ptrFromInt(@abs(sp[0]));
    const v: u8 = @truncate(@abs(sp[1]));
    p[0] = v;
    return sp[2..];
}
const storebyte = defword(&substore, Flag.ZERO, "C!", wrap(_storebyte));

inline fn _fetchbyte(sp: [*]isize) [*]isize {
    const p: [*]u8 = @ptrFromInt(@abs(sp[0]));
    sp[0] = p[0];
    return sp;
}
const fetchbyte = defword(&storebyte, Flag.ZERO, "C@", wrap(_fetchbyte));

inline fn _ccopy(sp: [*]isize) [*]isize {
    const p: [*]u8 = @ptrFromInt(@abs(sp[0]));
    const q: [*]u8 = @ptrFromInt(@abs(sp[1]));
    q[0] = p[0];
    return sp[2..];
}
const ccopy = defword(&fetchbyte, Flag.ZERO, "C@C!", wrap(_ccopy));

inline fn _cmove(sp: [*]isize) [*]isize {
    const n = @abs(sp[0]);
    @memcpy(dest: {
        const p: [*]u8 = @ptrFromInt(@abs(sp[1]));
        break :dest p[0..n];
    }, source: {
        const q: [*]u8 = @ptrFromInt(@abs(sp[2]));
        break :source q[0..n];
    });
    sp[2] = sp[1];
    return sp[2..];
}
const cmove = defword(&ccopy, Flag.ZERO, "CMOVE", wrap(_cmove));
const state = defword(&cmove, Flag.ZERO, "STATE", attr("state"));

fn _here(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const s = sp - 1;
    self.memory.ensureUnusedCapacity(@sizeOf(Instr)) catch @panic("_here cannot ensureUnusedCapacity");
    s[0] = @intCast(@intFromPtr(&self.here));
    self.next(s, rsp, ip, target);
}
const here = defword(&state, Flag.ZERO, "HERE", &.{.{ .code = _here }});
const latest = defword(&here, Flag.ZERO, "LATEST", attr("latest"));
const sz = defword(&latest, Flag.ZERO, "S0", attr("s0"));
const base = defword(&sz, Flag.ZERO, "BASE", attr("base"));

inline fn _argc(sp: [*]isize) [*]isize {
    const s = sp - 1;
    const u = @intFromPtr(os.argv.ptr - 1);
    s[0] = @intCast(u);
    return s;
}
const argc = defword(&base, Flag.ZERO, "(ARGC)", wrap(_argc));
const version = defword(&if (arch.isWasm()) base else argc, Flag.ZERO, "VERSION", value(47));

fn _rz(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const s = sp - 1;
    const u = @intFromPtr(self.r0);
    s[0] = @intCast(u);
    self.next(s, rsp, ip, target);
}
const rz = defword(&version, Flag.ZERO, "R0", &.{.{ .code = _rz }});

fn docol_(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const r = rsp - 1;
    r[0] = ip;
    self.next(sp, r, target[1..], target);
}

inline fn _docol(sp: [*]isize) [*]isize {
    const s = sp - 1;
    s[0] = @intCast(@intFromPtr(&docol_));
    return s;
}
const docol = defword(&rz, Flag.ZERO, "DOCOL", wrap(_docol));

fn dodoes_(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const r = rsp - 1;
    const s = sp - 1;
    r[0] = ip;
    s[0] = @intCast(@intFromPtr(&target[2]));
    self.next(s, r, target[1].word, target);
}

inline fn _dodoes(sp: [*]isize) [*]isize {
    const s = sp - 1;
    s[0] = @intCast(@intFromPtr(&dodoes_));
    return s;
}
const dodoes = defword(&docol, Flag.ZERO, "DODOES", wrap(_dodoes));
const f_immed = defword(&dodoes, Flag.ZERO, "F_IMMED", value(@intFromEnum(Flag.IMMED)));
const f_hidden = defword(&f_immed, Flag.ZERO, "F_HIDDEN", value(@intFromEnum(Flag.HIDDEN)));
const f_lenmask = defword(&f_hidden, Flag.ZERO, "F_LENMASK", value(F_LENMASK));
const sys_exit = defword(&f_lenmask, Flag.ZERO, "SYS_EXIT", value(@intFromEnum(syscalls.X64.exit)));
const sys_open = defword(&sys_exit, Flag.ZERO, "SYS_OPEN", value(@intFromEnum(syscalls.X64.open)));
const sys_close = defword(&sys_open, Flag.ZERO, "SYS_CLOSE", value(@intFromEnum(syscalls.X64.close)));
const sys_read = defword(&sys_close, Flag.ZERO, "SYS_READ", value(@intFromEnum(syscalls.X64.read)));
const sys_write = defword(&sys_read, Flag.ZERO, "SYS_WRITE", value(@intFromEnum(syscalls.X64.write)));
const sys_creat = defword(&sys_write, Flag.ZERO, "SYS_CREAT", value(@intFromEnum(syscalls.X64.creat)));
const sys_brk = defword(&sys_creat, Flag.ZERO, "SYS_BRK", value(@intFromEnum(syscalls.X64.brk)));
const o_rdonly = defword(&sys_brk, Flag.ZERO, "O_RDONLY", value(O_RDONLY));
const o_wronly = defword(&o_rdonly, Flag.ZERO, "O_WRONLY", value(O_WRONLY));
const o_rdwr = defword(&o_wronly, Flag.ZERO, "O_RDWR", value(O_RDWR));
const o_creat = defword(&o_rdwr, Flag.ZERO, "O_CREAT", value(O_CREAT));
const o_excl = defword(&o_creat, Flag.ZERO, "O_EXCL", value(O_EXCL));
const o_trunc = defword(&o_excl, Flag.ZERO, "O_TRUNC", value(O_TRUNC));
const o_append = defword(&o_trunc, Flag.ZERO, "O_APPEND", value(O_APPEND));
const o_nonblock = defword(&o_append, Flag.ZERO, "O_NONBLOCK", value(O_NONBLOCK));

fn _tor(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const r = rsp - 1;
    const t: [*]Instr = @ptrFromInt(@abs(sp[0]));
    r[0] = t;
    self.next(sp[1..], r, ip, target);
}
const tor = defword(&o_nonblock, Flag.ZERO, ">R", &.{.{ .code = _tor }});

fn _fromr(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const s = sp - 1;
    s[0] = @intCast(@intFromPtr(rsp[0]));
    self.next(s, rsp[1..], ip, target);
}
const fromr = defword(&tor, Flag.ZERO, "R>", &.{.{ .code = _fromr }});

fn _rspfetch(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const s = sp - 1;
    s[0] = @intCast(@intFromPtr(rsp));
    self.next(s, rsp, ip, target);
}
const rspfetch = defword(&fromr, Flag.ZERO, "RSP@", &.{.{ .code = _rspfetch }});

fn _rspstore(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    _ = rsp;
    const s = @abs(sp[0]);
    const t: [*][*]const Instr = @ptrFromInt(s);
    self.next(sp[1..], t, ip, target);
}
const rspstore = defword(&rspfetch, Flag.ZERO, "RSP!", &.{.{ .code = _rspstore }});

fn _rdrop(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    self.next(sp, rsp[1..], ip, target);
}
const rdrop = defword(&rspstore, Flag.ZERO, "RDROP", &.{.{ .code = _rdrop }});

inline fn _dspfetch(sp: [*]isize) [*]isize {
    const s = sp - 1;
    s[0] = @intCast(@intFromPtr(sp));
    return s;
}
const dspfetch = defword(&rdrop, Flag.ZERO, "DSP@", wrap(_dspfetch));

inline fn _dspstore(sp: [*]isize) [*]isize {
    const u = @abs(sp[0]);
    const p: [*]isize = @ptrFromInt(u);
    return p;
}
const dspstore = defword(&dspfetch, Flag.ZERO, "DSP!", wrap(_dspstore));

inline fn _key(sp: [*]isize) [*]isize {
    const s = sp - 1;
    s[0] = @intCast(key());
    return s;
}
const key_ = defword(&dspstore, Flag.ZERO, "KEY", wrap(_key));

inline fn _emit(sp: [*]isize) [*]isize {
    const c: u8 = @truncate(@abs(sp[0]));
    stdout.print("{c}", .{c}) catch {};
    stdout.flush() catch {};
    return sp[1..];
}
const emit = defword(&key_, Flag.ZERO, "EMIT", wrap(_emit));

fn _word(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const s = sp - 2;
    const u = @intFromPtr(&self.buffer);
    s[1] = @intCast(u);
    s[0] = @intCast(self.word());
    self.next(s, rsp, ip, target);
}
const word_ = defword(&emit, Flag.ZERO, "WORD", &.{.{ .code = _word }});

fn _number(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    if (fmt.parseInt(isize, buf: {
        const s: [*]u8 = @ptrFromInt(@abs(sp[1]));
        break :buf s[0..@abs(sp[0])];
    }, @truncate(@abs(self.base)))) |num| {
        sp[1] = num;
        sp[0] = 0;
    } else |_| {}
    self.next(sp, rsp, ip, target);
}
const number = defword(&word_, Flag.ZERO, "NUMBER", &.{.{ .code = _number }});

fn _find(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const s: [*]u8 = @ptrFromInt(@abs(sp[1]));
    const v = self.find(s[0..@abs(sp[0])]);

    sp[1] = @intCast(@intFromPtr(v));
    self.next(sp[1..], rsp, ip, target);
}
const find_ = defword(&number, Flag.ZERO, "FIND", &.{.{ .code = _find }});

inline fn _tcfa(sp: [*]isize) [*]isize {
    const w: [*]const Instr = @ptrFromInt(@abs(sp[0]));
    sp[0] = @intCast(@intFromPtr(codeFieldAddress(w)));
    return sp;
}
const tcfa = defword(&find_, Flag.ZERO, ">CFA", wrap(_tcfa));
const tdfa = defword(
    &tcfa,
    Flag.ZERO,
    ">DFA",
    words(&.{ &tcfa, &incrp, &exit, &exit }),
);

fn _create(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const c = @abs(sp[0]);
    const s: [*]u8 = @ptrFromInt(@abs(sp[1]));
    const code = self.memory.addManyAsSlice(@sizeOf(Word)) catch @panic("_create cannot addManyAsSlice");
    var new: *Word = @ptrCast(@alignCast(code.ptr));
    new.link = self.latest;
    new.flag = @truncate(c);
    @memcpy(new.name[0..c], s[0..c]);
    @memset(new.name[c..F_LENMASK], 0);
    self.latest = new;
    self.here = self.memory.items.ptr + self.memory.items.len;
    self.next(sp[2..], rsp, ip, target);
}
const create = defword(&tdfa, Flag.ZERO, "CREATE", &.{.{ .code = _create }});

fn _comma(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const s: isize = sp[0];
    const instr: Instr = if (s < 0x1000)
        .{ .literal = s }
    else if (s == @intFromPtr(&docol_))
        .{ .code = docol_ }
    else
        .{ .word = blk: {
            const p: [*]const Instr = @ptrFromInt(@abs(s));
            break :blk p;
        } };
    self.append(instr);
    self.next(sp[1..], rsp, ip, target);
}
const comma = defword(&create, Flag.ZERO, ",", &.{.{ .code = _comma }});

fn _lbrac(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    self.state = 0;
    self.next(sp, rsp, ip, target);
}
const lbrac = defword(
    &comma,
    Flag.IMMED,
    "[",
    &.{.{ .code = _lbrac }},
);

fn _rbrac(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    self.state = 1;
    self.next(sp, rsp, ip, target);
}
const rbrac = defword(&lbrac, Flag.ZERO, "]", &.{.{ .code = _rbrac }});

fn _immediate(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    self.latest.flag ^= @intFromEnum(Flag.IMMED);
    self.next(sp, rsp, ip, target);
}
const immediate = defword(
    &rbrac,
    Flag.IMMED,
    "IMMEDIATE",
    &.{.{ .code = _immediate }},
);

inline fn _hidden(sp: [*]isize) [*]isize {
    const w: *Word = @ptrFromInt(@abs(sp[0]));
    w.flag ^= @intFromEnum(Flag.HIDDEN);
    return sp[1..];
}
const hidden = defword(&immediate, Flag.ZERO, "HIDDEN", wrap(_hidden));
const hide = defword(
    &hidden,
    Flag.ZERO,
    "HIDE",
    words(&.{ &word_, &find_, &hidden, &exit }),
);
const colon = defword(
    &hide,
    Flag.ZERO,
    ":",
    words(&.{ &word_, &create, &docol, &comma, &latest, &fetch, &hidden, &rbrac, &exit, &exit }),
);

fn _tick(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const s = sp - 1;
    const u = @intFromPtr(ip[0].word);
    s[0] = @intCast(u);
    self.next(s, rsp, ip[1..], target);
}
const tick = defword(&colon, Flag.ZERO, "'", &.{.{ .code = _tick }});
const semicolon = defword(
    &tick,
    Flag.IMMED,
    ";",
    words(&.{ &tick, &exit, &comma, &latest, &fetch, &hidden, &lbrac, &exit }),
);

fn _branch(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const n = @divTrunc(ip[0].literal, @sizeOf(Instr));
    const a = @abs(n);
    const p = if (n < 0) ip - a else ip + a;
    self.next(sp, rsp, p, target);
}
const branch = defword(&semicolon, Flag.ZERO, "BRANCH", &.{.{ .code = _branch }});

fn _zbranch(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    if (sp[0] == 0)
        return @call(.always_tail, _branch, .{ self, sp[1..], rsp, ip, target });
    self.next(sp[1..], rsp, ip[1..], target);
}
const zbranch = defword(&branch, Flag.ZERO, "0BRANCH", &.{.{ .code = _zbranch }});

fn _litstring(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const c = @abs(ip[0].literal);
    const s = sp - 2;
    s[1] = @intCast(@intFromPtr(&ip[1]));
    s[0] = @intCast(c);
    const n = @abs(1 + @divTrunc(c + @sizeOf(Instr), @sizeOf(Instr)));
    self.next(s, rsp, ip[n..], target);
}
const litstring = defword(&zbranch, Flag.ZERO, "LITSTRING", &.{.{ .code = _litstring }});

inline fn _tell(sp: [*]isize) [*]isize {
    const p: [*]u8 = @ptrFromInt(@abs(sp[1]));
    _ = stdout.write(p[0..@abs(sp[0])]) catch -1;
    stdout.flush() catch {};
    return sp[2..];
}
const tell = defword(&litstring, Flag.ZERO, "TELL", wrap(_tell));

fn _interpret(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const c = self.word();
    var s = sp;

    if (self.find(self.buffer[0..c])) |new| {
        const tgt = codeFieldAddress(@ptrCast(new));
        if ((new.flag & @intFromEnum(Flag.IMMED)) != 0 or self.state == 0) {
            return @call(.always_tail, tgt[0].code, .{ self, sp, rsp, ip, tgt });
        } else {
            self.append(.{ .word = tgt });
        }
    } else if (fmt.parseInt(isize, self.buffer[0..c], @truncate(@abs(self.base)))) |a| {
        if (self.state == 1) {
            self.append(.{ .word = &.{.{ .code = _lit }} });
            self.append(.{ .literal = a });
        } else {
            s = sp - 1;
            s[0] = a;
        }
    } else |_| {
        std.debug.print("PARSE ERROR: {s}\n", .{self.buffer[0..c]});
        std.process.exit(0);
    }
    self.next(s, rsp, ip, target);
}
const interpret = defword(&tell, Flag.ZERO, "INTERPRET", &.{.{ .code = _interpret }});
const _quit: [7]Instr = .{
    .{ .code = docol_ },
    .{ .word = codeFieldAddress(&rz) },
    .{ .word = codeFieldAddress(&rspstore) },
    .{ .word = codeFieldAddress(&interpret) },
    .{ .word = codeFieldAddress(&branch) },
    .{ .literal = -2 * @sizeOf(Instr) },
    .{ .word = codeFieldAddress(&exit) },
};
const quit = defword(&interpret, Flag.ZERO, "QUIT", &_quit);

fn _char(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const s = sp - 1;
    _ = self.word();
    s[0] = self.buffer[0];
    self.next(s, rsp, ip, target);
}
const char = defword(&quit, Flag.ZERO, "CHAR", &.{.{ .code = _char }});

fn _execute(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    _ = target;
    const target_: *Instr = @ptrFromInt(@abs(sp[0]));
    return @call(.always_tail, target_.code, .{ self, sp[1..], rsp, ip, target_[0..0] });
}
const execute = defword(&char, Flag.ZERO, "EXECUTE", &.{.{ .code = _execute }});

inline fn _syscall3(sp: [*]isize) [*]isize {
    const number_: syscalls.X64 = @enumFromInt(sp[0]);

    switch (number_) {
        .open => {
            const p: usize = @intCast(sp[1]);
            const file_path: [*:0]u8 = @ptrFromInt(p);
            const flags: u32 = @intCast(sp[2]);
            const perm: fs.File.Mode = @intCast(sp[3]);
            sp[3] = if (fs.cwd().createFileZ(file_path, .{
                .read = (flags & (O_RDONLY | O_RDWR)) != 0,
                .truncate = (flags & O_TRUNC) != 0,
                .exclusive = (flags & O_EXCL) != 0,
                .lock_nonblocking = (flags & O_NONBLOCK) != 0,
                .mode = perm,
            })) |file| @intCast(file.handle) else |_| -1;
        },
        .read => {
            const file: fs.File = .{ .handle = @intCast(sp[1]) };
            const p: usize = @intCast(sp[2]);
            const buf: [*]u8 = @ptrFromInt(p);
            const n: usize = @intCast(sp[3]);
            sp[3] = if (file.read(buf[0..n])) |m| @intCast(m) else |_| -1;
        },
        .write => {
            const file: fs.File = .{ .handle = @intCast(sp[1]) };
            const p: usize = @intCast(sp[2]);
            const buf: [*]u8 = @ptrFromInt(p);
            const n: usize = @intCast(sp[3]);
            sp[3] = if (file.write(buf[0..n])) |m| @intCast(m) else |_| -1;
        },
        else => {},
    }
    return sp[3..];
}
const syscall3 = defword(&execute, Flag.ZERO, "SYSCALL3", wrap(_syscall3));

inline fn _syscall2(sp: [*]isize) [*]isize {
    const number_: syscalls.X64 = @enumFromInt(sp[0]);

    switch (number_) {
        .open => {
            const p: usize = @intCast(sp[1]);
            const file_path: [*:0]u8 = @ptrFromInt(p);
            const flags: u32 = @intCast(sp[2]);
            sp[2] = if (fs.cwd().openFileZ(file_path, .{
                .mode = @enumFromInt(flags & (O_RDONLY | O_WRONLY | O_RDWR)),
                .lock_nonblocking = (flags & O_NONBLOCK) != 0,
            })) |file| @intCast(file.handle) else |_| -1;
        },
        else => {},
    }
    return sp[2..];
}
const syscall2 = defword(&syscall3, Flag.ZERO, "SYSCALL2", wrap(_syscall2));

fn _syscall1(self: *Interp, sp: [*]isize, rsp: [*][*]const Instr, ip: [*]const Instr, target: [*]const Instr) callconv(conv) void {
    const number_: syscalls.X64 = @enumFromInt(sp[0]);

    switch (number_) {
        .exit => {
            const status: u8 = @truncate(@abs(sp[1]));
            std.process.exit(status);
        },
        .close => {
            const file: fs.File = .{ .handle = @intCast(sp[1]) };
            file.close();
        },
        .brk => {
            const m = @abs(sp[1]);
            const p: *std.heap.FixedBufferAllocator = @ptrCast(@alignCast(self.memory.allocator.ptr));
            if (m > 0) {
                const n = if (arch.isWasm())
                    @wasmMemoryGrow(0, @divTrunc(m, 0x10000))
                else
                    os.linux.syscall1(.brk, m);
                if (n < m)
                    @panic("brk syscall failed");
                p.buffer.len = m - @intFromPtr(p.buffer.ptr);
            }
            sp[1] = @intCast(@intFromPtr(p.buffer.ptr + p.buffer.len));
        },
        else => {},
    }
    self.next(sp[1..], rsp, ip, target);
}
const syscall1 = defword(&syscall2, Flag.ZERO, "SYSCALL1", &.{.{ .code = _syscall1 }});

inline fn _syscall0(sp: [*]isize) [*]isize {
    const number_: syscalls.X64 = @enumFromInt(sp[0]);
    switch (number_) {
        .getppid => {
            sp[0] = if (arch.isWasm())
                @panic("getppid not supported")
            else
                @intCast(os.linux.getppid());
        },
        else => {},
    }
    return sp;
}
var syscall0 = defword(&syscall1, Flag.ZERO, "SYSCALL0", wrap(_syscall0));

var memory: [0x800000]u8 linksection(".bss") = undefined;

pub fn main() callconv(conv) void {
    const N = 0x20;
    var stack: [N]isize = undefined;
    const sp = stack[N..];
    var return_stack: [N][*]const Instr = undefined;
    const rsp = return_stack[N..];
    var fba: std.heap.FixedBufferAllocator = .init(&memory);
    var m: std.array_list.AlignedManaged(u8, mem.Alignment.of(Instr)) = .init(fba.allocator());
    defer m.deinit();
    var env: Interp = .init(sp, rsp, &m);
    const target = &_quit;
    const cold_start: [1]Instr = .{.{ .word = target }};
    const ip: [*]const Instr = &cold_start;

    target[0].code(&env, sp, rsp, ip, target);
}

fn mainWithoutEnv(c_argc: c_int, c_argv: [*][*:0]c_char) callconv(.c) c_int {
    _ = @as([*][*:0]u8, @ptrCast(c_argv))[0..@as(usize, @intCast(c_argc))];
    @call(.always_inline, main, .{});
    return 0;
}

comptime {
    @export(&mainWithoutEnv, .{ .name = "__main_argc_argv" });
}
