;; A port of jonesforth to WebAssembly
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

    (memory (export "memory") 2)

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
    (data (i32.const 0x5004) "\fc\56\00\00")        ;; HERE initialized to 0x56ec
    (data (i32.const 0x5008) "\e8\56\00\00")        ;; LATEST initialized to 0x56d8
    (data (i32.const 0x500C) "\00\20\00\00")        ;; S0 initialized to top of data stack
    (data (i32.const 0x5010) "\0a\00\00\00")        ;; BASE initialized to 10
    (data (i32.const 0x5040) "\88\56\00\00")        ;; cold_start initialized to >DFA of QUIT

    (global $f_immed   i32 (i32.const 0x0080))
    (global $f_hidden  i32 (i32.const 0x0020))
    (global $f_lenmask i32 (i32.const 0x001F))

    (func $_key (result i32)
        (local $c i32)
        (block $break
            (loop $while
                (br_if $break (i32.lt_u (global.get $currkey) (global.get $buftop)))
                (global.set $currkey (i32.const 0x4000))
                (i32.store offset=0 (global.get $iovec) (global.get $currkey)) ;; TIB
                (i32.store offset=4 (global.get $iovec) (i32.const 0x1000)) ;; BUFFER_SIZE
                (if (local.tee $c (call $fd_read (i32.const 0) (global.get $iovec) (i32.const 1) (global.get $nwritten)))
                    (then (call $proc_exit (local.get $c)))
                )
                (global.set $buftop (i32.add (global.get $currkey) (i32.load (global.get $nwritten))))
                (br $while)
            )
        )
        (local.set $c (i32.load8_u (global.get $currkey)))
        (global.set $currkey (i32.add (global.get $currkey) (i32.const 1)))
        (local.get $c)
    )

    (func $write (param i32 i32 i32)
        (i32.store offset=0 (global.get $iovec) (local.get 1))
        (i32.store offset=4 (global.get $iovec) (local.get 2))
        (drop (call $fd_write (local.get 0) (global.get $iovec) (i32.const 1) (global.get $nwritten)))
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
        (i32.mul (local.get $res) (local.get $sign))
    )

    (func $_find (param $n i32) (param $s i32) (result i32)
        (local $word i32)
        (local.set $word (i32.load (global.get $latest))) ;; LATEST
        (block $break
            (loop $while
                (if (i32.eq (i32.and (i32.load8_u offset=4 (local.get $word)) (i32.const 0x3F)) (local.get $n))
                    (then (br_if $break (call $equal (local.get $n) (local.get $s) (i32.add (local.get $word) (i32.const 5)))))
                )
                (br_if $while (local.tee $word (i32.load (local.get $word))))  ;; word = word->link
            )
        )
        (local.get $word)
    )

    (func $_>cfa (param $word i32) (result i32)
        (i32.add
            (i32.and
                (i32.add
                    (i32.and (i32.load8_u offset=4 (local.get $word)) (global.get $f_lenmask))
                    (i32.const 8)  ;; link + flag + 3
                )
                (i32.const -4)  ;; align to 4 bytes
            )
            (local.get $word)
        )
    )

    (func $forth (export "_start")
        (local $cfa i32) ;; code field address of the current word to execute (%eax)
        (local $ip i32)  ;; instruction pointer (%esi)
        (local $sp i32)  ;; data stack pointer (grows downward) (%esp)
        (local $rsp i32) ;; return stack pointer (grows downward) (%ebp)
        (local i32 i32 i32 i32)

        (local.set $ip (i32.const 0x5040)) ;; initial code field address (%eax)
        (local.set $sp (i32.const 0x2000)) ;; initial data stack pointer
        (local.set $rsp (i32.const 0x4000)) ;; initial return stack pointer

        (loop $next
            (local.set $cfa (i32.load (local.get $ip)))             ;; cfa = *ip
            (local.set $ip (i32.add (local.get $ip) (i32.const 4))) ;; ip += 4

            (loop $dispatch

            (block $syscall1   (block $syscall2   (block $syscall3   (block $execute    (block $char       (block $interpret  (block $tell       (block $litstring  (block $0branch
            (block $branch     (block $'          (block $hidden     (block $immediate  (block $rbrac      (block $lbrac      (block $comma      (block $create     (block $>cfa
            (block $find       (block $number     (block $word       (block $emit       (block $key        (block $dsp!       (block $dsp@       (block $rdrop      (block $rsp!
            (block $rsp@       (block $r>         (block $>r         (block $o_nonblock (block $o_append   (block $o_trunc    (block $o_excl     (block $o_creat    (block $o_rdwr
            (block $o_wronly   (block $o_rdonly   (block $sys_brk    (block $sys_creat  (block $sys_write  (block $sys_read   (block $sys_close  (block $sys_open   (block $sys_exit
            (block $f_lenmask  (block $f_hidden   (block $f_immed    (block $docol      (block $r0         (block $version    (block $base       (block $s0         (block $latest
            (block $here       (block $state      (block $cmove      (block $c@c!       (block $c@         (block $c!         (block $-!         (block $+!         (block $@
            (block $!          (block $lit        (block $exit       (block $invert     (block $xor        (block $or         (block $and        (block $0>=        (block $0<=
            (block $0>         (block $0<         (block $0<>        (block $0=         (block $>=         (block $<=         (block $>          (block $<          (block $<>
            (block $=          (block $/mod       (block $*          (block $-          (block $+          (block $4-         (block $4+         (block $1-         (block $1+
            (block $?dup       (block $2swap      (block $2dup       (block $2drop      (block $-rot       (block $rot        (block $over       (block $dup        (block $swap
            (block $drop       (block $_docol

            (br_table
                $_docol    $drop      $swap     $dup       $over      $rot       $-rot      $2drop      $2dup
                $2swap     $?dup      $1+       $1-        $4+        $4-        $+         $-          $*
                $/mod      $=         $<>       $<         $>         $<=        $>=        $0=         $0<>
                $0<        $0>        $0<=      $0>=       $and       $or        $xor       $invert     $exit
                $lit       $!         $@        $+!        $-!        $c!        $c@        $c@c!       $cmove
                $state     $here      $latest   $s0        $base      $version   $r0        $docol      $f_immed
                $f_hidden  $f_lenmask $sys_exit $sys_open  $sys_close $sys_read  $sys_write $sys_creat  $sys_brk
                $o_rdonly  $o_wronly  $o_rdwr   $o_creat   $o_excl    $o_trunc   $o_append  $o_nonblock $>r
                $r>        $rsp@      $rsp!     $rdrop     $dsp@      $dsp!      $key       $emit       $word
                $number    $find      $>cfa     $create    $comma     $lbrac     $rbrac     $immediate  $hidden
                $'         $branch    $0branch  $litstring $tell      $interpret $char      $execute    $syscall3
                $syscall2 $syscall1 (i32.load (local.get $cfa)))
            )

            ;; _docol
            (i32.store (local.tee $rsp (i32.sub (local.get $rsp) (i32.const 4))) (local.get $ip))
            (local.set $ip (i32.add (local.get $cfa) (i32.const 4)))
            (br $next))

            ;; drop
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; swap
            (local.set 4 (i32.load offset=4 (local.get $sp)))
            (i32.store offset=4 (local.get $sp) (i32.load (local.get $sp)))
            (i32.store (local.get $sp) (local.get 4))
            (br $next))

            ;; dup
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.load offset=4 (local.get $sp)))
            (br $next))

            ;; over
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.load offset=8 (local.get $sp)))
            (br $next))

            ;; rot
            (local.set 4 (i32.load offset=0 (local.get $sp)))
            (local.set 5 (i32.load offset=4 (local.get $sp)))
            (local.set 6 (i32.load offset=8 (local.get $sp)))
            (i32.store offset=8 (local.get $sp) (local.get 5))
            (i32.store offset=4 (local.get $sp) (local.get 4))
            (i32.store offset=0 (local.get $sp) (local.get 6))
            (br $next))

            ;; -rot
            (local.set 4 (i32.load offset=0 (local.get $sp)))
            (local.set 5 (i32.load offset=4 (local.get $sp)))
            (local.set 6 (i32.load offset=8 (local.get $sp)))
            (i32.store offset=8 (local.get $sp) (local.get 4))
            (i32.store offset=4 (local.get $sp) (local.get 6))
            (i32.store offset=0 (local.get $sp) (local.get 5))
            (br $next))

            ;; 2drop
            (local.set $sp (i32.add (local.get $sp) (i32.const 8)))
            (br $next))

            ;; 2dup
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.load offset=8 (local.get $sp)))
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.load offset=8 (local.get $sp)))
            (br $next))

            ;; 2swap
            (local.set 4 (i32.load offset=0 (local.get $sp)))
            (local.set 5 (i32.load offset=4 (local.get $sp)))
            (local.set 6 (i32.load offset=8 (local.get $sp)))
            (local.set 7 (i32.load offset=12 (local.get $sp)))
            (i32.store offset=12 (local.get $sp) (local.get 5))
            (i32.store offset=8 (local.get $sp) (local.get 4))
            (i32.store offset=4 (local.get $sp) (local.get 7))
            (i32.store offset=0 (local.get $sp) (local.get 6))
            (br $next))

            ;; ?dup
            (if (local.tee 4 (i32.load (local.get $sp)))
                (then (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (local.get 4)))
            )
            (br $next))

            ;; 1+
            (i32.store (local.get $sp) (i32.add (i32.load (local.get $sp)) (i32.const 1)))
            (br $next))

            ;; 1-
            (i32.store (local.get $sp) (i32.sub (i32.load (local.get $sp)) (i32.const 1)))
            (br $next))

            ;; 4+
            (i32.store (local.get $sp) (i32.add (i32.load (local.get $sp)) (i32.const 4)))
            (br $next))

            ;; 4-
            (i32.store (local.get $sp) (i32.sub (i32.load (local.get $sp)) (i32.const 4)))
            (br $next))

            ;; +
            (i32.store offset=4 (local.get $sp) (i32.add (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp))))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; -
            (i32.store offset=4 (local.get $sp) (i32.sub (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp))))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; *
            (i32.store offset=4 (local.get $sp) (i32.mul (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp))))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; /mod
            (local.set 4 (i32.load offset=4 (local.get $sp)))
            (local.set 5 (i32.load offset=0 (local.get $sp)))
            (i32.store offset=4 (local.get $sp) (i32.rem_s (local.get 4) (local.get 5))) ;; mod
            (i32.store offset=0 (local.get $sp) (i32.div_s (local.get 4) (local.get 5))) ;; /
            (br $next))

            ;; =
            (i32.store offset=4 (local.get $sp) (i32.eq (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp))))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; <>
            (i32.store offset=4 (local.get $sp) (i32.ne (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp))))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; <
            (i32.store offset=4 (local.get $sp) (i32.lt_s (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp))))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; >
            (i32.store offset=4 (local.get $sp) (i32.gt_s (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp))))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; <=
            (i32.store offset=4 (local.get $sp) (i32.le_s (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp))))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; >=
            (i32.store offset=4 (local.get $sp) (i32.ge_s (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp))))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; 0=
            (i32.store (local.get $sp) (i32.eqz (i32.load (local.get $sp))))
            (br $next))

            ;; 0<>
            (i32.store (local.get $sp) (i32.ne (i32.load (local.get $sp)) (i32.const 0)))
            (br $next))

            ;; 0<
            (i32.store (local.get $sp) (i32.lt_s (i32.load (local.get $sp)) (i32.const 0)))
            (br $next))

            ;; 0>
            (i32.store (local.get $sp) (i32.gt_s (i32.load (local.get $sp)) (i32.const 0)))
            (br $next))

            ;; 0<=
            (i32.store (local.get $sp) (i32.le_s (i32.load (local.get $sp)) (i32.const 0)))
            (br $next))

            ;; 0>=
            (i32.store (local.get $sp) (i32.ge_s (i32.load (local.get $sp)) (i32.const 0)))
            (br $next))

            ;; and
            (i32.store offset=4 (local.get $sp) (i32.and (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp))))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; or
            (i32.store offset=4 (local.get $sp) (i32.or (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp))))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; xor
            (i32.store offset=4 (local.get $sp) (i32.xor (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp))))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; invert
            (i32.store (local.get $sp) (i32.xor (i32.load (local.get $sp)) (i32.const -1)))
            (br $next))

            ;; exit
            (local.set $ip (i32.load (local.get $rsp)))
            (local.set $rsp (i32.add (local.get $rsp) (i32.const 4)))
            (br $next))

            ;; lit
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.load (local.get $ip)))
            (local.set $ip (i32.add (local.get $ip) (i32.const 4)))
            (br $next))

            ;; !
            (i32.store (i32.load (local.get $sp)) (i32.load offset=4 (local.get $sp)))
            (local.set $sp (i32.add (local.get $sp) (i32.const 8)))
            (br $next))

            ;; @
            (i32.store (local.get $sp) (i32.load (i32.load (local.get $sp))))
            (br $next))

            ;; +!
            (i32.store (local.tee 4 (i32.load (local.get $sp))) (i32.add (i32.load (local.get 4)) (i32.load offset=4 (local.get $sp))))
            (local.set $sp (i32.add (local.get $sp) (i32.const 8)))
            (br $next))

            ;; -!
            (i32.store (local.tee 4 (i32.load (local.get $sp))) (i32.sub (i32.load (local.get 4)) (i32.load offset=4 (local.get $sp))))
            (local.set $sp (i32.add (local.get $sp) (i32.const 8)))
            (br $next))

            ;; c!
            (i32.store8 (i32.load (local.get $sp)) (i32.load offset=4 (local.get $sp)))
            (local.set $sp (i32.add (local.get $sp) (i32.const 8)))
            (br $next))

            ;; c@
            (i32.store (local.get $sp) (i32.load8_u (i32.load (local.get $sp))))
            (br $next))

            ;; c@c!
            (memory.copy (local.tee 4 (i32.load (local.get $sp))) (i32.load offset=4 (local.get $sp)) (i32.const 1))
            (i32.store offset=4 (local.get $sp) (local.get 4))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; cmove
            (memory.copy (local.tee 4 (i32.load offset=4 (local.get $sp))) (i32.load offset=8 (local.get $sp)) (i32.load (local.get $sp)))
            (i32.store offset=8 (local.get $sp) (local.get 4))
            (local.set $sp (i32.add (local.get $sp) (i32.const 8)))
            (br $next))

            ;; state
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (global.get $state))
            (br $next))

            ;; here
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (global.get $here))
            (br $next))

            ;; latest
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (global.get $latest))
            (br $next))

            ;; s0
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (global.get $s0))
            (br $next))

            ;; base
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (global.get $base))
            (br $next))

            ;; version
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 0x2f))
            (br $next))

            ;; r0
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 0x4000))
            (br $next))

            ;; docol
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 0))
            (br $next))

            ;; f_immed
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (global.get $f_immed))
            (br $next))

            ;; f_hidden
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (global.get $f_hidden))
            (br $next))

            ;; f_lenmask
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (global.get $f_lenmask))
            (br $next))

            ;; sys_exit
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 1))
            (br $next))

            ;; sys_open
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 5))
            (br $next))

            ;; sys_close
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 6))
            (br $next))

            ;; sys_read
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 3))
            (br $next))

            ;; sys_write
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 4))
            (br $next))

            ;; sys_creat
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 8))
            (br $next))

            ;; sys_brk
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 45))
            (br $next))

            ;; o_rdonly
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 0x04000000))
            (br $next))

            ;; o_wronly
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 0x10000000))
            (br $next))

            ;; o_rdwr
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 0x14000000))
            (br $next))

            ;; o_creat
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 0x1000))
            (br $next))

            ;; o_excl
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 0x4000))
            (br $next))

            ;; o_trunc
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 0x8000))
            (br $next))

            ;; o_append
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 0x1))
            (br $next))

            ;; o_nonblock
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.const 0x4))
            (br $next))

            ;; >r
            (i32.store (local.tee $rsp (i32.sub (local.get $rsp) (i32.const 4))) (i32.load (local.get $sp)))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; r>
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.load (local.get $rsp)))
            (local.set $rsp (i32.add (local.get $rsp) (i32.const 4)))
            (br $next))

            ;; rsp@
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (local.get $rsp))
            (br $next))

            ;; rsp!
            (local.set $rsp (i32.load (local.get $sp)))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; rdrop
            (local.set $rsp (i32.add (local.get $rsp) (i32.const 4)))
            (br $next))

            ;; dsp@
            (i32.store (local.tee $sp (i32.sub (local.tee 4 (local.get $sp)) (i32.const 4))) (local.get 4))
            (br $next))

            ;; dsp!
            (local.set $sp (i32.load (local.get $sp)))
            (br $next))

            ;; key
            (i32.store (local.tee $sp (i32.sub (local.tee 4 (local.get $sp)) (i32.const 4))) (local.get 4))
            (br $next))

            ;; emit
            (call $write (i32.const 1) (local.get $sp) (i32.const 1))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; word
            (i32.store offset=4 (local.tee $sp (i32.sub (local.get $sp) (i32.const 8))) (global.get $buffer))
            (i32.store (local.get $sp) (call $_word))
            (br $next))

            ;; number
            (i32.store offset=4 (local.get $sp) (call $_number (i32.load (local.get $sp)) (i32.load offset=4 (local.get $sp))))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; find
            (i32.store offset=4 (local.get $sp) (call $_find (i32.load (local.get $sp)) (i32.load offset=4 (local.get $sp))))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; >cfa
            (i32.store (local.get $sp) (call $_>cfa (i32.load (local.get $sp))))
            (br $next))

            ;; create
            (i32.store (local.tee 5 (i32.load (global.get $here))) (i32.load (global.get $latest))) ;; *HERE = *LATEST
            (i32.store (global.get $latest) (local.get 5)) ;; LATEST = HERE
            (i32.store8 offset=4 (local.get 5) (local.tee 4 (i32.load (local.get $sp)))) ;; set flags to len
            (memory.copy (local.tee 5 (i32.add (local.get 5) (i32.const 5))) (i32.load offset=4 (local.get $sp)) (local.get 4))
            (i32.store (global.get $here) (i32.and (i32.add (local.get 5) (i32.add (local.get 4)) (i32.const 3)) (i32.const -4))) ;; HERE = d (aligned)
            (local.set $sp (i32.add (local.get $sp) (i32.const 8)))
            (br $next))

            ;; comma
            (i32.store (local.tee 4 (i32.load (global.get $here))) (i32.load (local.get $sp)))
            (i32.store (global.get $here) (i32.add (local.get 4) (i32.const 4)))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; [
            (i32.store (global.get $state) (i32.const 0))
            (br $next))

            ;; ]
            (i32.store (global.get $state) (i32.const 1))
            (br $next))

            ;; immediate
            (i32.store8 offset=4 (local.tee 4 (i32.load (global.get $latest))) (i32.xor (i32.load8_u offset=4 (local.get 4)) (global.get $f_immed)))
            (br $next))

            ;; hidden
            (i32.store8 offset=4 (local.tee 4 (i32.load (local.get $sp))) (i32.xor (i32.load8_u offset=4 (local.get 4)) (global.get $f_hidden)))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))

            ;; '
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.load (local.get $ip)))
            (local.set $ip (i32.add (local.get $ip) (i32.const 4)))
            (br $next))

            ;; branch (ip += *ip)
            (local.set $ip (i32.add (local.get $ip) (i32.load (local.get $ip))))
            (br $next))

            ;; 0branch
            (if (i32.load (local.get $sp))
                (then
                    (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
                    (local.set $ip (i32.add (local.get $ip) (i32.const 4)))
                )
                (else
                    (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
                    (local.set $ip (i32.add (local.get $ip) (i32.load (local.get $ip))))
                )
            )
            (br $next))

            ;; litstring
            (local.set 4 (i32.load (local.get $ip)))
            (local.set $ip (i32.add (local.get $ip) (i32.const 4)))
            (i32.store offset=4 (local.tee $sp (i32.sub (local.get $sp) (i32.const 8))) (local.get $ip))
            (i32.store (local.get $sp) (local.get 4))
            (local.set $ip (i32.add (local.get $ip) (i32.and (i32.add (local.get 4) (i32.const 3)) (i32.const -4))))
            (br $next))

            ;; tell
            (call $write (i32.const 1) (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp)))
            (local.set $sp (i32.add (local.get $sp) (i32.const 8)))
            (br $next))

            ;; interpret
            (if (local.tee 4 (call $_find (local.tee 5 (call $_word)) (global.get $buffer)))
                (then ;; found word => execute or append
                    (local.set $cfa (call $_>cfa (local.get 4)))
                    (if (i32.or
                            (i32.and (i32.load8_u offset=4 (local.get 4)) (global.get $f_immed))
                            (i32.eqz (i32.load (global.get $state)))
                        )
                        (then (br $dispatch))
                    )
                    (i32.store (i32.load (global.get $here)) (local.get $cfa))
                    (i32.store (global.get $here) (i32.add (i32.load (global.get $here)) (i32.const 4)))
                )
                (else
                    (local.set 4 (call $_number (local.get 5) (global.get $buffer)))
                    (if (i32.load (global.get $nwritten)) ;; unconsumed input => parse error
                        (then
                            (call $write (i32.const 2) (i32.const 0x566c) (i32.const 13)) ;; "PARSE ERROR:"
                            (call $write (i32.const 2) (global.get $buffer) (local.get 5))
                            (call $write (i32.const 2) (i32.const 0x5679) (i32.const 1)) ;; "\n"
                        )
                        (else
                            (if (i32.load (global.get $state)) ;; compile number
                                (then
                                    (i32.store (i32.load (global.get $here)) (i32.const 0x521c)) ;; LIT cfa
                                    (i32.store offset=4 (i32.load (global.get $here)) (local.get 4))
                                    (i32.store (global.get $here) (i32.add (i32.load (global.get $here)) (i32.const 8)))
                                )
                                (else (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (local.get 4)))
                            )
                        )
                    )
                )
            )
            (br $next))

            ;; char
            (drop (call $_word))
            (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.load8_u (global.get $buffer)))
            (br $next))

            ;; execute
            (local.set $cfa (i32.load (local.get $sp)))
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $dispatch))

            ;; syscall3
            unreachable)

            ;; syscall2
            unreachable)

            ;; syscall1
            (if (i32.eq (i32.load (local.get $sp)) (i32.const 45))
                (then (i32.store offset=4 (local.get $sp) (i32.mul (memory.size) (i32.const 0x10000))))
                (else unreachable)
            )
            (local.set $sp (i32.add (local.get $sp) (i32.const 4)))
            (br $next))
        )
    )

    (data (i32.const 0x5044) "\00\00\00\00\04DROP\00\00\00\01\00\00\00")
    (data (i32.const 0x5054) "\44\50\00\00\04SWAP\00\00\00\02\00\00\00")
    (data (i32.const 0x5064) "\54\50\00\00\03DUP\03\00\00\00")
    (data (i32.const 0x5070) "\64\50\00\00\04OVER\00\00\00\04\00\00\00")
    (data (i32.const 0x5080) "\70\50\00\00\03ROT\05\00\00\00")
    (data (i32.const 0x508c) "\80\50\00\00\04-ROT\00\00\00\06\00\00\00")
    (data (i32.const 0x509c) "\8c\50\00\00\052DROP\00\00\07\00\00\00")
    (data (i32.const 0x50ac) "\9c\50\00\00\042DUP\00\00\00\08\00\00\00")
    (data (i32.const 0x50bc) "\ac\50\00\00\052SWAP\00\00\09\00\00\00")
    (data (i32.const 0x50cc) "\bc\50\00\00\04?DUP\00\00\00\0a\00\00\00")
    (data (i32.const 0x50dc) "\cc\50\00\00\021+\00\0b\00\00\00")
    (data (i32.const 0x50e8) "\dc\50\00\00\021-\00\0c\00\00\00")
    (data (i32.const 0x50f4) "\e8\50\00\00\024+\00\0d\00\00\00")
    (data (i32.const 0x5100) "\f4\50\00\00\024-\00\0e\00\00\00")
    (data (i32.const 0x510c) "\00\51\00\00\01+\00\00\0f\00\00\00")
    (data (i32.const 0x5118) "\0c\51\00\00\01-\00\00\10\00\00\00")
    (data (i32.const 0x5124) "\18\51\00\00\01*\00\00\11\00\00\00")
    (data (i32.const 0x5130) "\24\51\00\00\04/MOD\00\00\00\12\00\00\00")
    (data (i32.const 0x5140) "\30\51\00\00\01=\00\00\13\00\00\00")
    (data (i32.const 0x514c) "\40\51\00\00\02<>\00\14\00\00\00")
    (data (i32.const 0x5158) "\4c\51\00\00\01<\00\00\15\00\00\00")
    (data (i32.const 0x5164) "\58\51\00\00\01>\00\00\16\00\00\00")
    (data (i32.const 0x5170) "\64\51\00\00\02<=\00\17\00\00\00")
    (data (i32.const 0x517c) "\70\51\00\00\02>=\00\18\00\00\00")
    (data (i32.const 0x5188) "\7c\51\00\00\020=\00\19\00\00\00")
    (data (i32.const 0x5194) "\88\51\00\00\030<>\1a\00\00\00")
    (data (i32.const 0x51a0) "\94\51\00\00\020<\00\1b\00\00\00")
    (data (i32.const 0x51ac) "\a0\51\00\00\020>\00\1c\00\00\00")
    (data (i32.const 0x51b8) "\ac\51\00\00\030<=\1d\00\00\00")
    (data (i32.const 0x51c4) "\b8\51\00\00\030>=\1e\00\00\00")
    (data (i32.const 0x51d0) "\c4\51\00\00\03AND\1f\00\00\00")
    (data (i32.const 0x51dc) "\d0\51\00\00\02OR\00\20\00\00\00")
    (data (i32.const 0x51e8) "\dc\51\00\00\03XOR\21\00\00\00")
    (data (i32.const 0x51f4) "\e8\51\00\00\06INVERT\00\22\00\00\00")
    (data (i32.const 0x5204) "\f4\51\00\00\04EXIT\00\00\00\23\00\00\00")
    (data (i32.const 0x5214) "\04\52\00\00\03LIT\24\00\00\00")
    (data (i32.const 0x5220) "\14\52\00\00\01!\00\00\25\00\00\00")
    (data (i32.const 0x522c) "\20\52\00\00\01@\00\00\26\00\00\00")
    (data (i32.const 0x5238) "\2c\52\00\00\02+!\00\27\00\00\00")
    (data (i32.const 0x5244) "\38\52\00\00\02-!\00\28\00\00\00")
    (data (i32.const 0x5250) "\44\52\00\00\02C!\00\29\00\00\00")
    (data (i32.const 0x525c) "\50\52\00\00\02C@\00\2a\00\00\00")
    (data (i32.const 0x5268) "\5c\52\00\00\04C@C!\00\00\00\2b\00\00\00")
    (data (i32.const 0x5278) "\68\52\00\00\05CMOVE\00\00\2c\00\00\00")
    (data (i32.const 0x5288) "\78\52\00\00\05STATE\00\00\2d\00\00\00")
    (data (i32.const 0x5298) "\88\52\00\00\04HERE\00\00\00\2e\00\00\00")
    (data (i32.const 0x52a8) "\98\52\00\00\06LATEST\00\2f\00\00\00")
    (data (i32.const 0x52b8) "\a8\52\00\00\02S0\00\30\00\00\00")
    (data (i32.const 0x52c4) "\b8\52\00\00\04BASE\00\00\00\31\00\00\00")
    (data (i32.const 0x52d4) "\c4\52\00\00\07VERSION\32\00\00\00")
    (data (i32.const 0x52e4) "\d4\52\00\00\02R0\00\33\00\00\00")
    (data (i32.const 0x52f0) "\e4\52\00\00\05DOCOL\00\00\34\00\00\00")
    (data (i32.const 0x5300) "\f0\52\00\00\07F_IMMED\35\00\00\00")
    (data (i32.const 0x5310) "\00\53\00\00\08F_HIDDEN\00\00\00\36\00\00\00")
    (data (i32.const 0x5324) "\10\53\00\00\09F_LENMASK\00\00\37\00\00\00")
    (data (i32.const 0x5338) "\24\53\00\00\08SYS_EXIT\00\00\00\38\00\00\00")
    (data (i32.const 0x534c) "\38\53\00\00\08SYS_OPEN\00\00\00\39\00\00\00")
    (data (i32.const 0x5360) "\4c\53\00\00\09SYS_CLOSE\00\00\3a\00\00\00")
    (data (i32.const 0x5374) "\60\53\00\00\08SYS_READ\00\00\00\3b\00\00\00")
    (data (i32.const 0x5388) "\74\53\00\00\09SYS_WRITE\00\00\3c\00\00\00")
    (data (i32.const 0x539c) "\88\53\00\00\09SYS_CREAT\00\00\3d\00\00\00")
    (data (i32.const 0x53b0) "\9c\53\00\00\07SYS_BRK\3e\00\00\00")
    (data (i32.const 0x53c0) "\b0\53\00\00\08O_RDONLY\00\00\00\3f\00\00\00")
    (data (i32.const 0x53d4) "\c0\53\00\00\08O_WRONLY\00\00\00\40\00\00\00")
    (data (i32.const 0x53e8) "\d4\53\00\00\06O_RDWR\00\41\00\00\00")
    (data (i32.const 0x53f8) "\e8\53\00\00\07O_CREAT\42\00\00\00")
    (data (i32.const 0x5408) "\f8\53\00\00\06O_EXCL\00\43\00\00\00")
    (data (i32.const 0x5418) "\08\54\00\00\07O_TRUNC\44\00\00\00")
    (data (i32.const 0x5428) "\18\54\00\00\08O_APPEND\00\00\00\45\00\00\00")
    (data (i32.const 0x543c) "\28\54\00\00\0aO_NONBLOCK\00\46\00\00\00")
    (data (i32.const 0x5450) "\3c\54\00\00\02>R\00\47\00\00\00")
    (data (i32.const 0x545c) "\50\54\00\00\02R>\00\48\00\00\00")
    (data (i32.const 0x5468) "\5c\54\00\00\04RSP@\00\00\00\49\00\00\00")
    (data (i32.const 0x5478) "\68\54\00\00\04RSP!\00\00\00\4a\00\00\00")
    (data (i32.const 0x5488) "\78\54\00\00\05RDROP\00\00\4b\00\00\00")
    (data (i32.const 0x5498) "\88\54\00\00\04DSP@\00\00\00\4c\00\00\00")
    (data (i32.const 0x54a8) "\98\54\00\00\04DSP!\00\00\00\4d\00\00\00")
    (data (i32.const 0x54b8) "\a8\54\00\00\03KEY\4e\00\00\00")
    (data (i32.const 0x54c4) "\b8\54\00\00\04EMIT\00\00\00\4f\00\00\00")
    (data (i32.const 0x54d4) "\c4\54\00\00\04WORD\00\00\00\50\00\00\00")
    (data (i32.const 0x54e4) "\d4\54\00\00\06NUMBER\00\51\00\00\00")
    (data (i32.const 0x54f4) "\e4\54\00\00\04FIND\00\00\00\52\00\00\00")
    (data (i32.const 0x5504) "\f4\54\00\00\04>CFA\00\00\00\53\00\00\00")
    (data (i32.const 0x5514) "\04\55\00\00\04>DFA\00\00\00\00\00\00\00\10\55\00\00\fc\50\00\00\10\52\00\00")
    (data (i32.const 0x5530) "\14\55\00\00\06CREATE\00\54\00\00\00")
    (data (i32.const 0x5540) "\30\55\00\00\01,\00\00\55\00\00\00")
    (data (i32.const 0x554c) "\40\55\00\00\81[\00\00\56\00\00\00")
    (data (i32.const 0x5558) "\4c\55\00\00\01]\00\00\57\00\00\00")
    (data (i32.const 0x5564) "\58\55\00\00\89IMMEDIATE\00\00\58\00\00\00")
    (data (i32.const 0x5578) "\64\55\00\00\06HIDDEN\00\59\00\00\00")
    (data (i32.const 0x5588) "\78\55\00\00\04HIDE\00\00\00\00\00\00\00\e0\54\00\00\00\55\00\00\84\55\00\00\10\52\00\00")
    (data (i32.const 0x55a8) "\88\55\00\00\01:\00\00\00\00\00\00\e0\54\00\00\3c\55\00\00\1c\52\00\00\00\00\00\00\48\55\00\00\b4\52\00\00\34\52\00\00\84\55\00\00\60\55\00\00\10\52\00\00")
    (data (i32.const 0x55dc) "\a8\55\00\00\81;\00\00\00\00\00\00\1c\52\00\00\10\52\00\00\48\55\00\00\b4\52\00\00\34\52\00\00\84\55\00\00\54\55\00\00\10\52\00\00")
    (data (i32.const 0x5608) "\dc\55\00\00\01'\00\00\5a\00\00\00")
    (data (i32.const 0x5614) "\08\56\00\00\06BRANCH\00\5b\00\00\00")
    (data (i32.const 0x5624) "\14\56\00\00\070BRANCH\5c\00\00\00")
    (data (i32.const 0x5634) "\24\56\00\00\09LITSTRING\00\00\5d\00\00\00")
    (data (i32.const 0x5648) "\34\56\00\00\04TELL\00\00\00\5e\00\00\00")
    (data (i32.const 0x5658) "\48\56\00\00\09INTERPRET\00\00\5f\00\00\00")
    (data (i32.const 0x566c) "PARSE ERROR: \0A\00\00")
    (data (i32.const 0x567c) "\58\56\00\00\04QUIT\00\00\00\00\00\00\00\ec\52\00\00\84\54\00\00\68\56\00\00\20\56\00\00\f8\ff\ff\ff")
    (data (i32.const 0x56a0) "\7c\56\00\00\04CHAR\00\00\00\60\00\00\00")
    (data (i32.const 0x56b0) "\a0\56\00\00\07EXECUTE\61\00\00\00")
    (data (i32.const 0x56c0) "\b0\56\00\00\08SYSCALL3\00\00\00\62\00\00\00")
    (data (i32.const 0x56d4) "\c0\56\00\00\08SYSCALL2\00\00\00\63\00\00\00")
    (data (i32.const 0x56e8) "\d4\56\00\00\08SYSCALL1\00\00\00\64\00\00\00")
)