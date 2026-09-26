"""Thompson's on-the-fly regular expression compiler, emitting x86-64 or arm64.

A port of ``x86.c`` and ``arm.c``.  ``sieve`` and ``postfix`` are the first two
stages from https://bur.gy/2026/09/24/what-makes-an-expression-regular.html, the
third stage emits machine code for the host, which ``ctypes`` then calls.

The current list lives on the machine stack as return addresses, the next list in
the frame of ``search``.  Unlike the C originals, ``NNODE`` files each state at most
once, so the next list never needs more than one slot per character node, and
``strip`` replaces Thompson's lambda revision: no star body ever matches ε.

>>> Pattern("a(b|c)*d").search("xxabccbcccdyy")
11
>>> Pattern("x(a*b*)*c").search("xbc")
3
>>> Pattern("(a|b)*a").search("bbbab")
4
>>> Pattern("a(b|c)*d").search("abccbcccde")
9
>>> Pattern("x").search("abc")
-1
>>> Pattern("a·b").search("xa·b")
4
"""

import ctypes
import mmap
import platform
import struct
import sys
import weakref
from collections.abc import Iterable

SYMBOLS = "()|·*"  # an operator token is its index here, so precedence is numeric order
ALTERN, CONCAT, KLEENE = map(SYMBOLS.index, "|·*")


def sieve(src: str):
    concat, chars = False, iter(src)
    for c in chars:
        if concat and c not in ")|*":
            yield SYMBOLS.index("·")
        concat = c not in "(|"
        yield (
            next(chars, "\\") if c == "\\" else SYMBOLS.index(c) if c in "()|*" else c
        )
    yield SYMBOLS.index(")")


def postfix(tokens: Iterable[str | int]):
    stack = [SYMBOLS.index("(")]
    for t in tokens:
        if isinstance(t, str):
            yield t
            continue
        while stack[0] < t <= stack[-1]:
            yield stack.pop()
        if SYMBOLS[t] == ")":
            stack.pop()
        else:
            stack.append(t)


def strip(tokens: Iterable[str | int]) -> list[str | int]:
    """Rewrite every e* as e'*, where e' == e minus ε, so no star loops on ε."""
    terms = [([], [], True)]  # (postfix of e, postfix of e', e matches ε)
    for t in tokens:
        if isinstance(t, str):
            terms.append(([t], [t], False))
        elif t == KLEENE:
            s = terms.pop()[1]
            terms.append((s + [t], s, True))
        else:
            (p1, s1, n1), (p2, s2, n2) = terms.pop(-2), terms.pop()
            n = n1 and n2 if t == CONCAT else n1 or n2
            p = p1 + p2 + [t]
            terms.append((p, s1 + s2 + [ALTERN] if n else p, n))
    return terms[-1][0]


class X86_64(bytearray):
    """Code addresses are byte offsets; every jump or call to patch is 5 bytes."""

    NNODE = 50
    # fmt: off
    FOOTER = b"".join([
        b"\x48\x8d\x46\xff",          #         leaq   -1(%rsi), %rax
        b"\xc9",                      #         leave
        b"\xc3",                      #         ret
    ])
    # fmt: on

    def __init__(self, size: int):
        disp = struct.pack("<i", -size)
        # fmt: off
        super().__init__(b"".join([
            b"\xc8" + struct.pack("<H", size) + b"\x00",  # enter  $size, $0
            b"\x48\x89\xfe",          #         movq   %rdi, %rsi
            b"\x31\xc0",              #         xorl   %eax, %eax
            b"\xff\xc0",              #         incl   %eax
            b"\x31\xc9",              #         xorl   %ecx, %ecx
            b"\xe8\x00\x00\x00\x00",  #         call   _next
                                      # _next:
            b"\x48\x83\x2c\x24\x05",  #         subq   $5, (%rsp)
            b"\xa8\xff",              #         testb  $0xff, %al
            b"\x75\x02",              #         jnz    _L1
            b"\xc9",                  #         leave
            b"\xc3",                  #         ret
                                      # _L1:
            b"\xe3\x0c",              #         jrcxz  _L2
            b"\x48\xff\xc9",          #         decq   %rcx
            b"\xff\xb4\xcd" + disp,   #         pushq  -size(%rbp,%rcx,8)
            b"\xeb\xf2",              #         jmp    _L1
                                      # _L2:
            b"\xac",                  #         lodsb
            b"\xe8\x24\x00\x00\x00",  #         call   _code
                                      # _fail:
            b"\xc3",                  #         ret
                                      # _nnode:
            b"\x5a",                  #         popq   %rdx
            b"\x48\x8d\xbd" + disp,   #         leaq   -size(%rbp), %rdi
            b"\x51",                  #         pushq  %rcx
            b"\x50",                  #         pushq  %rax
            b"\x48\x89\xd0",          #         movq   %rdx, %rax
            b"\x48\x85\xc0",          #         testq  %rax, %rax
            b"\xf2\x48\xaf",          #         repne scasq
            b"\x58",                  #         popq   %rax
            b"\x59",                  #         popq   %rcx
            b"\x74\xe8",              #         je     _fail
            b"\x48\x89\x94\xcd" + disp,  #      movq   %rdx, -size(%rbp,%rcx,8)
            b"\x48\xff\xc1",          #         incq   %rcx
            b"\xc3",                  #         ret
                                      # _code:
        ]))
        # fmt: on

    def jmp(self, to: int) -> None:
        self.extend(struct.pack("<Bi", 0xE9, to - len(self) - 5))

    def call(self, to: int) -> None:
        self.extend(struct.pack("<Bi", 0xE8, to - len(self) - 5))

    def link(self, at: int, to: int) -> None:
        struct.pack_into("<i", self, at + 1, to - (at + 5))

    def target(self, at: int) -> int:
        return at + 5 + struct.unpack_from("<i", self, at + 1)[0]

    def char(self, c: int) -> None:
        self.jmp(len(self) + 5)
        self.extend(b"\x3c%c\x74\x01\xc3" % c)  # cmp $c, %al; je +1; ret
        self.call(self.NNODE)

    def kleene(self, s: int) -> None:
        entry = self.target(s)
        self.call(entry)
        self.extend(b"\xeb\x05")  # jmp over the call below
        self.link(s, len(self))
        self.call(entry)

    def altern(self, s1: int, s2: int) -> None:
        entry1, entry2 = self.target(s1), self.target(s2)
        self.extend(b"\xeb\x0a")  # jmp over the call and jmp below
        self.link(s1, len(self))
        self.call(entry2)
        self.jmp(entry1)
        self.link(s2, len(self))

    def finish(self) -> bytes:
        return bytes(self + self.FOOTER)


class Arm64(list):
    """Code addresses are word indices; every jump to patch is a b or bl."""

    FAIL, NNODE = 22, 24
    B, BL, BNE = 0x14000000, 0x94000000, 0x54000001
    CMP = 0x7100005F  # cmp w2, #0
    ADR = 0x10000010  # adr x16, #0
    PUSH = 0xF81F0FF0  # str x16, [sp, #-16]!
    # fmt: off
    FOOTER = [
        0xD1000420,  #         sub    x0, x1, #1
        0x910003BF,  #         mov    sp, x29
        0xA8C17BFD,  #         ldp    x29, x30, [sp], #16
        0xD65F03C0,  #         ret
    ]
    # fmt: on

    def __init__(self, size: int):
        # fmt: off
        super().__init__([
            0xA9BF7BFD,  #         stp    x29, x30, [sp, #-16]!
            0x910003FD,  #         mov    x29, sp
            0xD2800010 | size << 5,  # mov x16, #size
            0xCB3063FF,  #         sub    sp, sp, x16
            0xCB1003A4,  #         sub    x4, x29, x16
            0xAA0003E1,  #         mov    x1, x0
            0x52800022,  #         mov    w2, #1
            0xD2800003,  #         mov    x3, #0
            0x10000030,  #         adr    x16, _next
                         # _next:
            0xF81F0FF0,  #         str    x16, [sp, #-16]!
            0x350000A2,  #         cbnz   w2, _L1
            0xD2800000,  #         mov    x0, #0
            0x910003BF,  #         mov    sp, x29
            0xA8C17BFD,  #         ldp    x29, x30, [sp], #16
            0xD65F03C0,  #         ret
                         # _L1:
            0xB40000A3,  #         cbz    x3, _L2
            0xD1000463,  #         sub    x3, x3, #1
            0xF8637890,  #         ldr    x16, [x4, x3, lsl #3]
            0xF81F0FF0,  #         str    x16, [sp, #-16]!
            0x17FFFFFC,  #         b      _L1
                         # _L2:
            0x38401422,  #         ldrb   w2, [x1], #1
            0x1400000E,  #         b      _code
                         # _fail:
            0xF84107F0,  #         ldr    x16, [sp], #16
            0xD61F0200,  #         br     x16
                         # _nnode:
            0xD2800005,  #         mov    x5, #0
                         # _scan:
            0xEB0300BF,  #         cmp    x5, x3
            0x540000C0,  #         b.eq   _add
            0xF8657886,  #         ldr    x6, [x4, x5, lsl #3]
            0x910004A5,  #         add    x5, x5, #1
            0xEB1E00DF,  #         cmp    x6, x30
            0x54FFFF61,  #         b.ne   _scan
            0x17FFFFF7,  #         b      _fail
                         # _add:
            0xF823789E,  #         str    x30, [x4, x3, lsl #3]
            0x91000463,  #         add    x3, x3, #1
            0x17FFFFF4,  #         b      _fail
                         # _code:
        ])
        # fmt: on

    def jmp(self, to: int, op: int = B) -> None:
        self.append(op | (to - len(self)) & 0x3FFFFFF)

    def call(self, to: int) -> None:
        self.extend([self.ADR | 3 << 5, self.PUSH])  # adr x16, .+12; push x16
        self.jmp(to)

    def link(self, at: int, to: int) -> None:
        self[at] = self[at] & 0xFC000000 | (to - at) & 0x3FFFFFF

    def target(self, at: int) -> int:
        return at + ((self[at] & 0x3FFFFFF) ^ 0x2000000) - 0x2000000

    def char(self, c: int) -> None:
        self.jmp(len(self) + 1)
        self.append(self.CMP | c << 10)
        self.append(self.BNE | ((self.FAIL - len(self)) & 0x7FFFF) << 5)
        self.jmp(self.NNODE, self.BL)

    def kleene(self, s: int) -> None:
        entry = self.target(s)
        self.call(entry)
        self.jmp(len(self) + 4)
        self.link(s, len(self))
        self.call(entry)

    def altern(self, s1: int, s2: int) -> None:
        entry1, entry2 = self.target(s1), self.target(s2)
        self.jmp(len(self) + 5)
        self.link(s1, len(self))
        self.call(entry2)
        self.jmp(entry1)
        self.link(s2, len(self))

    def finish(self) -> bytes:
        return struct.pack(f"<{len(self) + 4}I", *self, *self.FOOTER)


ISA = {"x86_64": X86_64, "amd64": X86_64, "arm64": Arm64, "aarch64": Arm64}


def assemble(regexp: str, isa: type[X86_64 | Arm64] | None = None) -> bytes:
    program = strip(postfix(sieve(regexp)))
    size = -(-8 * sum(isinstance(t, str) for t in program) // 16) * 16
    if size > 0xFFFF:
        raise ValueError("too many characters")
    asm = (isa or ISA[platform.machine().lower()])(size)
    stack: list[int] = []  # the leading jmp of each fragment
    for t in program:
        if isinstance(t, str):
            stack.append(len(asm))
            asm.char(ord(t))
        elif t == CONCAT:
            stack.pop()
        elif t == KLEENE:
            asm.kleene(stack[-1])
        elif t == ALTERN:
            asm.altern(*stack[-2:])
            stack.pop()
    return asm.finish()


libc = ctypes.CDLL(None, use_errno=True)
libc.mmap.restype = ctypes.c_void_p
libc.mmap.argtypes = [
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_long,
]
libc.mprotect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
MAP_FAILED = ctypes.c_void_p(-1).value


class Pattern:
    def __init__(self, regexp: str):
        code = assemble(regexp)
        size = -(-len(code) // mmap.PAGESIZE) * mmap.PAGESIZE
        addr = libc.mmap(
            None,
            size,
            mmap.PROT_READ | mmap.PROT_WRITE,
            mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
            -1,
            0,
        )
        if addr in (None, MAP_FAILED):
            raise OSError(ctypes.get_errno(), "mmap failed")
        weakref.finalize(self, libc.munmap, addr, size)
        ctypes.memmove(addr, code, len(code))
        # Linux flushes the instruction cache itself when a page turns executable
        if sys.platform == "darwin" and platform.machine() == "arm64":
            libc.sys_icache_invalidate(
                ctypes.c_void_p(addr), ctypes.c_size_t(len(code))
            )
        if libc.mprotect(addr, size, mmap.PROT_READ | mmap.PROT_EXEC):
            raise OSError(ctypes.get_errno(), "mprotect failed")
        self._search = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p)(addr)

    def search(self, s: str) -> int:
        """End of the shortest match at the leftmost position, or -1."""
        buf = ctypes.create_string_buffer(s.encode("latin-1"))
        end = self._search(buf)
        return -1 if end is None else end - ctypes.addressof(buf)


if __name__ == "__main__":
    for r, s in [
        ("abcdefg", "abcdefg"),
        ("(a|b)*a", "ababababab"),
        ("(a|b)*a", "aaaaaaaaba"),
        ("(a|b)*a", "aaaaaabac"),
        ("a(b|c)*d", "abccbcccd"),
        ("a(b|c)*d", "abccbcccde"),
        ("(a|a)*", "aaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
        ("a(b|c)*d", "abccccccccd"),
        ("a*", "aaab"),
        ("a(b|c)*d", "abcd"),
        ("a**", "b"),
        ("(a*b*)*c", "abbac"),
        ("(a*|b*)*c", "abac"),
        ("b*(c|d)", "c"),
        ("(a|a)*b", "aaaaaaaaaaaaaaaab"),
    ]:
        n = Pattern(r).search(s)
        print(f"search {r} {s}")
        print(f"match found after {n} bytes" if n >= 0 else "match not found")
