(module
    (func $proc_exit (import "wasi_snapshot_preview1" "proc_exit") (param i32))

    (memory (export "memory") 1)
    (data (i32.const 0) "-32")

    (func $number (param $n i32) (param $s i32) (param $base i32) (result i32)
        (local $c i32)
        (local $res i32)
        (local $sign i32)
        (local.set $res (i32.const 0))
        (local.set $sign (i32.const 1))
        (if (i32.eqz (local.tee $c (i32.load8_u (local.get $s)))) (then (return (local.get $res))))
        (if (i32.eq (local.get $c) (i32.const 0x2D)) ;; if (c == '-')
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
                (br_if $while (i32.gt_s (local.tee $n (i32.sub (local.get $n) (i32.const 1))) (i32.const 0))) ;; while (--n)
            )
        )
        (return (i32.mul (local.get $res) (local.get $sign)))
    )

    (func (export "_start")
        (call $log (call $number (i32.const 3) (i32.const 0) (i32.const 10)))
    )
)