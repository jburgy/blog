;; forth.rkt's run-defun shape, with jonesforth's vocabulary: IF, THEN, BEGIN, ... are
;; defined in FORTH (4th.32.fs) on top of LIT, BRANCH, 0BRANCH, ', `,`, HERE, IMMEDIATE, ...
;;
;;   forth.rkt                       here
;;   --------------------------      ------------------------------------------------
;;   defun-code  (code i k)          $defun_code (ip sp rsp)       NEXT
;;   defun-word  (w k)               $defun_word (cfa ip sp rsp)   run the word's codeword
;;   apply-k / frame (code i k)      EXIT / a return stack of saved ips
;;   lit / br / brz instructions     LIT, BRANCH, 0BRANCH words followed by a cell
;;   (c) then (k) for primitives     a primitive maps (ip sp rsp) to (ip sp rsp) and
;;                                   $defun_word then continues with $defun_code
;;   run-forth's token loop          INTERPRET, looped by QUIT
;;
;; Everything tail-calls (return_call), so loops run in constant wasm stack. Cells are
;; 4 bytes (i32) like jonesforth.f and localize.wast, and the dictionary layout is
;; 5th.c's on wasm32:
;;   link(4) flag|len(1) name(15) codeword(4) body...
;; A codeword is a table index: 1 DOCOL, 2 DODOES, 3.. one per builtin, in the order of
;; the names table. Words that share a function (binary operators, unary operators,
;; constants) recover which one they are from their own codeword. Deliberate
;; differences from jonesforth: EOF on stdin exits 0, division by zero is reported and
;; ignored (as in 5th.c), and SYSCALL3 only reads/writes the WASI stdio fds.
(module
    (func $fd_read   (import "wasi_snapshot_preview1" "fd_read")   (param i32 i32 i32 i32) (result i32))
    (func $fd_write  (import "wasi_snapshot_preview1" "fd_write")  (param i32 i32 i32 i32) (result i32))
    (func $proc_exit (import "wasi_snapshot_preview1" "proc_exit") (param i32))

    ;; Memory map (16 pages):
    ;;   0x0000 - 0x2000  data stack, grows down from S0
    ;;   0x2000 - 0x4000  return stack, grows down from R0
    ;;   0x4100 -         STATE HERE LATEST S0 BASE (ARGC) cells, cold start, WORD buffer,
    ;;                    iovec, constant values, messages, builtin names
    ;;   0x5000 - 0x6000  input buffer; starts out holding the boot text below
    ;;   0x8000 -         dictionary: builtins at a 28-byte stride, then user words
    (memory (export "memory") 16)
    (type $prim (func (param i32 i32 i32 i32) (result i32 i32 i32)))   ;; ( cfa ip sp rsp -- ip sp rsp )
    (table 108 funcref)

    (global $s0       i32 (i32.const 0x2000))
    (global $r0       i32 (i32.const 0x4000))
    (global $state_a  i32 (i32.const 0x4100))
    (global $here_a   i32 (i32.const 0x4104))
    (global $latest_a i32 (i32.const 0x4108))
    (global $s0_a     i32 (i32.const 0x410c))
    (global $base_a   i32 (i32.const 0x4110))
    (global $cold     i32 (i32.const 0x4140))
    (global $wordbuf  i32 (i32.const 0x4160))
    (global $iov      i32 (i32.const 0x4180))
    (global $nw       i32 (i32.const 0x4188))
    (global $ch       i32 (i32.const 0x418c))
    (global $constval i32 (i32.const 0x41a0))
    (global $m_parse  i32 (i32.const 0x4220))
    (global $m_under  i32 (i32.const 0x4230))
    (global $m_zero   i32 (i32.const 0x4250))
    (global $names    i32 (i32.const 0x4300))
    (global $inbuf    i32 (i32.const 0x5000))
    (global $dict     i32 (i32.const 0x8000))
    (global $lit_cfa  i32 (i32.const 0x8030))    ;; builtin #1: 0x8000 + 28 + 20
    (global $exit_cfa i32 (i32.const 0x8014))    ;; builtin #0

    (global $currkey (mut i32) (i32.const 0x5000))
    (global $buftop  (mut i32) (i32.const 0x5000))
    (global $num     (mut i32) (i32.const 0))     ;; value parsed by $number

    (data (i32.const 0x410c) "\00\20\00\00")   ;; S0
    (data (i32.const 0x4110) "\0a\00\00\00")   ;; BASE
    ;; QUIT's cold start: INTERPRET BRANCH -8
    (data (i32.const 0x4140) "\68\80\00\00" "\4c\80\00\00" "\f8\ff\ff\ff")
    (data (i32.const 0x4220) "PARSE ERROR: ")
    (data (i32.const 0x4230) "STACK UNDERFLOW\0a")
    (data (i32.const 0x4250) "DIVISION BY ZERO\0a")

    ;; values of the constant words, in names order
    (data (i32.const 0x41a0)
        "\00\41\00\00" "\04\41\00\00" "\08\41\00\00" "\0c\41\00\00" "\10\41\00\00" "\14\41\00\00"  ;; STATE HERE LATEST S0 BASE (ARGC)
        "\2f\00\00\00" "\00\40\00\00" "\01\00\00\00" "\02\00\00\00"                              ;; VERSION R0 DOCOL DODOES
        "\80\00\00\00" "\20\00\00\00" "\1f\00\00\00"                                              ;; F_IMMED F_HIDDEN F_LENMASK
        "\00\00\00\00" "\01\00\00\00" "\02\00\00\00" "\03\00\00\00" "\04\00\00\00" "\05\00\00\00" "\06\00\00\00"  ;; SYS_*
        "\00\00\00\00" "\01\00\00\00" "\02\00\00\00" "\40\00\00\00" "\80\00\00\00" "\00\02\00\00" "\00\04\00\00" "\00\08\00\00")  ;; O_*

    ;; name = flags|length, characters; the order is the order of the elem segment below.
    ;; The first four are known to $cold, $lit_cfa and $exit_cfa.
    (data (i32.const 0x4300)
        "\04EXIT" "\03LIT" "\06BRANCH" "\09INTERPRET"
        "\04DROP" "\04SWAP" "\03DUP" "\04OVER" "\03ROT" "\04-ROT" "\052DROP" "\042DUP" "\052SWAP" "\04?DUP"
        "\01+" "\01-" "\01*" "\03AND" "\02OR" "\03XOR" "\01=" "\02<>" "\01<" "\01>" "\02<=" "\02>="
        "\021+" "\021-" "\024+" "\024-" "\020=" "\030<>" "\020<" "\020>" "\030<=" "\030>=" "\06INVERT"
        "\04/MOD"
        "\01!" "\01@" "\02+!" "\02-!" "\02C!" "\02C@" "\04C@C!" "\05CMOVE"
        "\02>R" "\02R>" "\04RSP@" "\04RSP!" "\05RDROP" "\04DSP@" "\04DSP!"
        "\03KEY" "\04EMIT" "\04WORD" "\06NUMBER" "\04TELL" "\04CHAR"
        "\04FIND" "\04>CFA" "\06CREATE" "\01," "\81[" "\01]" "\01:" "\81;" "\89IMMEDIATE" "\06HIDDEN" "\01'"
        "\070BRANCH" "\09LITSTRING" "\07EXECUTE"
        "\08SYSCALL3" "\08SYSCALL2" "\08SYSCALL1" "\08SYSCALL0"
        "\05STATE" "\04HERE" "\06LATEST" "\02S0" "\04BASE" "\06(ARGC)" "\07VERSION" "\02R0" "\05DOCOL" "\06DODOES"
        "\07F_IMMED" "\08F_HIDDEN" "\09F_LENMASK"
        "\08SYS_EXIT" "\08SYS_OPEN" "\09SYS_CLOSE" "\08SYS_READ" "\09SYS_WRITE" "\09SYS_CREAT" "\07SYS_BRK"
        "\08O_RDONLY" "\08O_WRONLY" "\06O_RDWR" "\07O_CREAT" "\06O_EXCL" "\07O_TRUNC" "\08O_APPEND" "\0aO_NONBLOCK"
        "\00")

    ;; Words jonesforth.S builds out of other words, written the same way here
    (data (i32.const 0x5000)
        ": >DFA >CFA 4+ EXIT ;\0a"
        ": HIDE WORD FIND HIDDEN ;\0a"
        ": QUIT R0 RSP! INTERPRET BRANCH [ -8 , ] ;\0a\00")

    ;; ---- I/O -----------------------------------------------------------
    ;; bytes written, or -1
    (func $write (param $fd i32) (param $buf i32) (param $len i32) (result i32)
        (i32.store (global.get $iov) (local.get $buf))
        (i32.store offset=4 (global.get $iov) (local.get $len))
        (if (result i32) (call $fd_write (local.get $fd) (global.get $iov) (i32.const 1) (global.get $nw))
            (then (i32.const -1))
            (else (i32.load (global.get $nw)))
        )
    )

    ;; bytes read, or -1
    (func $read (param $fd i32) (param $buf i32) (param $len i32) (result i32)
        (i32.store (global.get $iov) (local.get $buf))
        (i32.store offset=4 (global.get $iov) (local.get $len))
        (if (result i32) (call $fd_read (local.get $fd) (global.get $iov) (i32.const 1) (global.get $nw))
            (then (i32.const -1))
            (else (i32.load (global.get $nw)))
        )
    )

    ;; next input byte, or -1 at EOF
    (func $key (result i32)
        (local $n i32)
        (if (i32.ge_u (global.get $currkey) (global.get $buftop))
            (then
                (global.set $currkey (global.get $inbuf))
                (global.set $buftop (global.get $inbuf))
                (if (i32.le_s (local.tee $n (call $read (i32.const 0) (global.get $inbuf) (i32.const 0x1000))) (i32.const 0))
                    (then (return (i32.const -1)))
                )
                (global.set $buftop (i32.add (global.get $inbuf) (local.get $n)))
            )
        )
        (global.set $currkey (i32.add (global.get $currkey) (i32.const 1)))
        (i32.load8_u (i32.sub (global.get $currkey) (i32.const 1)))
    )

    ;; reads a blank-delimited token into $wordbuf (\ comments skipped), returns its length
    (func $word (result i32)
        (local $c i32)
        (local $n i32)
        (loop $blank
            (if (i32.lt_s (local.tee $c (call $key)) (i32.const 0)) (then (call $proc_exit (i32.const 0))))
            (if (i32.eq (local.get $c) (i32.const 0x5c))
                (then (loop $comment (br_if $comment (i32.and (i32.ne (local.tee $c (call $key)) (i32.const 10)) (i32.ne (local.get $c) (i32.const -1))))))
            )
            (br_if $blank (i32.le_s (local.get $c) (i32.const 32)))
        )
        (loop $chars
            (if (i32.lt_u (local.get $n) (i32.const 31))
                (then
                    (i32.store8 (i32.add (global.get $wordbuf) (local.get $n)) (local.get $c))
                    (local.set $n (i32.add (local.get $n) (i32.const 1)))
                )
            )
            (br_if $chars (i32.and (i32.gt_u (local.tee $c (call $key)) (i32.const 32)) (i32.ne (local.get $c) (i32.const -1))))
        )
        (local.get $n)
    )

    ;; ---- dictionary ----------------------------------------------------
    (func $here (result i32) (i32.load (global.get $here_a)))
    (func $latest (result i32) (i32.load (global.get $latest_a)))

    (func $comma (param $x i32)
        (local $h i32)
        (i32.store (local.tee $h (call $here)) (local.get $x))
        (i32.store (global.get $here_a) (i32.add (local.get $h) (i32.const 4)))
    )

    (func $same (param $a i32) (param $b i32) (param $n i32) (result i32)
        (loop $next
            (if (i32.eqz (local.get $n)) (then (return (i32.const 1))))
            (local.set $n (i32.sub (local.get $n) (i32.const 1)))
            (br_if $next (i32.eq (i32.load8_u (i32.add (local.get $a) (local.get $n))) (i32.load8_u (i32.add (local.get $b) (local.get $n)))))
        )
        (i32.const 0)
    )

    ;; hidden words don't match (F_HIDDEN | F_LENMASK = 0x3f)
    (func $find (param $addr i32) (param $len i32) (result i32)
        (local $w i32)
        (local.set $w (call $latest))
        (loop $next
            (if (i32.eqz (local.get $w)) (then (return (i32.const 0))))
            (if (i32.eq (i32.and (i32.load8_u offset=4 (local.get $w)) (i32.const 0x3f)) (local.get $len))
                (then
                    (if (call $same (i32.add (local.get $w) (i32.const 5)) (local.get $addr) (local.get $len))
                        (then (return (local.get $w)))
                    )
                )
            )
            (local.set $w (i32.load (local.get $w)))
            (br $next)
        )
        (unreachable)
    )

    ;; the codeword sits after the name, 4-aligned, and never before offset 20
    (func $tcfa (param $w i32) (result i32)
        (local $o i32)
        (local.set $o (i32.and (i32.add (i32.and (i32.load8_u offset=4 (local.get $w)) (i32.const 0x1f)) (i32.const 8)) (i32.const -4)))
        (i32.add (local.get $w) (select (local.get $o) (i32.const 20) (i32.gt_u (local.get $o) (i32.const 20))))
    )

    (func $create (param $addr i32) (param $len i32)
        (local $new i32)
        (i32.store (local.tee $new (i32.and (i32.add (call $here) (i32.const 3)) (i32.const -4))) (call $latest))
        (i32.store8 offset=4 (local.get $new) (local.get $len))
        (memory.copy (i32.add (local.get $new) (i32.const 5)) (local.get $addr) (local.get $len))
        (i32.store (global.get $here_a) (call $tcfa (local.get $new)))
        (i32.store (global.get $latest_a) (local.get $new))
    )

    ;; parses addr/len in BASE into $num; returns the number of unparsed characters
    (func $number (param $addr i32) (param $len i32) (result i32)
        (local $i i32)
        (local $c i32)
        (local $start i32)
        (local $neg i32)
        (local $v i32)
        (global.set $num (i32.const 0))
        (if (i32.and (i32.gt_u (local.get $len) (i32.const 0)) (i32.eq (i32.load8_u (local.get $addr)) (i32.const 45)))
            (then (local.set $neg (i32.const 1)) (local.set $i (i32.const 1)))
        )
        (local.set $start (local.get $i))
        (block $done
            (loop $digit
                (br_if $done (i32.ge_u (local.get $i) (local.get $len)))
                (local.set $c (i32.load8_u (i32.add (local.get $addr) (local.get $i))))
                (if (i32.lt_u (i32.sub (local.get $c) (i32.const 48)) (i32.const 10))
                    (then (local.set $c (i32.sub (local.get $c) (i32.const 48))))
                    (else
                        (br_if $done (i32.ge_u (i32.sub (local.get $c) (i32.const 65)) (i32.const 26)))
                        (local.set $c (i32.sub (local.get $c) (i32.const 55)))
                    )
                )
                (br_if $done (i32.ge_u (local.get $c) (i32.load (global.get $base_a))))
                (local.set $v (i32.add (i32.mul (local.get $v) (i32.load (global.get $base_a))) (local.get $c)))
                (local.set $i (i32.add (local.get $i) (i32.const 1)))
                (br $digit)
            )
        )
        (if (i32.eq (local.get $i) (local.get $start)) (then (return (local.get $len))))
        (global.set $num (select (i32.sub (i32.const 0) (local.get $v)) (local.get $v) (local.get $neg)))
        (i32.sub (local.get $len) (local.get $i))
    )

    ;; ---- inner interpreter: defunctionalized ---------------------------
    ;; NEXT: the next cell of the threaded code names the word to run
    (func $defun_code (param $ip i32) (param $sp i32) (param $rsp i32) (result i32)
        (return_call $defun_word (i32.load (local.get $ip)) (i32.add (local.get $ip) (i32.const 4)) (local.get $sp) (local.get $rsp))
    )

    (func $defun_word (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32)
        (return_call $defun_code
            (call_indirect (type $prim) (local.get $cfa) (local.get $ip) (local.get $sp) (local.get $rsp) (i32.load (local.get $cfa))))
    )

    ;; ---- codewords -----------------------------------------------------
    (func $docol (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (local.tee $rsp (i32.sub (local.get $rsp) (i32.const 4))) (local.get $ip))
        (i32.add (local.get $cfa) (i32.const 4)) (local.get $sp) (local.get $rsp)
    )

    ;; CREATE ... DODOES , <code address> , <data> ...: run the code with the data's address pushed
    (func $dodoes (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (local.tee $rsp (i32.sub (local.get $rsp) (i32.const 4))) (local.get $ip))
        (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.add (local.get $cfa) (i32.const 8)))
        (i32.load offset=4 (local.get $cfa)) (local.get $sp) (local.get $rsp)
    )

    ;; apply-k: resume the frame on top of the return stack; the bottom is 'done
    (func $exit (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (if (i32.eq (local.get $rsp) (global.get $r0)) (then (call $proc_exit (i32.const 0))))
        (i32.load (local.get $rsp)) (local.get $sp) (i32.add (local.get $rsp) (i32.const 4))
    )

    ;; LIT and ' push the next cell
    (func $lit (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.load (local.get $ip)))
        (i32.add (local.get $ip) (i32.const 4)) (local.get $sp) (local.get $rsp)
    )

    ;; the offset is in bytes, relative to the offset cell
    (func $branch (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.add (local.get $ip) (i32.load (local.get $ip))) (local.get $sp) (local.get $rsp)
    )

    (func $0branch (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (select
            (i32.add (local.get $ip) (i32.load (local.get $ip)))
            (i32.add (local.get $ip) (i32.const 4))
            (i32.eqz (i32.load (local.get $sp))))
        (i32.add (local.get $sp) (i32.const 4)) (local.get $rsp)
    )

    ;; ( -- addr length ) of a string compiled in line, which is then skipped
    (func $litstring (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $c i32)
        (local.set $c (i32.load (local.get $ip)))
        (local.set $ip (i32.add (local.get $ip) (i32.const 4)))
        (i32.store offset=4 (local.tee $sp (i32.sub (local.get $sp) (i32.const 8))) (local.get $ip))
        (i32.store (local.get $sp) (local.get $c))
        (i32.add (local.get $ip) (i32.and (i32.add (local.get $c) (i32.const 4)) (i32.const -4))) (local.get $sp) (local.get $rsp)
    )

    ;; ---- the outer interpreter: one token per INTERPRET, looped by QUIT --
    (func $interpret (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $len i32)
        (local $w i32)
        (if (i32.gt_u (local.get $sp) (i32.load (global.get $s0_a)))
            (then
                (drop (call $write (i32.const 2) (global.get $m_under) (i32.const 16)))
                (local.set $sp (i32.load (global.get $s0_a)))
            )
        )
        (local.set $len (call $word))
        (if (local.tee $w (call $find (global.get $wordbuf) (local.get $len)))
            (then
                (local.set $cfa (call $tcfa (local.get $w)))
                (if (i32.or (i32.and (i32.load8_u offset=4 (local.get $w)) (i32.const 0x80)) (i32.eqz (i32.load (global.get $state_a))))
                    (then
                        (return_call_indirect (type $prim)
                            (local.get $cfa) (local.get $ip) (local.get $sp) (local.get $rsp) (i32.load (local.get $cfa)))
                    )
                )
                (call $comma (local.get $cfa))
                (return (local.get $ip) (local.get $sp) (local.get $rsp))
            )
        )
        (if (call $number (global.get $wordbuf) (local.get $len))
            (then
                (drop (call $write (i32.const 2) (global.get $m_parse) (i32.const 13)))
                (drop (call $write (i32.const 2) (global.get $wordbuf) (local.get $len)))
                (i32.store8 (global.get $ch) (i32.const 10))
                (drop (call $write (i32.const 2) (global.get $ch) (i32.const 1)))
            )
            (else
                (if (i32.eqz (i32.load (global.get $state_a)))
                    (then (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (global.get $num)))
                    (else
                        (call $comma (global.get $lit_cfa))
                        (call $comma (global.get $num))
                    )
                )
            )
        )
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )

    (func $execute (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local.set $cfa (i32.load (local.get $sp)))
        (return_call_indirect (type $prim)
            (local.get $cfa) (local.get $ip) (i32.add (local.get $sp) (i32.const 4)) (local.get $rsp) (i32.load (local.get $cfa)))
    )

    ;; ---- stack manipulation --------------------------------------------
    (func $drop (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local.get $ip) (i32.add (local.get $sp) (i32.const 4)) (local.get $rsp)
    )
    (func $swap (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $t i32)
        (local.set $t (i32.load offset=4 (local.get $sp)))
        (i32.store offset=4 (local.get $sp) (i32.load (local.get $sp)))
        (i32.store (local.get $sp) (local.get $t))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    (func $dup (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.load offset=4 (local.get $sp)))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    (func $over (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.load offset=8 (local.get $sp)))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    (func $rot (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $a i32) (local $b i32) (local $c i32)
        (local.set $a (i32.load (local.get $sp)))
        (local.set $b (i32.load offset=4 (local.get $sp)))
        (local.set $c (i32.load offset=8 (local.get $sp)))
        (i32.store offset=8 (local.get $sp) (local.get $b))
        (i32.store offset=4 (local.get $sp) (local.get $a))
        (i32.store (local.get $sp) (local.get $c))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    (func $-rot (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $a i32) (local $b i32) (local $c i32)
        (local.set $a (i32.load (local.get $sp)))
        (local.set $b (i32.load offset=4 (local.get $sp)))
        (local.set $c (i32.load offset=8 (local.get $sp)))
        (i32.store offset=8 (local.get $sp) (local.get $a))
        (i32.store offset=4 (local.get $sp) (local.get $c))
        (i32.store (local.get $sp) (local.get $b))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    (func $2drop (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local.get $ip) (i32.add (local.get $sp) (i32.const 8)) (local.get $rsp)
    )
    (func $2dup (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store offset=4 (local.tee $sp (i32.sub (local.get $sp) (i32.const 8))) (i32.load offset=12 (local.get $sp)))
        (i32.store (local.get $sp) (i32.load offset=8 (local.get $sp)))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    (func $2swap (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $a i32) (local $b i32) (local $c i32) (local $d i32)
        (local.set $a (i32.load (local.get $sp)))
        (local.set $b (i32.load offset=4 (local.get $sp)))
        (local.set $c (i32.load offset=8 (local.get $sp)))
        (local.set $d (i32.load offset=12 (local.get $sp)))
        (i32.store offset=12 (local.get $sp) (local.get $b))
        (i32.store offset=8 (local.get $sp) (local.get $a))
        (i32.store offset=4 (local.get $sp) (local.get $d))
        (i32.store (local.get $sp) (local.get $c))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    (func $?dup (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (if (i32.load (local.get $sp))
            (then (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.load offset=4 (local.get $sp))))
        )
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )

    ;; ---- arithmetic and comparison -------------------------------------
    ;; true is 1, as in jonesforth.S (5th.c and forth.rkt use -1)
    (func $flag (param i32) (result i32) (local.get 0))

    ;; + - * AND OR XOR = <> < > <= >=: codewords 17..28
    (func $binop (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $a i32) (local $b i32)
        (local.set $a (i32.load offset=4 (local.get $sp)))
        (local.set $b (i32.load (local.get $sp)))
        (i32.store offset=4 (local.get $sp)
            (block $r (result i32)
                (block $ge (block $le (block $gt (block $lt (block $ne (block $eq (block $xor (block $or (block $and (block $mul (block $sub (block $add
                    (br_table $add $sub $mul $and $or $xor $eq $ne $lt $gt $le $ge
                        (i32.sub (i32.load (local.get $cfa)) (i32.const 17)))
                ) (br $r (i32.add (local.get $a) (local.get $b))))
                (br $r (i32.sub (local.get $a) (local.get $b))))
                (br $r (i32.mul (local.get $a) (local.get $b))))
                (br $r (i32.and (local.get $a) (local.get $b))))
                (br $r (i32.or (local.get $a) (local.get $b))))
                (br $r (i32.xor (local.get $a) (local.get $b))))
                (br $r (call $flag (i32.eq (local.get $a) (local.get $b)))))
                (br $r (call $flag (i32.ne (local.get $a) (local.get $b)))))
                (br $r (call $flag (i32.lt_s (local.get $a) (local.get $b)))))
                (br $r (call $flag (i32.gt_s (local.get $a) (local.get $b)))))
                (br $r (call $flag (i32.le_s (local.get $a) (local.get $b)))))
                (call $flag (i32.ge_s (local.get $a) (local.get $b)))
            )
        )
        (local.get $ip) (i32.add (local.get $sp) (i32.const 4)) (local.get $rsp)
    )

    ;; 1+ 1- 4+ 4- 0= 0<> 0< 0> 0<= 0>= INVERT: codewords 29..39
    (func $unop (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $a i32)
        (local.set $a (i32.load (local.get $sp)))
        (i32.store (local.get $sp)
            (block $r (result i32)
                (block $inv (block $zge (block $zle (block $zgt (block $zlt (block $zne (block $zeq (block $sub4 (block $add4 (block $dec (block $inc
                    (br_table $inc $dec $add4 $sub4 $zeq $zne $zlt $zgt $zle $zge $inv
                        (i32.sub (i32.load (local.get $cfa)) (i32.const 29)))
                ) (br $r (i32.add (local.get $a) (i32.const 1))))
                (br $r (i32.sub (local.get $a) (i32.const 1))))
                (br $r (i32.add (local.get $a) (i32.const 4))))
                (br $r (i32.sub (local.get $a) (i32.const 4))))
                (br $r (call $flag (i32.eqz (local.get $a)))))
                (br $r (call $flag (i32.ne (local.get $a) (i32.const 0)))))
                (br $r (call $flag (i32.lt_s (local.get $a) (i32.const 0)))))
                (br $r (call $flag (i32.gt_s (local.get $a) (i32.const 0)))))
                (br $r (call $flag (i32.le_s (local.get $a) (i32.const 0)))))
                (br $r (call $flag (i32.ge_s (local.get $a) (i32.const 0)))))
                (i32.xor (local.get $a) (i32.const -1))
            )
        )
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )

    ;; ( a b -- remainder quotient ); b = -1 sidesteps the INT_MIN / -1 trap
    (func $/mod (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $a i32) (local $b i32)
        (local.set $a (i32.load offset=4 (local.get $sp)))
        (if (i32.eqz (local.tee $b (i32.load (local.get $sp))))
            (then
                (drop (call $write (i32.const 2) (global.get $m_zero) (i32.const 17)))
                (return (local.get $ip) (local.get $sp) (local.get $rsp))
            )
        )
        (if (i32.eq (local.get $b) (i32.const -1))
            (then
                (i32.store offset=4 (local.get $sp) (i32.const 0))
                (i32.store (local.get $sp) (i32.sub (i32.const 0) (local.get $a)))
            )
            (else
                (i32.store offset=4 (local.get $sp) (i32.rem_s (local.get $a) (local.get $b)))
                (i32.store (local.get $sp) (i32.div_s (local.get $a) (local.get $b)))
            )
        )
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )

    ;; ---- memory --------------------------------------------------------
    (func $! (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (i32.load (local.get $sp)) (i32.load offset=4 (local.get $sp)))
        (local.get $ip) (i32.add (local.get $sp) (i32.const 8)) (local.get $rsp)
    )
    (func $@ (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (local.get $sp) (i32.load (i32.load (local.get $sp))))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    (func $+! (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $t i32)
        (i32.store (local.tee $t (i32.load (local.get $sp)))
            (i32.add (i32.load (local.get $t)) (i32.load offset=4 (local.get $sp))))
        (local.get $ip) (i32.add (local.get $sp) (i32.const 8)) (local.get $rsp)
    )
    (func $-! (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $t i32)
        (i32.store (local.tee $t (i32.load (local.get $sp)))
            (i32.sub (i32.load (local.get $t)) (i32.load offset=4 (local.get $sp))))
        (local.get $ip) (i32.add (local.get $sp) (i32.const 8)) (local.get $rsp)
    )
    (func $c! (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store8 (i32.load (local.get $sp)) (i32.load offset=4 (local.get $sp)))
        (local.get $ip) (i32.add (local.get $sp) (i32.const 8)) (local.get $rsp)
    )
    (func $c@ (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (local.get $sp) (i32.load8_u (i32.load (local.get $sp))))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    ;; ( source dest -- source+1 dest+1 )
    (func $c@c! (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $dest i32) (local $source i32)
        (local.set $dest (i32.load (local.get $sp)))
        (local.set $source (i32.load offset=4 (local.get $sp)))
        (memory.copy (local.get $dest) (local.get $source) (i32.const 1))
        (i32.store (local.get $sp) (i32.add (local.get $dest) (i32.const 1)))
        (i32.store offset=4 (local.get $sp) (i32.add (local.get $source) (i32.const 1)))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    ;; ( source dest length -- )
    (func $cmove (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (memory.copy (i32.load offset=4 (local.get $sp)) (i32.load offset=8 (local.get $sp)) (i32.load (local.get $sp)))
        (local.get $ip) (i32.add (local.get $sp) (i32.const 12)) (local.get $rsp)
    )

    ;; ---- return and parameter stack pointers ----------------------------
    (func $>r (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (local.tee $rsp (i32.sub (local.get $rsp) (i32.const 4))) (i32.load (local.get $sp)))
        (local.get $ip) (i32.add (local.get $sp) (i32.const 4)) (local.get $rsp)
    )
    (func $r> (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.load (local.get $rsp)))
        (local.get $ip) (local.get $sp) (i32.add (local.get $rsp) (i32.const 4))
    )
    (func $rsp@ (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (local.get $rsp))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    (func $rsp! (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local.get $ip) (i32.add (local.get $sp) (i32.const 4)) (i32.load (local.get $sp))
    )
    (func $rdrop (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local.get $ip) (local.get $sp) (i32.add (local.get $rsp) (i32.const 4))
    )
    (func $dsp@ (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (i32.sub (local.get $sp) (i32.const 4)) (local.get $sp))
        (local.get $ip) (i32.sub (local.get $sp) (i32.const 4)) (local.get $rsp)
    )
    (func $dsp! (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local.get $ip) (i32.load (local.get $sp)) (local.get $rsp)
    )

    ;; ---- input and output ------------------------------------------------
    (func $keyw (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $c i32)
        (if (i32.lt_s (local.tee $c (call $key)) (i32.const 0)) (then (call $proc_exit (i32.const 0))))
        (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (local.get $c))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    (func $emit (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store8 (global.get $ch) (i32.load (local.get $sp)))
        (drop (call $write (i32.const 1) (global.get $ch) (i32.const 1)))
        (local.get $ip) (i32.add (local.get $sp) (i32.const 4)) (local.get $rsp)
    )
    ;; ( -- addr length )
    (func $wordw (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $len i32)
        (local.set $len (call $word))
        (i32.store offset=4 (local.tee $sp (i32.sub (local.get $sp) (i32.const 8))) (global.get $wordbuf))
        (i32.store (local.get $sp) (local.get $len))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    ;; ( addr length -- n unparsed )
    (func $numberw (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (local.get $sp) (call $number (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp))))
        (i32.store offset=4 (local.get $sp) (global.get $num))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    (func $tell (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (drop (call $write (i32.const 1) (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp))))
        (local.get $ip) (i32.add (local.get $sp) (i32.const 8)) (local.get $rsp)
    )
    (func $char (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (drop (call $word))
        (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4))) (i32.load8_u (global.get $wordbuf)))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )

    ;; ---- the compiler's vocabulary ---------------------------------------
    ;; ( addr length -- word | 0 )
    (func $findw (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store offset=4 (local.get $sp) (call $find (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp))))
        (local.get $ip) (i32.add (local.get $sp) (i32.const 4)) (local.get $rsp)
    )
    (func $>cfa (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (local.get $sp) (call $tcfa (i32.load (local.get $sp))))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    ;; ( addr length -- )
    (func $createw (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (call $create (i32.load offset=4 (local.get $sp)) (i32.load (local.get $sp)))
        (local.get $ip) (i32.add (local.get $sp) (i32.const 8)) (local.get $rsp)
    )
    (func $commaw (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (call $comma (i32.load (local.get $sp)))
        (local.get $ip) (i32.add (local.get $sp) (i32.const 4)) (local.get $rsp)
    )
    (func $lbrac (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (global.get $state_a) (i32.const 0))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    (func $rbrac (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (global.get $state_a) (i32.const 1))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    ;; : = WORD CREATE LIT DOCOL , LATEST @ HIDDEN ]
    (func $colon (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (call $create (global.get $wordbuf) (call $word))
        (call $comma (i32.const 1))
        (i32.store8 offset=4 (call $latest) (i32.xor (i32.load8_u offset=4 (call $latest)) (i32.const 0x20)))
        (i32.store (global.get $state_a) (i32.const 1))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    ;; ; = LIT EXIT , LATEST @ HIDDEN [
    (func $semicolon (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (call $comma (global.get $exit_cfa))
        (i32.store8 offset=4 (call $latest) (i32.xor (i32.load8_u offset=4 (call $latest)) (i32.const 0x20)))
        (i32.store (global.get $state_a) (i32.const 0))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    (func $immediate (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store8 offset=4 (call $latest) (i32.xor (i32.load8_u offset=4 (call $latest)) (i32.const 0x80)))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )
    (func $hidden (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $w i32)
        (local.set $w (i32.load (local.get $sp)))
        (i32.store8 offset=4 (local.get $w) (i32.xor (i32.load8_u offset=4 (local.get $w)) (i32.const 0x20)))
        (local.get $ip) (i32.add (local.get $sp) (i32.const 4)) (local.get $rsp)
    )

    ;; ---- system calls ----------------------------------------------------
    ;; ( arg3 arg2 arg1 number -- result ): only read(2) and write(2) of the stdio fds
    (func $syscall3 (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $n i32)
        (local.set $n (i32.const -1))
        (if (i32.eq (i32.load (local.get $sp)) (i32.const 3))
            (then (local.set $n (call $read (i32.load offset=4 (local.get $sp)) (i32.load offset=8 (local.get $sp)) (i32.load offset=12 (local.get $sp)))))
        )
        (if (i32.eq (i32.load (local.get $sp)) (i32.const 4))
            (then (local.set $n (call $write (i32.load offset=4 (local.get $sp)) (i32.load offset=8 (local.get $sp)) (i32.load offset=12 (local.get $sp)))))
        )
        (i32.store offset=12 (local.get $sp) (local.get $n))
        (local.get $ip) (i32.add (local.get $sp) (i32.const 12)) (local.get $rsp)
    )
    (func $syscall2 (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store offset=8 (local.get $sp) (i32.const -1))
        (local.get $ip) (i32.add (local.get $sp) (i32.const 8)) (local.get $rsp)
    )
    ;; exit(2) and brk(2): memory is the break
    (func $syscall1 (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (local $arg i32) (local $n i32)
        (local.set $arg (i32.load offset=4 (local.get $sp)))
        (local.set $n (i32.const -1))
        (if (i32.eqz (i32.load (local.get $sp))) (then (call $proc_exit (local.get $arg))))
        (if (i32.eq (i32.load (local.get $sp)) (i32.const 6))
            (then
                (if (i32.gt_u (local.get $arg) (i32.shl (memory.size) (i32.const 16)))
                    (then (drop (memory.grow (i32.shr_u (i32.add (local.get $arg) (i32.const 0xffff)) (i32.const 16)))))
                )
                (local.set $n (i32.shl (memory.size) (i32.const 16)))
            )
        )
        (i32.store offset=4 (local.get $sp) (local.get $n))
        (local.get $ip) (i32.add (local.get $sp) (i32.const 4)) (local.get $rsp)
    )
    (func $syscall0 (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (local.get $sp) (i32.const -1))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )

    ;; DEFCONST words: codewords 80..107 index the constant values
    (func $const (param $cfa i32) (param $ip i32) (param $sp i32) (param $rsp i32) (result i32 i32 i32)
        (i32.store (local.tee $sp (i32.sub (local.get $sp) (i32.const 4)))
            (i32.load (i32.add (global.get $constval) (i32.shl (i32.sub (i32.load (local.get $cfa)) (i32.const 80)) (i32.const 2)))))
        (local.get $ip) (local.get $sp) (local.get $rsp)
    )

    ;; codeword n runs table entry n; 0 is unused
    (elem (i32.const 1) $docol $dodoes
        $exit $lit $branch $interpret
        $drop $swap $dup $over $rot $-rot $2drop $2dup $2swap $?dup
        $binop $binop $binop $binop $binop $binop $binop $binop $binop $binop $binop $binop
        $unop $unop $unop $unop $unop $unop $unop $unop $unop $unop $unop
        $/mod
        $! $@ $+! $-! $c! $c@ $c@c! $cmove
        $>r $r> $rsp@ $rsp! $rdrop $dsp@ $dsp!
        $keyw $emit $wordw $numberw $tell $char
        $findw $>cfa $createw $commaw $lbrac $rbrac $colon $semicolon $immediate $hidden $lit
        $0branch $litstring $execute
        $syscall3 $syscall2 $syscall1 $syscall0
        $const $const $const $const $const $const $const $const $const $const
        $const $const $const $const $const $const $const $const $const $const
        $const $const $const $const $const $const $const $const)

    ;; the words at the addresses hard-coded above must be the ones expected: flags|length, first letter
    (func $expect (param $cfa i32) (param $want i32)
        (if (i32.ne (i32.load16_u (i32.sub (local.get $cfa) (i32.const 16))) (local.get $want)) (then (unreachable)))
    )

    ;; builtins at a 28-byte stride: link, flags|name[15], codeword, spare cell for data
    (func $init
        (local $p i32) (local $w i32) (local $prev i32) (local $k i32) (local $n i32)
        (local.set $p (global.get $names))
        (local.set $w (global.get $dict))
        (local.set $k (i32.const 3))
        (loop $word
            (i32.store (local.get $w) (local.get $prev))
            (local.set $n (i32.add (i32.and (i32.load8_u (local.get $p)) (i32.const 31)) (i32.const 1)))
            (memory.copy (i32.add (local.get $w) (i32.const 4)) (local.get $p) (local.get $n))
            (i32.store offset=20 (local.get $w) (local.get $k))
            (local.set $prev (local.get $w))
            (local.set $w (i32.add (local.get $w) (i32.const 28)))
            (local.set $p (i32.add (local.get $p) (local.get $n)))
            (local.set $k (i32.add (local.get $k) (i32.const 1)))
            (br_if $word (i32.load8_u (local.get $p)))
        )
        (i32.store (global.get $here_a) (local.get $w))
        (i32.store (global.get $latest_a) (local.get $prev))
        (call $expect (global.get $exit_cfa) (i32.const 0x4504))                 ;; EXIT
        (call $expect (global.get $lit_cfa) (i32.const 0x4c03))                  ;; LIT
        (call $expect (i32.load (global.get $cold)) (i32.const 0x4909))          ;; INTERPRET
        (call $expect (i32.load offset=4 (global.get $cold)) (i32.const 0x4206)) ;; BRANCH
        (local.set $p (global.get $inbuf))
        (loop $len
            (br_if $len (i32.load8_u (local.tee $p (i32.add (local.get $p) (i32.const 1)))))
        )
        (global.set $buftop (local.get $p))
    )

    (func (export "_start")
        (call $init)
        (drop (call $defun_code (global.get $cold) (global.get $s0) (global.get $r0)))
    )
)
