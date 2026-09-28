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
| **Zig** | [jansforth.zig](jansforth.zig)<br>[labeled.zig](labeled.zig) | — | [6th.zig](6th.zig) |
| **Rust** | [jansforth.rs](jansforth.rs) | — | [4th.rs](4th.rs) |
| **wasm** | [wasm/tabulate.wast](wasm/tabulate.wast)<br>[wasm/recurse.wast](wasm/recurse.wast) | — | [wasm/jonesforth.wast](wasm/jonesforth.wast)<br>[wasm/localize.wast](wasm/localize.wast) |

Two holes are structural rather than accidental: neither Zig nor WebAssembly
has anything like GCC's `&&label`, so the middle column can only ever be C.
The Zig cell holds two implementations rather than one: same `switch`
strategy, two different ways of writing it (see below).

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
the loop. LLVM lowers each `continue` to its own indirect jump (its own
jump-table entry), so it sits between plain `switch` and labels-as-values:
still one shared jump *table*, but no more shared jump *site*. Keeping it a
byte-for-byte copy of jansforth.zig save for that one change isolates the
cost of the extra jump for benchmarking.

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
| [4th.c](4th.c) | C | labels as values | ✅ | Emscripten (`make 4th.js`) | Original; `NEXT` is `goto **target`; standalone Wasm used for Wasmtime | 70.8 (57.8-219.5) / 2 | 92.6 (79.3-181.3) / 3 |
| [5th.c](5th.c) | C | tail calls | ✅ | Emscripten *and* wasi-sdk clang | `NEXT` is `musttail return ip->word->code(...)`; standalone Wasm used for Wasmtime | 66.9 (58.4-128.0) / 1 | 284.7 (277.5-355.3) / 5 |
| [jansforth.c](jansforth.c) | C | switch | — | — | Opcode enum, everything in one `memory[]` array | 93.0 (87.8-111.0) / 6 | — |
| [recurse.c](recurse.c) | C | switch | — | — | `docol()` is the loop and recurses; return stack becomes a shadow stack | 96.2 (88.2-189.6) / 6 | — |
| [6th.zig](6th.zig) | Zig | tail calls | ✅ | Emscripten via `zig build -Dtarget=wasm32-emscripten` | `@call(.always_tail, primitives[code], ...)`; native result only | 89.1 (83.9-221.4) / 5 | — |
| [jansforth.zig](jansforth.zig) | Zig | switch | — | — | `while (true) switch (op) { ... }`; dictionary generated like jansforth.rs's | 71.8 (65.1-104.3) / 2 | — |
| [labeled.zig](labeled.zig) | Zig | labeled switch | — | — | jansforth.zig cell for cell; every prong `continue`s a labeled `switch` instead | 76.7 (65.7-88.2) / 4 | — |
| [4th.rs](4th.rs) | Rust | tail calls | ✅ | wasm32-wasip1 (Wasmtime, and uwasi in the browser) | Nightly `become`; every primitive returns `!` | 105.0 (94.5-114.8) / 9 | 490.5 (448.0-549.3) / 7 |
| [jansforth.rs](jansforth.rs) | Rust | switch | — | — | Transcription of jansforth.c, run with `rust-script` | 94.3 (84.7-111.3) / 6 | — |
| [wasm/tabulate.wast](wasm/tabulate.wast) | wasm | switch | ✅ | wat2wasm + Wasmtime | One big `br_table`, no indirect calls | — | 72.8 (68.7-110.3) / 1 |
| [wasm/recurse.wast](wasm/recurse.wast) | wasm | switch | ✅ | wat2wasm + Wasmtime | Tabulate with a recursive `$docol`; colon-word returns live on the wasm call stack | — | 76.1 (64.2-87.5) / 2 |
| [wasm/jonesforth.wast](wasm/jonesforth.wast) | wasm | tail calls | ✅ | wat2wasm + Wasmtime | `return_call_indirect`; state in globals | — | 303.2 (287.7-371.3) / 6 |
| [wasm/localize.wast](wasm/localize.wast) | wasm | tail calls | ✅ | wat2wasm + Wasmtime | Same, with `cfa`/`ip`/`sp`/`rsp` passed as parameters | — | 268.0 (241.3-391.6) / 4 |
| [jonesforth.S](../jonesforth/jonesforth.S) | x86 assembly | indirect threaded | — | Linux/i386 | Requires Linux on x86; not runnable on this macOS/arm64 host | N/R | — |

## Benchmarks

Measured on macOS/arm64 with Apple clang 21.0.0, Rust nightly 1.101.0,
Zig 0.15.2, Emscripten 6.0.2, WABT 1.0.39, and Wasmtime 49.0.1.
Lower times are faster. Native and Wasmtime ranks are separate; medians within
3% are tied.

Each result is the median and min-max range of eleven timed runs after a warm-up. Targets are
run in a different deterministic shuffled order on each trial to reduce
systematic ordering bias; the harness also prints each range and every sample.
The benchmark loads the definitions from [`fibonacci.fs`](../talks/fibonacci.fs) and executes
its fast-doubling `FIBONACCI` word 100,000 times at `n=46`, then checks the
result against `1836311903`. Using 46 keeps the result in range for the
32-bit-cell implementations. The Wasmtime column includes the hand-written
`.wast` files, standalone Emscripten builds of `4th.c` and `5th.c`, and the
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

Run `python3 benchmark.py` from this directory to rebuild the native and Wasm
targets in a temporary directory, validate each result, and print medians,
ranges, and individual timings.
The script accepts `--iterations`, `--trials`, and `--timeout` overrides; it
requires clang, Emscripten, nightly Rust with the `wasm32-wasip1` target and
`rust-src`, Zig, WABT, and Wasmtime.

### Toolkits, briefly

- **Emscripten** — full libc and a POSIX-ish runtime, paired here with
  [xterm-pty](https://github.com/mame/xterm-pty) so the pages in [html/](html/)
  get a real terminal. Emits a `.mjs` loader beside the `.wasm`.
- **wasi-sdk clang** — plain `wasm32-wasip1`, no JS glue; the artifact is a
  bare `5th.wasm` driven by [uwasi](https://github.com/kateinoigakukun/uwasi)
  in [5th.test.ts](5th.test.ts).
- **Rust `wasm32-wasip1`** — two profiles, because [4th.rs](4th.rs) halts by
  panicking: `make test-wasm` rebuilds `std` with `panic_unwind` for wasmtime,
  while `make web` swaps the panic for a host throw so the browser build in
  [web/](web/) needs no exception-handling proposal.
- **wat2wasm** — the `.wast` files *are* the source, so the "toolkit" is only
  an assembler; the WASI imports are satisfied by hand in
  [wasm/worker.js](wasm/worker.js).

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
| `make` | 4th, 5th, 6th, jansforth-zig, jansforth-zig-labeled, jansforth, recurse, and both Rust binaries |
| `pytest forth/` | [test_4th.py](test_4th.py) (native) and [test_4th_wasm.py](test_4th_wasm.py) (Emscripten) |
| `npm test` | builds `5th.wasm` with wasi-sdk, then runs every vitest suite |
| `npm run test:web` | [web/4th.test.ts](web/4th.test.ts) only — the browser demo, driven in node |
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
