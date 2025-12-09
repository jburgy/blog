# ruff: noqa: E501

from itertools import batched

# 0x0000 - 0x07FF: data stack
# 0x0800 - 0x0FFF: return stack
# 0x1000 - 0x13FF: temporary input buffer
# 0x1400 - 0x1400: STATE
# 0x1401 - 0x1401: HERE
# 0x1402 - 0x1402: LATEST
# 0x1403 - 0x1403: S0
# 0x1404 - 0x1404: BASE
# 0x1405 - 0x140C: word_buffer (aka 0x5014)
# 0x140D -       : word definitions (\00\00\00\00 4DROP\00\00\00 \02\00\00\00)

names = [
    "DROP",
    "SWAP",
    "DUP",
    "OVER",
    "ROT",
    "-ROT",
    "2DROP",
    "2DUP",
    "2SWAP",
    "?DUP",
    "1+",
    "1-",
    "4+",
    "4-",
    "+",
    "-",
    "*",
    "/MOD",
    "=",
    "<>",
    "<=",
    "<",
    ">",
    "<=",
    ">=",
    "0=",
    "0<>",
    "0<",
    "0>",
    "0<=",
    "0>=",
    "AND",
    "OR",
    "XOR",
    "INVERT",
    "EXIT",
    "LIT",
    "!",
    "@",
    "+!",
    "-!",
    "C!",
    "C@",
    "C@C!",
    "CMOVE",
    "STATE",
    "HERE",
    "LATEST",
    "S0",
    "BASE",
    "VERSION",
    "R0",
    "DOCOL",
    "F_IMMED",
    "F_HIDDEN",
    "F_LENMASK",
    "SYS_EXIT",
    "SYS_OPEN",
    "SYS_CLOSE",
    "SYS_READ",
    "SYS_WRITE",
    "SYS_CREAT",
    "SYS_BRK",
    "O_RDONLY",
    "O_WRONLY",
    "O_RDWR",
    "O_CREAT",
    "O_EXCL",
    "O_TRUNC",
    "O_APPEND",
    "O_NONBLOCK",
    ">R",
    "R>",
    "RSP@",
    "RSP!",
    "RDROP",
    "DSP@",
    "DSP!",
    "KEY",
    "EMIT",
    "WORD",
    "NUMBER",
    "FIND",
    ">CFA",
    ">DFA",
    "CREATE",
    ",",
    "[",
    "]",
    "IMMEDIATE",
    "HIDDEN",
    "HIDE",
    ":",
    ";",
    "'",
    "BRANCH",
    "0BRANCH",
    "LITSTRING",
    "TELL",
    "INTERPRET",
    "QUIT",
    "CHAR",
    "EXECUTE",
    "SYSCALL3",
    "SYSCALL2",
    "SYSCALL1",
]

immediate = {"[", "IMMEDIATE", ";"}

composite = {
    ">DFA": [">CFA", "4+", "EXIT"],
    "HIDE": ["WORD", "FIND", "HIDDEN", "EXIT"],
    ":": ["WORD", "CREATE", "LIT", 0, ",", "LATEST", "@", "HIDDEN", "]", "EXIT"],
    ";": ["LIT", "EXIT", ",", "LATEST", "@", "HIDDEN", "[", "EXIT"],
    "QUIT": ["R0", "RSP!", "INTERPRET", "BRANCH", -8],
}

print("static int memory[0x8000] = {")
print("    /* STATE      */ [5120] =    0,")
print("    /* HERE       */ [5121] = 5547 << 2,")
print("    /* LATEST     */ [5122] = 5543,")
print("    /* S0         */ [5123] = 2048,")
print("    /* BASE       */ [5124] =   10,")

index = link = 0
offset = 0x140D - 1
offsets = {}

shifts = [1 << i for i in range(0, 32, 8)]

for name in names:
    print(f"    /* {name:10s} */", end=" ")
    offset += 1
    print(f"[{offset}] = {link:4d}", end=", ")
    link = offset
    offset += 1
    x = sum(
        (ord(ch) * shift for ch, shift in zip(name[:3], shifts[1:])),
        (len(name) | (0x80 if name in immediate else 0)) * shifts[0]
    )
    print(f"[{offset}] = 0x{x:08x}", end=", ")
    for chunk in batched(name[3:], 4):
        offset += 1
        x = sum(ord(ch) * shift for ch, shift in zip(chunk, shifts))
        print(f"[{offset}] = 0x{x:08x}", end=", ")
    offsets[name] = offset + 1
    code = composite.get(name)
    if code:
        offset += 1
        print(f"[{offset}] = 0", end=", ")
        for item in code:
            offset += 1
            print(f"[{offset}] = {offsets.get(item, item)}", end=", ")
    else:
        offset += 1
        index += 1
        print(f"[{offset}] = {index}", end=", ")
    print()
print("};")
