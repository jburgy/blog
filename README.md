[![Python package](https://github.com/jburgy/blog/actions/workflows/pythonpackage.yml/badge.svg)](https://github.com/jburgy/blog/actions/workflows/pythonpackage.yml)
[![JavaScript](https://github.com/jburgy/blog/actions/workflows/javascript.yml/badge.svg)](https://github.com/jburgy/blog/actions/workflows/javascript.yml)
[![Build and Deploy](https://github.com/jburgy/blog/actions/workflows/deploy.yml/badge.svg)](https://github.com/jburgy/blog/actions/workflows/deploy.yml)
[![GitHub Pages](https://img.shields.io/github/deployments/jburgy/blog/github-pages?label=demos&logo=githubpages)](https://bur.gy/blog/)

[![Tested with pytest](https://img.shields.io/badge/py-test-blue?logo=pytest)](https://github.com/jburgy/blog/actions/workflows/pythonpackage.yml)
[![codecov](https://codecov.io/gh/jburgy/blog/graph/badge.svg)](https://codecov.io/gh/jburgy/blog)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Checked with ty](https://img.shields.io/badge/types-ty-261230)](https://github.com/astral-sh/ty)
[![Checked with pyright](https://microsoft.github.io/pyright/img/pyright_badge.svg)](https://microsoft.github.io/pyright/)

[![Python 3.13 | 3.14](https://img.shields.io/badge/python-3.13%20%7C%203.14-blue?logo=python&logoColor=white)](pyproject.toml)
[![License](https://img.shields.io/github/license/jburgy/blog)](LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/jburgy/blog)](https://github.com/jburgy/blog/commits/main)
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/jburgy/blog.git/main)

# blog

Support materials for the posts on **[bur.gy](https://bur.gy)** — interpreters,
compilers, solvers and assorted experiments, plus the machinery that turns some
of them into demos you can type into from inside a blog post.

The prose lives in a different repository,
[jburgy/jburgy.github.io](https://github.com/jburgy/jburgy.github.io); this one
holds the code the prose talks about.

## How a demo reaches the page

The two repositories are deployed separately but land on the same origin.

```
jburgy.github.io  --Jekyll-->  https://bur.gy/            (the posts)
jburgy/blog       --Pages -->  https://bur.gy/blog/       (the demos)
```

1. **[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)** runs on
   every push to `main` (and builds, without deploying, on pull requests). It
   checks out submodules, installs node, wasi-sdk and `uv`, then runs
   `make --jobs=4` in [`assets/`](assets/).
2. `actions/upload-pages-artifact` takes the whole of `assets/` as-is and
   `actions/deploy-pages` publishes it. **Nothing outside `assets/` is ever
   served.**
3. A post on bur.gy loads the result with an absolute path — `/blog/wasi-repl.mjs`,
   `/blog/jonesforth.wasm`, `/blog/regexp/web/demo.mjs`. Same origin, so no CORS,
   no CDN, and the demo version always matches whatever `main` last built.
4. The WASI REPL demos need no COOP/COEP headers or service worker: `wasi-command.mjs`
   runs the guest on the main thread and suspends its blocking `read()` with JSPI
   (`WebAssembly.Suspending`/`promising`: Chrome 137+, Firefox 139+, not Safari).

### The role of `assets/`

[`assets/`](assets/) is *not* a source folder — it is the staging area that
becomes the published site. Almost everything in it is generated and gitignored;
what is checked in is the recipe:

| file | what it does |
| --- | --- |
| [`assets/Makefile`](assets/Makefile) | the whole build. `VPATH = ../forth`, so it reaches back into sibling folders rather than duplicating their sources: wasi-sdk/`uvx`+`python-zig` for the C and Zig interpreters' `.wasm` builds, `wat2wasm` for the hand-written wasm, `asc` for the AssemblyScript ones, and plain `cp` for data files like `jonesforth.f` |
| [`assets/package.json`](assets/package.json) | wraps the `asc` invocations for the AssemblyScript builds, run through `npx` so nothing needs installing |
| [`assets/thug-life.js`](assets/thug-life.js), [`assets/regexp-snapshot.svg`](assets/regexp-snapshot.svg) | one-off assets embedded by a single post each |
| [`assets/index.html`](assets/index.html) | the `/blog/` landing page: every demo below, latest first, inlined inside a `<details>` per demo and lazily mounted the first time it's opened |

What comes out, and where it comes from:

| published as | built from | seen in |
| --- | --- | --- |
| `/blog/4th-wasi.wasm` | [`forth/4th.c`](forth/4th.c) (wasi-sdk target) | [forth/html/4th.html](forth/html/4th.html) and [What, Forth, Again?](https://bur.gy/2023/02/24/what-forth-again.html), as published |
| `/blog/5th-wasi.wasm` | [`forth/5th.c`](forth/5th.c) (wasi-sdk target) | [forth/html/5th.html](forth/html/5th.html) and [What is Tail Call Elimination?](https://bur.gy/2024/03/29/tail-recursion.html), as published |
| `/blog/6th-wasi.wasm` | [`forth/6th.zig`](forth/6th.zig) (`wasm32-wasi` target) | [forth/html/6th.html](forth/html/6th.html) and [Why not try Zig next?](https://bur.gy/2024/08/31/why-not-zig.html), as published |
| `/blog/jonesforth.wasm` | [`forth/wasm/jonesforth.wast`](forth/wasm/jonesforth.wast) | [How Many Roads Must a Man Walk Down?](https://bur.gy/2025/11/29/how-many-roads.html) |
| `/blog/regexp/web/` | [`regexp/web/`](regexp/web/) + [`forth/wasm/tabulate.wast`](forth/wasm/tabulate.wast) | [What Makes an Expression Regular?](https://bur.gy/2026/09/24/what-makes-an-expression-regular.html) |
| `/blog/fourt2py/web/` | [`fourt2py/web/`](fourt2py/web/) | shape a waveform's spectrum and hear `FOURT.F` transform it back, post forthcoming |
| `/blog/lisp-wasi.wasm` | [`lisp/assembly/wasi.ts`](lisp/assembly/wasi.ts) (real WASI ABI, same `core.ts`) | [What do you mean, homoiconic?](https://bur.gy/2023/03/09/what-do-you-mean-homoiconic.html); preamble is [`lisp/eliza.lisp`](lisp/eliza.lisp), a pattern-matching ELIZA chatbot |
| `/blog/lisp-wast.wasm` | [`lisp/assembly/core.wast`](lisp/assembly/core.wast) (`core.ts` by hand in WAT, WASI command) | the same post, as the `core.wast` tab, with the same `lisp/eliza.lisp` preamble |
| `/blog/tabulate.wasm` + `/blog/lisp/eliza.f` | [`lisp/lisp.f`](lisp/lisp.f) on [`forth/wasm/tabulate.wast`](forth/wasm/tabulate.wast) | the same post, as the `lisp.f` tab; `eliza.f` is `jonesforth.f`, `lisp.f`, `LISP` and `eliza.lisp` concatenated, since a REPL takes one preamble |
| `/blog/TinyBasic-wasi.wasm` | [`TinyBasic/assembly/wasi.ts`](TinyBasic/assembly/wasi.ts) (real WASI ABI, same `core.ts`) | [When did Basic become insulting?](https://bur.gy/2023/03/16/put-it-in-a-brandy-snifter.html) |
| `/blog/jonesforth.f` | the [`jonesforth`](jonesforth/) submodule | every Forth terminal |

Every row above is also embedded live in [`assets/index.html`](assets/index.html) itself
(`/blog/`'s own landing page), one `<details>` per demo, alongside `ising/`'s and
`fourt2py/web/`'s demos -- not just linked to its post.

## Folders

Folders that feed a demo are marked ▶.

| folder | | what is in it |
| --- | :---: | --- |
| [`forth/`](forth/) — [README](forth/README.md) | ▶ | Eleven jonesforth interpreters in C, Zig, Rust and hand-written wasm, catalogued by dispatch strategy. `4th.c`, `5th.c`, `6th.zig` and `wasm/jonesforth.wast` are the ones that ship |
| [`regexp/`](regexp/) | ▶ | Thompson's 1968 construction, ported over and over: the original Algol 60, C (bytecode, threaded, switched, and a 32-bit JIT), Julia, Zig, Python and Forth. [`regexp/web/`](regexp/web/) is the browser demo, [`regexp/tracing/`](regexp/tracing/) — [README](regexp/tracing/README.md) — draws the animated snapshot |
| [`lisp/`](lisp/) | ▶ | [sectorlisp](https://justine.lol/sectorlisp/) rewritten in AssemblyScript, unmodified. `assembly/core.ts` holds the interpreter; `host.ts`/`wasiHost.ts` give it either the original custom getchar/putchar host import or real WASI fd_read/fd_write (see `asc`'s `--use` flags in `package.json`), without duplicating `core.ts`. [`eliza.lisp`](lisp/eliza.lisp) is a small ELIZA chatbot fed as the demo's preamble, written as a single self-recursive expression (the same sibling-`LAMBDA`/self-application trick `lisp.lisp`'s own metacircular-evaluator bootstrap already uses); its keyword/reflection rules follow [z88dk's `clisp` Tiny ELIZA example](https://github.com/z88dk/z88dk/blob/master/examples/clisp/eliza.l), reimplemented from scratch against sectorlisp's nine primitives (no numbers, no mutation). [`lisp.f`](lisp.f) is the same language again in FORTH, with a mark-and-sweep GC whose roots are the FORTH data and return stacks; it runs `eliza.lisp` unmodified on `forth/wasm/jonesforth.wast` and `forth/wasm/tabulate.wast` (see [`tests/lisp-forth.test.mjs`](lisp/tests/lisp-forth.test.mjs)). [`assembly/core.wast`](lisp/assembly/core.wast) is `core.ts` once more, hand-written in WAT for the fewest instructions (raw-address cells, nil = 0, shallow binding), as a WASI command checked by [`tests/wast.test.mjs`](lisp/tests/wast.test.mjs) |
| [`TinyBasic/`](TinyBasic/) | ▶ | Tiny BASIC's original IL virtual machine, plus a Python assembler for it and an AssemblyScript interpreter, split into `core.ts`/`host.ts`/`wasiHost.ts` the same way as `lisp/` |
| [`assets/`](assets/) | ▶ | The build and publish staging area described above |
| [`simplex/`](simplex/) — [README](simplex/README.md) | | The NSWC `SMPLX` revised simplex solver: the Fortran, a NumPy transcription, an f2py wrapper and benchmarks |
| [`linprog/`](linprog/) | | Linear-programming odds and ends around the same posts |
| [`sudoku/`](sudoku/) | | Sudoku as an exact-cover / satisfiability problem |
| [`fourt2py/`](fourt2py/) | ▶ | Calling 1960s Fortran (`FOURT`) from Python — the "what ever happened to Fortran?" experiment. [`fourt2py/web/`](fourt2py/web/) is a browser demo: drag knots on a frequency-domain chart and [`fourt.pow2.mjs`](fourt2py/web/fourt.pow2.mjs) — a plain-JS specialization of `FOURT.F` to one dimension and power-of-two lengths — turns it into an oscilloscope trace and a tone. [`fourt2py/wasm/fourt.c`](fourt2py/wasm/fourt.c) (a general C transliteration compiled to WebAssembly) and [`fourt2py/web/fourt.pure.mjs`](fourt2py/web/fourt.pure.mjs) (its general, non-power-of-two pure-JS counterpart) aren't part of the deployed demo but remain for comparison — see [`fourt2py/web/benchmark.mjs`](fourt2py/web/benchmark.mjs) |
| [`progress/`](progress/) | | Foreign-function and progress-reporting experiments |
| [`talks/`](talks/) | | Slide decks, including the Zig-from-Python and data-visualisation talks |
| [`fun/`](fun/) | | The scratch drawer: n-body, bytecode assemblers, Prechelt's benchmark, Zig toys |
| [`aoc2024/`](aoc2024/), [`aoc2025/`](aoc2025/), [`foo/`](foo/) | | Advent of Code and puzzle solutions; excluded from pytest collection (see [`CODE_REVIEW.md`](CODE_REVIEW.md)) |
| [`notebooks/`](notebooks/) | | Jupyter notebooks, reachable through the Binder badge above |
| [`jonesforth/`](jonesforth/) | ▶ | Submodule, not ours. `deploy.yml` needs `submodules: true` |

## The other workflows

| workflow | what it does |
| --- | --- |
| [`pythonpackage.yml`](.github/workflows/pythonpackage.yml) | `uv` + `ruff` + `ty` + `pytest` on 3.13 and 3.14. Needs `gfortran` and 32-bit gcc for the Fortran and jonesforth fixtures |
| [`javascript.yml`](.github/workflows/javascript.yml) | node 24, wasi-sdk and nightly Rust; builds `forth/5th.wasm` and `forth/web/4th.wasm`, then runs the vitest and mocha suites with coverage |
| [`deploy.yml`](.github/workflows/deploy.yml) | the Pages build described above |

`pythonpackage.yml` and `javascript.yml` both upload coverage to [Codecov](https://codecov.io/gh/jburgy/blog)
(the badge above links there), the latter tagged with `forth`/`regexp-web`/`fourt2py`
flags so each job's numbers stay distinguishable. Both workflows run
unconditionally on every push (`javascript.yml` has no path filter) so every
commit produces the same 5 uploads (2 Python matrix jobs + 3 JS jobs);
[`codecov.yml`](codecov.yml)'s `after_n_builds: 5` tells Codecov to wait for
all of them before finalizing the report — without it, Codecov finalizes as
soon as the first couple of uploads land, silently dropping whichever jobs
are still running. This requires activating the repo at
[codecov.io](https://codecov.io) once and adding its upload token as the
`CODECOV_TOKEN` repo secret; after that, opening a pull request's **Files
changed** tab shows uncovered lines flagged inline, right next to the diff —
install the [Codecov browser extension](https://github.com/codecov/browser-extension) to
get the same green/red coverage gutters on any file on github.com, not just
the ones in a diff.
