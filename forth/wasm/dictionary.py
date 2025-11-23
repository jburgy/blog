# ruff: noqa: E501

import struct

binary = "(i32.store (global.get $sp) ({} (call $pop) (i32.load (global.get $sp))))".format
cinary = "(i32.store (global.get $sp) ({} (i32.load (global.get $sp)) (i32.const {:d})))".format

words = {
    "DROP": ["(global.set $sp (i32.add (global.get $sp) (i32.const 4)))"],
    "SWAP": [
        "(local $t i32)",
        "(local.set $t (i32.load offset=4 (global.get $sp)))",
        "(i32.store offset=4 (global.get $sp) (i32.load (global.get $sp)))",
        "(i32.store (global.get $sp) (local.get $t))",
    ],
    "DUP": ["(call $push (i32.load (global.get $sp)))"],
    "OVER": [],
    "ROT": [],
    "-ROT": [],
    "2DRROP": ["(global.set $sp (i32.add (global.get $sp) (i32.const 8)))"],
    "2DUP": [],
    "2SWAP": [],
    "?DUP": [],
    "1+": [cinary("i32.add", 1)],
    "1-": [cinary("i32.sub", 1)],
    "4+": [cinary("i32.add", 4)],
    "4-": [cinary("i32.sub", 4)],
    "+": [binary("i32.add")],
    "-": [binary("i32.sub")],
    "*": [binary("i32.mul")],
    "/MOD": [],
    "=": [binary("i32.eq")],
    "<>": [binary("i32.ne")],
    "<": [binary("i32.lt_s")],
    ">": [binary("i32.gt_s")],
    "<=": [binary("i32.le_s")],
    ">=": [binary("i32.ge_s")],
    "0=": [cinary("i32.eq", 0)],
    "0<>": [cinary("i32.ne", 0)],
    "0<": [cinary("i32.lt_s", 0)],
    "0>": [cinary("i32.gt_s", 0)],
    "0<=": [cinary("i32.le_s", 0)],
    "0>=": [cinary("i32.ge_s", 0)],
    "AND": [binary("i32.and")],
    "OR": [binary("i32.or")],
    "XOR": [binary("i32.xor")],
    "INVERT": [cinary("i32.xor", -1)],
    "EXIT": [],
    "LIT": [
        "(call $push (i32.load (global.get $ip)))",
        "(global.set $ip (i32.add (global.get $ip) (i32.const 4)))",
    ],
    "!": ["(i32.store (call $pop) (call $pop))"],
    "@": ["(call $push (i32.load (call $pop)))"],
    "+!": [
        "(local $p i32)",
        "(i32.store (local.tee $p (call $pop)) (i32.add (i32.load (local.get $p)) (call $pop)))",
    ],
    "-!": [
        "(local $p i32)",
        "(i32.store (local.tee $p (call $pop)) (i32.sub (i32.load (local.get $p)) (call $pop)))",
    ],
    "C!": ["(i32.store8 (call $pop) (call $pop))"],
    "C@": ["(call $push (i32.load8_u (call $pop)))"],
    "CMOVE": [],
    "STATE": ["(call $push (i32.const 0x5000))"],
    "HERE": ["(call $push (i32.const 0x5005))"],
    "LATEST": ["(call $push (i32.const 0x5008))"],
    "S0": ["(call $push (i32.const 0x500C))"],
    "BASE": ["(call $push (i32.const 0x5010))"],
    "VERSION": ["(call $push (i32.const 47))"],
    "R0": ["(call $push (global.get $r0))"],
    "DOCOL": ["(call $push (i32.const 0))"],
    "F_IMMED": ["(call $push (global.get $f_immed))"],
    "F_HIDDEN": ["(call $push (global.get $f_hidden))"],
    "F_LENMASK": ["(call $push (global.get $f_lenmask))"],
    ">R": ["(call $pushrsp (call $pop))"],
    "R>": ["(call $push (call $poprsp))"],
    "RSP@": ["(call $push (global.get $rsp))"],
    "RSP!": ["(global.set $rsp (call $pop))"],
    "RDROP": ["(global.set $rsp (i32.add (global.get $rsp) (i32.const 4)))"],
    "DSP@": ["(call $push (global.get $sp))"],
    "DSP!": ["(global.set $sp (call $pop))"],
    "KEY": ["(call $push (call $_key))"],
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
    "FIND": ["(call $push (call $_find (call $pop) (call $pop)))"],
    ">CFA": ["(call $push (call $_>cfa (call $pop)))"],
    ">DFA": ">CFA 4+ EXIT",
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
    "[": ["(i32.store (i32.const 0x5000) (i32.const 0))"],
    "]": ["(i32.store (i32.const 0x5000) (i32.const 1))"],
    "IMMEDIATE": [
        "(local $latest i32)",
        "(i32.store8 offset=4 (local.tee $latest (i32.load (i32.const 0x5008))) (i32.xor (i32.load8_u offset=4 (local.get $latest)) (global.get $f_immed)))"
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
    "HIDE": "WORD FIND HIDDEN EXIT",
    ":": "WORD CREATE LIT DOCOL , LATEST @ HIDDEN ] EXIT",
    ";": "LIT EXIT , LATEST @ HIDDEN [ EXIT",
    "BRANCH": ["(global.set $ip (i32.add (global.get $ip) (i32.load (global.get $ip))))"],
    "0BRANCH": [
        "(if (i32.eqz (call $pop))",
        "   (then (return_call $branch))",
        "   (else (global.set $ip (i32.add (global.get $ip) (i32.const 4))))",
        ")",
    ],
    "LITSTRING": [],
    "TELL": [
        "(i32.store offset=4 (global.get $iovec) (call $pop))",
        "(i32.store offset=0 (global.get $iovec) (call $pop))",
        "(drop (call $fd_write (i32.const 1) (global.get $iovec) (i32.const 1) (global.get $nwritten)))",
    ],
    "INTERPRET": [
        "(local $c i32)",
        "(local $w i32)",
        "(if (i32.eqz (local.tee $w (call $_find (local.tee $c (call $_word)) (global.get $buffer))))",
        "    (then (call $push (call $_number (local.get $c) (global.get $buffer) (i32.load (i32.const 0x5010)))))",
        "    (else (return_call_indirect (type 0) (i32.load (call $_>cfa (local.get $w)))))",
        ")",
    ],
    "QUIT": "R0 RSP! INTERPRET BRANCH -8",
    "CHAR": [
        "(drop (call $_word))",
        "(call $push (i32.load8_u (global.get $buffer)))",
    ],
    "EXECUTE": [],
}

immediate = {"LBRAC", "IMMEDIATE", ";"}
overrides = {",": "comma", "[": "lbrac", "]": "rbrac"}

index = 0
link = 0
offset = 0x5044
ip = None

indices = {"DOCOL": 0}

for name, code in words.items():
    data = []
    if isinstance(code, list):
        index = len(indices)
        indices[name] = index
    elif isinstance(code, str):
        data = code.split()

    pad = (len(name) + 1) % 4
    if pad:
        pad = 4 - pad
    data = struct.pack(
        f"<IB{len(name)}s{pad}s{len(data) + 1}i",
        link,
        len(name) | (0x80 if name in immediate else 0),
        name.encode(),
        b"\x00" * pad,
        indices.get(name, 0),
        *(indices[arg] if arg in indices else int(arg) for arg in data),
    )
    chars = "".join(chr(byte) if 5 <= i < 5 + len(name) else f"\\{byte:02x}" for i, byte in enumerate(data))
    print(f'    (data (i32.const 0x{offset:x}) "{chars}")')

    if isinstance(code, list):
        print(f"    (func ${overrides.get(name, name).lower()} (type 0)")
        print(f"        {'\n        '.join(code or ['unreachable'])}")
        print("        (return_call $next)")
        print("    )")
        print(f"    (elem (i32.const 0x{index:x}) ${overrides.get(name, name).lower()})")
    print("")
    if name == "QUIT":
        ip = offset + 16
    link = offset
    offset += len(data)

print(f";; IP    : 0x{ip:04x}")
print(";; HERE  :", "".join(f"\\{byte:02x}" for byte in struct.pack("<I", offset)))
print(";; LATEST:", "".join(f"\\{byte:02x}" for byte in struct.pack("<I", link)))
