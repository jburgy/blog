CC = emcc
CFLAGS = -Wall -Wextra -Os -fblocks -mtail-call -pthread -DEMSCRIPTEN
ZFLAGS = -ODebug -target wasm32-emscripten -mcpu baseline+atomics+bulk_memory+tail_call
LDFLAGS = -sPROXY_TO_PTHREAD -sEXPORTED_FUNCTIONS=_malloc,_main
VPATH = ../forth
# matcher.mjs fetches ../regexp.f and ../../forth/4th.32.fs, so keep the repo layout
REGEXP = $(addprefix regexp/,web/index.html web/demo.mjs web/matcher.mjs web/forth.mjs regexp.f)

all : 4th.mjs 5th.mjs 6th.mjs lisp TinyBasic jonesforth.wasm regexp
	rm -rf *.a *.o node_modules/@xterm/xterm/src

%.mjs : %.o jonesforth.f node_modules/xterm-pty/emscripten-pty.js
	$(CC) $(CFLAGS) $(LDFLAGS) --js-library=$(lastword $^) -o $@ $<

%.mjs : lib%.a jonesforth.f node_modules/xterm-pty/emscripten-pty.js
	$(CC) $(CFLAGS) $(LDFLAGS) --js-library=$(lastword $^) -o $@ $<

4th.mjs : 4th.o

5th.mjs : 5th.o

6th.mjs : lib6th.a

jonesforth.wasm : ../forth/wasm/jonesforth.wast jonesforth.f main.js worker.js
	npx -y --package wabt wat2wasm --enable-tail-call --debug-names -o $@ $<

lib%.a : %.zig
	uvx --from ziglang==0.15.2 python-zig build-lib $(ZFLAGS) -Mroot=$< -lc --name $(basename $(<F)) -static -rdynamic

lib6th.a : 6th.zig

regexp : $(REGEXP) regexp/web/forth.wasm forth/4th.32.fs

$(REGEXP) : regexp/% : ../regexp/%
	@mkdir -p $(@D)
	cp $< $@

regexp/web/forth.wasm : ../forth/wasm/tabulate.wast
	@mkdir -p $(@D)
	npx -y --package wabt wat2wasm --enable-multi-memory -o $@ $<

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

.PHONY : regexp

clean :
	rm -rf *.o *.a *.mjs *.d.ts *.wasm* node_modules dist jonesforth.f lisp.js TinyBasic.js main.js worker.js regexp forth
