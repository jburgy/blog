[![Python package](https://github.com/jburgy/blog/actions/workflows/pythonpackage.yml/badge.svg)](https://github.com/jburgy/blog/actions/workflows/pythonpackage.yml)
[![JavaScript](https://github.com/jburgy/blog/actions/workflows/javascript.yml/badge.svg)](https://github.com/jburgy/blog/actions/workflows/javascript.yml)
[![Build and Deploy](https://github.com/jburgy/blog/actions/workflows/deploy.yml/badge.svg)](https://github.com/jburgy/blog/actions/workflows/deploy.yml)
[![GitHub Pages](https://img.shields.io/github/deployments/jburgy/blog/github-pages?label=demos&logo=githubpages)](https://bur.gy/blog/)

[![Tested with pytest](https://img.shields.io/badge/py-test-blue?logo=pytest)](https://github.com/jburgy/blog/actions/workflows/pythonpackage.yml)
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
   checks out submodules, installs node, `emsdk` and `uv`, then runs
   `make --jobs=4` in [`assets/`](assets/).
2. `actions/upload-pages-artifact` takes the whole of `assets/` as-is and
   `actions/deploy-pages` publishes it. **Nothing outside `assets/` is ever
   served.**
3. A post on bur.gy loads the result with an absolute path — `/blog/5th.mjs`,
   `/blog/lisp.worker.js`, `/blog/regexp/web/demo.mjs`. Same origin, so no CORS,
   no CDN, and the demo version always matches whatever `main` last built.
4. GitHub Pages sends no COOP/COEP headers, but `xterm-pty` needs
   `SharedArrayBuffer` to block a worker on a read. The site works around this
   with a service worker,
   [`docs/sw.js`](https://github.com/jburgy/jburgy.github.io/blob/main/docs/sw.js),
   which re-serves the demo URLs with cross-origin-isolation headers. A new
   demo asset has to be added to the pattern list there or it will not be
   isolated.

### The role of `assets/`

[`assets/`](assets/) is *not* a source folder — it is the staging area that
becomes the published site. Almost everything in it is generated and gitignored;
what is checked in is the recipe:

| file | what it does |
| --- | --- |
| [`assets/Makefile`](assets/Makefile) | the whole build. `VPATH = ../forth`, so it reaches back into sibling folders rather than duplicating their sources: `emcc` for the C and Zig interpreters, `wat2wasm` for the hand-written wasm, `asc` for the AssemblyScript ones, and plain `cp` for data files like `jonesforth.f` |
| [`assets/package.json`](assets/package.json) | pulls in `@xterm/xterm` and `xterm-pty` (which the posts import straight out of `/blog/node_modules/`) and wraps the AssemblyScript builds |
| [`assets/tsdown.config.ts`](assets/tsdown.config.ts) | bundles the `xterm-pty` submodule's `ttyClient`/`ttyServer` into `dist/`, which the site's `terminal.html` include imports |
| [`assets/lisp.html`](assets/lisp.html), [`assets/TinyBasic.html`](assets/TinyBasic.html), `*.worker.js` | the standalone pages and worker entry points for the AssemblyScript demos |
| [`assets/thug-life.js`](assets/thug-life.js), [`assets/regexp-snapshot.svg`](assets/regexp-snapshot.svg) | one-off assets embedded by a single post each |

What comes out, and where it comes from:

| published as | built from | seen in |
| --- | --- | --- |
| `/blog/4th.mjs` | [`forth/4th.c`](forth/4th.c) | [What, Forth, Again?](https://bur.gy/2023/02/24/what-forth-again.html) |
| `/blog/5th.mjs` | [`forth/5th.c`](forth/5th.c) | [What is Tail Call Elimination?](https://bur.gy/2024/03/29/tail-recursion.html) |
| `/blog/6th.mjs` | [`forth/6th.zig`](forth/6th.zig) | [Why not try Zig next?](https://bur.gy/2024/08/31/why-not-zig.html) |
| `/blog/jonesforth.wasm` | [`forth/wasm/jonesforth.wast`](forth/wasm/jonesforth.wast) | [How Many Roads Must a Man Walk Down?](https://bur.gy/2025/11/29/how-many-roads.html) |
| `/blog/regexp/web/` | [`regexp/web/`](regexp/web/) + [`forth/wasm/tabulate.wast`](forth/wasm/tabulate.wast) | [What Makes an Expression Regular?](https://bur.gy/2026/09/24/what-makes-an-expression-regular.html) |
| `/blog/lisp.worker.js` | [`lisp/assembly/`](lisp/assembly/) | [What do you mean, homoiconic?](https://bur.gy/2023/03/09/what-do-you-mean-homoiconic.html) |
| `/blog/TinyBasic.worker.js` | [`TinyBasic/assembly/`](TinyBasic/assembly/) | [When did Basic become insulting?](https://bur.gy/2023/03/16/put-it-in-a-brandy-snifter.html) |
| `/blog/jonesforth.f` | the [`jonesforth`](jonesforth/) submodule | every Forth terminal |
| `/blog/dist/`, `/blog/node_modules/` | the [`xterm-pty`](xterm-pty/) submodule and npm | every terminal |

## Folders

Folders that feed a demo are marked ▶.

| folder | | what is in it |
| --- | :---: | --- |
| [`forth/`](forth/) — [README](forth/README.md) | ▶ | Eleven jonesforth interpreters in C, Zig, Rust and hand-written wasm, catalogued by dispatch strategy. `4th.c`, `5th.c`, `6th.zig` and `wasm/jonesforth.wast` are the ones that ship |
| [`regexp/`](regexp/) | ▶ | Thompson's 1968 construction, ported over and over: the original Algol 60, C (bytecode, threaded, switched, and a 32-bit JIT), Julia, Zig, Python and Forth. [`regexp/web/`](regexp/web/) is the browser demo, [`regexp/tracing/`](regexp/tracing/) — [README](regexp/tracing/README.md) — draws the animated snapshot |
| [`lisp/`](lisp/) | ▶ | [sectorlisp](https://justine.lol/sectorlisp/) rewritten in AssemblyScript |
| [`TinyBasic/`](TinyBasic/) | ▶ | Tiny BASIC's original IL virtual machine, plus a Python assembler for it and an AssemblyScript interpreter |
| [`assets/`](assets/) | ▶ | The build and publish staging area described above |
| [`simplex/`](simplex/) — [README](simplex/README.md) | | The NSWC `SMPLX` revised simplex solver: the Fortran, a NumPy transcription, an f2py wrapper and benchmarks |
| [`linprog/`](linprog/) | | Linear-programming odds and ends around the same posts |
| [`sudoku/`](sudoku/) | | Sudoku as an exact-cover / satisfiability problem |
| [`fourt2py/`](fourt2py/) | | Calling 1960s Fortran (`FOURT`) from Python — the "what ever happened to Fortran?" experiment |
| [`progress/`](progress/) | | Foreign-function and progress-reporting experiments |
| [`talks/`](talks/) | | Slide decks, including the Zig-from-Python and data-visualisation talks |
| [`fun/`](fun/) | | The scratch drawer: n-body, bytecode assemblers, Prechelt's benchmark, Zig toys |
| [`aoc2024/`](aoc2024/), [`aoc2025/`](aoc2025/), [`foo/`](foo/) | | Advent of Code and puzzle solutions; excluded from pytest collection (see [`CODE_REVIEW.md`](CODE_REVIEW.md)) |
| [`notebooks/`](notebooks/) | | Jupyter notebooks, reachable through the Binder badge above |
| [`jonesforth/`](jonesforth/), [`xterm-pty/`](xterm-pty/) | ▶ | Submodules, not ours. `deploy.yml` needs `submodules: true` for both |

## The other workflows

| workflow | what it does |
| --- | --- |
| [`pythonpackage.yml`](.github/workflows/pythonpackage.yml) | `uv` + `ruff` + `ty` + `pytest` on 3.13 and 3.14. Needs `gfortran` and 32-bit gcc for the Fortran and jonesforth fixtures |
| [`javascript.yml`](.github/workflows/javascript.yml) | node 24, wasi-sdk and nightly Rust; builds `forth/5th.wasm` and `forth/web/4th.wasm`, then runs the vitest and mocha suites |
| [`deploy.yml`](.github/workflows/deploy.yml) | the Pages build described above |
