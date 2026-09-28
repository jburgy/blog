#!/usr/bin/env python3
"""Benchmark every runnable implementation in this directory on one shared
workload: find the leftmost match of ``a(b|c)*d`` in ``abccbcccd`` -- a
9-byte string the match consumes in full, so unanchored search-anywhere
engines (the C variants, ``arm.c``, ``regexp.f``) and anchored-at-0
interpreters (``regexp.py``'s ``Instructions``/``Graph``) report the same
answer and their timings compare like for like.

Three files can't run on this host at all and are skipped:

* ``x86.c`` emits x86-64 machine code into RWX memory, which macOS/arm64
  cannot execute without Rosetta (not installed here).
* ``regexp.jl`` needs Julia, which is not installed.
* ``thompson1968.a60`` and ``thompson1968-lambda.a60`` are ALGOL-60
  transcriptions of the 1968 paper; no ALGOL-60 compiler is available.

``regexp.zig`` implements a different, simpler algorithm (Kernighan and
Pike's recursive backtracking matcher, see beautiful.html in its docstring)
that has no grouping or alternation, so it is timed on ``a.*d`` instead --
the closest equivalent it can express -- rather than the shared pattern.
Its number is not directly comparable to the others; see the README.

Run `python3 benchmark.py` from this directory. Requires clang, Zig, and
Node (for the regexp.f/forth.wasm target); each missing tool degrades that
one row to "N/R" rather than failing the whole run.
"""

from __future__ import annotations

import argparse
import ctypes
import importlib.util
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
PATTERN = "a(b|c)*d"
TEXT = "abccbcccd"
ZIG_PATTERN = "a.*d"

TIME_RE = re.compile(r"([\d.]+)\s*us per search")


def time_calls(fn, iterations: int, trials: int, warmup: int) -> list[float]:
    """Return one microseconds-per-call sample per trial."""
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(trials):
        start = time.perf_counter()
        for _ in range(iterations):
            fn()
        samples.append((time.perf_counter() - start) / iterations * 1e6)
    return samples


def cc_shared(tmp: Path, source: str) -> ctypes.CDLL:
    out = tmp / f"{Path(source).stem}.so"
    subprocess.run(
        [
            "cc", "-w", "-O3", "-shared", "-fPIC", "-Dmain=demo",
            "-o", str(out), str(HERE / source),
        ],
        check=True,
    )
    return ctypes.CDLL(str(out))


def bench_bytecode(tmp: Path, iterations: int, trials: int, warmup: int) -> list[float]:
    lib = cc_shared(tmp, "bytecode.c")
    lib.study.argtypes = [ctypes.c_char_p]
    lib.study.restype = ctypes.c_void_p
    lib.execute.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.execute.restype = ctypes.c_int
    code = lib.study(PATTERN.encode())
    text = TEXT.encode()
    assert lib.execute(code, text) == 1
    return time_calls(lambda: lib.execute(code, text), iterations, trials, warmup)


def bench_switched(tmp: Path, iterations: int, trials: int, warmup: int) -> list[float]:
    lib = cc_shared(tmp, "switched.c")
    lib.study.argtypes = [ctypes.c_char_p]
    lib.study.restype = ctypes.c_void_p
    lib.search.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.search.restype = ctypes.c_void_p
    code = lib.study(PATTERN.encode())
    buf = ctypes.create_string_buffer(TEXT.encode())
    assert lib.search(code, buf) is not None
    return time_calls(lambda: lib.search(code, buf), iterations, trials, warmup)


def bench_threaded(tmp: Path, iterations: int, trials: int, warmup: int) -> list[float]:
    lib = cc_shared(tmp, "threaded.c")
    lib.search.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    lib.search.restype = ctypes.c_void_p
    buf = ctypes.create_string_buffer(TEXT.encode())
    pattern = PATTERN.encode()
    assert lib.search(pattern, buf) is not None
    return time_calls(lambda: lib.search(pattern, buf), iterations, trials, warmup)


def bench_arm(tmp: Path, iterations: int, trials: int, warmup: int) -> list[float]:
    lib = cc_shared(tmp, "arm.c")
    lib.study.argtypes = [ctypes.c_char_p]
    lib.study.restype = ctypes.c_void_p
    lib.forget.argtypes = [ctypes.c_void_p]
    raw = lib.study(PATTERN.encode())
    search = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p)(raw)
    buf = ctypes.create_string_buffer(TEXT.encode())
    assert search(buf) is not None
    samples = time_calls(lambda: search(buf), iterations, trials, warmup)
    lib.forget(raw)
    return samples


def bench_jit(iterations: int, trials: int, warmup: int) -> list[float]:
    sys.path.insert(0, str(HERE))
    from jit import Pattern  # noqa: PLC0415

    pattern = Pattern(PATTERN)
    assert pattern.search(TEXT) == len(TEXT)
    return time_calls(lambda: pattern.search(TEXT), iterations, trials, warmup)


def load_regexp_py() -> ModuleType:
    spec = importlib.util.spec_from_file_location("regexp_py_impl", HERE / "regexp.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bench_instructions(iterations: int, trials: int, warmup: int) -> list[float]:
    module = load_regexp_py()
    instructions = module.Instructions(PATTERN)
    assert instructions(TEXT) is True
    return time_calls(lambda: instructions(TEXT), iterations, trials, warmup)


def bench_graph(iterations: int, trials: int, warmup: int) -> list[float]:
    module = load_regexp_py()
    graph = module.Graph(PATTERN)
    assert graph(TEXT) is True
    return time_calls(lambda: graph(TEXT), iterations, trials, warmup)


ZIG_BENCH = """\
const std = @import("std");
const re = @import("regexp.zig");

pub fn main() !void {{
    const args = try std.process.argsAlloc(std.heap.page_allocator);
    const text: [:0]const u8 = args[1];
    var timer = try std.time.Timer.start();
    const n: usize = {iterations};
    var hits: usize = 0;
    var i: usize = 0;
    while (i < n) : (i += 1) {{
        std.mem.doNotOptimizeAway(text);
        if (re.match("{pattern}", text)) hits += 1;
    }}
    const elapsed = timer.read();
    const us = @as(f64, @floatFromInt(elapsed)) / @as(f64, @floatFromInt(n)) / 1000.0;
    var stdout_buffer: [64]u8 = undefined;
    var stdout_writer = std.fs.File.stdout().writer(&stdout_buffer);
    try stdout_writer.interface.print("{{d}} {{d:.4}}\\n", .{{ hits, us }});
    try stdout_writer.interface.flush();
}}
"""


def bench_zig(tmp: Path, iterations: int, trials: int) -> list[float] | None:
    zig = shutil.which("zig")
    if zig is None:
        return None
    source = (HERE / "regexp.zig").read_text()
    # match() is private; a benchmark driver needs to call it from outside the module.
    source, n = re.subn(r"(?m)^fn match\(", "pub fn match(", source, count=1)
    assert n == 1, "regexp.zig's match() signature changed"
    (tmp / "regexp.zig").write_text(source)
    (tmp / "bench.zig").write_text(
        ZIG_BENCH.format(iterations=iterations, pattern=ZIG_PATTERN)
    )
    subprocess.run(
        [zig, "build-exe", "bench.zig", "-O", "ReleaseFast", "--name", "bench"],
        cwd=tmp, check=True, capture_output=True,
    )
    samples = []
    for _ in range(trials):
        out = subprocess.run(
            [str(tmp / "bench"), TEXT], capture_output=True, check=True, text=True
        ).stdout
        hits, us = out.split()
        assert int(hits) == iterations, "regexp.zig match() did not find a.*d"
        samples.append(float(us))
    return samples


def bench_forth(trials: int) -> list[float] | None:
    node = shutil.which("node")
    tracing = HERE / "tracing"
    if node is None or not (tracing / "bench.mjs").exists():
        return None
    samples = []
    for _ in range(trials):
        out = subprocess.run(
            [node, "bench.mjs", TEXT],
            cwd=tracing, capture_output=True, check=True, text=True,
        ).stdout
        match = TIME_RE.search(out)
        assert match, f"unexpected bench.mjs output: {out!r}"
        samples.append(float(match.group(1)))
    return samples


def summarize(
    name: str, notes: str, samples: list[float] | None
) -> tuple[str, str, float | None, str]:
    if not samples:
        return name, notes, None, "N/R"
    median = statistics.median(samples)
    return name, notes, median, f"{median:.4f} ({min(samples):.4f}-{max(samples):.4f})"


def rank(
    rows: list[tuple[str, str, float | None, str]],
) -> list[tuple[str, str, str, str]]:
    ranked = sorted(
        [(i, row) for i, row in enumerate(rows) if row[2] is not None],
        key=lambda pair: pair[1][2],
    )
    ranks = {}
    place: int = 0
    previous: float | None = None
    for i, (_, _, median, _) in ranked:
        assert median is not None
        if previous is None or median > previous * 1.03:
            place += 1
        ranks[i] = place
        previous = median
    out = []
    for i, (name, notes, _, formatted) in enumerate(rows):
        out.append((name, notes, formatted, str(ranks[i]) if i in ranks else "N/R"))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=200_000)
    parser.add_argument("--zig-iterations", type=int, default=2_000_000)
    parser.add_argument("--trials", type=int, default=7)
    parser.add_argument("--warmup", type=int, default=1_000)
    args = parser.parse_args()

    rows = []
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        rows.append(summarize(
            "bytecode.c", "struct instr + switch, full-match only",
            bench_bytecode(tmp, args.iterations, args.trials, args.warmup),
        ))
        rows.append(summarize(
            "switched.c", "union cell + switch, unanchored search",
            bench_switched(tmp, args.iterations, args.trials, args.warmup),
        ))
        rows.append(summarize(
            "threaded.c", "union cell + labels as values",
            bench_threaded(tmp, args.iterations, args.trials, args.warmup),
        ))
        rows.append(summarize(
            "arm.c", "hand-written arm64 codegen into RWX memory",
            bench_arm(tmp, args.iterations, args.trials, args.warmup),
        ))
        rows.append(summarize(
            "x86.c", "hand-written x86-64 codegen; needs Rosetta on arm64",
            None,
        ))
        rows.append(summarize(
            "jit.py: Pattern", "Python port of arm.c/x86.c codegen via ctypes",
            bench_jit(args.iterations, args.trials, args.warmup),
        ))
        rows.append(summarize(
            "regexp.py: Instructions", "Ken's bytecode machine as a Python list",
            bench_instructions(args.iterations, args.trials, args.warmup),
        ))
        rows.append(summarize(
            "regexp.py: Graph", "dict-of-dict graph walk",
            bench_graph(args.iterations, args.trials, args.warmup),
        ))
        rows.append(summarize(
            "regexp.jl", "walks PCRE2's own bytecode; needs Julia",
            None,
        ))
        rows.append(summarize(
            "regexp.zig", f"backtracking match on {ZIG_PATTERN!r}, not {PATTERN!r}",
            bench_zig(tmp, args.zig_iterations, args.trials),
        ))
        rows.append(summarize(
            "regexp.f", "threaded code inside jonesforth, run as forth.wasm",
            bench_forth(args.trials),
        ))
        rows.append(summarize(
            "thompson1968.a60", "1968 CACM listing; no ALGOL-60 compiler",
            None,
        ))
        rows.append(summarize(
            "thompson1968-lambda.a60", "the paper's own lambda-tracking revision",
            None,
        ))

    print(f"{'implementation':<26} {'notes':<52} {'us/op (range)':<24} rank")
    for name, notes, formatted, place in rank(rows):
        print(f"{name:<26} {notes:<52} {formatted:<24} {place}")


if __name__ == "__main__":
    main()
