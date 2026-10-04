#!/usr/bin/env python3
# pragma: exclude file
"""Build and benchmark the Forth interpreters on the fast-doubling workload."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import os
from pathlib import Path
import random
import select
import shutil
import statistics
import subprocess
import sys
import tempfile
import time


FORTH_DIR = Path(__file__).resolve().parent
FIBONACCI_FILE = FORTH_DIR.parent / "talks" / "fibonacci.fs"
SUCCESS = 0x7F
FAILURE = 0x80
EXPECTED = 1_836_311_903
DEFAULT_ITERATIONS = 100_000


def require(command: str) -> str:
    path = shutil.which(command)
    if path is None:
        raise RuntimeError(f"required command not found: {command}")
    return path


def build(command: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=FORTH_DIR, env=env, check=True)


def benchmark_input(iterations: int) -> bytes:
    lines = FIBONACCI_FILE.read_text().splitlines()
    if not lines or lines[-1].strip() != "92 FIBONACCI U.":
        raise RuntimeError(f"unexpected final line in {FIBONACCI_FILE}")
    definitions = "\n".join(lines[:-1])
    program = (
        f"{definitions}\n"
        ": CHECK 46 FIBONACCI DROP ;\n"
        f": RUN {iterations} BEGIN DUP 0> WHILE CHECK 1- REPEAT DROP ;\n"
        f": VERIFY 46 FIBONACCI {EXPECTED} = "
        f"IF {SUCCESS} EMIT ELSE {FAILURE} EMIT THEN ;\n"
        "RUN VERIFY\n"
    )
    return program.encode()


# Enough of jonesforth.f to write the non-Fibonacci workloads. `CELLW` measures
# the cell width by comma-ing one cell and differencing HERE, so the same source
# runs on the 32-bit and 64-bit interpreters alike. `BUF` is scratch space well
# clear of the dictionary; both are frozen into literals so the inner loops do
# not re-measure them.
PREAMBLE = """: / /MOD SWAP DROP ;
: RECURSE IMMEDIATE LATEST @ >CFA , ;
: IF      IMMEDIATE ' 0BRANCH , HERE @ 0 , ;
: THEN    IMMEDIATE DUP HERE @ SWAP - SWAP ! ;
: ELSE    IMMEDIATE ' BRANCH , HERE @ 0 , SWAP DUP HERE @ SWAP - SWAP ! ;
: BEGIN   IMMEDIATE HERE @ ;
: WHILE   IMMEDIATE ' 0BRANCH , HERE @ 0 , ;
: REPEAT  IMMEDIATE ' BRANCH , SWAP HERE @ - , DUP HERE @ SWAP - SWAP ! ;
: LITERAL IMMEDIATE ' LIT , , ;
: U. BASE @ /MOD ?DUP IF RECURSE THEN DUP 10 < IF 48 ELSE 55 THEN + EMIT ;
HERE @ 0 , HERE @ SWAP -
: CELLW LITERAL ;
HERE @ 16384 +
: BUF LITERAL ;
"""

# Inner-loop repeat counts. They are only roughly equalised -- `printing` is
# several times the others -- but each is large enough to swamp process startup.
WORKLOAD_BODIES: dict[str, tuple[int, str]] = {
    "cells": (
        400,
        """: FILL BEGIN DUP 0> WHILE DUP DUP CELLW * BUF + ! 1- REPEAT DROP ;
: SUM 0 SWAP BEGIN DUP 0> WHILE DUP CELLW * BUF + @ ROT + SWAP 1- REPEAT DROP ;
: ONE 2000 FILL 2000 SUM DROP ;
: VERIFY 2000 FILL 2000 SUM 2001000 = IF {ok} EMIT ELSE {bad} EMIT THEN ;""",
    ),
    "bytes": (
        300,
        """: BFILL BEGIN DUP 0> WHILE DUP DUP 255 AND SWAP BUF + C! 1- REPEAT DROP ;
: BSUM 0 SWAP BEGIN DUP 0> WHILE DUP BUF + C@ ROT + SWAP 1- REPEAT DROP ;
: COPY BEGIN DUP 0> WHILE DUP BUF + C@ OVER 8192 + BUF + C! 1- REPEAT DROP ;
: ONE 4000 BFILL 4000 COPY 4000 BSUM DROP ;
: VERIFY 4000 BFILL 4000 BSUM 502480 = IF {ok} EMIT ELSE {bad} EMIT THEN ;""",
    ),
    "calls": (
        40000,
        """: L0 1+ ;
: L1 L0 L0 ;
: L2 L1 L1 ;
: L3 L2 L2 ;
: L4 L3 L3 ;
: L5 L4 L4 ;
: L6 L5 L5 ;
: L7 L6 L6 ;
: STASH >R >R R> R> ;
: ONE 0 L7 DROP 1 2 STASH 2DROP ;
: VERIFY 0 L7 128 = IF {ok} EMIT ELSE {bad} EMIT THEN ;""",
    ),
    "printing": (
        60,
        """: UWIDTH BASE @ / ?DUP IF RECURSE 1+ ELSE 1 THEN ;
: PR BEGIN DUP 0> WHILE DUP U. 1- REPEAT DROP ;
: ONE 500 PR ;
: VERIFY 500 UWIDTH 3 = IF {ok} EMIT ELSE {bad} EMIT THEN ;""",
    ),
}

# How many colon definitions `compile` keeps live at once. 4th.c has the
# tightest budget (a 64 KiB sbrk'd dictionary, unchecked), so the workload
# rewinds HERE/LATEST between batches instead of defining everything at once.
COMPILE_BATCH = 200


def loop_input(name: str, iterations: int) -> bytes:
    """A workload whose body is a stack-neutral `ONE` run `reps` times."""
    default, body = WORKLOAD_BODIES[name]
    reps = max(1, round(default * iterations / DEFAULT_ITERATIONS))
    program = (
        PREAMBLE
        + body.format(ok=SUCCESS, bad=FAILURE)
        + f"\n: RUN {reps} BEGIN DUP 0> WHILE ONE 1- REPEAT DROP ;\nRUN VERIFY\n"
    )
    return program.encode()


def compile_input(iterations: int) -> bytes:
    """Dictionary-building workload: INTERPRET/WORD/FIND/CREATE/`,` dominate."""
    batches = max(1, round(150 * iterations / DEFAULT_ITERATIONS))
    batch = "\n".join(f": Q{n} 1 2 + ;" for n in range(COMPILE_BATCH))
    # `REWIND` must be defined before the mark it restores, or it deletes itself.
    program = (
        PREAMBLE + ": REWIND BUF @ HERE ! BUF CELLW + @ LATEST ! ;\n"
        "HERE @ BUF ! LATEST @ BUF CELLW + !\n"
        + "".join(f"{batch}\nREWIND\n" for _ in range(batches - 1))
        # The last batch survives so VERIFY can call something it defined.
        + f"{batch}\n"
        f": VERIFY Q{COMPILE_BATCH - 1} 3 = "
        f"IF {SUCCESS} EMIT ELSE {FAILURE} EMIT THEN ;\nVERIFY\n"
    )
    return program.encode()


WORKLOADS: dict[str, Callable[[int], bytes]] = {
    "fibonacci": benchmark_input,
    "cells": lambda n: loop_input("cells", n),
    "bytes": lambda n: loop_input("bytes", n),
    "calls": lambda n: loop_input("calls", n),
    "compile": compile_input,
    "printing": lambda n: loop_input("printing", n),
}


def time_once(command: list[str], program: bytes, timeout: float) -> float:
    start = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=FORTH_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    output = bytearray()
    error: str | None = None
    try:
        process.stdin.write(program)
        process.stdin.flush()
        deadline = start + timeout
        while time.perf_counter() < deadline:
            ready, _, _ = select.select(
                [process.stdout], [], [], max(0, deadline - time.perf_counter())
            )
            if not ready:
                error = "timed out waiting for the result marker"
                break
            chunk = os.read(process.stdout.fileno(), 4096)
            if not chunk:
                error = "interpreter exited before emitting a result marker"
                break
            output.extend(chunk)
            if FAILURE in chunk:
                error = "the workload's VERIFY reported a wrong result"
                break
            if SUCCESS in chunk:
                return (time.perf_counter() - start) * 1000
    except (BrokenPipeError, OSError) as exc:
        error = f"interpreter pipe failed: {exc}"
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            _, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            _, stderr = process.communicate()
        process.stdin.close()
        process.stdout.close()
        process.stderr.close()

    detail = stderr.decode(errors="replace").strip()
    if detail:
        error = f"{error}: {detail}"
    raise RuntimeError(error or f"interpreter failed; output={bytes(output[-100:])!r}")


def build_targets(work: Path) -> list[tuple[str, str, list[str]]]:
    clang = require(os.environ.get("CC", "clang"))
    wasi_sdk = os.environ.get("WASI_SDK_PATH")
    if not wasi_sdk:
        raise RuntimeError(
            "WASI_SDK_PATH must be set (see bytecodealliance/setup-wasi-sdk-action)"
        )
    wasi_clang = str(Path(wasi_sdk) / "bin" / "clang")
    wasi_sysroot = str(Path(wasi_sdk) / "share" / "wasi-sysroot")
    rustup = require("rustup")
    cargo = require("cargo")
    zig = require("zig")
    wasmtime = require("wasmtime")
    wat2wasm = require(str(FORTH_DIR / "node_modules" / ".bin" / "wat2wasm"))

    native = work / "native"
    wasm = work / "wasm"
    native.mkdir()
    wasm.mkdir()
    targets: list[tuple[str, str, list[str]]] = []

    c_flags = ["-O3", "-DNDEBUG", "-fomit-frame-pointer", "-fblocks"]
    build([clang, *c_flags, "-o", str(native / "4th"), "4th.c"])
    build([clang, *c_flags, "-o", str(native / "5th"), "5th.c"])
    build(
        [
            clang,
            "-O3",
            "-DNDEBUG",
            "-std=c2x",
            "-D_DEFAULT_SOURCE",
            "-o",
            str(native / "jansforth"),
            "jansforth.c",
        ]
    )
    build(
        [
            clang,
            "-O3",
            "-DNDEBUG",
            "-std=c2x",
            "-D_DEFAULT_SOURCE",
            "-o",
            str(native / "recurse"),
            "recurse.c",
        ]
    )

    native_rust_target = work / "rust-native"
    native_env = os.environ | {
        "CARGO_TARGET_DIR": str(native_rust_target),
        "CARGO_PROFILE_RELEASE_OPT_LEVEL": "3",
    }
    build(
        [
            rustup,
            "run",
            "nightly",
            cargo,
            "build",
            "--release",
            "--bin",
            "4th",
        ],
        env=native_env,
    )
    build(
        [
            cargo,
            "build",
            "--release",
            "--features",
            "jansforth",
            "--bin",
            "jansforth",
        ],
        env=native_env,
    )

    zig_prefix = work / "zig-native"
    build(
        [
            zig,
            "build",
            "--build-file",
            "build.zig",
            "--prefix",
            str(zig_prefix),
            "-Doptimize=ReleaseFast",
        ]
    )

    targets.extend(
        [
            ("4th.c", "native", [str(native / "4th")]),
            ("5th.c", "native", [str(native / "5th")]),
            ("jansforth.c", "native", [str(native / "jansforth")]),
            ("recurse.c", "native", [str(native / "recurse")]),
            ("4th.rs", "native", [str(native_rust_target / "release" / "4th")]),
            (
                "jansforth.rs",
                "native",
                [str(native_rust_target / "release" / "jansforth")],
            ),
            ("6th.zig", "native", [str(zig_prefix / "bin" / "6th")]),
            ("jansforth.zig", "native", [str(zig_prefix / "bin" / "jansforth-zig")]),
            (
                "labeled.zig",
                "native",
                [str(zig_prefix / "bin" / "labeled-zig")],
            ),
            (
                "hybrid.zig",
                "native",
                [str(zig_prefix / "bin" / "hybrid-zig")],
            ),
        ]
    )

    for source in ("tabulate", "recurse", "jonesforth", "localize"):
        wasm_file = wasm / f"{source}.wasm"
        build(
            [
                wat2wasm,
                "--enable-tail-call",
                f"wasm/{source}.wast",
                "-o",
                str(wasm_file),
            ]
        )
        command = compile_wasm(wasmtime, wasm_file, wasm)
        targets.append((f"wasm/{source}.wast", "Wasmtime", command))

    # Same wasi-sdk target assets/Makefile publishes as 4th-wasi.wasm/
    # 5th-wasi.wasm (`-O3` added here for a fair comparison against the
    # other optimized Wasmtime targets; the published build favours
    # simplicity/size over speed). 5th.c's EMSCRIPTEN branch is reused
    # rather than vestigial: wasi-libc's <sys/syscall.h>, like Emscripten's,
    # doesn't define SYS_read/SYS_write/etc. either.
    for source, extra_flags in (("4th", []), ("5th", ["-DEMSCRIPTEN", "-mtail-call"])):
        wasm_file = wasm / f"{source}-wasi.wasm"
        build(
            [
                wasi_clang,
                f"--sysroot={wasi_sysroot}",
                "-O3",
                "-Wall",
                "-Wextra",
                *extra_flags,
                "-o",
                str(wasm_file),
                f"{source}.c",
            ]
        )
        targets.append(
            (
                f"{source}.c -> WASI Wasm",
                "Wasmtime",
                compile_wasm(wasmtime, wasm_file, wasm),
            )
        )

    rust_wasm_target = work / "rust-wasm"
    rust_wasm_env = os.environ | {
        "CARGO_TARGET_DIR": str(rust_wasm_target),
        "CARGO_PROFILE_RELEASE_OPT_LEVEL": "3",
        "RUSTFLAGS": "-Ctarget-feature=+tail-call",
    }
    build(
        [
            rustup,
            "run",
            "nightly",
            "cargo",
            "build",
            "--release",
            "--manifest-path",
            str(FORTH_DIR / "Cargo.toml"),
            "--target",
            "wasm32-wasip1",
            "-Zbuild-std=std,panic_unwind",
            "--bin",
            "4th",
        ],
        env=rust_wasm_env,
    )
    rust_wasm = rust_wasm_target / "wasm32-wasip1" / "release" / "4th.wasm"
    targets.append(
        ("4th.rs -> WASI Wasm", "Wasmtime", compile_wasm(wasmtime, rust_wasm, wasm))
    )
    return targets


def compile_wasm(wasmtime: str, source: Path, work: Path) -> list[str]:
    compiled = work / f"{source.stem}.cwasm"
    build(
        [
            wasmtime,
            "compile",
            "-O",
            "opt-level=2",
            "-W",
            "tail-call=y",
            "-W",
            "exceptions=y",
            str(source),
            "-o",
            str(compiled),
        ]
    )
    return [
        wasmtime,
        "run",
        "--allow-precompiled",
        "-W",
        "tail-call=y",
        "-W",
        "exceptions=y",
        str(compiled),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--trials", type=int, default=11)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument(
        "--workload",
        choices=[*WORKLOADS, "all"],
        default="fibonacci",
        help="which program to time; 'all' runs the whole suite",
    )
    args = parser.parse_args()
    if args.iterations < 1 or args.trials < 1:
        parser.error("--iterations and --trials must be positive")

    chosen = list(WORKLOADS) if args.workload == "all" else [args.workload]
    programs = {name: WORKLOADS[name](args.iterations) for name in chosen}
    try:
        with tempfile.TemporaryDirectory(prefix="forth-benchmark-") as directory:
            targets = build_targets(Path(directory))
            print(
                "workload\tsource\tmedian_ms\tmin_ms\tmax_ms\ttrials_ms",
                flush=True,
            )
            for workload, program in programs.items():
                for name, group, command in targets:
                    try:
                        time_once(command, program, args.timeout)
                    except RuntimeError as exc:
                        print(
                            f"{workload}\t{group}: {name}\tWARM-UP FAILED\t{exc}",
                            file=sys.stderr,
                            flush=True,
                        )
                        return 1

                samples = {name: [] for name, _, _ in targets}
                # Reseeded per workload so every workload sees the same order.
                rng = random.Random(2026)
                for _ in range(args.trials):
                    order = targets.copy()
                    rng.shuffle(order)
                    for name, group, command in order:
                        try:
                            samples[name].append(
                                time_once(command, program, args.timeout)
                            )
                        except RuntimeError as exc:
                            print(
                                f"{workload}\t{group}: {name}\tFAILED\t{exc}",
                                file=sys.stderr,
                                flush=True,
                            )
                            return 1

                for name, group, _ in targets:
                    timings = samples[name]
                    print(
                        f"{workload}\t{group}: {name}\t"
                        f"{statistics.median(timings):.3f}\t"
                        f"{min(timings):.2f}\t{max(timings):.2f}\t"
                        + ",".join(f"{sample:.2f}" for sample in timings),
                        flush=True,
                    )
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"benchmark setup failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
