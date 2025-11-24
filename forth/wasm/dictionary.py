# ruff: noqa: E501

import struct

# TODO: rewrite ROT -ROT 2SWAP using offset instead of local variables

# offset=4 when loading and storing because (local.get $sp) happens _before_ (call $pop)
binary = "(i32.store offset=4 (global.get $sp) ({} (i32.load offset=4 (global.get $sp)) (call $pop)))".format
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
    "OVER": ["(call $push (i32.load offset=4 (global.get $sp)))"],
    "ROT": [
        "(local $a i32)",
        "(local $b i32)",
        "(local $c i32)",
        "(local.set $a (call $pop))",
        "(local.set $b (call $pop))",
        "(local.set $c (call $pop))",
        "(call $push (local.get $b))",
        "(call $push (local.get $a))",
        "(call $push (local.get $c))",
    ],
    "-ROT": [
        "(local $a i32)",
        "(local $b i32)",
        "(local $c i32)",
        "(local.set $a (call $pop))",
        "(local.set $b (call $pop))",
        "(local.set $c (call $pop))",
        "(call $push (local.get $a))",
        "(call $push (local.get $c))",
        "(call $push (local.get $b))",
    ],
    "2DRROP": ["(global.set $sp (i32.add (global.get $sp) (i32.const 8)))"],
    "2DUP": [
        "(call $push (i32.load offset=4 (global.get $sp)))",
        "(call $push (i32.load offset=4 (global.get $sp)))",
    ],
    "2SWAP": [
        "(local $a i32)",
        "(local $b i32)",
        "(local $c i32)",
        "(local $d i32)",
        "(local.set $a (call $pop))",
        "(local.set $b (call $pop))",
        "(local.set $c (call $pop))",
        "(local.set $d (call $pop))",
        "(call $push (local.get $b))",
        "(call $push (local.get $a))",
        "(call $push (local.get $d))",
        "(call $push (local.get $c))",

    ],
    "?DUP": [
        "(local $a i32)",
        "(if (i32.eqz (local.tee $a (i32.load (global.get $sp))))",
        "    (then (call $push (local.get $a)))",
        ")",
    ],
    "1+": [cinary("i32.add", 1)],
    "1-": [cinary("i32.sub", 1)],
    "4+": [cinary("i32.add", 4)],
    "4-": [cinary("i32.sub", 4)],
    "+": [binary("i32.add")],
    "-": [binary("i32.sub")],
    "*": [binary("i32.mul")],
    "/MOD": [
        "(local $a i32)",
        "(local $b i32)",
        "(local.set $a (call $pop))",
        "(local.set $b (call $pop))",
        "(call $push (i32.rem_s (local.get $b) (local.get $a)))",
        "(call $push (i32.div_s (local.get $b) (local.get $a)))",
    ],
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
    "EXIT": ["(global.set $ip (call $poprsp))"],
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
    "CMOVE": ["(call $memcpy (call $pop) (call $pop) (call $pop))"],
    "STATE": ["(call $push (global.get $state))"],
    "HERE": ["(call $push (global.get $here))"],
    "LATEST": ["(call $push (global.get $latest))"],
    "S0": ["(call $push (global.get $s0))"],
    "BASE": ["(call $push (global.get $base))"],
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
        "(call $push (call $_number (call $pop) (call $pop)))",
    ],
    "FIND": ["(call $push (call $_find (call $pop) (call $pop)))"],
    ">CFA": ["(call $push (call $_>cfa (call $pop)))"],
    ">DFA": ">CFA 4+ EXIT",
    "CREATE": [
        "(local $c i32) ;; count (%ecx)",
        "(local $d i32) ;; destination (%edi)",
        "(i32.store (local.tee $d (i32.load (global.get $here))) (i32.load (global.get $latest))) ;; *HERE = *LATEST",
        "(i32.store (global.get $latest) (local.get $d)) ;; LATEST = HERE",
        "(i32.store8 (local.tee $d (i32.add (local.get $d) (i32.const 4))) (local.tee $c (call $pop))) ;; set flags to len",
        "(i32.store (global.get $here) (i32.and (i32.add (call $memcpy (local.get $c) (local.get $d) (call $pop)) (i32.const 3)) (i32.const -4))) ;; HERE = d (aligned)",
    ],
    ",": [
        "(local $d i32)",
        "(i32.store (local.tee $d (global.get $here)) (call $pop))",
        "(i32.store (global.get $here) (i32.add (local.get $d) (i32.const 4)))",
    ],
    "[": ["(i32.store (global.get $state) (i32.const 0))"],
    "]": ["(i32.store (global.get $state) (i32.const 1))"],
    "IMMEDIATE": [
        "(local $latest i32)",
        "(i32.store8 offset=4 (local.tee $latest (i32.load (global.get $latest))) (i32.xor (i32.load8_u offset=4 (local.get $latest)) (global.get $f_immed)))"
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
    "LITSTRING": [
        "(local $len i32)",
        "(local.set $len (i32.load (global.get $ip)))",
        "(global.set $ip (i32.add (global.get $ip) (i32.const 4)))",
        "(call $push (global.get $sp))",
        "(call $push (local.get $len))",
        "(global.set $ip (i32.add (global.get $ip) (i32.and (i32.add (local.get $len) (i32.const 3)) (i32.const -4))))",
    ],
    "TELL": [
        "(i32.store offset=4 (global.get $iovec) (call $pop))",
        "(i32.store offset=0 (global.get $iovec) (call $pop))",
        "(drop (call $fd_write (i32.const 1) (global.get $iovec) (i32.const 1) (global.get $nwritten)))",
    ],
    "INTERPRET": [
        "(local $c i32)",
        "(local $w i32)",
        "(if (local.tee $w (call $_find (local.tee $c (call $_word)) (global.get $buffer)))",
        "    (then ;; found word => execute or append",
        "        (if (i32.or",
        "                (i32.and (i32.load8_u offset=4 (local.get $w)) (global.get $f_immed))",
        "                (i32.eqz (i32.load (global.get $state)))",
        "            )",
        "            (then",
        "                (global.set $cfa (call $_>cfa (local.get $w)))",
        "                (return_call_indirect (type 0) (i32.load (global.get $cfa)))",
        "            )",
        "        )",
        "        (i32.store (i32.load (global.get $here)) (local.get $w))",
        "        (i32.store (global.get $here) (i32.add (i32.load (global.get $here)) (i32.const 4)))",
        "    )",
        "    (else",
        "        (local.set $w (call $_number (local.get $c) (global.get $buffer)))",
        "        (if (i32.load (global.get $nwritten)) ;; unconsumed input => parse error",
        "            (then",
        '                (i32.store offset=0 (global.get $iovec) (i32.const 0x5538)) ;; "PARSE ERROR: "',
        '                (i32.store offset=4 (global.get $iovec) (i32.const 13)) ;; len("PARSE ERROR: ")',
        "                (drop (call $fd_write (i32.const 2) (global.get $iovec) (i32.const 1) (global.get $nwritten)))",
        "                (i32.store offset=0 (global.get $iovec) (global.get $buffer))",
        "                (i32.store offset=4 (global.get $iovec) (local.get $c))",
        "                (drop (call $fd_write (i32.const 2) (global.get $iovec) (i32.const 1) (global.get $nwritten)))",
        '                (i32.store offset=0 (global.get $iovec) (i32.const 0x5545)) ;; "\\n"',
        '                (i32.store offset=4 (global.get $iovec) (i32.const 1)) ;; len("\\n")',
        "                (drop (call $fd_write (i32.const 2) (global.get $iovec) (i32.const 1) (global.get $nwritten)))",
        "            )",
        "            (else",
        "                (if (i32.load (global.get $state)) ;; compile number",
        "                    (then",
        "                        (i32.store (i32.load (global.get $here)) (i32.const 0x521C)) ;; LIT cfa",
        "                        (i32.store offset=4 (i32.load (global.get $here)) (local.get $w))",
        "                        (i32.store (global.get $here) (i32.add (i32.load (global.get $here)) (i32.const 8)))",
        "                    )",
        "                    (else (call $push (local.get $w)))",
        "                )",
        "            )",
        "        )",
        "    )",
        ")",
    ],
    "QUIT": "R0 RSP! INTERPRET BRANCH -8",
    "CHAR": [
        "(drop (call $_word))",
        "(call $push (i32.load8_u (global.get $buffer)))",
    ],
    "EXECUTE": ["(return_call_indirect (type 0) (i32.load (call $pop)))"],
}

immediate = {"LBRAC", "IMMEDIATE", ";"}
overrides = {",": "comma", "[": "lbrac", "]": "rbrac"}

index = 0
link = 0
offset = 0x5044

indices = {"DOCOL": 0}
offsets = {"-8": -8}

for name, code in words.items():
    args = code.split() if isinstance(code, str) else []

    pad = (len(name) + 1) % 4
    if pad:
        pad = 4 - pad
    data = struct.pack(
        f"<IB{len(name)}s{pad}s{len(args) + 1}i",
        link,
        len(name) | (0x80 if name in immediate else 0),
        name.encode(),
        b"\x00" * pad,
        index := 0 if isinstance(code, str) else len(indices),
        *(offsets[arg] for arg in args),
    )
    chars = "".join(chr(byte) if 5 <= i < 5 + len(name) else f"\\{byte:02x}" for i, byte in enumerate(data))
    print(f'    (data (i32.const 0x{offset:x}) "{chars}")')

    if isinstance(code, list):
        indices[name] = len(indices)

        print(f"    (func ${overrides.get(name, name).lower()} (type 0)")
        print(f"        {'\n        '.join(code or ['unreachable'])}")
        print("        (return_call $next)")
        print("    )")
        print(f"    (elem (i32.const 0x{index:x}) ${overrides.get(name, name).lower()})")
    if name not in {"HIDE", ":"}:
        print("")
    link = offset
    offsets[name] = offset + 5 + len(name) + pad
    offset += len(data)

    if name == "INTERPRET":
        print(f'    (data (i32.const 0x{offset:x}) "PARSE ERROR: \\0A\\00\\00")')
        offset += 16

print("  (data (i32.const 0x5004) ", "".join(f"\\{byte:02x}" for byte in struct.pack("<I", offset)), ")", sep="")
print("  (data (i32.const 0x5008) ", "".join(f"\\{byte:02x}" for byte in struct.pack("<I", link)), ")", sep="")
print("  (data (i32.const 0x5040) ", "".join(f"\\{byte:02x}" for byte in struct.pack("<I", offsets["QUIT"])), ")", sep="")
