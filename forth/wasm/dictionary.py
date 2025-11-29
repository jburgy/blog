# ruff: noqa: E501

import struct

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
        "(local i32 i32 i32)",
        "(local.set 0 (i32.load offset=0 (global.get $sp)))",
        "(local.set 1 (i32.load offset=4 (global.get $sp)))",
        "(local.set 2 (i32.load offset=8 (global.get $sp)))",
        "(i32.store offset=8 (global.get $sp) (local.get 1))",
        "(i32.store offset=4 (global.get $sp) (local.get 0))",
        "(i32.store offset=0 (global.get $sp) (local.get 2))",
    ],
    "-ROT": [
        "(local i32 i32 i32)",
        "(local.set 0 (i32.load offset=0 (global.get $sp)))",
        "(local.set 1 (i32.load offset=4 (global.get $sp)))",
        "(local.set 2 (i32.load offset=8 (global.get $sp)))",
        "(i32.store offset=0 (global.get $sp) (local.get 0))",
        "(i32.store offset=4 (global.get $sp) (local.get 2))",
        "(i32.store offset=8 (global.get $sp) (local.get 1))",
    ],
    "2DROP": ["(global.set $sp (i32.add (global.get $sp) (i32.const 8)))"],
    "2DUP": [
        "(call $push (i32.load offset=4 (global.get $sp)))",
        "(call $push (i32.load offset=4 (global.get $sp)))",
    ],
    "2SWAP": [
        "(local i32 i32 i32 i32)",
        "(local.set 0 (i32.load offset=0 (global.get $sp)))",
        "(local.set 1 (i32.load offset=4 (global.get $sp)))",
        "(local.set 2 (i32.load offset=8 (global.get $sp)))",
        "(local.set 3 (i32.load offset=12 (global.get $sp)))",
        "(i32.store offset=12 (global.get $sp) (local.get 1))",
        "(i32.store offset=8 (global.get $sp) (local.get 0))",
        "(i32.store offset=4 (global.get $sp) (local.get 3))",
        "(i32.store offset=0 (global.get $sp) (local.get 2))",

    ],
    "?DUP": [
        "(local i32)",
        "(if (local.tee 0 (i32.load (global.get $sp)))",
        "    (then (call $push (local.get 0)))",
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
        "(local i32 i32)",
        "(local.set 0 (i32.load offset=4 (global.get $sp)))",
        "(local.set 1 (i32.load offset=0 (global.get $sp)))",
        "(i32.store offset=4 (global.get $sp) (i32.rem_s (local.get 0) (local.get 1)))",
        "(i32.store offset=0 (global.get $sp) (i32.div_s (local.get 0) (local.get 1)))",
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
    "C@C!": [
        "(local i32)",
        "(memory.copy (local.tee 0 (call $pop)) (call $pop) (i32.const 1))",
        "(call $push (local.get 0))",
    ],
    "CMOVE": [
        "(local i32 i32)",
        "(local.set 1 (call $pop))",
        "(memory.copy (local.tee 0 (call $pop)) (call $pop) (local.get 1))",
        "(call $push (local.get 0))",
    ],
    "STATE": ["(call $push (global.get $state))"],
    "HERE": ["(call $push (global.get $here))"],
    "LATEST": ["(call $push (global.get $latest))"],
    "S0": ["(call $push (global.get $s0))"],
    "BASE": ["(call $push (global.get $base))"],
    "VERSION": ["(call $push (i32.const 0x2f))"],
    "R0": ["(call $push (i32.const 0x4000))"],
    "DOCOL": ["(call $push (i32.const 0))"],
    "F_IMMED": ["(call $push (global.get $f_immed))"],
    "F_HIDDEN": ["(call $push (global.get $f_hidden))"],
    "F_LENMASK": ["(call $push (global.get $f_lenmask))"],
    "SYS_EXIT": ["(call $push (i32.const 1))"],
    "SYS_OPEN": ["(call $push (i32.const 5))"],
    "SYS_CLOSE": ["(call $push (i32.const 6))"],
    "SYS_READ": ["(call $push (i32.const 3))"],
    "SYS_WRITE": ["(call $push (i32.const 4))"],
    "SYS_CREAT": ["(call $push (i32.const 8))"],
    "SYS_BRK": ["(call $push (i32.const 45))"],
    # https://github.com/WebAssembly/wasi-libc/blob/main/expected/wasm32-wasip1/predefined-macros.txt
    "O_RDONLY": ["(call $push (i32.const 0x04000000))"],
    "O_WRONLY": ["(call $push (i32.const 0x10000000))"],
    "O_RDWR": ["(call $push (i32.const 0x14000000))"],
    # __wasi_oflags_t (CREAT DIRECTORY EXCL TRUNC) << 12
    "O_CREAT": ["(call $push (i32.const 0x1000))"],
    "O_EXCL": ["(call $push (i32.const 0x4000))"],
    "O_TRUNC": ["(call $push (i32.const 0x8000))"],
    # __wasi_fdflags_t (APPEND DSYNC NONBLOCK RSYNC SYNC)
    "O_APPEND": ["(call $push (i32.const 0x1))"],
    "O_NONBLOCK": ["(call $push (i32.const 0x4))"],
    ">R": ["(call $pushrsp (call $pop))"],
    "R>": ["(call $push (call $poprsp))"],
    "RSP@": ["(call $push (global.get $rsp))"],
    "RSP!": ["(global.set $rsp (call $pop))"],
    "RDROP": ["(global.set $rsp (i32.add (global.get $rsp) (i32.const 4)))"],
    "DSP@": ["(call $push (global.get $sp))"],
    "DSP!": ["(global.set $sp (call $pop))"],
    "KEY": ["(call $push (call $_key))"],
    "EMIT": [
        "(call $write (i32.const 1) (global.get $sp) (i32.const 1))",
        "(global.set $sp (i32.add (global.get $sp) (i32.const 4)))",
    ],
    "WORD": [
        "(call $push (global.get $buffer))",
        "(call $push (call $_word))",
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
        "(i32.store8 offset=4 (local.get $d) (local.tee $c (call $pop))) ;; set flags to len",
        "(memory.copy (local.tee $d (i32.add (local.get $d) (i32.const 5))) (call $pop) (local.get $c))",
        "(i32.store (global.get $here) (i32.and (i32.add (local.get $d) (i32.add (local.get $c)) (i32.const 3)) (i32.const -4))) ;; HERE = d (aligned)",
    ],
    ",": [
        "(local $d i32)",
        "(i32.store (local.tee $d (i32.load (global.get $here))) (call $pop))",
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
        "(i32.store8 offset=4 (local.tee $p (call $pop))",
        "    (i32.xor",
        "        (i32.load8_u offset=4 (local.get $p))",
        "        (global.get $f_hidden)",
        "    )",
        ")",
    ],
    "HIDE": "WORD FIND HIDDEN EXIT",
    ":": "WORD CREATE LIT &DOCOL , LATEST @ HIDDEN ] EXIT",
    ";": "LIT EXIT , LATEST @ HIDDEN [ EXIT",
    "'": [
        "(call $push (i32.load (global.get $ip)))",
        "(global.set $ip (i32.add (global.get $ip) (i32.const 4)))",
    ],
    "BRANCH": ["(global.set $ip (i32.add (global.get $ip) (i32.load (global.get $ip))))"],
    "0BRANCH": [
        "(if (call $pop)",
        "    (then (global.set $ip (i32.add (global.get $ip) (i32.const 4))))",
        "    (else (return_call $branch))",
        ")",
    ],
    "LITSTRING": [
        "(local $len i32)",
        "(local.set $len (i32.load (global.get $ip)))",
        "(global.set $ip (i32.add (global.get $ip) (i32.const 4)))",
        "(call $push (global.get $ip))",
        "(call $push (local.get $len))",
        "(global.set $ip (i32.add (global.get $ip) (i32.and (i32.add (local.get $len) (i32.const 3)) (i32.const -4))))",
    ],
    "TELL": [
        "(local i32)",
        "(local.set 0 (call $pop))",
        "(call $write (i32.const 1) (call $pop) (local.get 0))",
    ],
    "INTERPRET": [
        "(local $c i32)",
        "(local $w i32)",
        "(if (local.tee $w (call $_find (local.tee $c (call $_word)) (global.get $buffer)))",
        "    (then ;; found word => execute or append",
        "        (global.set $cfa (call $_>cfa (local.get $w)))",
        "        (if (i32.or",
        "                (i32.and (i32.load8_u offset=4 (local.get $w)) (global.get $f_immed))",
        "                (i32.eqz (i32.load (global.get $state)))",
        "            )",
        "            (then",
        "                (return_call_indirect (type 0) (i32.load (global.get $cfa)))",
        "            )",
        "        )",
        "        (i32.store (i32.load (global.get $here)) (global.get $cfa))",
        "        (i32.store (global.get $here) (i32.add (i32.load (global.get $here)) (i32.const 4)))",
        "    )",
        "    (else",
        "        (local.set $w (call $_number (local.get $c) (global.get $buffer)))",
        "        (if (i32.load (global.get $nwritten)) ;; unconsumed input => parse error",
        "            (then",
        '                (call $write (i32.const 2) (i32.const 0x5668) (i32.const 13)) ;; "PARSE ERROR:"',
        "                (call $write (i32.const 2) (global.get $buffer) (local.get $c))",
        '                (call $write (i32.const 2) (i32.const 0x5675) (i32.const 1)) ;; "\\n"',
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
    "EXECUTE": [
        "(global.set $cfa (call $pop))",
        "(return_call_indirect (type 0) (i32.load (global.get $cfa)))"
    ],
    "SYSCALL3": ["unreachable"],
    "SYSCALL2": ["unreachable"],
    "SYSCALL1": [
        "(if (i32.eq (call $pop) (i32.const 45))",
        "    (then (i32.store (global.get $sp) (i32.mul (memory.size) (i32.const 0x10000))))",
        ")",
    ],
}

immediate = {"[", "IMMEDIATE", ";"}
overrides = {",": "comma", "[": "lbrac", "]": "rbrac"}

index = 1
link = 0
offset = 0x5044

offsets = {"-8": -8, "&DOCOL": 0}

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
        0 if isinstance(code, str) else index,
        *(offsets[arg] for arg in args),
    )
    chars = "".join(chr(byte) if 5 <= i < 5 + len(name) else f"\\{byte:02x}" for i, byte in enumerate(data))
    print(f'    (data (i32.const 0x{offset:x}) "{chars}")')

    if isinstance(code, list):
        print(f"    (func ${overrides.get(name, name).lower()} (type 0)", *code, "(return_call $next)", sep="\n        ")
        print("    )")
        print(f"    (elem (i32.const 0x{index:x}) ${overrides.get(name, name).lower()})")
        index += 1
    if name not in {"HIDE", ":"}:
        print("")
    link = offset
    offsets[name] = offset + 5 + len(name) + pad
    offset += len(data)

    if name == "INTERPRET":
        print(f'    (data (i32.const 0x{offset:x}) "PARSE ERROR: \\0A\\00\\00")')
        offset += 16

print('  (data (i32.const 0x5004) "', "".join(f"\\{byte:02x}" for byte in struct.pack("<I", offset)), '")', sep="")
print('  (data (i32.const 0x5008) "', "".join(f"\\{byte:02x}" for byte in struct.pack("<I", link)), '")', sep="")
print('  (data (i32.const 0x5040) "', "".join(f"\\{byte:02x}" for byte in struct.pack("<I", offsets["QUIT"])), '")', sep="")
print(f';; "PARSE ERROR:" 0x{offsets["QUIT"] - 16:04x}')
print(f';; "\\n"           0x{offsets["QUIT"] - 3:04x}')
print(f";; LIT            0x{offsets['LIT']:04x}")
