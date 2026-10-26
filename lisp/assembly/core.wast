;; SectorLisp in WebAssembly, written for the fewest instructions.
;; A WASI command, driven like build/lisp-wasi.wasm (see tests/wast.test.mjs).
;;
;; Pointers are raw byte addresses and nil is 0, so no tagging, shifting or base offsets.
;;   [0, 0x8000)   atoms {value: i32, name: NUL-terminated}; an atom is the address of its value
;;   [0x8000, ...) cons cells {car: i32, cdr: i32}, bump-allocated upward
;; An atom is anything below $M, so one compare replaces core.ts's sign test.
;;
;; Variables use shallow binding: Eval of an atom is a single load of its value, and
;; calling a lambda swaps the (fresh) argument list into the parameters' values and
;; swaps it back afterwards. That removes Assoc, Pairlis and the env parameter.
;; Duplicate parameter names and arity mismatches are not supported.
;;
;; The tokenizer writes each token at the end of the atom table ($e + 4), so Intern
;; compares in place; the token always matches itself, which ends the scan, and
;; interning a new atom is just moving $e past it.
(module
    (func $fd_read  (import "wasi_snapshot_preview1" "fd_read")  (param i32 i32 i32 i32) (result i32))
    (func $fd_write (import "wasi_snapshot_preview1" "fd_write") (param i32 i32 i32 i32) (result i32))

    ;; Pages 0-1 are atoms and cells; page 2 is I/O scratch: iovec {0x20008, 1}, the byte, nread/nwritten
    (memory (export "memory") 3)
    (data (i32.const 0x20000) "\08\00\02\00\01\00\00\00")

    ;; Atom entries: NIL T QUOTE COND READ PRINT ATOM CAR CDR CONS EQ (address = start of entry)
    (data (i32.const 0)
        "\00\00\00\00NIL\00\00\00\00\00T\00\00\00\00\00QUOTE\00\00\00\00\00COND\00\00\00\00\00READ\00"
        "\00\00\00\00PRINT\00\00\00\00\00ATOM\00\00\00\00\00CAR\00\00\00\00\00CDR\00\00\00\00\00CONS\00"
        "\00\00\00\00EQ\00")

    (global $T     i32 (i32.const 8))
    (global $QUOTE i32 (i32.const 14))
    (global $COND  i32 (i32.const 24))
    (global $READ  i32 (i32.const 33))
    (global $PRINT i32 (i32.const 42))
    (global $ATOM  i32 (i32.const 52))
    (global $CAR   i32 (i32.const 61))
    (global $CDR   i32 (i32.const 69))
    (global $CONS  i32 (i32.const 77))
    (global $EQ    i32 (i32.const 86))
    (global $M     i32 (i32.const 0x8000))

    (global $e  (mut i32) (i32.const 93))      ;; end of atom table, where the next atom or token goes
    (global $cx (mut i32) (i32.const 0x8000))  ;; next free cons cell
    (global $dx (mut i32) (i32.const 0))       ;; lookahead character
    (global $m  (mut i32) (i32.const 0))       ;; Gc: cells at or above $m are new
    (global $k  (mut i32) (i32.const 0))       ;; Gc: distance from new cells to their copies

    ;; -1 on error or EOF, like wasiHost.ts
    (func $getchar (result i32)
        (if (result i32)
            (i32.or
                (call $fd_read (i32.const 0) (i32.const 0x20000) (i32.const 1) (i32.const 0x2000C))
                (i32.eqz (i32.load (i32.const 0x2000C))))
            (then (i32.const -1))
            (else (i32.load8_u (i32.const 0x20008)))
        )
    )

    (func $putchar (param $c i32)
        (i32.store8 (i32.const 0x20008) (local.get $c))
        (drop (call $fd_write (i32.const 1) (i32.const 0x20000) (i32.const 1) (i32.const 0x2000C)))
    )

    (func $cons (param $a i32) (param $d i32) (result i32)
        (i32.store (global.get $cx) (local.get $a))
        (i32.store offset=4 (global.get $cx) (local.get $d))
        (global.get $cx)
        (global.set $cx (i32.add (global.get $cx) (i32.const 8)))
    )

    ;; Reads one token at $e + 4 and returns its last character
    (func $token (result i32)
        (local $c i32) (local $i i32)
        (local.set $i (i32.add (global.get $e) (i32.const 4)))
        (loop $next
            (i32.store8 (local.get $i) (local.tee $c (global.get $dx)))
            (global.set $dx (call $getchar))
            (local.set $i (i32.add (local.get $i) (i32.gt_u (local.get $c) (i32.const 32))))
            (br_if $next (i32.or
                (i32.le_u (local.get $c) (i32.const 32))
                (i32.and (i32.gt_u (local.get $c) (i32.const 41)) (i32.gt_u (global.get $dx) (i32.const 41)))))
        )
        (i64.store (local.get $i) (i64.const 0))  ;; NUL terminator and the next atom's zero value
        (local.get $c)
    )

    ;; p and q walk an atom's name and the token in lockstep; a mismatch skips to the next atom.
    (func $intern (result i32)
        (local $p i32) (local $q i32) (local $c i32)
        (local.set $q (global.get $e))
        (loop $scan
            (if (i32.eq (local.tee $c (i32.load8_u offset=4 (local.get $q)))
                        (i32.load8_u offset=4 (local.get $p)))
                (then
                    (local.set $p (i32.add (local.get $p) (i32.const 1)))
                    (local.set $q (i32.add (local.get $q) (i32.const 1)))
                    (br_if $scan (local.get $c))
                )
                (else
                    (loop $skip
                        (br_if $skip (i32.load8_u offset=3 (local.tee $p (i32.add (local.get $p) (i32.const 1)))))
                    )
                    (local.set $p (i32.add (local.get $p) (i32.const 4)))
                    (local.set $q (global.get $e))
                    (br $scan)
                )
            )
        )
        (local.set $p (i32.add (i32.sub (local.get $p) (local.get $q)) (global.get $e)))  ;; atom address
        (if (i32.eq (local.get $p) (global.get $e))
            (then (global.set $e (i32.add (local.get $q) (i32.const 4))))
        )
        (local.get $p)
    )

    (func $obj (param $c i32) (result i32)
        (if (result i32) (i32.eq (local.get $c) (i32.const 40))
            (then (call $list))
            (else (call $intern))
        )
    )

    (func $list (result i32)
        (local $c i32)
        (if (result i32) (i32.eq (local.tee $c (call $token)) (i32.const 41))
            (then (i32.const 0))
            (else (call $cons (call $obj (local.get $c)) (call $list)))
        )
    )

    (func $print (param $x i32)
        (local $c i32)
        (if (i32.lt_u (local.get $x) (global.get $M))
            (then
                (loop $char
                    (if (local.tee $c (i32.load8_u offset=4 (local.get $x)))
                        (then
                            (call $putchar (local.get $c))
                            (local.set $x (i32.add (local.get $x) (i32.const 1)))
                            (br $char)
                        )
                    )
                )
            )
            (else
                (call $putchar (i32.const 40))
                (call $print (i32.load (local.get $x)))
                (call $tail (local.get $x))
            )
        )
    )

    ;; Prints what follows the car of cell $x, then ")"
    (func $tail (param $x i32)
        (if (local.tee $x (i32.load offset=4 (local.get $x)))
            (then
                (if (i32.lt_u (local.get $x) (global.get $M))
                    (then
                        (call $putchar (i32.const 0x2219))
                        (call $print (local.get $x))
                    )
                    (else
                        (call $putchar (i32.const 32))
                        (call $print (i32.load (local.get $x)))
                        (return_call $tail (local.get $x))
                    )
                )
            )
        )
        (call $putchar (i32.const 41))
    )

    ;; Copies the cells allocated since $m, relocating pointers as if they were already moved down by $k
    (func $gc (param $x i32) (result i32)
        (if (result i32) (i32.lt_u (local.get $x) (global.get $m))
            (then (local.get $x))
            (else (i32.sub
                (call $cons (call $gc (i32.load (local.get $x)))
                            (call $gc (i32.load offset=4 (local.get $x))))
                (global.get $k)))
        )
    )

    ;; Swaps the values of atoms in $p with the elements of list $x; calling it twice restores them
    (func $swap (param $p i32) (param $x i32)
        (local $a i32) (local $t i32)
        (if (local.get $p)
            (then
                (local.set $t (i32.load (local.tee $a (i32.load (local.get $p)))))
                (i32.store (local.get $a) (i32.load (local.get $x)))
                (i32.store (local.get $x) (local.get $t))
                (return_call $swap (i32.load offset=4 (local.get $p)) (i32.load offset=4 (local.get $x)))
            )
        )
    )

    (func $evlis (param $m i32) (result i32)
        (if (result i32) (local.get $m)
            (then (call $cons (call $eval (i32.load (local.get $m)))
                              (call $evlis (i32.load offset=4 (local.get $m)))))
            (else (i32.const 0))
        )
    )

    (func $evcon (param $c i32) (result i32)
        (if (call $eval (i32.load (i32.load (local.get $c))))
            (then (return_call $eval (i32.load (i32.load offset=4 (i32.load (local.get $c))))))
        )
        (return_call $evcon (i32.load offset=4 (local.get $c)))
    )

    (func $apply (param $f i32) (param $x i32) (result i32)
        (local $r i32)
        (if (i32.ge_u (local.get $f) (global.get $M))  ;; (LAMBDA params body)
            (then
                (local.set $f (i32.load offset=4 (local.get $f)))
                (call $swap (i32.load (local.get $f)) (local.get $x))
                (local.set $r (call $eval (i32.load (i32.load offset=4 (local.get $f)))))
                (call $swap (i32.load (local.get $f)) (local.get $x))
                (return (local.get $r))
            )
        )
        (if (i32.gt_u (local.get $f) (global.get $EQ))
            (then (return_call $apply (i32.load (local.get $f)) (local.get $x)))
        )
        (if (i32.eq (local.get $f) (global.get $EQ))
            (then (return (i32.mul (global.get $T)
                (i32.eq (i32.load (local.get $x)) (i32.load (i32.load offset=4 (local.get $x)))))))
        )
        (if (i32.eq (local.get $f) (global.get $CONS))
            (then (return_call $cons (i32.load (local.get $x)) (i32.load (i32.load offset=4 (local.get $x)))))
        )
        (if (i32.eq (local.get $f) (global.get $ATOM))
            (then (return (i32.mul (global.get $T) (i32.lt_u (i32.load (local.get $x)) (global.get $M)))))
        )
        (if (i32.eq (local.get $f) (global.get $CAR))
            (then (return (i32.load (i32.load (local.get $x)))))
        )
        (if (i32.eq (local.get $f) (global.get $CDR))
            (then (return (i32.load offset=4 (i32.load (local.get $x)))))
        )
        (if (i32.eq (local.get $f) (global.get $READ))
            (then (return_call $obj (call $token)))
        )
        (if (i32.eq (local.get $f) (global.get $PRINT))
            (then
                (if (local.get $x)
                    (then (call $print (i32.load (local.get $x))))
                    (else (call $putchar (i32.const 10)))
                )
            )
        )
        (i32.const 0)
    )

    (func $eval (param $e i32) (result i32)
        (local $a i32)
        (if (i32.lt_u (local.get $e) (global.get $M))
            (then (return (i32.load (local.get $e))))
        )
        (if (i32.eq (i32.load (local.get $e)) (global.get $QUOTE))
            (then (return (i32.load (i32.load offset=4 (local.get $e)))))
        )
        (local.set $a (global.get $cx))
        (local.set $e
            (if (result i32) (i32.eq (i32.load (local.get $e)) (global.get $COND))
                (then (call $evcon (i32.load offset=4 (local.get $e))))
                (else (call $apply (i32.load (local.get $e)) (call $evlis (i32.load offset=4 (local.get $e)))))
            )
        )
        ;; Copy the live result above the garbage, then slide it down over the garbage
        (global.set $m (local.get $a))
        (global.set $k (i32.sub (global.get $cx) (local.get $a)))
        (local.set $e (call $gc (local.get $e)))
        (global.set $cx (i32.sub (global.get $cx) (global.get $k)))
        (memory.copy
            (local.get $a)
            (i32.add (local.get $a) (global.get $k))
            (i32.sub (global.get $cx) (local.get $a)))
        (local.get $e)
    )

    (func (export "_start")
        (loop $repl
            (global.set $cx (global.get $M))
            (call $putchar (i32.const 42))
            (call $putchar (i32.const 32))
            (call $print (call $eval (call $obj (call $token))))
            (call $putchar (i32.const 10))
            (br $repl)
        )
    )
)
