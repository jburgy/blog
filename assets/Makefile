CC = emcc
CFLAGS = -Wall -Wextra -Os -fblocks -mtail-call -pthread -DEMSCRIPTEN
ZFLAGS = -ODebug -target wasm32-emscripten -mcpu baseline+atomics+bulk_memory+tail_call
LDFLAGS = -sPROXY_TO_PTHREAD -sEXPORTED_FUNCTIONS=_malloc,_main
VPATH = ../forth
# matcher.mjs fetches ../regexp.f and ../../forth/4th.32.fs, so keep the repo layout
REGEXP = $(addprefix regexp/,web/index.html web/demo.mjs web/matcher.mjs web/forth.mjs regexp.f)
FOURT2PY = $(addprefix fourt2py/,web/index.html web/demo.mjs web/spectrum.mjs web/chart.mjs web/oscilloscope.mjs web/fourt.pow2.mjs)

# FIXME: drop 4th.mjs/5th.mjs/6th.mjs (and the emcc CC/CFLAGS/ZFLAGS/LDFLAGS
# vars and %.mjs/lib%.a rules below) once what-forth-again.html,
# tail-recursion.html, and why-not-zig.html each use the wasi .wasm build
# below instead.
all : 4th.mjs 5th.mjs 6th.mjs 4th.wasm 5th.wasm 6th.wasm wasi-repl.mjs wasi-repl-mocha.mjs lisp TinyBasic jonesforth.wasm regexp fourt2py
	rm -rf *.a *.o node_modules/@xterm/xterm/src

%.mjs : %.o jonesforth.f node_modules/xterm-pty/emscripten-pty.js
	$(CC) $(CFLAGS) $(LDFLAGS) --js-library=$(lastword $^) -o $@ $<

%.mjs : lib%.a jonesforth.f node_modules/xterm-pty/emscripten-pty.js
	$(CC) $(CFLAGS) $(LDFLAGS) --js-library=$(lastword $^) -o $@ $<

4th.mjs : 4th.o

5th.mjs : 5th.o

6th.mjs : lib6th.a

jonesforth.wasm : ../forth/wasm/jonesforth.wast jonesforth.f main.js worker.js wasi-worker.js
	npx -y --package wabt wat2wasm --enable-tail-call --debug-names -o $@ $<

lib%.a : %.zig
	uvx --from ziglang==0.15.2 python-zig build-lib $(ZFLAGS) -Mroot=$< -lc --name $(basename $(<F)) -static -rdynamic

lib6th.a : 6th.zig

# uvx/python-zig, not a bare `zig build`: deploy.yml has no system zig (same
# reason lib%.a below uses it). See build.zig's buildWasi.
6th.wasm : ../forth/6th.zig ../forth/build.zig worker.js wasi-worker.js wasi-repl.mjs wasi-repl-mocha.mjs forth/4th.32.fs
	cd ../forth && uvx --from ziglang==0.15.2 python-zig build -Dtarget=wasm32-wasi -Dcpu=baseline+tail_call
	cp ../forth/zig-out/web/wasi/6th.wasm $@

# wasi-sdk clang (deploy.yml: bytecodealliance/setup-wasi-sdk-action).
4th.wasm : ../forth/4th.c worker.js wasi-worker.js wasi-repl.mjs wasi-repl-mocha.mjs forth/4th.32.fs
	$${WASI_SDK_PATH}/bin/clang --sysroot=$${WASI_SDK_PATH}/share/wasi-sysroot -Wall -Wextra -o $@ $<

5th.wasm : ../forth/5th.c worker.js wasi-worker.js wasi-repl.mjs wasi-repl-mocha.mjs forth/4th.32.fs
	$${WASI_SDK_PATH}/bin/clang --sysroot=$${WASI_SDK_PATH}/share/wasi-sysroot -Wall -Wextra -DEMSCRIPTEN -mtail-call -o $@ $<

# Published standalone (not just a side effect of 4th.wasm/5th.wasm/6th.wasm
# above): a future jburgy.github.io post can hardcode /blog/wasi-repl.mjs
# directly, the same way the jonesforth post already hardcodes /blog/main.js
# -- startRepl(wasmUrl) takes the one thing that differs per interpreter as
# a plain argument, so there's no per-post copy to keep in sync.
wasi-repl.mjs : ../forth/wasm/wasi-repl.mjs
	cp $< $@

# html/4th.html/5th.html/6th.html each load this directly from /assets/ (not
# just a side effect of 4th.wasm/5th.wasm/6th.wasm): the in-browser mocha
# spec that gives a human visiting the page its own pass/fail report, same
# one CI drives headless (see forth/browser/wasi-demo.mjs).
wasi-repl-mocha.mjs : ../forth/wasm/wasi-repl-mocha.mjs
	cp $< $@

regexp : $(REGEXP) regexp/web/forth.wasm forth/4th.32.fs

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

forth/4th.32.fs : ../forth/4th.32.fs
	@mkdir -p $(@D)
	cp $< $@

node_modules/xterm-pty/emscripten-pty.js :
	npm install @xterm/xterm xterm-pty

lisp : client-server
	npm run asbuild:lisp

TinyBasic : client-server
	npm run asbuild:TinyBasic

client-server:
	npm run build

%.js: ../forth/wasm/%.js
	cp $< $@

jonesforth.f: ../jonesforth/jonesforth.f
	cp $< $@

# Local stand-in for GitHub Pages' split-origin, cross-origin-isolated setup
# (see serve-e2e.mjs's own docstring): needed to actually see a wasi-worker.js
# demo run in a browser, since that needs real SharedArrayBuffer/Atomics.wait.
# Depends only on the genuinely file-tracked targets (real output file, real
# mtime comparison against real prerequisites) so a stale one rebuilds and a
# fresh one no-ops -- what `make` is for. Deliberately excludes
# lisp/TinyBasic/regexp/fourt2py: none of those are file-tracked here (no
# output file matching the target name, or fragile directory-mtime tracking),
# so depending on them would rerun their recipes on every invocation,
# defeating the fast "rebuild assets, reload" inner loop below. `make
# <that target>` first if the demo you're testing needs one of those.
# Skips (re)building the jburgy.github.io Jekyll site; run `node serve-e2e.mjs`
# directly the first time, to build that site too.
serve-e2e : 4th.wasm 5th.wasm 6th.wasm 4th.mjs 5th.mjs 6th.mjs jonesforth.wasm
	node serve-e2e.mjs --skip-jekyll-build

.PHONY : regexp fourt2py serve-e2e

clean :
	rm -rf *.o *.a *.mjs *.d.ts *.wasm* node_modules dist jonesforth.f lisp.js TinyBasic.js main.js worker.js wasi-worker.js regexp forth fourt2py
