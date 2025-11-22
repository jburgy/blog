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
    ;;   0x5040 -       : word definitions (\00\00\00\00 4DROP\00\00\00 \02\00\00\00)

    (memory (export "memory") 1)
    (table 80 funcref)

    (global $ip      (mut i32) (i32.const 0x50e8))  ;; instruction pointer (initialized)
    (global $sp      (mut i32) (i32.const 0x2000))  ;; data stack pointer (grows downward)
    (global $rsp     (mut i32) (i32.const 0x4000))  ;; return stack pointer (grows downward)
    
    (global $currkey (mut i32) (i32.const 0x4000))  ;; current place in input buffer (next character to read)
    (global $buftop  (mut i32) (i32.const 0x4000))  ;; last valid data in input buffer + 1
    (global $iovec    i32      (i32.const 0x5014))
    (global $nwritten i32      (i32.const 0x501C))
    (global $buffer   i32      (i32.const 0x5020))  ;; word_buffer

    (data (i32.const 0x5000) "\00\00\00\00")        ;; STATE initialized to 0 (interpreting)
    (data (i32.const 0x5008) "\d8\50\00\00")        ;; LATEST initialized to 0x50d8
    (data (i32.const 0x500C) "\00\00\20\00")        ;; S0 initialized to top of data stack
    (data (i32.const 0x5010) "\0A\00\00\00")        ;; BASE initialized to 10

    (global $version   i32 (i32.const 0x002f))
    (global $r0        i32 (i32.const 0x4000))
    (global $f_immed   i32 (i32.const 0x0080))
    (global $f_hidden  i32 (i32.const 0x0020))
    (global $f_lenmask i32 (i32.const 0x001F))

    (type (;0;) (func)) 

    (func $next (type 0)
        (local $t i32)
        (local.set $t (i32.load (global.get $ip)))
        (global.set $ip (i32.add (global.get $ip) (i32.const 4)))
        (return_call_indirect (type 0) (local.get $t))
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

    (func $_key (result i32)
        (local $c i32)
        (block $break
            (loop $while
                (br_if $break (i32.lt_u (global.get $currkey) (global.get $buftop)))
                (global.set $currkey (i32.const 0x4000))
                (i32.store offset=0 (global.get $iovec) (global.get $currkey)) ;; TIB
                (i32.store offset=4 (global.get $iovec) (i32.const 0x1000)) ;; BUFFER_SIZE
                (local.set $c (call $fd_read (i32.const 0) (global.get $iovec) (i32.const 1) (global.get $nwritten)))
                (if (i32.eqz (local.get $c))
                    (then nop) ;; Errno::Success
                    (else (call $proc_exit (local.get $c)))
                )                
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
            (br_if $while (i32.ge_s (local.tee $n (i32.sub (local.get $n) (i32.const 1))) (i32.const 0)))
        )
        (i32.const 1)
    )

    (func $_number (param $n i32) (param $s i32) (param $base i32) (result i32)
        (local $c i32)
        (local $res i32)
        (local $sign i32)
        (local.set $res (i32.const 0))
        (local.set $sign (i32.const 1))
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
                (br_if $while (i32.gt_s (local.tee $n (i32.sub (local.get $n) (i32.const 1))) (i32.const 0)))
            )
        )
        (local.get $res)
    )

    (func $_find (param $n i32) (param $s i32) (result i32)
        (local $word i32)
        (local.set $word (i32.load (i32.const 0x5008))) ;; LATEST
        (block $break
            (loop $while
                (br_if $break (i32.eqz (local.get $word)))
                (if (i32.eq (i32.and (i32.load8_u offset=4 (local.get $word)) (i32.const 0x3F)) (local.get $n))
                    (then
                        (if (i32.eqz (call $equal (local.get $n) (local.get $s) (i32.add (local.get $word) (i32.const 5))))
                            (then nop)
                            (else (br $break))
                        )
                    )
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

    (data (i32.const 0x5040) "\00\00\00\00\04DROP\00\00\00\01\00\00\00")
    (func $drop (type 0)
        (global.set $sp (i32.add (global.get $sp) (i32.const 4)))
        (return_call $next)
    )
    (elem (i32.const 0x1) $drop)

    (data (i32.const 0x5050) "\40\50\00\00\04SWAP\00\00\00\02\00\00\00")
    (func $swap (type 0)
        (local $t i32)
        (local.set $t (i32.load offset=4 (global.get $sp)))
        (i32.store offset=4 (global.get $sp) (i32.load (global.get $sp)))
        (i32.store (global.get $sp) (local.get $t))
        (return_call $next)
    )
    (elem (i32.const 0x2) $swap)

    (data (i32.const 0x5060) "\50\50\00\00\03DUP\03\00\00\00")
    (func $dup (type 0)
        (call $push (i32.load (global.get $sp)))
        (return_call $next)
    )
    (elem (i32.const 0x3) $dup)

    (data (i32.const 0x506c) "\60\50\00\00\04EXIT\00\00\00\04\00\00\00")
    (func $exit (type 0)
    )
    (elem (i32.const 0x4) $exit)

    (data (i32.const 0x507c) "\6c\50\00\00\03LIT\05\00\00\00")
    (func $lit (type 0)
        (call $push (i32.load (global.get $ip)))
        (global.set $ip (i32.add (global.get $ip) (i32.const 4)))
        (return_call $next)
    )
    (elem (i32.const 0x5) $lit)

    (data (i32.const 0x5088) "\7c\50\00\00\02R0\00\06\00\00\00")
    (func $r0 (type 0)
        (call $push (global.get $r0))
        (return_call $next)
    )
    (elem (i32.const 0x6) $r0)

    (data (i32.const 0x5094) "\88\50\00\00\04RSP!\00\00\00\07\00\00\00")
    (func $rsp! (type 0)
        (global.set $rsp (call $pop))
        (return_call $next)
    )
    (elem (i32.const 0x7) $rsp!)

    (data (i32.const 0x50a4) "\94\50\00\00\04EMIT\00\00\00\08\00\00\00")
    (func $emit (type 0)
        (i32.store offset=0 (global.get $iovec) (global.get $sp))
        (i32.store offset=4 (global.get $iovec) (i32.const 1))        
        (drop (call $fd_write (i32.const 1) (global.get $iovec) (i32.const 1) (global.get $nwritten)))
        (global.set $sp (i32.add (global.get $sp) (i32.const 4)))
        (return_call $next)
    )
    (elem (i32.const 0x8) $emit)

    (data (i32.const 0x50b4) "\a4\50\00\00\06BRANCH\00\09\00\00\00")
    (func $branch (type 0)
        (global.set $ip (i32.add (global.get $ip) (i32.load (global.get $ip))))
        (return_call $next)
    )
    (elem (i32.const 0x9) $branch)

    (data (i32.const 0x50c4) "\b4\50\00\00\09INTERPRET\00\00\0a\00\00\00")
    (func $interpret (type 0)
        (local $c i32)
        (local $w i32)
        (if (i32.eqz (local.tee $w (call $_find (local.tee $c (call $_word)) (global.get $buffer))))
            (then (call $push (call $_number (local.get $c) (global.get $buffer) (i32.load (i32.const 0x5010)))))
            (else (return_call_indirect (type 0) (i32.load (call $_>cfa (local.get $w)))))
        )
        (return_call $next)
    )
    (elem (i32.const 0xa) $interpret)

    (data (i32.const 0x50d8) "\c4\50\00\00\04QUIT\00\00\00\00\00\00\00\06\00\00\00\07\00\00\00\0a\00\00\00\09\00\00\00\f8\ff\ff\ff")

    (start $next)
)