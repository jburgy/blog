CC = emcc
CFLAGS = -Wall -Wextra -Os -fblocks -mtail-call
ZFLAGS = -ODebug -target wasm32-emscripten -mcpu baseline+atomics+bulk_memory+tail_call
LDFLAGS = -sASYNCIFY -sEXPORTED_FUNCTIONS=_malloc,_main
VPATH = ../forth

all : 4th.mjs 5th.mjs 6th.mjs

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

clean :
	rm -f *.o *.a *.mjs *.wasm *.mjs
