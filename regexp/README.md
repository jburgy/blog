# One regex engine, six ways to run it

Every file in this directory implements (or, in two cases, deliberately
does *not* implement) [Thompson's construction](https://en.wikipedia.org/wiki/Thompson%27s_construction):
Ken Thompson's 1968 recipe for compiling a regular expression to an NFA and
simulating every live thread in lockstep, one input character at a time. What
varies is *where the NFA lives* and *what runs its states*:

- **bytecode** — a small opcode enum, walked by a `switch`
- **native codegen** — the regex compiles straight to machine code in
  executable memory, no interpreter loop at all
- **host-language data structures** — the NFA is a plain list, dict, or
  a foreign library's own compiled form
- **threaded code inside a second interpreter** — the same trick, but the
  "machine" is a hosted Forth
- **a different algorithm** — recursive backtracking, no NFA in sight
- **historical transcriptions** — the original 1968 ALGOL-60 listings,
  present for reference and not runnable here

## Grouped by implementation style

### Bytecode-machine dispatch loops (portable C)

Each of these tokenizes, converts to postfix, and compiles to a flat array of
cells exactly as [Thompson's paper](https://swtch.com/~rsc/regexp/regexp-bytecode.c.txt)
does; they differ only in what a cell holds and how the interpreter dispatches on it.

| source | cell holds | dispatch | match semantics |
| --- | --- | --- | --- |
| [bytecode.c](bytecode.c) | `{operand, address}` pair (`JUMP`/`MATCH`/`BRANCH`/`STOP`) | `switch` | full match (`re.fullmatch`), no leftmost-search sweep |
| [switched.c](switched.c) | `union cell` (`JUMP`/`CHAR`/`FORK`/`STOP`/`FAIL`) | `switch` | unanchored search, reports the match's end |
| [threaded.c](threaded.c) | `union cell` whose op is the *address of a label* | GCC labels as values (computed goto) | unanchored search, reports the match's end |
| [labeled.zig](labeled.zig) | `union` (`.op`/`.link`/`.chr`), `.link` a `u16` index rather than a pointer | Zig's labeled `switch`/`continue` | unanchored search, reports the match's end |

`switched.c`'s header calls itself out as "the same on-the-fly compiler for
Thompson's algorithm" as `threaded.c`, with the opcodes reworked so they no
longer have to double as label addresses. Both track Thompson's *Notes*
revision (a `lambda` pointer per fragment) so a starred subexpression that can
itself match the empty string, like `a**`, never loops on ε.

`threaded.c`'s `search()` takes a `union cell **cache` precisely because a
label's address (`&&JUMP`, `&&CHAR`, …) is only meaningful for `goto *` inside
the function that declares it — so the one-time compile step can't be pulled
out into its own function the way `switched.c`'s and `bytecode.c`'s `study()`
are. Passing a NULL `*cache` with a pattern compiles once and caches the
result there; passing NULL for the pattern on later calls skips straight to
the dispatch loop and reuses it, since a label's address is a fixed constant
of the compiled binary and stays valid across every call to that function.

`labeled.zig` is a cell-for-cell port of `switched.c` (same node layouts, same
`lambda[]` revision), with two things changed. First, dispatch: Zig has no
labels-as-values, but its 0.14+ labeled `switch` lets a case `continue` by
value straight to another case (see
[simonklee.dk/labeled-switch](https://simonklee.dk/labeled-switch)), which
compiles to one indirect jump per case like `threaded.c`'s computed goto
rather than the single shared dispatch site `switched.c`'s plain
`for (;;) switch` uses — without needing a GNU extension, and without
`threaded.c`'s scoping problem, so `study()` and `search()` are separate
functions here. Second, addressing: a `Cell.link` is a `u16` index into the
`code` slice rather than a raw pointer, following jansforth.rs, whose Forth
VM addresses its whole flat `memory` array by plain integer index for the
same reason Python's `jit.py` uses byte/word offsets instead of pointers —
none of these three languages love raw interior pointers into a slice/array
the way C does.

### Native code generation (no interpreter loop)

These skip the bytecode step entirely: the compiler emits real machine
instructions into `mmap(PROT_EXEC)` memory and calls the result directly.

| source | language | target | notes |
| --- | --- | --- | --- |
| [arm.c](arm.c) | C | arm64 | hand-encoded instruction words; runs natively here |
| [x86.c](x86.c) | C | x86-64 | hand-encoded instruction words; needs Rosetta on this arm64 host |
| [jit.py](jit.py) | Python | arm64 *or* x86-64 | `Arm64`/`X86_64` bytearray/list encoders, picked at runtime by `platform.machine()`; called through `ctypes.CFUNCTYPE` |

`arm.c` and `x86.c` share the same node layouts and the same `lambda[]`
pointer-per-fragment revision as `threaded.c`/`switched.c` above (see the
comment above each file's `codelen`). `jit.py` instead runs every pattern
through `strip()` first — rewriting `e*` to `e'*`, `e'` being `e` minus ε —
so its own `Arm64`/`X86_64` encoders never need a `lambda[]` array at all;
`regexp.f`, discussed below, has since adopted the same `strip()` in place of
`x86.c`'s lambda pointers.

### High-level / managed-runtime interpreters

| source | representation | notes |
| --- | --- | --- |
| [regexp.py](regexp.py): `Instructions` | Thompson's bytecode machine as a plain Python `list` | ports the C tokenizer/postfix step almost verbatim; anchored at position 0 |
| [regexp.py](regexp.py): `Graph` | `dict`-of-`dict`, ε-edges are `""` keys | more "pythonic" walk via `__getitem__`, in the spirit of `graphlib` |
| [regexp.jl](regexp.jl) | [PCRE2](https://www.pcre.org/)'s own compiled opcodes, read directly out of its `Ptr{UInt8}` | doesn't reimplement Thompson's construction — it lets PCRE compile, then interprets (or `eval`-generates and JITs) PCRE's bytecode from Julia |

`regexp.py` is the only file with two distinct engines side by side, on
purpose: its module docstring compares `Instructions` and `Graph` by showing
how each compiles `a\|b\|c`.

### Threaded code inside a second interpreter

| source | notes |
| --- | --- |
| [regexp.f](regexp.f) | `RE"` is an `IMMEDIATE` Forth word that pokes threaded code — a one-to-one port of `x86.c` — directly into the definition being compiled inside [jonesforth](https://github.com/nornagon/jonesforth). No second code generator needed; Forth already owns one. Its epsilon-elimination now reuses `jit.py`'s `strip()` instead of `x86.c`'s lambda-pointer revision. |

[web/](web/) (the browser demo) and [tracing/](tracing/) (its own
documented visualizer, see [tracing/README.md](tracing/README.md)) exist only
to drive and inspect this one file; both are listed under "Supporting
tooling" below.

### A different algorithm entirely

| source | algorithm | supports |
| --- | --- | --- |
| [regexp.zig](regexp.zig) | Kernighan and Pike's recursive-descent backtracking `match`/`matchhere`/`matchstar` (see [Beautiful Code](https://www.cs.princeton.edu/courses/archive/spr09/cos333/beautiful.html)) | literal characters, `.`, a trailing `*`, leading `^`, trailing `$` — **no groups, no alternation** |

This one isn't Thompson's construction at all, and its regex argument is
`comptime`, so Zig can specialize the recursion per pattern at compile time.
It can't run this directory's usual `a(b|c)*d` benchmark pattern — there is no
`(...)`/`|` support — so it's benchmarked separately, below.

### Historical transcriptions (not runnable here)

| source | what it is |
| --- | --- |
| [thompson1968.a60](thompson1968.a60) | the third stage from the 1968 CACM paper itself, transcribed from the published ALGOL-60 listing |
| [thompson1968-lambda.a60](thompson1968-lambda.a60) | the paper's own *Notes* revision, tracking `lambda` explicitly so `a**` doesn't compile an infinite loop — the same revision every C/Python/Forth file above already carries forward |

No ALGOL-60 compiler is available on this host (or, realistically, easily
anywhere), so these are read-only reference material, not benchmarked.

## Benchmarks

Measured on macOS/arm64 with Apple clang 21.0.0, Zig 0.15.2, and Node
v24.18.0. Lower is faster; medians within 3% are tied. Run
`python3 benchmark.py` from this directory to rebuild everything and
reproduce the table (add `--trials`/`--iterations` to adjust it).

The shared workload is one search for `a(b|c)*d` in `abccbcccd` — a 9-byte
string the match consumes in full, so unanchored search-anywhere engines
(the C variants, `arm.c`, `labeled.zig`, `regexp.f`) and the
anchored-at-position-0 Python interpreters (`regexp.py`'s
`Instructions`/`Graph`) report the same answer, keeping the comparison
apples to apples *except* where noted. Each figure is the median and
min–max range of seven timed calls after warm-up (native/JIT targets,
including `labeled.zig`'s small C-ABI dylib: 200,000 calls per trial
in-process; `regexp.zig`: 2,000,000 calls in a compiled binary; `regexp.f`:
5,000 calls per Node subprocess, matching the existing
[tracing/bench.mjs](tracing/bench.mjs)).

| # | implementation | style | µs/op (median, range) | rank |
| --- | --- | --- | ---: | ---: |
| 1 | [regexp.zig](regexp.zig) | different algorithm | 0.0055 (0.0041–0.0074)\* | 1\* |
| 2 | [bytecode.c](bytecode.c) | bytecode + switch | 0.628 (0.595–0.660) | 2 |
| 3 | [switched.c](switched.c) | bytecode + switch | 0.740 (0.696–0.821) | 3 |
| 4 | [labeled.zig](labeled.zig) | bytecode + Zig labeled switch | 0.887 (0.859–0.914) | 4 |
| 5 | [arm.c](arm.c) | native codegen | 0.911 (0.679–1.231) | 4 |
| 6 | [threaded.c](threaded.c) | bytecode + labels as values | 1.066 (1.021–1.481) | 5 |
| 7 | [jit.py](jit.py) `Pattern` | native codegen (from Python) | 1.414 (1.323–1.463) | 6 |
| 8 | [regexp.py](regexp.py) `Graph` | high-level interpreter | 5.947 (5.356–6.512) | 7 |
| 9 | [regexp.py](regexp.py) `Instructions` | high-level interpreter | 7.515 (7.005–8.879) | 8 |
| 10 | [regexp.f](regexp.f) | threaded code, hosted Forth | 35.0 (30.4–39.2) | 9 |
| — | [x86.c](x86.c) | native codegen | N/R — needs Rosetta on this arm64 host | N/R |
| — | [regexp.jl](regexp.jl) | host-language / PCRE2 | N/R — Julia is not installed here | N/R |
| — | [thompson1968.a60](thompson1968.a60), [thompson1968-lambda.a60](thompson1968-lambda.a60) | historical | N/R — no ALGOL-60 compiler | N/R |

\* `regexp.zig` cannot express `a(b|c)*d` — it has no grouping or alternation
— so it is measured on `a.*d` against the same string instead, using
`std.mem.doNotOptimizeAway` to keep the compiler from folding the whole loop
away at comptime. That workload is both algorithmically different and much
cheaper (no thread-list bookkeeping at all), so its rank of 1 reflects the
easier task, not a faster NFA engine; treat it as its own category rather
than a win over the C/JIT engines below it.

At this 9-byte input, the six C/Zig/JIT engines (ranks 2–6) sit within a bit
over 2x of each other, and the gaps between them are the same order of
magnitude as one `ctypes` call's own overhead — this benchmark mostly
measures dispatch and call overhead, not asymptotic NFA performance. All six
now time only the reusable execute/search step (see `threaded.c`'s note
above), so the small gaps between them are real, if modest, differences in
dispatch cost rather than artifacts of unequal measurement. In particular,
`labeled.zig`'s labeled `switch` lands in the same tied cluster as `arm.c`'s
hand-written machine code and a bit ahead of `threaded.c`'s computed goto —
at this scale it's a wash, not the clear win over a plain `switch` that
branch-prediction theory would suggest; a workload with a longer subject
string and more live threads per round would be a fairer test of that claim.
`regexp.f`'s cost is dominated by running inside `forth.wasm` under Node
rather than by the matching algorithm itself; see
[tracing/README.md](tracing/README.md) for a per-step breakdown of where that
time goes.

## Supporting tooling (not implementations)

| path | role |
| --- | --- |
| [test_regexp.py](test_regexp.py) | builds `bytecode.c`/`switched.c`/`threaded.c`/`arm.c` (plain and `-fsanitize=address,undefined`) and `jit.py`'s `Pattern`, then fuzzes all of them against Python's `re` on randomly generated nested-star patterns; also drives `regexp.f` through a native 32-bit jonesforth build when that toolchain is available |
| [benchmark.py](benchmark.py) | builds and times every runnable implementation on the shared workload above; produces the table in this README |
| [.clang-format](.clang-format) | LLVM-based style used by every `.c` source here |
| [web/](web/) | browser demo (`index.html`, `demo.mjs`, `matcher.mjs`, `forth.mjs`, `forth.wasm`) that compiles a live pattern with `regexp.f` and highlights matches in a paragraph of text |
| [tracing/](tracing/) | stops the browser demo mid-search and renders everything live at that moment (JS stack, V8 tier, linear memory, Forth stacks, Thompson's thread list) as an SVG; also home to `bench.mjs`, the µs-per-search timer this README's `regexp.f` row is built on |
