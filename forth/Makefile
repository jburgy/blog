CC = gcc
EC ?= emcc
CFLAGS ?= -Wall -Wextra -Os -DNDEBUG -fomit-frame-pointer -Wno-deprecated-declarations
ARFLAGS = -m32 -S -fverbose-asm
EFLAGS = -O -Wall -Wextra -sEXIT_RUNTIME=1 -sFORCE_FILESYSTEM=1 -sASSERTIONS=1
CPPFLAGS = -include cosmopolitan.h -I.
LDFLAGS = -Wl,--oformat=binary -Wl,--gc-sections -Wl,-z,max-page-size=0x1000 -fuse-ld=bfd -gdwarf-4 -Wl,-T,ape.lds
LDLIBS = cosmopolitan.a

all: 4th 5th zig-out/bin/6th jansforth recurse 4th-rs jansforth-rs

.PHONY: all 4th-rs jansforth-rs

4th-rs: Cargo.toml 4th.rs
	rustup run nightly cargo build --bin 4th

jansforth-rs: Cargo.toml jansforth.rs
	cargo build --features jansforth --bin jansforth

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

zig-out/bin/6th : 6th.zig build.zig
	zig build

web : web/4th.wasm

# panic=abort instead of the test profile's unwinding: `--features web` routes
# BYE through a host throw, so wasm never has to unwind itself. Separate target
# dir so the two wasip1 profiles do not keep invalidating each other.
WEB_RUSTFLAGS = -Ctarget-feature=+tail-call -Cpanic=abort \
	-Clink-arg=--import-undefined \
	-Clink-arg=--export=eval \
	-Clink-arg=--export=input \
	-Clink-arg=--export=input_capacity \
	-Clink-arg=--export=__stack_pointer

web/4th.wasm : 4th.rs
	RUSTFLAGS='$(WEB_RUSTFLAGS)' CARGO_TARGET_DIR=target/web \
		rustup run nightly cargo build --release --target wasm32-wasip1 --features web
	cp target/web/wasm32-wasip1/release/4th.wasm $@

serve-web : web/4th.wasm
	python3 -m http.server --directory . 8000

# The demo's JS, WASI layer and re-entrant eval loop are all testable in node;
# only the terminal rendering would need a browser, and that is wterm's problem.
test-web : web/4th.wasm
	npx vitest run web/

# The WASI build keeps the native panic/catch_unwind halt, which the prebuilt
# panic=abort std cannot do, so std is rebuilt from source.
test-wasm : 4th.rs
	rustup run nightly cargo test --release --target wasm32-wasip1 -Zbuild-std=std,panic_unwind

jansforth recurse : % : %.c
	$(CC) $(if $(filter Darwin,$(shell uname -s)),,-m32) -std=c2x -Wall -Wextra -Wpedantic -Wconversion -D_DEFAULT_SOURCE -o $@ $^

clean :
	$(RM) *.o ape.lds *.a cosmopolitan-amalgamation-2.2.zip cosmopolitan.h 4th.com 4th.com.dbg 4th *.js *.ll *.wasm* *th.*mjs *.html 4th.32 4th.gcov *.gcda *.gcno web/4th.wasm

define allbutlast
$(wordlist 2, $(words $(1)), x $(1))
endef
