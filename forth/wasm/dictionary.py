# ruff: noqa: E501

import struct

primitives = {
    "DROP": [
        "(global.set $sp (i32.add (global.get $sp) (i32.const 4)))",
    ],
    "SWAP": [
        "(local $t i32)",
        "(local.set $t (i32.load offset=4 (global.get $sp)))",
        "(i32.store offset=4 (global.get $sp) (i32.load (global.get $sp)))",
        "(i32.store (global.get $sp) (local.get $t))",
    ],
    "DUP": [
        "(call $push (i32.load (global.get $sp)))",
    ],
    "LIT": [
        "(call $push (i32.load (global.get $ip)))",
        "(global.set $ip (i32.add (global.get $ip) (i32.const 4)))",
        "(return_call $next)",
    ],
    "R0": [
        "(call $push (global.get $r0))",
    ],
    "RSP!": [
        "(global.set $rsp (call $pop))",
    ],
    "EMIT": [
        "(i32.store offset=0 (global.get $iovec) (global.get $sp))",
        "(i32.store offset=4 (global.get $iovec) (i32.const 1))",
        "(drop (call $fd_write (i32.const 1) (global.get $iovec) (i32.const 1) (global.get $nwritten)))",
        "(global.set $sp (i32.add (global.get $sp) (i32.const 4)))",
    ],
    "BRANCH": [
        "(global.set $ip (i32.add (global.get $ip) (i32.load (global.get $ip))))",
    ],
    "INTERPRET": [
        "(local $c i32)",
        "(local $w i32)",
        "(if (i32.eqz (local.tee $w (call $_find (local.tee $c (call $_word)) (global.get $buffer))))",
        "    (then (call $push (call $_number (local.get $c) (global.get $buffer) (i32.load (i32.const 0x5010)))))",
        "    (else (return_call_indirect (type 0) (local.get $w)))",
        ")",
    ],
}

words = {
    "DROP": "",
    "SWAP": "",
    "DUP": "",
    # "OVER": "",
    # "ROT": "",
    # "-ROT": "",
    # "2DRROP": "",
    # "2DUP": "",
    # "2SWAP": "",
    # "?DUP": "",
    # "1+": "",
    # "1-": "",
    # "4+": "",
    # "4-": "",
    # "+": "",
    # "-": "",
    # "*": "",
    # "/MOD": "",
    # "=": "",
    # "<>": "",
    # "<": "",
    # ">": "",
    # "<=": "",
    # ">=": "",
    # "0=": "",
    # "0<>": "",
    # "0<": "",
    # "0>": "",
    # "0<=": "",
    # "0>=": "",
    # "AND": "",
    # "OR": "",
    # "XOR": "",
    # "INVERT": "",
    "EXIT": "",
    "LIT": "",
    # "!": "",
    # "@": "",
    # "+!": "",
    # "-!": "",
    # "C!": "",
    # "C@": "",
    # "C@+": "",
    # "CMOVE": "",
    # "STATE": "",
    # "HERE": "",
    # "LATEST": "",
    # "S0": "",
    # "BASE": "",
    # "VERSION": "",
    "R0": "",
    # "DOCOL": "",
    # "F_IMMED": "",
    # "F_HIDDEN": "",
    # "F_LENMASK": "",
    # ">R": "",
    # "R>": "",
    # "RSP@": "",
    "RSP!": "",
    # "RDROP": "",
    # "DSP@": "",
    # "DSP!": "",
    # "KEY": "",
    "EMIT": "",
    # "WORD": "",
    # "NUMBER": "",
    # "FIND": "",
    # ">CFA": "",
    # ">DFA": ">CFA 4+ EXIT",
    # "CREATE": "",
    # ",": "",
    # "[": "",
    # "]": "",
    # "IMMEDIATE": "",
    # "HIDDEN": "",
    # "HIDE": ">CFA 4+ EXIT",
    # ":": "WORD CREATE LIT DOCOL , LATEST @ HIDDEN ] EXIT",
    # ";": "LIT EXIT , LATEST @ HIDDEN [ EXIT",
    # "'": "",
    "BRANCH": "",
    # "0BRANCH": "",
    # "LITSTRING": "",
    # "TELL": "",
    "INTERPRET": "",
    "QUIT": "R0 RSP! INTERPRET BRANCH -8",
    # "CHAR": "",
    # "EXECUTE": "",
}

immediate = {"LBRAC", "IMMEDIATE", ";"}

index = 0
link = 0
offset = 0x5040

indices = {}

for name, args in words.items():
    args = args.split()
    n = len(args)

    if n == 0:
        index = len(indices) + 1  # 0 is reserved for DOCOL
        indices[name] = index

    pad = (len(name) + 1) % 4
    if pad:
        pad = 4 - pad
    data = struct.pack(
        f"<IB{len(name)}s{pad}s{n + 1}i",
        link,
        len(name) | (0x80 if name in immediate else 0),
        name.encode(),
        b"\x00" * pad,
        indices.get(name, 0),
        *(indices.get(arg) or int(arg) for arg in args),
    )
    chars = "".join(chr(byte) if 5 <= i < 5 + len(name) else f"\\{byte:02x}" for i, byte in enumerate(data))
    print(f'    (data (i32.const 0x{offset:x}) "{chars}")')

    if n == 0:
        print(f"    (func ${name.lower()} (type 0)")
        print(f"        {'\n        '.join(primitives.get(name, ['unreachable']))}")
        print("        (return_call $next)")
        print("    )")
        print(f"    (elem (i32.const 0x{index:x}) ${name.lower()})")

    print("")
    link = offset
    offset += len(data)
