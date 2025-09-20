CC = emcc
CFLAGS = -Wall -Wextra -Os -fblocks -mtail-call -pthread
ZFLAGS = -ODebug -target wasm32-emscripten -mcpu baseline+atomics+bulk_memory+tail_call
LDFLAGS = -sPROXY_TO_PTHREAD -sEXPORTED_FUNCTIONS=_malloc,_main
VPATH = ../forth

all : 4th.mjs 5th.mjs 6th.mjs lisp TinyBasic
	rm -rf *.a *.o node_modules/@xterm/xterm/src

%.mjs : %.o node_modules/xterm-pty/emscripten-pty.js
	$(CC) $(CFLAGS) $(LDFLAGS) --js-library=$(lastword $^) -o $@ $<

4th.mjs : 4th.o

5th.mjs : 5th.o

6th.mjs : lib6th.a node_modules/xterm-pty/emscripten-pty.js
	$(CC) $(CFLAGS) $(LDFLAGS) --js-library=$(lastword $^) -o $@ $<

lib%.a : %.zig
	uv run --with ziglang -m ziglang build-lib $(ZFLAGS) -Mroot=$< -lc --name $(basename $(<F)) -static -rdynamic

lib6th.a : 6th.zig

node_modules/xterm-pty/emscripten-pty.js :
	npm install @xterm/xterm xterm-pty

lisp :
	npm run asbuild:lisp

TinyBasic :
	npm run asbuild:TinyBasic

clean :
	rm -rf *.o *.a *.js *.mjs *.d.ts *.wasm* *.mjs node_modules
