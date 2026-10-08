VPATH = ../forth
# matcher.mjs fetches ../regexp.f and ../../jonesforth/jonesforth.f, so keep the repo layout
REGEXP = $(addprefix regexp/,web/index.html web/demo.mjs web/matcher.mjs web/forth.mjs regexp.f)
FOURT2PY = $(addprefix fourt2py/,web/index.html web/demo.mjs web/spectrum.mjs web/chart.mjs web/oscilloscope.mjs web/fourt.pow2.mjs)
ISING = $(addprefix ising/,index.html demo.mjs lattice.mjs)
RESISTOR_NETWORK = $(addprefix resistor-network/,index.html demo.mjs lattice.mjs)

all : 4th-wasi.wasm 5th-wasi.wasm 6th-wasi.wasm 4th-rs-wasi.wasm lisp-wasi.wasm TinyBasic-wasi.wasm wasi-repl.mjs wasi-repl-mocha.mjs jonesforth.wasm localize.wasm tabulate.wasm regexp fourt2py ising resistor-network

%.wasm : ../forth/wasm/%.wast jonesforth/jonesforth.f worker.js wasi-worker.js
	npx -y --package wabt wat2wasm --enable-tail-call --debug-names -o $@ $<

# uvx/python-zig, not a bare `zig build`: deploy.yml has no system zig. See
# build.zig's buildWasi. Named <name>-wasi.wasm, not <name>.wasm, to match
# 4th-wasi.wasm/5th-wasi.wasm below.
6th-wasi.wasm : ../forth/6th.zig ../forth/build.zig worker.js wasi-worker.js wasi-repl.mjs wasi-repl-mocha.mjs forth/4th.32.fs
	cd ../forth && uvx --from ziglang==0.15.2 python-zig build -Dtarget=wasm32-wasi -Dcpu=baseline+tail_call
	cp ../forth/zig-out/web/wasi/6th.wasm $@

# wasi-sdk clang (deploy.yml: bytecodealliance/setup-wasi-sdk-action).
4th-wasi.wasm : ../forth/4th.c worker.js wasi-worker.js wasi-repl.mjs wasi-repl-mocha.mjs forth/4th.32.fs
	$${WASI_SDK_PATH}/bin/clang --sysroot=$${WASI_SDK_PATH}/share/wasi-sysroot -Wall -Wextra -o $@ $<

5th-wasi.wasm : ../forth/5th.c worker.js wasi-worker.js wasi-repl.mjs wasi-repl-mocha.mjs forth/4th.32.fs
	$${WASI_SDK_PATH}/bin/clang --sysroot=$${WASI_SDK_PATH}/share/wasi-sysroot -Wall -Wextra -DNO_LIBC_SYSCALL_NUMS -mtail-call -o $@ $<

4th-rs-wasi.wasm : ../forth/4th.rs ../forth/Cargo.toml worker.js wasi-worker.js wasi-repl.mjs wasi-repl-mocha.mjs forth/4th.32.fs
	cd ../forth && CARGO_TARGET_DIR=target/wasi-repl rustup run nightly cargo build --release --target wasm32-wasip1 --bin 4th -Zbuild-std=std,panic_unwind
	cp ../forth/target/wasi-repl/wasm32-wasip1/release/4th.wasm $@

# AssemblyScript (asc), not wasi-sdk/zig: wasi.ts/wasiHost.ts implement
# wasi_snapshot_preview1 fd_read/fd_write themselves, driven by the same
# worker.js/wasi-worker.js/wasi-repl.mjs harness as the C/Zig builds above.
lisp-wasi.wasm : ../lisp/assembly/wasi.ts ../lisp/assembly/core.ts ../lisp/assembly/wasiHost.ts worker.js wasi-worker.js wasi-repl.mjs wasi-repl-mocha.mjs
	npm run asbuild:lisp-wasi

TinyBasic-wasi.wasm : ../TinyBasic/assembly/wasi.ts ../TinyBasic/assembly/core.ts ../TinyBasic/assembly/wasiHost.ts worker.js wasi-worker.js wasi-repl.mjs wasi-repl-mocha.mjs
	npm run asbuild:TinyBasic-wasi

# Published standalone (not just a side effect of 4th.wasm/5th.wasm/6th.wasm
# above): the how-many-roads post's tab strip hardcodes /blog/wasi-repl.mjs
# directly (jburgy/jburgy.github.io) -- startRepl(wasmUrl, preambleUrl) takes
# the two things that differ per interpreter as plain arguments, so there's
# no per-post copy to keep in sync.
wasi-repl.mjs : ../forth/wasm/wasi-repl.mjs
	cp $< $@

# html/4th.html/5th.html/6th.html each load this directly from /assets/ (not
# just a side effect of 4th.wasm/5th.wasm/6th.wasm): the in-browser mocha
# spec that gives a human visiting the page its own pass/fail report, same
# one CI drives headless (see forth/browser/wasi-demo.mjs).
wasi-repl-mocha.mjs : ../forth/wasm/wasi-repl-mocha.mjs
	cp $< $@

regexp : $(REGEXP) regexp/web/forth.wasm jonesforth/jonesforth.f

$(REGEXP) : regexp/% : ../regexp/%
	@mkdir -p $(@D)
	cp $< $@

regexp/web/forth.wasm : ../forth/wasm/tabulate.wast
	@mkdir -p $(@D)
	npx -y --package wabt wat2wasm --enable-multi-memory -o $@ $<

fourt2py : $(FOURT2PY)

$(FOURT2PY) : fourt2py/% : ../fourt2py/%
	@mkdir -p $(@D)
	cp $< $@

ising : $(ISING)

$(ISING) : ising/% : ../ising/%
	@mkdir -p $(@D)
	cp $< $@

resistor-network : $(RESISTOR_NETWORK)

$(RESISTOR_NETWORK) : resistor-network/% : ../resistor-network/%
	@mkdir -p $(@D)
	cp $< $@

forth/4th.32.fs : ../forth/4th.32.fs
	@mkdir -p $(@D)
	cp $< $@

%.js: ../forth/wasm/%.js
	cp $< $@

# The one copy of jonesforth.f in the deployed site: the how-many-roads
# post's data-preamble attributes (jburgy/jburgy.github.io) point at this
# exact deployed path. matcher.mjs resolves the identical
# '../../jonesforth/jonesforth.f' relative to its own repo-layout
# location, mirroring the real jonesforth submodule path so it also
# works unmodified straight from the source tree (no copy needed in dev)
# -- same reasoning as forth/4th.32.fs above. regexp.f never touches
# ARGC/ARGV/ENVIRON, so the real jonesforth.f preamble works fine on
# tabulate.wast (regexp/web/forth.wasm's source), which never defines
# 4th.32.fs's (ARGC) primitive.
jonesforth/jonesforth.f : ../jonesforth/jonesforth.f
	@mkdir -p $(@D)
	cp $< $@

# Local stand-in for GitHub Pages' split-origin, cross-origin-isolated setup
# (see serve-e2e.mjs's own docstring): needed to actually see a wasi-worker.js
# demo run in a browser, since that needs real SharedArrayBuffer/Atomics.wait.
# Depends only on the genuinely file-tracked targets (real output file, real
# mtime comparison against real prerequisites) so a stale one rebuilds and a
# fresh one no-ops -- what `make` is for. Deliberately excludes
# regexp/fourt2py/ising/resistor-network: none of those are file-tracked here
# (fragile directory-mtime tracking instead of a single output file matching
# the target name), so depending on them would rerun their recipes on every
# invocation, defeating the fast "rebuild assets, reload" inner loop below.
# `make <that target>` first if the demo you're testing needs one of those.
# Skips (re)building the jburgy.github.io Jekyll site; run `node serve-e2e.mjs`
# directly the first time, to build that site too.
serve-e2e : 4th-wasi.wasm 5th-wasi.wasm 6th-wasi.wasm 4th-rs-wasi.wasm lisp-wasi.wasm TinyBasic-wasi.wasm jonesforth.wasm localize.wasm tabulate.wasm
	node serve-e2e.mjs --skip-jekyll-build

.PHONY : regexp fourt2py ising resistor-network serve-e2e

clean :
	rm -rf wasi-repl.mjs wasi-repl-mocha.mjs *.d.ts *.wasm* lisp-wasi.js TinyBasic-wasi.js jonesforth worker.js wasi-worker.js regexp forth fourt2py ising resistor-network
