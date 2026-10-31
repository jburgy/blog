CFLAGS ?= -Wall -Wextra -Os -DNDEBUG -fomit-frame-pointer -Wno-deprecated-declarations -fwrapv -fno-strict-aliasing

all: 4th 5th zig-out/bin/6th zig-out/bin/jansforth-zig zig-out/bin/labeled-zig zig-out/bin/hybrid-zig jansforth recurse 4th-rs jansforth-rs

.PHONY: all 4th-rs jansforth-rs

4th-rs: Cargo.toml 4th.rs
	rustup run nightly cargo build --bin 4th

jansforth-rs: Cargo.toml jansforth.rs
	cargo build --features jansforth --bin jansforth

% : %.c
	$(CC) $(CFLAGS) -mstackrealign -o $@ $^

zig-out/bin/6th zig-out/bin/jansforth-zig zig-out/bin/labeled-zig zig-out/bin/hybrid-zig : 6th.zig jansforth.zig labeled.zig hybrid.zig build.zig
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

# Feeds a preamble to the C binaries built above and diffs their stdout (tests/native.rs).
test-native : 4th 5th
	rustup run nightly cargo test --test native

jansforth recurse recurse-chicken : % : %.c
	$(CC) $(if $(filter Darwin,$(shell uname -s)),,-m32) -std=c2x -Wall -Wextra -Wpedantic -Wconversion -D_DEFAULT_SOURCE -o $@ $^

# `make 5th-NAME` applies 5th-opt/NAME.diff to 5th.c and builds the result with the generic rule above.
5th-%.c : 5th-opt/%.diff 5th.c
	patch -o $@ 5th.c $<

# `make 5th-order-p1-p2-p3-p4` reorders 5th.c's parameters (see 5th-opt/reorder.awk) and builds the result.
5th-order-%.c : 5th.c 5th-opt/reorder.awk
	awk -v order=$* -f 5th-opt/reorder.awk 5th.c > $@

5th-chicken% : CFLAGS += -fno-optimize-sibling-calls
5th-preserve-none : CFLAGS += -DPRESERVE_NONE

clean :
	$(RM) 4th 5th jansforth recurse recurse-chicken web/4th.wasm
	$(RM) $(patsubst 5th-opt/%.diff,5th-%,$(wildcard 5th-opt/*.diff)) 5th-order-*
