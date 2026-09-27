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
| **Zig** | — | — | [6th.zig](6th.zig) |
| **Rust** | [jansforth.rs](jansforth.rs) | — | [4th.rs](4th.rs) |
| **wasm** | [wasm/tabulate.wast](wasm/tabulate.wast)<br>[wasm/recurse.wast](wasm/recurse.wast) | — | [wasm/jonesforth.wast](wasm/jonesforth.wast)<br>[wasm/localize.wast](wasm/localize.wast) |

Two holes are structural rather than accidental: neither Zig nor WebAssembly
has anything like GCC's `&&label`, so the middle column can only ever be C.

## The strategies

**switch** — one flat loop, `while (1) switch (memory[cfa]) { ... }`, with the
code field holding a small integer opcode. Portable to anything, and the only
strategy a stock WebAssembly engine can express without the tail-call proposal
(`br_table`). Pays an indirect branch through the jump table on every word.

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

| source | language | strategy | wasm | toolkit | notes | native ms / rank | Wasmtime ms / rank |
| --- | --- | --- | :---: | --- | --- | ---: | ---: |
| [4th.c](4th.c) | C | labels as values | ✅ | Emscripten (`make 4th.js`) | Original; `NEXT` is `goto **target`; standalone Wasm used for Wasmtime | N/R (segfault) | 247.8 / 5 |
| [5th.c](5th.c) | C | tail calls | ✅ | Emscripten *and* wasi-sdk clang | `NEXT` is `musttail return ip->word->code(...)`; standalone Wasm used for Wasmtime | 53.9 / 1 | 228.2 / 4 |
| [jansforth.c](jansforth.c) | C | switch | — | — | Opcode enum, everything in one `memory[]` array | 72.9 / 3 | — |
| [recurse.c](recurse.c) | C | switch | — | — | `docol()` is the loop and recurses; return stack becomes a shadow stack | 77.7 / 4 | — |
| [6th.zig](6th.zig) | Zig | tail calls | ✅ | Emscripten via `zig build -Dtarget=wasm32-emscripten` | `@call(.always_tail, primitives[code], ...)`; native result only | 70.5 / 2 | — |
| [4th.rs](4th.rs) | Rust | tail calls | ✅ | wasm32-wasip1 (Wasmtime, and uwasi in the browser) | Nightly `become`; every primitive returns `!` | 82.9 / 6 | 377.1 / 6 |
| [jansforth.rs](jansforth.rs) | Rust | switch | — | — | Transcription of jansforth.c, run with `rust-script` | 78.7 / 4 | — |
| [wasm/tabulate.wast](wasm/tabulate.wast) | wasm | switch | ✅ | wat2wasm + Wasmtime | One big `br_table`, no indirect calls | — | 57.3 / 1 |
| [wasm/recurse.wast](wasm/recurse.wast) | wasm | switch | ✅ | wat2wasm + Wasmtime | Tabulate with a recursive `$docol`; colon-word returns live on the wasm call stack | — | 56.0 / 1 |
| [wasm/jonesforth.wast](wasm/jonesforth.wast) | wasm | tail calls | ✅ | wat2wasm + Wasmtime | `return_call_indirect`; state in globals | — | N/R (wrong result) |
| [wasm/localize.wast](wasm/localize.wast) | wasm | tail calls | ✅ | wat2wasm + Wasmtime | Same, with `cfa`/`ip`/`sp`/`rsp` passed as parameters | — | 202.6 / 3 |
| [jonesforth.S](../jonesforth/jonesforth.S) | x86 assembly | indirect threaded | — | Linux/i386 | Requires Linux on x86; not runnable on this macOS/arm64 host | N/R | — |

## Benchmarks

Measured on macOS/arm64 with Apple clang 21.0.0, Rust nightly 1.101.0,
Zig 0.15.2, Emscripten 6.0.2, WABT 1.0.39, and Wasmtime 49.0.1.
Lower times are faster. Native and Wasmtime ranks are separate; medians within
3% are tied.

Each result is the median of seven timed runs after one warm-up. The benchmark
loads the definitions from [`fibonacci.fs`](../talks/fibonacci.fs) and executes
its fast-doubling `FIBONACCI` word 100,000 times at `n=46`, then checks the
result against `1836311903`. Using 46 keeps the result in range for the
32-bit-cell implementations. The Wasmtime column includes the hand-written
`.wast` files, standalone Emscripten builds of `4th.c` and `5th.c`, and the
Rust `wasm32-wasip1` build. Wasmtime modules were compiled once at optimization
level 2 and run as precompiled modules with tail calls and exceptions enabled;
module compilation is excluded, while process/runtime startup is included.
Native builds used optimized settings (`-O3`, Cargo release, or Zig
`ReleaseFast`).

The file's default `n=92` exceeds the 32-bit cell range used by most variants.
At the common-width input `46`, `wasm/jonesforth.wast` produces the wrong
result, so it is not ranked. The native `4th.c` build also segfaulted before
consuming the benchmark input on this host; it is ranked only for its
Emscripten Wasm target.

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
| [5th-opt/](5th-opt/) | an LLM-driven search over `5th.c`'s parameter order, with patches and a transcript |
| [4th.fs](4th.fs), [4th.32.fs](4th.32.fs), [fixes.f](fixes.f) | the shared preamble, 64- and 32-bit cell flavours |

## Building and testing

`make` builds the native targets; the per-target recipes live in the
[Makefile](Makefile) and [build.zig](build.zig).

| command | covers |
| --- | --- |
| `make` | 4th, 5th, 6th, jansforth, recurse, and both Rust binaries |
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
