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
    "!": [
        "(i32.store (call $pop) (call $pop))",
    ],
    "@": [
        "(call $push (i32.load (call $pop)))",
    ],
    "LATEST": [
        "(call $push (i32.const 0x5008))",
    ],
    "R0": [
        "(call $push (global.get $r0))",
    ],
    "DOCOL" : [
        "(call $push (i32.const 0))",
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
    "WORD": [
        "(call $push (global.get $buffer))",
        "(call $push (call $_word (call $pop) (call $pop)))",
    ],
    "NUMBER": [
        "(call $push (call $_number (call $pop) (call $pop) (i32.load (i32.const 0x5010))))",
    ],
    "FIND": [
        "(call $push (call $_find (call $pop) (call $pop)))",
    ],
    ">CFA": [
        "(call $push (call $_>cfa (call $pop)))",
    ],
    "CREATE": [
        "(local $c i32) ;; count (%ecx)",
        "(local $d i32) ;; destination (%edi)",
        "(local $s i32) ;; source (%esi)",
        "(i32.store (local.tee $d (i32.load (i32.const 0x5004))) (i32.load (i32.const 0x5008))) ;; *HERE = *LATEST",
        "(i32.store (i32.const 0x5008) (local.get $d)) ;; LATEST = HERE",
        "(i32.store8 (local.tee $d (i32.add (local.get $d) (i32.const 4))) (local.tee $c (call $pop))) ;; set flags to len",
        "(local.set $s (call $pop))",
        "(loop $copy  ;; `rep movsb` would be nice here",
        "    (i32.store8 (local.get $d) (i32.load8_u (local.get $s)))",
        "    (local.set $d (i32.add (local.get $d) (i32.const 1)))",
        "    (local.set $s (i32.add (local.get $s) (i32.const 1)))",
        "    (br_if $copy (i32.gt_s (local.tee $c (i32.sub (local.get $c) (i32.const 1))) (i32.const 0)))",
        ")",
        "(i32.store (i32.const 0x5004) (i32.and (i32.add (local.get $d) (i32.const 3)) (i32.const -4))) ;; HERE = d (aligned)",
    ],
    ",": [
        "(local $d i32)",
        "(i32.store (local.tee $d (i32.const 0x5004)) (call $pop))",
        "(i32.store (i32.const 0x5004) (i32.add (local.get $d) (i32.const 4)))",
    ],
    "[": [
        "(i32.store (i32.const 0x5010) (i32.const 0))",
    ],
    "]": [
        "(i32.store (i32.load8_4 offset=4 (call $pop)))",
    ],
    "HIDDEN": [
        "(local $p i32)",
        "(i32.store8 offset=4 (local.get $p)",
        "    (i32.xor",
        "        (i32.load8_u offset=4 (local.tee $p (call $pop)))",
        "        (global.get $f_hidden)",
        "    )",
        ")",
    ],
    "BRANCH": [
        "(global.set $ip (i32.add (global.get $ip) (i32.load (global.get $ip))))",
    ],
    "INTERPRET": [
        "(local $c i32)",
        "(local $w i32)",
        "(if (i32.eqz (local.tee $w (call $_find (local.tee $c (call $_word)) (global.get $buffer))))",
        "    (then (call $push (call $_number (local.get $c) (global.get $buffer) (i32.load (i32.const 0x5010)))))",
        "    (else (return_call_indirect (type 0) (i32.load (call $_>cfa (local.get $w)))))",
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
    "!": "",
    "@": "",
    # "+!": "",
    # "-!": "",
    # "C!": "",
    # "C@": "",
    # "C@+": "",
    # "CMOVE": "",
    # "STATE": "",
    # "HERE": "",
    "LATEST": "",
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
    "WORD": "",
    "NUMBER": "",
    "FIND": "",
    ">CFA": "",
    # ">DFA": ">CFA 4+ EXIT",
    "CREATE": "",
    ",": "",
    "[": "",
    "]": "",
    # "IMMEDIATE": "",
    "HIDDEN": "",
    # "HIDE": ">CFA 4+ EXIT",
    ":": "WORD CREATE LIT DOCOL , LATEST @ HIDDEN ] EXIT",
    ";": "LIT EXIT , LATEST @ HIDDEN [ EXIT",
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
overrides = {",": "comma", "[": "lbrac", "]": "rbrac"}

index = 0
link = 0
offset = 0x5040
ip = None

indices = {"DOCOL": 0}

for name, args in words.items():
    args = args.split()
    n = len(args)

    if n == 0:
        index = len(indices)
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
        *(indices[arg] if arg in indices else int(arg) for arg in args),
    )
    chars = "".join(chr(byte) if 5 <= i < 5 + len(name) else f"\\{byte:02x}" for i, byte in enumerate(data))
    print(f'    (data (i32.const 0x{offset:x}) "{chars}")')

    if n == 0:
        print(f"    (func ${overrides.get(name, name).lower()} (type 0)")
        print(f"        {'\n        '.join(primitives.get(name, ['unreachable']))}")
        print("        (return_call $next)")
        print("    )")
        print(f"    (elem (i32.const 0x{index:x}) ${overrides.get(name, name).lower()})")
    print("")
    if name == "QUIT":
        ip = offset + 16
    link = offset
    offset += len(data)

print("IP    :", "".join(f"\\{byte:02x}" for byte in struct.pack("<I", ip)))
print("LATEST:", "".join(f"\\{byte:02x}" for byte in struct.pack("<I", link)))
print("HERE  :", "".join(f"\\{byte:02x}" for byte in struct.pack("<I", offset)))
