# macOS portability inventory

This document records the changes and checks needed to build, run, and test the programs in `forth/` on macOS. It distinguishes native macOS support from Linux-only or cross-target build paths. The primary macOS target assumed here is current macOS on Apple Silicon (`arm64`), with Intel macOS noted where it changes the result.

## Executive summary

The default `make` target is not currently a native macOS build: it starts with `4th.com`, which requires the Cosmopolitan APE toolchain, GNU BFD linker flags, and a downloaded archive. A native C build can be made usable by selecting `4th` explicitly, but the Makefile still exposes unsupported 32-bit and Linux-specific targets.

The Zig implementation has the largest source-level portability gap. `6th.zig` directly selects Linux syscall definitions, uses x86-64 syscall enums, calls the Linux `getppid` implementation, and treats macOS as an unreachable case when translating open flags. The Rust Cargo binary, `4th.rs`, uses ordinary Rust I/O and should be the easiest native implementation to run on macOS. The separate `jansforth.rs` is Unix-specific but its file-descriptor APIs are available on macOS; its hard-coded Linux syscall numbers are a runtime compatibility risk.

## C programs

### Blockers and build-path constraints

- **Default `make` selects the Cosmopolitan APE binary.** `all` depends on `4th.com`, and the `.com.dbg` rule depends on `crt.o`, `ape-no-modify-self.o`, and `ape.lds` ([Makefile](Makefile#L9-L23)). Its flags include `-fuse-ld=bfd`, `--oformat=binary`, `-z max-page-size`, and a Linux/APE linker script ([Makefile](Makefile#L5-L7)). Apple `ld64` does not provide the BFD linker or these GNU linker-script options. Treat `.com` as a Linux/Cosmopolitan target, or add a macOS conditional and make the native `4th` target the macOS default.
- **The Cosmopolitan prerequisite uses `wget`.** macOS does not ship with `wget`; the download rule ([Makefile](Makefile#L51-L53)) should either use the built-in `curl -L -o` workflow or document `wget` as a prerequisite. This is secondary to the fact that the APE link itself is not a native macOS build.
- **32-bit targets do not work on Apple Silicon.** `4th.32`, `4th.ll.32`, and `jansforth` pass `-m32` ([Makefile](Makefile#L32-L44), [Makefile](Makefile#L86-L88)). Modern macOS no longer supports 32-bit applications, and an arm64 compiler cannot produce a runnable native 32-bit macOS target. Skip or clearly label these targets on Darwin; an Intel Mac may still fail depending on its installed SDK/toolchain.

### Source-level portability risks

- **`4th.c` uses unlocked stdio names outside the Apple compatibility shim.** The source calls `getchar_unlocked` and `putchar_unlocked`, while only `fflush_unlocked` is mapped under `__APPLE__` ([4th.c](4th.c#L7-L10), [4th.c](4th.c#L62-L70)). Verify these declarations with Apple Clang and either provide an Apple fallback to `getchar`/`putchar` or use the standard locked APIs if the native build fails.
- **The C interpreters expose raw syscall-number words.** `5th.c` supplies Apple values for `SYS_creat` and `SYS_brk` ([5th.c](5th.c#L10-L20)); the syscall abstraction should remain explicitly target-dependent rather than relying on Linux enum values or macro redefinitions. Exercise the Forth `SYS_*` words on macOS, not just compilation.
- **`sbrk` is deprecated and fragile.** `5th.c` and `jansforth.c` use `sbrk` for interpreter memory. It is present on current macOS but is not a durable portability boundary. A future-proof implementation should reserve memory with `mmap` or use a managed allocation and handle allocation failure explicitly.
- **`openat`/`AT_FDCWD` depend on the POSIX libc surface.** `5th.c` uses them in its syscall implementation. They are available on current macOS, but feature-test assumptions should be made explicit if strict SDK or older deployment targets are supported.

### Test implications

`test_4th.py` and `test_4th_wasm.py` are not inherently Linux-specific, but they depend on the corresponding native/WASM artifacts being built first. Add platform skips or separate targets for `.32` and `.com` rather than allowing a general test command to fail because an unsupported artifact was requested.

Recommended first native checks on macOS:

```sh
make clean
make 4th
pytest test_4th.py
```

The `.com`, `.32`, and `jansforth` targets should be tested separately and either supported with an appropriate toolchain or explicitly excluded on unsupported macOS architectures.

## Zig program

The Zig implementation is [6th.zig](6th.zig), built by [build.zig](build.zig) and invoked from the Makefile ([Makefile](Makefile#L55-L57)). The following assumptions must be removed or isolated for native macOS:

- **Linux syscall namespace is selected unconditionally.** `const syscalls = os.linux.syscalls` ([6th.zig](6th.zig#L14-L20)) and the `_syscall0`/`_syscall1`/`_syscall2`/`_syscall3` handlers all type values as `syscalls.X64` ([6th.zig](6th.zig#L699-L775)). Introduce a target-aware abstraction, or keep these Forth syscall words explicitly Linux-only. macOS syscall numbers and calling conventions are not the Linux x86-64 table.
- **Exported Forth syscall constants are x86-64/Linux values.** The primitive table publishes `syscalls.X64.exit`, `open`, `close`, `read`, `write`, `creat`, and `brk` ([6th.zig](6th.zig#L835-L845)). On arm64 macOS these values cannot be used to represent native macOS syscalls. Prefer libc wrappers (`std.c`/`std.posix` as appropriate) or define separate target-specific tables.
- **`getppid` calls Linux directly.** The `getppid` branch invokes `os.linux.getppid()` for non-WASM targets ([6th.zig](6th.zig#L768-L779)). Use the platform-neutral Zig API or gate the word by OS.
- **File open flags treat macOS as unreachable.** `openFlags` handles Linux, Emscripten, and WASI, then reaches `unreachable` for every other OS ([6th.zig](6th.zig#L60-L79)). Native macOS file I/O will therefore panic or fail once this path is reached. Add a macOS mapping using the actual `std.c.O` representation, and test read, write, create, truncate, append, and nonblocking modes.
- **The calling-convention switch is architecture-specific.** Only x86-64 selects `.winapi`; all other architectures fall through to `.auto` ([6th.zig](6th.zig#L21-L27)). This should be reviewed together with the syscall handlers before claiming arm64 support. Do not assume that selecting a different convention alone makes Linux syscall numbers or register layouts portable.
- **The build script has no test step.** [build.zig](build.zig) installs a native executable and the WASM artifact but does not define `zig build test`. The source tests can be run directly with `zig test 6th.zig`; integrating that into the build would make macOS verification repeatable.
- **Zig is pinned through an external tool invocation.** The Makefile uses `uvx --from ziglang==0.15.2 python-zig build` ([Makefile](Makefile#L55-L57)). A macOS setup needs Python/`uvx`, network access, and a compatible Zig release, or a documented system Zig alternative.

Suggested focused checks after the source changes are:

```sh
zig test 6th.zig
zig build
./zig-out/bin/6th < 4th.fs
```

Run the native checks on both `x86_64` and `aarch64` if both macOS architectures are supported; syscall behavior should be tested, not inferred from a successful compile.

## Rust programs

### Cargo target: `4th.rs`

[Cargo.toml](Cargo.toml#L1-L18) declares only `4th.rs` as a Cargo binary. The implementation uses `std::fs`, `std::io`, and a memory-backed interpreter ([4th.rs](4th.rs#L11-L25)); it does not directly invoke OS syscalls for its normal I/O. Native Cargo build/test is therefore expected to work on macOS, subject to the project’s nightly Rust requirement for `explicit_tail_calls`.

The Makefile’s Rust targets are the WASI build and test paths ([Makefile](Makefile#L60-L78)), not native Cargo targets. They require `rustup`, a nightly toolchain, and the `wasm32-wasip1` target. That is a cross-target prerequisite rather than a macOS portability defect.

Recommended native checks:

```sh
rustup run nightly cargo test
rustup run nightly cargo run -- < 4th.fs
```

### Standalone experiment: `jansforth.rs`

- **Unix APIs are used directly.** The file imports `std::os::fd::{FromRawFd, IntoRawFd}` and `std::os::unix::fs::OpenOptionsExt`, and uses `OpenOptionsExt::mode`. macOS implements these Unix APIs, so this is not by itself a blocker, but it should be compiled and exercised as a separate target if it is meant to be supported.
- **Syscall constants are Linux-specific.** `SYS_EXIT`, `SYS_READ`, `SYS_WRITE`, `SYS_OPEN`, `SYS_CLOSE`, `SYS_BRK`, and `SYS_CREAT` use Linux numbers ([jansforth.rs](jansforth.rs#L9-L30)). Any Forth program that uses the `SYSCALL*` words will behave incorrectly on macOS. Use platform-specific constants or route those words through Rust/libc wrappers.
- **It needs an explicit Cargo target.** Keep `jansforth.rs` as a separate `[[bin]]` entry alongside `4th.rs`; do not rely on Cargo auto-discovery because the project intentionally keeps it disabled.

## Shared macOS worklist

1. Make the native C target explicit and prevent the Linux/APE `.com` target from being pulled into the default macOS build.
2. Gate or skip all `-m32` rules on modern macOS, especially arm64.
3. Replace `wget` with `curl` or document it as an optional dependency.
4. Decide whether raw syscall words are Linux-only. If they are intended to work on macOS, introduce OS and architecture-specific implementations in C, Zig, and `jansforth.rs` rather than sharing Linux numbers.
5. Add a repeatable native test step for Zig and document nightly Rust plus WASI prerequisites separately from native macOS support.
6. Run the native C, Zig, and Rust smoke tests on the supported macOS architectures; compilation alone will not detect incorrect syscall numbers or the Zig `openFlags` path.
