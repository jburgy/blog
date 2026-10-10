# Forth interpreters, one dictionary, many dispatch loops

Every program in this directory is the same [jonesforth](https://github.com/nornagon/jonesforth)
dictionary — the same primitives, the same `4th.fs` preamble — wired to a
different **inner interpreter**. They exist to answer one question: how much
does the *shape* of `NEXT` matter, and how portable is each shape?

Two things vary independently:

- **language** — C, Zig, Rust, or WebAssembly text written by hand
- **dispatch strategy** — how `NEXT` reaches the code of the next word

Those two axes are orthogonal, so the clearest way to present them is a grid.

## The grid

Rows are languages, columns are strategies. A cell holds every implementation
that sits at that intersection.

|  | **switch** | **labels as values** | **tail calls** |
| --- | --- | --- | --- |
| **C** | [jansforth.c](jansforth.c)<br>[recurse.c](recurse.c) | [4th.c](4th.c) | [5th.c](5th.c) |
| **Zig** | [jansforth.zig](jansforth.zig)<br>[labeled.zig](labeled.zig)<br>[hybrid.zig](hybrid.zig) | — | [6th.zig](6th.zig) |
| **Rust** | [jansforth.rs](jansforth.rs) | — | [4th.rs](4th.rs) |
| **wasm** | [wasm/tabulate.wast](wasm/tabulate.wast)<br>[wasm/recurse.wast](wasm/recurse.wast) | — | [wasm/jonesforth.wast](wasm/jonesforth.wast)<br>[wasm/localize.wast](wasm/localize.wast) |

Two holes are structural rather than accidental: neither Zig nor WebAssembly
has anything like GCC's `&&label`, so the middle column can only ever be C.
The Zig cell holds three implementations rather than one: same `switch`
strategy, three different ways of writing it (see below).

## The strategies

**switch** — one flat loop, `while (1) switch (memory[cfa]) { ... }`, with the
code field holding a small integer opcode. Portable to anything, and the only
strategy a stock WebAssembly engine can express without the tail-call proposal
(`br_table`). Pays an indirect branch through the jump table on every word,
*plus* an unconditional jump back to the top of the loop before that branch.
[labeled.zig](labeled.zig) trims that second jump: it is
[jansforth.zig](jansforth.zig)'s VM again, cell for cell, but every prong ends
with `continue :dispatch fetchOp(...)` -- Zig 0.14+'s labeled `switch`/
`continue`, see https://simonklee.dk/labeled-switch and
[regexp/labeled.zig](../regexp/labeled.zig) for the same trick applied to a
regex VM -- instead of falling out to a shared dispatch site at the bottom of
the loop. The expectation was that this lands somewhere between plain `switch`
and labels-as-values. It does not: on x86-64 it is *slower* than the plain
switch on most of the workload suite. Giving all 101 prongs their own dispatch
site makes every prong a predecessor of every other, and LLVM answers with 104
copies of the jump table (+41 KB of `.rodata`) and, worse, stops
register-allocating the VM state -- `ip`/`cfa`/`sp`/`rsp` move into stack slots
that every primitive then read-modify-writes.

[hybrid.zig](hybrid.zig) is the same file with the `continue :dispatch`
replicated for only the 37 hot opcodes; the remaining 63 prongs fall out of the
switch to one shared dispatch site. That keeps the per-site branch prediction
where it pays without the register pressure. On x86-64 it is the fastest of the
three, but the table below was measured on macOS/arm64 and has not been rerun,
so hybrid carries no number there yet. Measured on `Forth.run`:

| variant | prongs | insns | indirect jmp | stack-slot operands |
| --- | ---: | ---: | ---: | ---: |
| [jansforth.zig](jansforth.zig) | — | 2403 | 2 | 310 |
| [labeled.zig](labeled.zig) | 100 | 3814 | 104 | 1067 |
| [hybrid.zig](hybrid.zig) | 37 | 2452 | 41 | 229 |

The three are otherwise byte-for-byte copies of one another, so the benchmark
only ever sees the dispatch shape.

**labels as values** — GCC's computed goto. The code field holds `&&label`
directly, so `NEXT` is `goto **ip++`, and the branch predictor gets one
dispatch site per primitive instead of one shared site. Classic indirect
threading, and a GNU extension.

**tail calls** — every primitive is a function ending in a guaranteed tail call
to the next one, so the machine's `jmp` does the threading and the arguments
(`sp`, `rsp`, `ip`) stay in registers across the whole run. Needs an explicit
guarantee from the compiler: `__attribute__((musttail))`, `@call(.always_tail)`,
`become`, or wasm's `return_call`.

## Every implementation

| source | language | strategy | wasm | toolkit | notes | native ms (range) / rank | Wasmtime ms (range) / rank |
| --- | --- | --- | :---: | --- | --- | ---: | ---: |
| [4th.c](4th.c) | C | labels as values | ✅ | wasi-sdk clang (`npm run build:4th`) | Original; `NEXT` is `goto **target`; standalone Wasm used for Wasmtime | 58.1 (52.9-61.8) / 4 | 68.6 (58.5-82.0) / 3 |
| [5th.c](5th.c) | C | tail calls | ✅ | wasi-sdk clang | `NEXT` is `musttail return ip->word->code(...)`; standalone Wasm used for Wasmtime | 55.1 (49.7-58.8) / 1 | 233.8 (215.4-261.9) / 5 |
| [jansforth.c](jansforth.c) | C | switch | — | — | Opcode enum, everything in one `memory[]` array | 75.4 (72.9-79.5) / 6 | — |
| [recurse.c](recurse.c) | C | switch | — | — | `docol()` is the loop and recurses; return stack becomes a shadow stack | 76.4 (72.9-85.7) / 6 | — |
| [6th.zig](6th.zig) | Zig | tail calls | ✅ | wasm32-wasi (`zig build -Dtarget=wasm32-wasi`, see build.zig's `buildWasi`) | `@call(.always_tail, primitives[code], ...)`; native result only | 70.4 (66.3-79.2) / 5 | — |
| [jansforth.zig](jansforth.zig) | Zig | switch | — | — | `while (true) switch (op) { ... }`; dictionary generated like jansforth.rs's | 54.2 (51.2-63.8) / 1 | — |
| [labeled.zig](labeled.zig) | Zig | labeled switch | — | — | jansforth.zig cell for cell; every prong `continue`s a labeled `switch` instead | 56.3 (51.1-75.6) / 1 | — |
| [hybrid.zig](hybrid.zig) | Zig | labeled switch, hot prongs only | — | — | labeled.zig with the dispatch replicated for 37 hot opcodes; the rest share one site | — | — |
| [4th.rs](4th.rs) | Rust | tail calls | ✅ | wasm32-wasip1 (Wasmtime, and uwasi in the browser) | Nightly `become`; every primitive returns `!` | 82.0 (77.7-90.7) / 8 | 397.1 (346.0-441.2) / 7 |
| [jansforth.rs](jansforth.rs) | Rust | switch | — | — | Transcription of jansforth.c, run with `rust-script` | 79.7 (73.0-90.3) / 8 | — |
| [wasm/tabulate.wast](wasm/tabulate.wast) | wasm | switch | ✅ | wat2wasm + Wasmtime | One big `br_table`, no indirect calls | — | 58.7 (53.8-71.5) / 1 |
| [wasm/recurse.wast](wasm/recurse.wast) | wasm | switch | ✅ | wat2wasm + Wasmtime | Tabulate with a recursive `$docol`; colon-word returns live on the wasm call stack | — | 61.3 (51.4-67.5) / 2 |
| [wasm/jonesforth.wast](wasm/jonesforth.wast) | wasm | tail calls | ✅ | wat2wasm + Wasmtime | `return_call_indirect`; state in globals | — | 276.1 (224.7-326.2) / 6 |
| [wasm/localize.wast](wasm/localize.wast) | wasm | tail calls | ✅ | wat2wasm + Wasmtime | Same, with `cfa`/`ip`/`sp`/`rsp` passed as parameters | — | 222.2 (196.4-233.6) / 4 |
| [jonesforth.S](../jonesforth/jonesforth.S) | x86 assembly | indirect threaded | — | Linux/i386 | Requires Linux on x86; not runnable on this macOS/arm64 host | N/R | — |

## Benchmarks

Measured on macOS/arm64 with Apple clang 21.0.0, Rust nightly 1.101.0,
Zig 0.15.2, wasi-sdk 34.0, WABT 1.0.39, and Wasmtime 49.0.1.
Lower times are faster. Native and Wasmtime ranks are separate; medians within
3% are tied.

Each result is the median and min-max range of eleven timed runs after a warm-up. Targets are
run in a different deterministic shuffled order on each trial to reduce
systematic ordering bias; the harness also prints each range and every sample.
The benchmark loads the definitions from [`fibonacci.fs`](../talks/fibonacci.fs) and executes
its fast-doubling `FIBONACCI` word 100,000 times at `n=46`, then checks the
result against `1836311903`. Using 46 keeps the result in range for the
32-bit-cell implementations. The Wasmtime column includes the hand-written
`.wast` files, standalone wasi-sdk builds of `4th.c` and `5th.c`, and the
Rust `wasm32-wasip1` build. Wasmtime modules were compiled once at optimization
level 2 and run as precompiled modules with tail calls and exceptions enabled;
module compilation is excluded, while process/runtime startup is included.
Native builds used optimized settings (`-O3`, Cargo release with `opt-level=3`,
or Zig `ReleaseFast`).

The file's default `n=92` exceeds the 32-bit cell range used by most variants.
At the common-width input `46`, the benchmark verifies the computed result for
each target. `wasm/jonesforth.wast` now passes after correcting its `-ROT`
stack permutation. `4th.c` uses 16 KiB data and return stacks, enough for the
recursive workloads on this host.

### The workload suite

The numbers above are Fibonacci only, and Fibonacci is not representative: it
is a tight integer/stack loop that never executes `WORD`, `FIND`, `CREATE`,
`C@`, `!` or a syscall in anger. Twenty opcodes account for 99% of it, but only
40% of a compile-heavy program. Rankings move accordingly — on x86-64
`labeled.zig` ranges from 0.81x to 1.69x of `jansforth.zig` depending on which
program is timed.

`python3 benchmark.py --workload all` therefore times six programs with
deliberately different opcode mixes:

| workload | exercises |
| --- | --- |
| `fibonacci` | integer arithmetic and stack shuffling |
| `cells` | `!`/`@` over an array, cell-strided |
| `bytes` | `C!`/`C@` and byte copying |
| `calls` | nested colon words: `DOCOL`/`EXIT`/`>R`/`R>` |
| `compile` | `INTERPRET`/`WORD`/`FIND`/`CREATE`/`,` |
| `printing` | `U.`/`EMIT`/`/MOD` |

Each is self-verifying and cell-width agnostic (`CELLW` measures the cell size
at run time by comma-ing one cell and differencing `HERE`), so the same source
runs on the 32-bit and 64-bit interpreters alike. The `bytes` workload stores
values above 127 and sums them back, which caught `C@` sign-extending in all
four C ports; the `CMOVE` arity and `4th.rs`'s `R0`/`STATE` aliasing came from
auditing the ports against `jonesforth.S` rather than from the suite.

Run `python3 benchmark.py` from this directory to rebuild the native and Wasm
targets in a temporary directory, validate each result, and print medians,
ranges, and individual timings.
The script accepts `--iterations`, `--trials`, and `--timeout` overrides; it
requires clang, wasi-sdk (`WASI_SDK_PATH` set, see
bytecodealliance/setup-wasi-sdk-action), nightly Rust with the
`wasm32-wasip1` target and `rust-src`, Zig, WABT, and Wasmtime.

### Toolkits, briefly

- **wasi-sdk clang** — plain `wasm32-wasip1`, no JS glue; the artifacts are
  bare `4th.wasm`/`5th.wasm` (`npm run build:4th`/`build`), and
  [benchmark.py](benchmark.py) builds the same way (with `-O3`) for its own
  Wasmtime comparison. The three published posts
  ([what-forth-again](https://bur.gy/2023/02/24/what-forth-again.html),
  [tail-recursion](https://bur.gy/2024/03/29/tail-recursion.html),
  [why-not-zig](https://bur.gy/2024/08/31/why-not-zig.html)) used to hardcode
  a JS loader + xterm-pty directly; they now use
  `wasi-repl.mjs` against `4th-wasi.wasm`/`5th-wasi.wasm`/`6th-wasi.wasm`
  instead, same as [html/4th.html](html/4th.html), [html/5th.html](html/5th.html),
  and [html/6th.html](html/6th.html) below. Driven by
  [uwasi](https://github.com/kateinoigakukun/uwasi) both in
  [web/4th.test.ts](web/4th.test.ts) (a finite, scripted stdin, alongside the
  same primitive-wordset matrix run against the Rust `web/4th.wasm`) and in
  the browser, where [wasm/wasi-worker.js](wasm/wasi-worker.js) backs stdin
  with a `SharedInputChannel` so `read()` genuinely blocks instead of seeing
  EOF -- what [html/4th.html](html/4th.html) and [html/5th.html](html/5th.html)
  actually run. `4th.c`'s `brk(2)` shim (its `BRK`/`MORECORE` words pass an
  absolute address, but wasi-libc's `sbrk()` only does relative growth, and
  only in exact wasm-page multiples) is the one piece of source this needed;
  `5th.c` calls `sbrk()` directly already, though its own `SYS_brk` path
  (unlike `4th.c`'s) isn't exercised by any test here, this change included.
- **Zig `wasm32-wasi`** — `6th.zig`'s other wasm target (`build.zig`'s
  `buildWasi`): zig's own linker produces the standalone
  command directly. Shares `wasi-worker.js` with `4th.wasm`/`5th.wasm` above,
  and is what [html/6th.html](html/6th.html) actually runs -- no pty, no
  xterm-pty; [wasm/wasi-repl.mjs](wasm/wasi-repl.mjs) (`startRepl(wasmUrl)`)
  does the line editing against `xterm.js`, shared by `html/4th.html`,
  `html/5th.html`, and `html/6th.html`, and published standalone via
  `assets/Makefile`'s own `wasi-repl.mjs` target -- not just a side effect of
  building `4th-wasi.wasm`/`5th-wasi.wasm`/`6th-wasi.wasm` -- so a post can
  hardcode `/blog/wasi-repl.mjs` directly. `jonesforth.wasm` shares that same
  `jonesforth.f` dictionary too (its own `ARGC`/`ARGV`/`ENVIRON` just answer
  wrong instead of real argv under WASI, harmlessly, since nothing here calls
  them), so `startRepl`'s optional second argument is now a plain `preamble`
  boolean (default `true`), not a URL: `false` opts all the way out for a
  WASI command with no use for it (`lisp-wasi.wasm`/`TinyBasic-wasi.wasm`).
  A third, optional `container` argument (element or id, defaulting to
  `"terminal"`) lets a caller mount more than one REPL on the same page at
  once instead of sharing a single div -- `assets/index.html`'s demos
  landing page is the one consumer that needs this, one `<details>` per
  interpreter; the how-many-roads post's tab strip is the one that switches
  `wasmUrl` in place instead, `dispose()`-ing the previous REPL (terminates
  its Worker, tears down its Terminal) first. Each
  html/*.html page also loads mocha from a CDN
  and runs [wasm/wasi-repl-mocha.mjs](wasm/wasi-repl-mocha.mjs) against the
  live REPL (`startRepl`'s return value, not simulated keystrokes) -- a human
  visiting the page gets the same pass/fail report CI reads headless (see
  `npm run test:browser` above).
- **Rust `wasm32-wasip1`** — two profiles, because [4th.rs](4th.rs) halts by
  panicking: `make test-wasm` rebuilds `std` with `panic_unwind` for wasmtime,
  while `make web` swaps the panic for a host throw so the browser build in
  [web/](web/) needs no exception-handling proposal. Its stdin problem is
  sidestepped rather than solved: [web/4th.js](web/4th.js) re-enters `eval()`
  one host-supplied line at a time instead of blocking inside the guest, so it
  needs no Worker, no `SharedArrayBuffer`, and none of `wasi-worker.js`. A
  *third* profile, built the same `-Zbuild-std=std,panic_unwind` way but
  without `--features web` (`assets/Makefile`'s `4th-rs-wasi.wasm`), keeps
  4th.rs's ordinary blocking `main()` instead and needs none of that
  sidestepping -- it's just another `wasi-worker.js` console, published
  alongside jonesforth.wasm/4th-wasi.wasm/5th-wasi.wasm/6th-wasi.wasm for
  how-many-roads.html's tab strip.
- **wat2wasm** — the `.wast` files *are* the source, so the "toolkit" is only
  an assembler. `jonesforth.wast`'s `KEY` is a classic blocking `read()`, like
  the wasi-sdk and Zig builds above, so its browser demo (originally
  [wasm/worker.js](wasm/worker.js)/`main.js`, the subject of
  [How Many Roads Must a Man Walk Down?](https://bur.gy/2025/11/29/how-many-roads.html),
  now that post's tab strip driving [wasm/wasi-repl.mjs](wasm/wasi-repl.mjs)
  like the other three interpreters -- `main.js` itself was unused and has
  been removed; its hand-rolled protocol is what `wasi-repl.mjs` generalized)
  also runs on `wasi-worker.js` rather than hand-written WASI imports.
  [wasi-worker.test.ts](wasm/wasi-worker.test.ts) covers all three consumers,
  including why the never-exits-on-EOF jonesforth session is driven as a
  child process that's killed as soon as it has produced the expected
  output, rather than awaited to completion in-process.

## Not interpreters

| file | what it is |
| --- | --- |
| [src/main.rs](src/main.rs) | Cargo test harness: feeds the preamble to a built binary and diffs stdout |
| [comparison.rs](comparison.rs) | one-off script checking that the generated dictionary matches the static rodata table |
| [forth.py](forth.py) | a Forth-to-CPython-bytecode compiler — a different experiment entirely |
| [benchmark.py](benchmark.py) | rebuilds the native and Wasmtime targets and benchmarks the shared Fibonacci workload |
| [5th-opt/](5th-opt/) | an LLM-driven search over `5th.c`'s parameter order, with patches and a transcript |
| [4th.fs](4th.fs), [4th.32.fs](4th.32.fs), [fixes.f](fixes.f) | the shared preamble, 64- and 32-bit cell flavours |

## Building and testing

`make` builds the native targets; the per-target recipes live in the
[Makefile](Makefile) and [build.zig](build.zig).

| command | covers |
| --- | --- |
| `make` | 4th, 5th, 6th, jansforth-zig, labeled-zig, hybrid-zig, jansforth, recurse, and both Rust binaries |
| `pytest forth/` | [test_4th.py](test_4th.py) (native) only — [test_4th_wasm.py](test_4th_wasm.py) is excluded, supplanted by `web/4th.test.ts` |
| `npm test` | builds `4th.wasm`/`5th.wasm` with wasi-sdk and `6th.wasm` with Zig's `wasm32-wasi` target, runs every vitest suite, then drives [html/4th.html](html/4th.html)/[html/5th.html](html/5th.html)/[html/6th.html](html/6th.html) headless (`mocha-headless-chrome`, same tool `regexp/web` already uses) |
| `npm run test:browser` | [browser/wasi-repl.browser.mjs](browser/wasi-repl.browser.mjs) (shared harness: [browser/wasi-demo.mjs](browser/wasi-demo.mjs)): serves each real `<n>th.html` demo and checks that its own in-page mocha spec ([wasm/wasi-repl-mocha.mjs](wasm/wasi-repl-mocha.mjs), loaded from the page itself, same as a human visiting it would see) passed |
| `npm run test:web` | [web/4th.test.ts](web/4th.test.ts) — the browser demo, driven in node; also covers `5th.wasm` if it's already been built, skipped otherwise |
| `make test-wasm` | [4th.rs](4th.rs) under wasmtime with `-W exceptions=y` |

## Keeping the grid obvious

The table above has to be maintained by hand, which is exactly the kind of
thing that rots. Two cheap conventions would let the grid be *derived* instead:

1. **A banner line in every source.** One machine-readable comment as the first
   line of each implementation —

   ```
   //! forth: lang=rust dispatch=tail-call wasm=wasip1
   ```

   — lets a ten-line script regenerate this README's tables and lets CI fail
   when a new file appears without one.

2. **Name the strategy, not the ordinal.** `4th`, `5th`, `6th`, `jansforth`
   encode history, not behaviour; `threaded.c`, `tailcall.c`, `switch.c`,
   `tailcall.zig`, `switch.rs` would put the grid in the file listing itself —
   the same way [wasm/](wasm/) already names its variants after what they do.
   The `.wast` names (`tabulate`, `localize`, `recurse`) are the model to copy.
