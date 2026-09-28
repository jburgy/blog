#!/usr/bin/env python3
"""Build and benchmark the Forth interpreters on the fast-doubling workload."""

from __future__ import annotations

import argparse
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
                error = "FIBONACCI(46) returned the wrong value"
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
    emcc = require("emcc")
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

    for source in ("4th", "5th"):
        wasm_file = wasm / f"{source}-emscripten.wasm"
        build(
            [
                emcc,
                "-O3",
                "-DEMSCRIPTEN",
                "-fblocks",
                "-mtail-call",
                "-sSTANDALONE_WASM=1",
                "-sWASM=1",
                "-o",
                str(wasm_file),
                f"{source}.c",
            ]
        )
        targets.append(
            (
                f"{source}.c -> Emscripten Wasm",
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
    parser.add_argument("--iterations", type=int, default=100_000)
    parser.add_argument("--trials", type=int, default=11)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    if args.iterations < 1 or args.trials < 1:
        parser.error("--iterations and --trials must be positive")

    program = benchmark_input(args.iterations)
    try:
        with tempfile.TemporaryDirectory(prefix="forth-benchmark-") as directory:
            targets = build_targets(Path(directory))
            for name, group, command in targets:
                try:
                    time_once(command, program, args.timeout)
                except RuntimeError as exc:
                    print(
                        f"{group}: {name}\tWARM-UP FAILED\t{exc}",
                        file=sys.stderr,
                        flush=True,
                    )
                    return 1

            samples = {name: [] for name, _, _ in targets}
            rng = random.Random(2026)
            for _ in range(args.trials):
                order = targets.copy()
                rng.shuffle(order)
                for name, _, command in order:
                    try:
                        samples[name].append(time_once(command, program, args.timeout))
                    except RuntimeError as exc:
                        print(
                            f"{name}\tFAILED\t{exc}",
                            file=sys.stderr,
                            flush=True,
                        )
                        return 1

            print("source\tmedian_ms\tmin_ms\tmax_ms\ttrials_ms", flush=True)
            for name, group, _ in targets:
                timings = samples[name]
                print(
                    f"{group}: {name}\t{statistics.median(timings):.3f}\t"
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
