CC = gcc
EC ?= emcc
CFLAGS ?= -Wall -Wextra -Os -DNDEBUG -fomit-frame-pointer
ARFLAGS = -m32 -S -fverbose-asm
EFLAGS = -O -Wall -Wextra -sEXIT_RUNTIME=1 -sFORCE_FILESYSTEM=1 -sASSERTIONS=1
CPPFLAGS = -include cosmopolitan.h -I.
LDFLAGS = -Wl,--oformat=binary -Wl,--gc-sections -Wl,-z,max-page-size=0x1000 -fuse-ld=bfd -gdwarf-4 -Wl,-T,ape.lds
LDLIBS = cosmopolitan.a

all: 4th.com 4th 4th.ll serve

run: 4th
	cat 4th.fs - | ./4th

%.com : %.com.dbg
	objcopy -S -O binary $< $@

%.com.dbg : %.c crt.o ape-no-modify-self.o ape.lds
	$(CC) -g -Os -static -nostdlib -nostdinc -fno-pie -no-pie -mno-red-zone -fno-omit-frame-pointer -pg -mnop-mcount -mno-tls-direct-seg-refs $(LDFLAGS) -o $@ $(CPPFLAGS) $(call allbutlast, $^) $(LDLIBS)

%.js : %.c
	$(EC) $(EFLAGS) -fblocks -mtail-call -pthread -o $@ $^

%.mjs : %.c
	$(EC) $(EFLAGS) -fblocks -mtail-call -pthread -sPROXY_TO_PTHREAD -sEXPORTED_FUNCTIONS=_malloc,_main --js-library=node_modules/xterm-pty/emscripten-pty.js -o $@ $^

%.html : %.c
	$(EC) -Wall -Wextra -fblocks -mtail-call -sEXIT_RUNTIME=1 --emrun -o $@ $^

% : %.c
	$(CC) $(CFLAGS) -mstackrealign -o $@ $^

%.32 : %.c
	$(CC) $(CFLAGS) -m32 -o $@ $^

%.s : %.c
	$(CC) $(CFLAGS) $(ARFLAGS) -o $@ $^

%.ll : %.c
	clang $(CFLAGS) -fblocks -o $@ $^

%.ll.32 : %.c
	clang $(CFLAGS) -g -m32 -o $@ $^

serve: 5th.mjs
	open http://localhost:8000/5th.html
	python serve.py

crt.o ape-no-modify-self.o ape.lds &: cosmopolitan-amalgamation-2.2.zip
	unzip -u $<

cosmopolitan-amalgamation-2.2.zip :
	wget https://justine.lol/cosmopolitan/cosmopolitan-amalgamation-2.2.zip

%.gcov : %.c
	$(CC) -Wall -Wextra -Og --coverage -mstackrealign -o $@ $^

zig-out/bin/6th : 6th.zig
	uv run --with ziglang python -m ziglang build

jansforth : jansforth.c
	$(CC) -m32 -std=c2x -Wall -Wextra -Wpedantic -Wconversion -D_DEFAULT_SOURCE -o $@ $^

clean :
	$(RM) *.o ape.lds *.a cosmopolitan-amalgamation-2.2.zip cosmopolitan.h 4th.com 4th.com.dbg 4th *.js *.ll *.wasm* *th.*mjs *.html 4th.32 4th.gcov *.gcda *.gcno

define allbutlast
$(wordlist 2, $(words $(1)), x $(1))
endef
