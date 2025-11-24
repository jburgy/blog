;; A port of jonesforth to WebAssembly
;; Changelog:
;;   - 11/20/25: $next using return_call_indirect, basic stack operations, lit, _number
;;   - 11/21/25: interpret, quit
(module
    (func $fd_read   (import "wasi_snapshot_preview1" "fd_read")   (param i32 i32 i32 i32) (result i32))
    (func $fd_write  (import "wasi_snapshot_preview1" "fd_write")  (param i32 i32 i32 i32) (result i32))
    (func $proc_exit (import "wasi_snapshot_preview1" "proc_exit") (param i32))

    ;; Here's how I understand jonesforth's memory layout:
    ;;
    ;; machine stack (used as Forth data stack)
    ;;
    ;; .bss
    ;;   0x0000 - 0x1FFF: return_stack
    ;;   0x2000 - 0x2FFF: temporary input buffer when reading from files or the terminal
    ;;
    ;; .data (initially sized to 0x10000 bytes)
    ;;   0x0000 - 0x0003: STATE             Is the interpreter executing code (0) or compiling a word (non-zero)?
    ;;   0x0004 - 0x0007: HERE              Points to the latest (most recently defined) word in the dictionary.
    ;;   0x0008 - 0x000B: LATEST            Points to the next free byte of memory.  When compiling, compiled words go here.
    ;;   0x000C - 0x000F: S0                Stores the address of the top of the parameter stack.
    ;;   0x0010 - 0x0013: BASE              The current base for printing and reading numbers.
    ;;   0x0014 - 0x0017: currkey           Current place in input buffer (next character to read).
    ;;   0x0018 - 0x001B: buftop            Last valid data in input buffer + 1.
    ;;   0x001C - 0x001D: emit_scratch      Scratch used by EMIT
    ;;   0x001E - 0x003E: word_buffer       word_buffer
    ;;   0x0040 - 0x0043: interpret_is_lit  Flag used to record if reading a literal
    ;;
    ;; .rodata
    ;;   0x0000 - 0x0003: cold_start        High-level code without a codeword.
    ;;
    ;; .text
    ;;   DOCOL, primitives (DROP, SWAP, DUP, OVER, ROT, etc.)
    ;;
    ;; Several adjustments are needed to make this work in WebAssembly:
    ;; - We can't rely on the machine stack for the Forth data stack, so we allocate a region in linear memory for it.
    ;; - The memory layout is flattened; there is no separate .bss, .data, .rodata, and .text sections.
    ;; - Function pointers are implemented using a table.
    ;; - currkey, buftop, and interpret_is_lit are implemented as globals.
    ;; - fd_read and fd_write need at least one iovec plus nread in memory.
    ;;
    ;; Putting all of these together, we use the following:
    ;;   0x0000 - 0x1FFF: data stack
    ;;   0x2000 - 0x3FFF: return stack
    ;;   0x4000 - 0x4FFF: temporary input buffer
    ;;   0x5000 - 0x5003: STATE
    ;;   0x5004 - 0x5007: HERE
    ;;   0x5008 - 0x500B: LATEST
    ;;   0x500C - 0x500F: S0
    ;;   0x5010 - 0x5013: BASE
    ;;   0x5014 - 0x501B: iovec {buf: i32, len: i32}
    ;;   0x501C - 0x501F: nwritten
    ;;   0x5020 - 0x503F: word_buffer
    ;;   0x5040 - 0x5044: cold_start
    ;;   0x5044 -       : word definitions (\00\00\00\00 4DROP\00\00\00 \02\00\00\00)

    (memory (export "memory") 1)
    (table 80 funcref)

    (global $cfa     (mut i32) (i32.const 0xcccc))  ;; code field address of the next word to define
    (global $ip      (mut i32) (i32.const 0x5040))  ;; instruction pointer (initialized)
    (global $sp      (mut i32) (i32.const 0x2000))  ;; data stack pointer (grows downward)
    (global $rsp     (mut i32) (i32.const 0x4000))  ;; return stack pointer (grows downward)

    (global $currkey (mut i32) (i32.const 0x4000))  ;; current place in input buffer (next character to read)
    (global $buftop  (mut i32) (i32.const 0x4000))  ;; last valid data in input buffer + 1
    (global $state    i32      (i32.const 0x5000))
    (global $here     i32      (i32.const 0x5004))
    (global $latest   i32      (i32.const 0x5008))
    (global $s0       i32      (i32.const 0x500C))
    (global $base     i32      (i32.const 0x5010))
    (global $iovec    i32      (i32.const 0x5014))
    (global $nwritten i32      (i32.const 0x501C))
    (global $buffer   i32      (i32.const 0x5020))  ;; word_buffer

    (data (i32.const 0x5000) "\00\00\00\00")        ;; STATE initialized to 0 (interpreting)
    (data (i32.const 0x5004) "\8c\55\00\00")        ;; HERE initialized to 0x558c
    (data (i32.const 0x5008) "\7c\55\00\00")        ;; LATEST initialized to 0x557c
    (data (i32.const 0x500C) "\00\00\20\00")        ;; S0 initialized to top of data stack
    (data (i32.const 0x5010) "\0A\00\00\00")        ;; BASE initialized to 10
    (data (i32.const 0x5040) "\54\55\00\00")        ;; cold_start initialized to >CFA of QUIT

    (global $version   i32 (i32.const 0x002f))
    (global $r0        i32 (i32.const 0x4000))
    (global $f_immed   i32 (i32.const 0x0080))
    (global $f_hidden  i32 (i32.const 0x0020))
    (global $f_lenmask i32 (i32.const 0x001F))

    (type (;0;) (func))

    (func $next (type 0)
        (global.set $cfa (i32.load (global.get $ip)))
        (global.set $ip (i32.add (global.get $ip) (i32.const 4)))
        (return_call_indirect (type 0) (i32.load (global.get $cfa)))
    )

    (func $push (param $v i32)
        (global.set $sp (i32.sub (global.get $sp) (i32.const 4)))
        (i32.store (global.get $sp) (local.get $v))
    )

    (func $pop (result i32)
        (local $v i32)
        (local.set $v (i32.load (global.get $sp)))
        (global.set $sp (i32.add (global.get $sp) (i32.const 4)))
        (local.get $v)
    )

    (func $pushrsp (param $v i32)
        (global.set $rsp (i32.sub (global.get $rsp) (i32.const 4)))
        (i32.store (global.get $rsp) (local.get $v))
    )

    (func $poprsp (result i32)
        (local $v i32)
        (local.set $v (i32.load (global.get $rsp)))
        (global.set $rsp (i32.add (global.get $rsp) (i32.const 4)))
        (local.get $v)
    )

    (func $_key (result i32)
        (local $c i32)
        (block $break
            (loop $while
                (br_if $break (i32.lt_u (global.get $currkey) (global.get $buftop)))
                (global.set $currkey (i32.const 0x4000))
                (i32.store offset=0 (global.get $iovec) (global.get $currkey)) ;; TIB
                (i32.store offset=4 (global.get $iovec) (i32.const 0x1000)) ;; BUFFER_SIZE
                (local.set $c (call $fd_read (i32.const 0) (global.get $iovec) (i32.const 1) (global.get $nwritten)))
                (if (local.get $c) (then (call $proc_exit (local.get $c))))
                (global.set $buftop (i32.add (global.get $currkey) (i32.load (global.get $nwritten))))
                (br $while)
            )
        )
        (local.set $c (i32.load8_u (global.get $currkey)))
        (global.set $currkey (i32.add (global.get $currkey) (i32.const 1)))
        (local.get $c)
    )

    (func $_word (result i32)
        (local $c i32)
        (local $d i32)
        (local.set $d (global.get $buffer)) ;; word_buffer
        (loop $while_blank
            (if (i32.eq (local.tee $c (call $_key)) (i32.const 0x5C)) ;; backslash
                (then
                    (loop $while_comment
                        (br_if $while_comment (i32.ne (local.tee $c (call $_key)) (i32.const 0x0A))) ;; newline
                        (br $while_blank)
                    )
                )
            )
            (br_if $while_blank (i32.le_u (local.get $c) (i32.const 0x20))) ;; space
        )
        (loop $while_word
            (i32.store8 (local.get $d) (local.get $c))
            (local.set $d (i32.add (local.get $d) (i32.const 1)))
            (br_if $while_word (i32.gt_u (local.tee $c (call $_key)) (i32.const 0x20))) ;; space
        )
        (i32.sub (local.get $d) (global.get $buffer))
    )

    (func $equal (param $n i32) (param $s i32) (param $t i32) (result i32)
        ;; do { if (*s++ != *t++) return 0; } while (--n);
        (loop $while
            (if (i32.ne (i32.load8_u (local.get $s)) (i32.load8_u (local.get $t)))
                (then (return (i32.const 0)))
            )
            (local.set $s (i32.add (local.get $s) (i32.const 1)))
            (local.set $t (i32.add (local.get $t) (i32.const 1)))
            (br_if $while (local.tee $n (i32.sub (local.get $n) (i32.const 1))))
        )
        (i32.const 1)
    )

    (func $memcpy (param $c i32) (param $d i32) (param $s i32) (result i32)
        (loop $copy  ;; `rep movsb` would be nice here
            (i32.store8 (local.get $d) (i32.load8_u (local.get $s)))
            (local.set $d (i32.add (local.get $d) (i32.const 1)))
            (local.set $s (i32.add (local.get $s) (i32.const 1)))
            (br_if $copy (i32.gt_s (local.tee $c (i32.sub (local.get $c) (i32.const 1))) (i32.const 0)))
        )
        (local.get $d)
    )

    (func $_number (param $n i32) (param $s i32) (result i32)
        (local $base i32)
        (local $c i32)
        (local $res i32)
        (local $sign i32)
        (local.set $base (i32.load (global.get $base))) ;; BASE
        (local.set $res (i32.const 0))
        (local.set $sign (i32.const 1))
        (i32.store (global.get $nwritten) (local.get $c)) ;; number of unparsed characters (0 = no error)
        (if (i32.eqz (local.tee $c (i32.load8_u (local.get $s)))) (then (return (local.get $res))))
        (if (i32.eq (local.get $c) (i32.const 0x2D))
            (then
                (local.set $sign (i32.const -1))
                (local.set $n (i32.sub (local.get $n) (i32.const 1))) ;; --n
                (local.set $s (i32.add (local.get $s) (i32.const 1))) ;; ++s
            )
        )
        (block $break
            (loop $while
                (local.set $res (i32.mul (local.get $res) (local.get $base))) ;; res *= base
                (local.set $c (i32.sub (i32.load8_u (local.get $s)) (i32.const 0x30))) ;; c = *s++ - '0'
                (br_if $break (i32.lt_s (local.get $c) (i32.const 0))) ;; if (c < 0) break;
                (if (i32.ge_u (local.get $c) (i32.const 0xA)) ;; if (c > '9') c -= 'A' - '0' - 10
                    (then
                        (local.set $c (i32.sub (local.get $c) (i32.const 0x7))) ;; c -= 7
                        (br_if $break (i32.lt_u (local.get $c) (i32.const 0xA))) ;; if (c < 10) break;
                    )
                )
                (br_if $break (i32.ge_u (local.get $c) (local.get $base))) ;; if (c >= base) break;
                (local.set $res (i32.add (local.get $res) (local.get $c))) ;; res += c
                (local.set $s (i32.add (local.get $s) (i32.const 1)))
                (br_if $while (local.tee $n (i32.sub (local.get $n) (i32.const 1))))
            )
        )
        (i32.store (global.get $nwritten) (local.get $n)) ;; number of unparsed characters (0 = no error)
        (local.get $res)
    )

    (func $_find (param $n i32) (param $s i32) (result i32)
        (local $word i32)
        (local.set $word (i32.load (global.get $latest))) ;; LATEST
        (block $break
            (loop $while
                (br_if $break (i32.eqz (local.get $word)))
                (if (i32.eq (i32.and (i32.load8_u offset=4 (local.get $word)) (i32.const 0x3F)) (local.get $n))
                    (then (br_if $break (call $equal (local.get $n) (local.get $s) (i32.add (local.get $word) (i32.const 5)))))
                )
                (local.set $word (i32.load (local.get $word)))  ;; word = word->link
                (br $while)
            )
        )
        (local.get $word)
    )

    (func $_>cfa (param $word i32) (result i32)
        (i32.add
            (i32.and
                (i32.add
                    (i32.and (i32.load8_u offset=4 (local.get $word)) (i32.const 0x1F))
                    (i32.const 8)  ;; link + flag + 3
                )
                (i32.const -4)  ;; align to 4 bytes
            )
            (local.get $word)
        )
    )

    (func $_docol (type 0)
        (call $pushrsp (global.get $ip))
        (global.set $ip (i32.add (global.get $cfa) (i32.const 4)))
        (return_call $next)
    )
    (elem (i32.const 0x0) $_docol)

    (data (i32.const 0x5044) "\00\00\00\00\04DROP\00\00\00\01\00\00\00")
    (func $drop (type 0)
        (global.set $sp (i32.add (global.get $sp) (i32.const 4)))
        (return_call $next)
    )
    (elem (i32.const 0x1) $drop)

    (data (i32.const 0x5054) "\44\50\00\00\04SWAP\00\00\00\02\00\00\00")
    (func $swap (type 0)
        (local $t i32)
        (local.set $t (i32.load offset=4 (global.get $sp)))
        (i32.store offset=4 (global.get $sp) (i32.load (global.get $sp)))
        (i32.store (global.get $sp) (local.get $t))
        (return_call $next)
    )
    (elem (i32.const 0x2) $swap)

    (data (i32.const 0x5064) "\54\50\00\00\03DUP\03\00\00\00")
    (func $dup (type 0)
        (call $push (i32.load (global.get $sp)))
        (return_call $next)
    )
    (elem (i32.const 0x3) $dup)

    (data (i32.const 0x5070) "\64\50\00\00\04OVER\00\00\00\04\00\00\00")
    (func $over (type 0)
        (call $push (i32.load offset=4 (global.get $sp)))
        (return_call $next)
    )
    (elem (i32.const 0x4) $over)

    (data (i32.const 0x5080) "\70\50\00\00\03ROT\05\00\00\00")
    (func $rot (type 0)
        (local $a i32)
        (local $b i32)
        (local $c i32)
        (local.set $a (call $pop))
        (local.set $b (call $pop))
        (local.set $c (call $pop))
        (call $push (local.get $b))
        (call $push (local.get $a))
        (call $push (local.get $c))
        (return_call $next)
    )
    (elem (i32.const 0x5) $rot)

    (data (i32.const 0x508c) "\80\50\00\00\04-ROT\00\00\00\06\00\00\00")
    (func $-rot (type 0)
        (local $a i32)
        (local $b i32)
        (local $c i32)
        (local.set $a (call $pop))
        (local.set $b (call $pop))
        (local.set $c (call $pop))
        (call $push (local.get $a))
        (call $push (local.get $c))
        (call $push (local.get $b))
        (return_call $next)
    )
    (elem (i32.const 0x6) $-rot)

    (data (i32.const 0x509c) "\8c\50\00\00\062DRROP\00\07\00\00\00")
    (func $2drrop (type 0)
        (global.set $sp (i32.add (global.get $sp) (i32.const 8)))
        (return_call $next)
    )
    (elem (i32.const 0x7) $2drrop)

    (data (i32.const 0x50ac) "\9c\50\00\00\042DUP\00\00\00\08\00\00\00")
    (func $2dup (type 0)
        (call $push (i32.load offset=4 (global.get $sp)))
        (call $push (i32.load offset=4 (global.get $sp)))
        (return_call $next)
    )
    (elem (i32.const 0x8) $2dup)

    (data (i32.const 0x50bc) "\ac\50\00\00\052SWAP\00\00\09\00\00\00")
    (func $2swap (type 0)
        (local $a i32)
        (local $b i32)
        (local $c i32)
        (local $d i32)
        (local.set $a (call $pop))
        (local.set $b (call $pop))
        (local.set $c (call $pop))
        (local.set $d (call $pop))
        (call $push (local.get $b))
        (call $push (local.get $a))
        (call $push (local.get $d))
        (call $push (local.get $c))
        (return_call $next)
    )
    (elem (i32.const 0x9) $2swap)

    (data (i32.const 0x50cc) "\bc\50\00\00\04?DUP\00\00\00\0a\00\00\00")
    (func $?dup (type 0)
        (local $a i32)
        (if (i32.eqz (local.tee $a (i32.load (global.get $sp))))
            (then (call $push (local.get $a)))
        )
        (return_call $next)
    )
    (elem (i32.const 0xa) $?dup)

    (data (i32.const 0x50dc) "\cc\50\00\00\021+\00\0b\00\00\00")
    (func $1+ (type 0)
        (i32.store (global.get $sp) (i32.add (i32.load (global.get $sp)) (i32.const 1)))
        (return_call $next)
    )
    (elem (i32.const 0xb) $1+)

    (data (i32.const 0x50e8) "\dc\50\00\00\021-\00\0c\00\00\00")
    (func $1- (type 0)
        (i32.store (global.get $sp) (i32.sub (i32.load (global.get $sp)) (i32.const 1)))
        (return_call $next)
    )
    (elem (i32.const 0xc) $1-)

    (data (i32.const 0x50f4) "\e8\50\00\00\024+\00\0d\00\00\00")
    (func $4+ (type 0)
        (i32.store (global.get $sp) (i32.add (i32.load (global.get $sp)) (i32.const 4)))
        (return_call $next)
    )
    (elem (i32.const 0xd) $4+)

    (data (i32.const 0x5100) "\f4\50\00\00\024-\00\0e\00\00\00")
    (func $4- (type 0)
        (i32.store (global.get $sp) (i32.sub (i32.load (global.get $sp)) (i32.const 4)))
        (return_call $next)
    )
    (elem (i32.const 0xe) $4-)

    (data (i32.const 0x510c) "\00\51\00\00\01+\00\00\0f\00\00\00")
    (func $+ (type 0)
        (i32.store offset=4 (global.get $sp) (i32.add (i32.load offset=4 (global.get $sp)) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0xf) $+)

    (data (i32.const 0x5118) "\0c\51\00\00\01-\00\00\10\00\00\00")
    (func $- (type 0)
        (i32.store offset=4 (global.get $sp) (i32.sub (i32.load offset=4 (global.get $sp)) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x10) $-)

    (data (i32.const 0x5124) "\18\51\00\00\01*\00\00\11\00\00\00")
    (func $* (type 0)
        (i32.store offset=4 (global.get $sp) (i32.mul (i32.load offset=4 (global.get $sp)) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x11) $*)

    (data (i32.const 0x5130) "\24\51\00\00\04/MOD\00\00\00\12\00\00\00")
    (func $/mod (type 0)
        (local $a i32)
        (local $b i32)
        (local.set $a (call $pop))
        (local.set $b (call $pop))
        (call $push (i32.rem_s (local.get $b) (local.get $a)))
        (call $push (i32.div_s (local.get $b) (local.get $a)))
        (return_call $next)
    )
    (elem (i32.const 0x12) $/mod)

    (data (i32.const 0x5140) "\30\51\00\00\01=\00\00\13\00\00\00")
    (func $= (type 0)
        (i32.store offset=4 (global.get $sp) (i32.eq (i32.load offset=4 (global.get $sp)) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x13) $=)

    (data (i32.const 0x514c) "\40\51\00\00\02<>\00\14\00\00\00")
    (func $<> (type 0)
        (i32.store offset=4 (global.get $sp) (i32.ne (i32.load offset=4 (global.get $sp)) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x14) $<>)

    (data (i32.const 0x5158) "\4c\51\00\00\01<\00\00\15\00\00\00")
    (func $< (type 0)
        (i32.store offset=4 (global.get $sp) (i32.lt_s (i32.load offset=4 (global.get $sp)) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x15) $<)

    (data (i32.const 0x5164) "\58\51\00\00\01>\00\00\16\00\00\00")
    (func $> (type 0)
        (i32.store offset=4 (global.get $sp) (i32.gt_s (i32.load offset=4 (global.get $sp)) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x16) $>)

    (data (i32.const 0x5170) "\64\51\00\00\02<=\00\17\00\00\00")
    (func $<= (type 0)
        (i32.store offset=4 (global.get $sp) (i32.le_s (i32.load offset=4 (global.get $sp)) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x17) $<=)

    (data (i32.const 0x517c) "\70\51\00\00\02>=\00\18\00\00\00")
    (func $>= (type 0)
        (i32.store offset=4 (global.get $sp) (i32.ge_s (i32.load offset=4 (global.get $sp)) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x18) $>=)

    (data (i32.const 0x5188) "\7c\51\00\00\020=\00\19\00\00\00")
    (func $0= (type 0)
        (i32.store (global.get $sp) (i32.eq (i32.load (global.get $sp)) (i32.const 0)))
        (return_call $next)
    )
    (elem (i32.const 0x19) $0=)

    (data (i32.const 0x5194) "\88\51\00\00\030<>\1a\00\00\00")
    (func $0<> (type 0)
        (i32.store (global.get $sp) (i32.ne (i32.load (global.get $sp)) (i32.const 0)))
        (return_call $next)
    )
    (elem (i32.const 0x1a) $0<>)

    (data (i32.const 0x51a0) "\94\51\00\00\020<\00\1b\00\00\00")
    (func $0< (type 0)
        (i32.store (global.get $sp) (i32.lt_s (i32.load (global.get $sp)) (i32.const 0)))
        (return_call $next)
    )
    (elem (i32.const 0x1b) $0<)

    (data (i32.const 0x51ac) "\a0\51\00\00\020>\00\1c\00\00\00")
    (func $0> (type 0)
        (i32.store (global.get $sp) (i32.gt_s (i32.load (global.get $sp)) (i32.const 0)))
        (return_call $next)
    )
    (elem (i32.const 0x1c) $0>)

    (data (i32.const 0x51b8) "\ac\51\00\00\030<=\1d\00\00\00")
    (func $0<= (type 0)
        (i32.store (global.get $sp) (i32.le_s (i32.load (global.get $sp)) (i32.const 0)))
        (return_call $next)
    )
    (elem (i32.const 0x1d) $0<=)

    (data (i32.const 0x51c4) "\b8\51\00\00\030>=\1e\00\00\00")
    (func $0>= (type 0)
        (i32.store (global.get $sp) (i32.ge_s (i32.load (global.get $sp)) (i32.const 0)))
        (return_call $next)
    )
    (elem (i32.const 0x1e) $0>=)

    (data (i32.const 0x51d0) "\c4\51\00\00\03AND\1f\00\00\00")
    (func $and (type 0)
        (i32.store offset=4 (global.get $sp) (i32.and (i32.load offset=4 (global.get $sp)) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x1f) $and)

    (data (i32.const 0x51dc) "\d0\51\00\00\02OR\00\20\00\00\00")
    (func $or (type 0)
        (i32.store offset=4 (global.get $sp) (i32.or (i32.load offset=4 (global.get $sp)) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x20) $or)

    (data (i32.const 0x51e8) "\dc\51\00\00\03XOR\21\00\00\00")
    (func $xor (type 0)
        (i32.store offset=4 (global.get $sp) (i32.xor (i32.load offset=4 (global.get $sp)) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x21) $xor)

    (data (i32.const 0x51f4) "\e8\51\00\00\06INVERT\00\22\00\00\00")
    (func $invert (type 0)
        (i32.store (global.get $sp) (i32.xor (i32.load (global.get $sp)) (i32.const -1)))
        (return_call $next)
    )
    (elem (i32.const 0x22) $invert)

    (data (i32.const 0x5204) "\f4\51\00\00\04EXIT\00\00\00\23\00\00\00")
    (func $exit (type 0)
        (global.set $ip (call $poprsp))
        (return_call $next)
    )
    (elem (i32.const 0x23) $exit)

    (data (i32.const 0x5214) "\04\52\00\00\03LIT\24\00\00\00")
    (func $lit (type 0)
        (call $push (i32.load (global.get $ip)))
        (global.set $ip (i32.add (global.get $ip) (i32.const 4)))
        (return_call $next)
    )
    (elem (i32.const 0x24) $lit)

    (data (i32.const 0x5220) "\14\52\00\00\01!\00\00\25\00\00\00")
    (func $! (type 0)
        (i32.store (call $pop) (call $pop))
        (return_call $next)
    )
    (elem (i32.const 0x25) $!)

    (data (i32.const 0x522c) "\20\52\00\00\01@\00\00\26\00\00\00")
    (func $@ (type 0)
        (call $push (i32.load (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x26) $@)

    (data (i32.const 0x5238) "\2c\52\00\00\02+!\00\27\00\00\00")
    (func $+! (type 0)
        (local $p i32)
        (i32.store (local.tee $p (call $pop)) (i32.add (i32.load (local.get $p)) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x27) $+!)

    (data (i32.const 0x5244) "\38\52\00\00\02-!\00\28\00\00\00")
    (func $-! (type 0)
        (local $p i32)
        (i32.store (local.tee $p (call $pop)) (i32.sub (i32.load (local.get $p)) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x28) $-!)

    (data (i32.const 0x5250) "\44\52\00\00\02C!\00\29\00\00\00")
    (func $c! (type 0)
        (i32.store8 (call $pop) (call $pop))
        (return_call $next)
    )
    (elem (i32.const 0x29) $c!)

    (data (i32.const 0x525c) "\50\52\00\00\02C@\00\2a\00\00\00")
    (func $c@ (type 0)
        (call $push (i32.load8_u (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x2a) $c@)

    (data (i32.const 0x5268) "\5c\52\00\00\05CMOVE\00\00\2b\00\00\00")
    (func $cmove (type 0)
        (call $memcpy (call $pop) (call $pop) (call $pop))
        (return_call $next)
    )
    (elem (i32.const 0x2b) $cmove)

    (data (i32.const 0x5278) "\68\52\00\00\05STATE\00\00\2c\00\00\00")
    (func $state (type 0)
        (call $push (global.get $state))
        (return_call $next)
    )
    (elem (i32.const 0x2c) $state)

    (data (i32.const 0x5288) "\78\52\00\00\04HERE\00\00\00\2d\00\00\00")
    (func $here (type 0)
        (call $push (global.get $here))
        (return_call $next)
    )
    (elem (i32.const 0x2d) $here)

    (data (i32.const 0x5298) "\88\52\00\00\06LATEST\00\2e\00\00\00")
    (func $latest (type 0)
        (call $push (global.get $latest))
        (return_call $next)
    )
    (elem (i32.const 0x2e) $latest)

    (data (i32.const 0x52a8) "\98\52\00\00\02S0\00\2f\00\00\00")
    (func $s0 (type 0)
        (call $push (global.get $s0))
        (return_call $next)
    )
    (elem (i32.const 0x2f) $s0)

    (data (i32.const 0x52b4) "\a8\52\00\00\04BASE\00\00\00\30\00\00\00")
    (func $base (type 0)
        (call $push (global.get $base))
        (return_call $next)
    )
    (elem (i32.const 0x30) $base)

    (data (i32.const 0x52c4) "\b4\52\00\00\07VERSION\31\00\00\00")
    (func $version (type 0)
        (call $push (i32.const 47))
        (return_call $next)
    )
    (elem (i32.const 0x31) $version)

    (data (i32.const 0x52d4) "\c4\52\00\00\02R0\00\32\00\00\00")
    (func $r0 (type 0)
        (call $push (global.get $r0))
        (return_call $next)
    )
    (elem (i32.const 0x32) $r0)

    (data (i32.const 0x52e0) "\d4\52\00\00\05DOCOL\00\00\33\00\00\00")
    (func $docol (type 0)
        (call $push (i32.const 0))
        (return_call $next)
    )
    (elem (i32.const 0x33) $docol)

    (data (i32.const 0x52f0) "\e0\52\00\00\07F_IMMED\33\00\00\00")
    (func $f_immed (type 0)
        (call $push (global.get $f_immed))
        (return_call $next)
    )
    (elem (i32.const 0x33) $f_immed)

    (data (i32.const 0x5300) "\f0\52\00\00\08F_HIDDEN\00\00\00\34\00\00\00")
    (func $f_hidden (type 0)
        (call $push (global.get $f_hidden))
        (return_call $next)
    )
    (elem (i32.const 0x34) $f_hidden)

    (data (i32.const 0x5314) "\00\53\00\00\09F_LENMASK\00\00\35\00\00\00")
    (func $f_lenmask (type 0)
        (call $push (global.get $f_lenmask))
        (return_call $next)
    )
    (elem (i32.const 0x35) $f_lenmask)

    (data (i32.const 0x5328) "\14\53\00\00\02>R\00\36\00\00\00")
    (func $>r (type 0)
        (call $pushrsp (call $pop))
        (return_call $next)
    )
    (elem (i32.const 0x36) $>r)

    (data (i32.const 0x5334) "\28\53\00\00\02R>\00\37\00\00\00")
    (func $r> (type 0)
        (call $push (call $poprsp))
        (return_call $next)
    )
    (elem (i32.const 0x37) $r>)

    (data (i32.const 0x5340) "\34\53\00\00\04RSP@\00\00\00\38\00\00\00")
    (func $rsp@ (type 0)
        (call $push (global.get $rsp))
        (return_call $next)
    )
    (elem (i32.const 0x38) $rsp@)

    (data (i32.const 0x5350) "\40\53\00\00\04RSP!\00\00\00\39\00\00\00")
    (func $rsp! (type 0)
        (global.set $rsp (call $pop))
        (return_call $next)
    )
    (elem (i32.const 0x39) $rsp!)

    (data (i32.const 0x5360) "\50\53\00\00\05RDROP\00\00\3a\00\00\00")
    (func $rdrop (type 0)
        (global.set $rsp (i32.add (global.get $rsp) (i32.const 4)))
        (return_call $next)
    )
    (elem (i32.const 0x3a) $rdrop)

    (data (i32.const 0x5370) "\60\53\00\00\04DSP@\00\00\00\3b\00\00\00")
    (func $dsp@ (type 0)
        (call $push (global.get $sp))
        (return_call $next)
    )
    (elem (i32.const 0x3b) $dsp@)

    (data (i32.const 0x5380) "\70\53\00\00\04DSP!\00\00\00\3c\00\00\00")
    (func $dsp! (type 0)
        (global.set $sp (call $pop))
        (return_call $next)
    )
    (elem (i32.const 0x3c) $dsp!)

    (data (i32.const 0x5390) "\80\53\00\00\03KEY\3d\00\00\00")
    (func $key (type 0)
        (call $push (call $_key))
        (return_call $next)
    )
    (elem (i32.const 0x3d) $key)

    (data (i32.const 0x539c) "\90\53\00\00\04EMIT\00\00\00\3e\00\00\00")
    (func $emit (type 0)
        (i32.store offset=0 (global.get $iovec) (global.get $sp))
        (i32.store offset=4 (global.get $iovec) (i32.const 1))
        (drop (call $fd_write (i32.const 1) (global.get $iovec) (i32.const 1) (global.get $nwritten)))
        (global.set $sp (i32.add (global.get $sp) (i32.const 4)))
        (return_call $next)
    )
    (elem (i32.const 0x3e) $emit)

    (data (i32.const 0x53ac) "\9c\53\00\00\04WORD\00\00\00\3f\00\00\00")
    (func $word (type 0)
        (call $push (global.get $buffer))
        (call $push (call $_word (call $pop) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x3f) $word)

    (data (i32.const 0x53bc) "\ac\53\00\00\06NUMBER\00\40\00\00\00")
    (func $number (type 0)
        (call $push (call $_number (call $pop) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x40) $number)

    (data (i32.const 0x53cc) "\bc\53\00\00\04FIND\00\00\00\41\00\00\00")
    (func $find (type 0)
        (call $push (call $_find (call $pop) (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x41) $find)

    (data (i32.const 0x53dc) "\cc\53\00\00\04>CFA\00\00\00\42\00\00\00")
    (func $>cfa (type 0)
        (call $push (call $_>cfa (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x42) $>cfa)

    (data (i32.const 0x53ec) "\dc\53\00\00\04>DFA\00\00\00\00\00\00\00\e8\53\00\00\fc\50\00\00\10\52\00\00")

    (data (i32.const 0x5408) "\ec\53\00\00\06CREATE\00\43\00\00\00")
    (func $create (type 0)
        (local $c i32) ;; count (%ecx)
        (local $d i32) ;; destination (%edi)
        (i32.store (local.tee $d (i32.load (global.get $here))) (i32.load (global.get $latest))) ;; *HERE = *LATEST
        (i32.store (global.get $latest) (local.get $d)) ;; LATEST = HERE
        (i32.store8 (local.tee $d (i32.add (local.get $d) (i32.const 4))) (local.tee $c (call $pop))) ;; set flags to len
        (i32.store (global.get $here) (i32.and (i32.add (call $memcpy (local.get $c) (local.get $d) (call $pop)) (i32.const 3)) (i32.const -4))) ;; HERE = d (aligned)
        (return_call $next)
    )
    (elem (i32.const 0x43) $create)

    (data (i32.const 0x5418) "\08\54\00\00\01,\00\00\44\00\00\00")
    (func $comma (type 0)
        (local $d i32)
        (i32.store (local.tee $d (global.get $here)) (call $pop))
        (i32.store (global.get $here) (i32.add (local.get $d) (i32.const 4)))
        (return_call $next)
    )
    (elem (i32.const 0x44) $comma)

    (data (i32.const 0x5424) "\18\54\00\00\01[\00\00\45\00\00\00")
    (func $lbrac (type 0)
        (i32.store (global.get $state) (i32.const 0))
        (return_call $next)
    )
    (elem (i32.const 0x45) $lbrac)

    (data (i32.const 0x5430) "\24\54\00\00\01]\00\00\46\00\00\00")
    (func $rbrac (type 0)
        (i32.store (global.get $state) (i32.const 1))
        (return_call $next)
    )
    (elem (i32.const 0x46) $rbrac)

    (data (i32.const 0x543c) "\30\54\00\00\89IMMEDIATE\00\00\47\00\00\00")
    (func $immediate (type 0)
        (local $latest i32)
        (i32.store8 offset=4 (local.tee $latest (i32.load (global.get $latest))) (i32.xor (i32.load8_u offset=4 (local.get $latest)) (global.get $f_immed)))
        (return_call $next)
    )
    (elem (i32.const 0x47) $immediate)

    (data (i32.const 0x5450) "\3c\54\00\00\06HIDDEN\00\48\00\00\00")
    (func $hidden (type 0)
        (local $p i32)
        (i32.store8 offset=4 (local.get $p)
            (i32.xor
                (i32.load8_u offset=4 (local.tee $p (call $pop)))
                (global.get $f_hidden)
            )
        )
        (return_call $next)
    )
    (elem (i32.const 0x48) $hidden)

    (data (i32.const 0x5460) "\50\54\00\00\04HIDE\00\00\00\00\00\00\00\b8\53\00\00\d8\53\00\00\5c\54\00\00\10\52\00\00")
    (data (i32.const 0x5480) "\60\54\00\00\01:\00\00\00\00\00\00\b8\53\00\00\14\54\00\00\1c\52\00\00\ec\52\00\00\20\54\00\00\a4\52\00\00\34\52\00\00\5c\54\00\00\38\54\00\00\10\52\00\00")
    (data (i32.const 0x54b4) "\80\54\00\00\81;\00\00\00\00\00\00\1c\52\00\00\10\52\00\00\20\54\00\00\a4\52\00\00\34\52\00\00\5c\54\00\00\2c\54\00\00\10\52\00\00")

    (data (i32.const 0x54e0) "\b4\54\00\00\06BRANCH\00\49\00\00\00")
    (func $branch (type 0)
        (global.set $ip (i32.add (global.get $ip) (i32.load (global.get $ip))))
        (return_call $next)
    )
    (elem (i32.const 0x49) $branch)

    (data (i32.const 0x54f0) "\e0\54\00\00\070BRANCH\4a\00\00\00")
    (func $0branch (type 0)
        (if (i32.eqz (call $pop))
           (then (return_call $branch))
           (else (global.set $ip (i32.add (global.get $ip) (i32.const 4))))
        )
        (return_call $next)
    )
    (elem (i32.const 0x4a) $0branch)

    (data (i32.const 0x5500) "\f0\54\00\00\09LITSTRING\00\00\4b\00\00\00")
    (func $litstring (type 0)
        (local $len i32)
        (local.set $len (i32.load (global.get $ip)))
        (global.set $ip (i32.add (global.get $ip) (i32.const 4)))
        (call $push (global.get $sp))
        (call $push (local.get $len))
        (global.set $ip (i32.add (global.get $ip) (i32.and (i32.add (local.get $len) (i32.const 3)) (i32.const -4))))
        (return_call $next)
    )
    (elem (i32.const 0x4b) $litstring)

    (data (i32.const 0x5514) "\00\55\00\00\04TELL\00\00\00\4c\00\00\00")
    (func $tell (type 0)
        (i32.store offset=4 (global.get $iovec) (call $pop))
        (i32.store offset=0 (global.get $iovec) (call $pop))
        (drop (call $fd_write (i32.const 1) (global.get $iovec) (i32.const 1) (global.get $nwritten)))
        (return_call $next)
    )
    (elem (i32.const 0x4c) $tell)

    (data (i32.const 0x5524) "\14\55\00\00\09INTERPRET\00\00\4d\00\00\00")
    (func $interpret (type 0)
        (local $c i32)
        (local $w i32)
        (if (local.tee $w (call $_find (local.tee $c (call $_word)) (global.get $buffer)))
            (then ;; found word => execute or append
                (if (i32.or
                        (i32.and (i32.load8_u offset=4 (local.get $w)) (global.get $f_immed))
                        (i32.eqz (i32.load (global.get $state)))
                    )
                    (then
                        (global.set $cfa (call $_>cfa (local.get $w)))
                        (return_call_indirect (type 0) (i32.load (global.get $cfa)))
                    )
                )
                (i32.store (i32.load (global.get $here)) (local.get $w))
                (i32.store (global.get $here) (i32.add (i32.load (global.get $here)) (i32.const 4)))
            )
            (else
                (local.set $w (call $_number (local.get $c) (global.get $buffer)))
                (if (i32.load (global.get $nwritten)) ;; unconsumed input => parse error
                    (then
                        (i32.store offset=0 (global.get $iovec) (i32.const 0x5538)) ;; "PARSE ERROR: "
                        (i32.store offset=4 (global.get $iovec) (i32.const 13)) ;; len("PARSE ERROR: ")
                        (drop (call $fd_write (i32.const 2) (global.get $iovec) (i32.const 1) (global.get $nwritten)))
                        (i32.store offset=0 (global.get $iovec) (global.get $buffer))
                        (i32.store offset=4 (global.get $iovec) (local.get $c))
                        (drop (call $fd_write (i32.const 2) (global.get $iovec) (i32.const 1) (global.get $nwritten)))
                        (i32.store offset=0 (global.get $iovec) (i32.const 0x5545)) ;; "\n"
                        (i32.store offset=4 (global.get $iovec) (i32.const 1)) ;; len("\n")
                        (drop (call $fd_write (i32.const 2) (global.get $iovec) (i32.const 1) (global.get $nwritten)))
                    )
                    (else
                        (if (i32.load (global.get $state)) ;; compile number
                            (then
                                (i32.store (i32.load (global.get $here)) (i32.const 0x521C)) ;; LIT cfa
                                (i32.store offset=4 (i32.load (global.get $here)) (local.get $w))
                                (i32.store (global.get $here) (i32.add (i32.load (global.get $here)) (i32.const 8)))
                            )
                            (else (call $push (local.get $w)))
                        )
                    )
                )
            )
        )
        (return_call $next)
    )
    (elem (i32.const 0x4d) $interpret)

    (data (i32.const 0x5538) "PARSE ERROR: \0A\00\00")
    (data (i32.const 0x5548) "\24\55\00\00\04QUIT\00\00\00\00\00\00\00\dc\52\00\00\5c\53\00\00\34\55\00\00\ec\54\00\00\f8\ff\ff\ff")

    (data (i32.const 0x556c) "\48\55\00\00\04CHAR\00\00\00\4e\00\00\00")
    (func $char (type 0)
        (drop (call $_word))
        (call $push (i32.load8_u (global.get $buffer)))
        (return_call $next)
    )
    (elem (i32.const 0x4e) $char)

    (data (i32.const 0x557c) "\6c\55\00\00\07EXECUTE\4f\00\00\00")
    (func $execute (type 0)
        (return_call_indirect (type 0) (i32.load (call $pop)))
        (return_call $next)
    )
    (elem (i32.const 0x4f) $execute)

    (start $next)
)