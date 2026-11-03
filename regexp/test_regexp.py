"""Check the portable C derivatives of Thompson's compiler against re."""

import ctypes
import importlib
import itertools
import os
import platform
import random
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest  # pyright: ignore[reportMissingImports]

from jit import Pattern

HERE = Path(__file__).parent
JONESFORTH = HERE.parent / "jonesforth"
CC = os.environ.get("CC", "cc")
STRICT = f"@{HERE.parent / 'strict.flags'}"
SANITIZE = ["-g", "-O1", "-fsanitize=address,undefined", "-fno-sanitize-recover=all"]

THREADED = re.compile(
    r"^search (\S+) (\S+)\n(?:match found after (\d+) bytes|match not found)$",
    re.M,
)
BYTECODE = re.compile(r"^(\S+) (!?~) /(\S+)/$", re.M)
FORTH_TABLE = re.compile(
    r"^(\S+) (\S+) (?:match found after (\d+) bytes|match not found)$", re.M
)
FORTH_CASE = re.compile(
    r"^(\d+) (?:match found after (\d+) bytes|match not found)$", re.M
)


def to_python(pattern: str) -> str:
    # re rejects a** as a "multiple repeat", but (e*)* is e*
    return re.sub(r"\*+", "*", pattern)


def earliest_end(pattern: str, s: str) -> int:
    """End of the first match anywhere in s, which is what search() reports."""
    r = re.compile(pattern)
    for j in range(len(s) + 1):
        if any(r.fullmatch(s, i, j) for i in range(j + 1)):
            return j
    return -1


def build(tmp: Path, source: str, *flags: str) -> str:
    out = str(tmp / Path(source).stem)
    subprocess.run([CC, STRICT, *flags, "-o", out, str(HERE / source)], check=True)
    return out


def run(exe: str) -> str:
    return subprocess.run(
        [exe], capture_output=True, check=True, text=True, timeout=60
    ).stdout


@pytest.mark.parametrize(
    ("source", "flags"),
    [
        ("arm.c", []),
        ("cps.c", []),
        ("copypatch/copypatch.c", []),
        pytest.param(  # a 32-bit JIT
            "x86.c",
            ["-m32"],
            marks=pytest.mark.skipif(
                sys.platform != "linux" or platform.machine() != "x86_64",
                reason="x86.c needs -m32",
            ),
        ),
    ],
)
def test_strict_syntax(source: str, flags: list[str]) -> None:
    """Sources no other test builds (arm64/x86 codegen) still pass strict.flags."""
    subprocess.run(
        [CC, STRICT, *flags, "-fsyntax-only", str(HERE / source)], check=True
    )


@pytest.mark.parametrize(
    ("source", "flags"),
    [
        pytest.param(source, flags, id=f"{source}-{kind}")
        for source in ["threaded.c", "switched.c"]
        for kind, flags in [("plain", []), ("sanitized", SANITIZE)]
    ]
    + [pytest.param("switched.c", ["-funsigned-char"], id="switched.c-unsigned")],
)
def test_threaded_table(tmp_path: Path, source: str, flags: list[str]) -> None:
    out = run(build(tmp_path, source, *flags))
    cases = THREADED.findall(out)
    assert cases and len(cases) == out.count("search ")
    for pattern, s, n in cases:
        assert (int(n) if n else -1) == earliest_end(to_python(pattern), s), pattern


@pytest.mark.parametrize("flags", [[], SANITIZE], ids=["plain", "sanitized"])
def test_bytecode_table(tmp_path: Path, flags: list[str]) -> None:
    out = run(build(tmp_path, "bytecode.c", *flags))
    cases = BYTECODE.findall(out)
    assert cases and len(cases) == len(out.splitlines())
    for s, op, pattern in cases:
        assert (op == "~") == bool(re.fullmatch(to_python(pattern), s)), pattern


def generate(rng: random.Random, depth: int) -> tuple:
    k = rng.random()
    if depth == 0 or k < 0.3:
        return ("c", rng.choice("abc"))
    if k < 0.55:
        return ("*", generate(rng, depth - 1))
    if k < 0.8:
        return (".", generate(rng, depth - 1), generate(rng, depth - 1))
    return ("|", generate(rng, depth - 1), generate(rng, depth - 1))


def ours(e: tuple) -> str:
    match e:
        case ("c", c):
            return c
        case ("*", x):
            return (ours(x) if x[0] in "c*" else f"({ours(x)})") + "*"
        case (".", *xs):
            return "".join(f"({ours(x)})" if x[0] == "|" else ours(x) for x in xs)
        case ("|", a, b):
            return f"({ours(a)}|{ours(b)})"
    raise ValueError(e)


def python(e: tuple) -> str:
    match e:
        case ("c", c):
            return c
        case ("*", x):
            return f"(?:{python(x)})*"
        case (".", a, b):
            return f"(?:{python(a)})(?:{python(b)})"
        case ("|", a, b):
            return f"(?:{python(a)}|{python(b)})"
    raise ValueError(e)


def random_cases(seed: int, n: int = 3000) -> Iterator[tuple[str, str, str]]:
    """Random nested-star patterns and short subjects, e.g. ('(a*|b)*c', 'bac')."""
    rng = random.Random(seed)
    for _ in range(n):
        tree = generate(rng, rng.randint(1, 4))
        s = "".join(rng.choice("abc") for _ in range(rng.randint(0, 5)))
        yield ours(tree), python(tree), s


def shared(tmp: Path, source: str) -> ctypes.CDLL:
    out = str(tmp / f"{Path(source).stem}.so")
    # -Dmain=demo leaves a non-static demo() without a prototype
    flags = ["-O1", "-shared", "-fPIC", "-Dmain=demo", "-Wno-missing-prototypes"]
    subprocess.run([CC, STRICT, *flags, "-o", out, str(HERE / source)], check=True)
    return ctypes.CDLL(out)


@pytest.fixture(scope="module")
def threaded(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str, str], int]:
    lib = shared(tmp_path_factory.mktemp("threaded"), "threaded.c")
    lib.search.argtypes = [
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_char_p, ctypes.c_char_p,
    ]
    lib.search.restype = ctypes.c_void_p
    free = ctypes.CDLL(None).free
    free.argtypes = [ctypes.c_void_p]

    def search(pattern: str, s: str) -> int:
        code = ctypes.c_void_p(None)
        buf = ctypes.create_string_buffer(s.encode())
        try:
            end = lib.search(ctypes.byref(code), pattern.encode(), buf)
            return -1 if end is None else end - ctypes.addressof(buf)
        finally:
            free(code)

    return search


@pytest.fixture(scope="module")
def switched(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str, str], int]:
    lib = shared(tmp_path_factory.mktemp("switched"), "switched.c")
    lib.study.argtypes = [ctypes.c_char_p]
    lib.study.restype = ctypes.c_void_p
    lib.search.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.search.restype = ctypes.c_void_p
    free = ctypes.CDLL(None).free
    free.argtypes = [ctypes.c_void_p]

    def search(pattern: str, s: str) -> int:
        code = lib.study(pattern.encode())
        buf = ctypes.create_string_buffer(s.encode())
        try:
            end = lib.search(code, buf)
        finally:
            free(code)
        return -1 if end is None else end - ctypes.addressof(buf)

    return search


@pytest.fixture(scope="module")
def copypatch(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str, str], int]:
    lib = shared(tmp_path_factory.mktemp("copypatch"), "copypatch/copypatch.c")
    lib.study.argtypes = [ctypes.c_char_p]
    lib.study.restype = ctypes.c_void_p
    lib.forget.argtypes = [ctypes.c_void_p]
    matcher = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p)

    def search(pattern: str, s: str) -> int:
        code = lib.study(pattern.encode())
        buf = ctypes.create_string_buffer(s.encode())
        try:
            end = matcher(code)(buf)
        finally:
            lib.forget(code)
        return -1 if end is None else end - ctypes.addressof(buf)

    return search


@pytest.fixture(scope="module")
def bytecode(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str, str], bool]:
    lib = shared(tmp_path_factory.mktemp("bytecode"), "bytecode.c")
    lib.study.argtypes = [ctypes.c_char_p]
    lib.study.restype = ctypes.c_void_p
    lib.execute.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    free = ctypes.CDLL(None).free
    free.argtypes = [ctypes.c_void_p]

    def execute(pattern: str, s: str) -> bool:
        code = lib.study(pattern.encode())
        try:
            return bool(lib.execute(code, s.encode()))
        finally:
            free(code)

    return execute


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_threaded_against_re(threaded: Callable[[str, str], int], seed: int) -> None:
    bad = [
        (pattern, s)
        for pattern, py, s in random_cases(seed)
        if threaded(pattern, s) != earliest_end(py, s)
    ]
    assert not bad, bad[:5]


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_switched_against_re(switched: Callable[[str, str], int], seed: int) -> None:
    bad = [
        (pattern, s)
        for pattern, py, s in random_cases(seed)
        if switched(pattern, s) != earliest_end(py, s)
    ]
    assert not bad, bad[:5]


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_copypatch_against_re(
    copypatch: Callable[[str, str], int], seed: int
) -> None:
    bad = [
        (pattern, s)
        for pattern, py, s in random_cases(seed)
        if copypatch(pattern, s) != earliest_end(py, s)
    ]
    assert not bad, bad[:5]


def test_copypatch_table(tmp_path: Path) -> None:
    """The committed stencils for the host ISA, through copypatch.c's own table."""
    run(build(tmp_path, "copypatch/copypatch.c"))


def test_copypatch_grep(tmp_path: Path) -> None:
    """Given patterns, copypatch copies stdin and colors every match green."""
    exe = build(tmp_path, "copypatch/copypatch.c")

    def grep(*patterns: str, text: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [exe, *patterns], input=text, capture_output=True, text=True, timeout=60
        )

    def green(s: str) -> str:
        return f"\x1b[32m{s}\x1b[0m"

    # several matches per line, from several patterns, and a line that never matches
    out = grep("a(b|c)*d", "yy", text="abcd-yy-abd\nnone\n")
    assert out.stdout == f"{green('abcd')}-{green('yy')}-{green('abd')}\nnone\n"
    # a line is cut at 1023 characters; the rest of it is not read as another line
    out = grep("a", text="a" * 2000 + "\nb")
    assert out.stdout == green("a" * 1023) + "\nb\n"
    out = grep("a(", text="a\n")
    assert (out.returncode, out.stdout) == (1, "")
    assert "cannot compile a(" in out.stderr


@pytest.mark.skipif(
    sys.platform != "darwin" or platform.machine() != "arm64",
    reason="x86-64 stencils only run here under Rosetta",
)
def test_copypatch_rosetta(tmp_path: Path) -> None:  # pragma: no cover -- not on CI
    exe = build(tmp_path, "copypatch/copypatch.c", "-arch", "x86_64")
    out = subprocess.run(["arch", "-x86_64", exe], capture_output=True)
    if b"Bad CPU type" in out.stderr:
        pytest.skip("no Rosetta")
    assert out.returncode == 0, out.stderr


@pytest.mark.skipif(
    not (shutil.which("clang") and shutil.which("llvm-readobj")),
    reason="needs clang to cross-compile and llvm-readobj to read the object",
)
@pytest.mark.parametrize("arch", ["aarch64", "x86_64"])
def test_copypatch_gen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arch: str,
) -> None:
    """make builds stencils_<arch>.o with the real flags; gen.py makes a header."""
    work = tmp_path / "copypatch"
    ignore = shutil.ignore_patterns("stencils_*.h")
    shutil.copytree(HERE / "copypatch", work, ignore=ignore)
    obj = work / f"stencils_{arch}.o"
    subprocess.run(["make", "-C", str(work), obj.name], check=True)

    monkeypatch.syspath_prepend(str(work))
    gen = importlib.import_module("gen")
    gen.main(str(obj), arch)
    out = capsys.readouterr().out
    for name in ["ch", "alt", "star", "accept", "search"]:
        assert f"static const struct stencil stencil_{name} =" in out

    other = "x86_64" if arch == "aarch64" else "aarch64"
    with pytest.raises(SystemExit, match=f"object is not {other}"):
        gen.main(str(obj), other)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_bytecode_against_re(bytecode: Callable[[str, str], bool], seed: int) -> None:
    bad = [
        (pattern, s)
        for pattern, py, s in random_cases(seed)
        if bytecode(pattern, s) != bool(re.fullmatch(py, s))
    ]
    assert not bad, bad[:5]


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_jit_against_re(seed: int) -> None:
    bad = [
        (pattern, s)
        for pattern, py, s in random_cases(seed)
        if Pattern(pattern).search(s) != earliest_end(py, s)
    ]
    assert not bad, bad[:5]


@pytest.fixture(scope="module")
def jonesforth(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], str]:
    """Build jonesforth from jonesforth.S; run regexp.f on top of jonesforth.f."""
    prelude = [JONESFORTH / "jonesforth.f", HERE / "regexp.f"]
    if not all(path.exists() for path in [JONESFORTH / "jonesforth.S", *prelude]):
        pytest.skip("jonesforth submodule is not checked out")

    exe = tmp_path_factory.mktemp("jonesforth") / "jonesforth"
    # jonesforth's own -Wl,-Ttext,0 faults on current binutils; the Makefile omits it.
    # clang's integrated assembler rejects jonesforth.S's `.set link,...` reassignments.
    gas = ["-fno-integrated-as"] if "clang" in CC else []
    argv = [CC, "-m32", *gas, "-nostdlib", "-static", "-o", str(exe), "jonesforth.S"]
    try:
        subprocess.run(argv, cwd=JONESFORTH, check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"no 32-bit toolchain: {exc}")

    def forth(source: str) -> str:
        # TEST-MODE suppresses jonesforth.f's banner
        text = "\n".join(
            [": TEST-MODE ;", *(path.read_text() for path in prelude), source, "BYE"]
        )
        return subprocess.run(
            [str(exe)],
            input=text,
            capture_output=True,
            check=True,
            text=True,
            timeout=120,
        ).stdout

    return forth


def test_forth_table(jonesforth: Callable[[str], str]) -> None:
    out = jonesforth("RE-TESTS")
    cases = FORTH_TABLE.findall(out)
    assert cases and len(cases) == len(out.splitlines())
    for pattern, s, n in cases:
        assert (int(n) if n else -1) == earliest_end(to_python(pattern), s), pattern


# SEE prints LIT as its bare value and an XCALL operand as the word it lands in
SEE_HEADER = (
    ": RE-PAT RSP@ RE-RSP ! RE-START RE-DONE? 0BRANCH ( 16 ) 0 EXIT RE-PAT+20 >R"
    " RE-THREAD DUP 0BRANCH ( 16 ) >R BRANCH ( -24 ) DROP RE-LOAD"
)

# one line per block: character node, KLEENE or ALTERN.  RE-STRIP rewrites e* to
# e'*, so a** and, further down, (a*b*)*c and (a*|b*)*c collapse to identical code.
SEE_BLOCKS = {
    "abcdefg": (
        "BRANCH ( 4 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 4 ) 98 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 4 ) 99 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 4 ) 100 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 4 ) 101 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 4 ) 102 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 4 ) 103 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
    ),
    "(a|b)*a": (
        "BRANCH ( 108 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 56 ) 98 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 20 ) XCALL RE-PAT BRANCH ( -84 )",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT",
        "BRANCH ( 4 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
    ),
    "a(b|c)*d": (
        "BRANCH ( 4 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 108 ) 98 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 56 ) 99 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 20 ) XCALL RE-PAT BRANCH ( -84 )",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT",
        "BRANCH ( 4 ) 100 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
    ),
    "(a|a)*": (
        "BRANCH ( 108 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 56 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 20 ) XCALL RE-PAT BRANCH ( -84 )",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT",
    ),
    "a*": (
        "BRANCH ( 48 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT",
    ),
    "a**": (
        "BRANCH ( 48 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT",
    ),
    "(a*b*)*c": (
        "BRANCH ( 108 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 56 ) 98 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 20 ) XCALL RE-PAT BRANCH ( -84 )",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT",
        "BRANCH ( 4 ) 99 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
    ),
    "(a*|b*)*c": (
        "BRANCH ( 108 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 56 ) 98 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 20 ) XCALL RE-PAT BRANCH ( -84 )",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT",
        "BRANCH ( 4 ) 99 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
    ),
    "b*(c|d)": (
        "BRANCH ( 48 ) 98 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT",
        "BRANCH ( 76 ) 99 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 56 ) 100 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 20 ) XCALL RE-PAT BRANCH ( -84 )",
    ),
}


@pytest.mark.parametrize("pattern", SEE_BLOCKS)
def test_forth_see(jonesforth: Callable[[str], str], pattern: str) -> None:
    out = jonesforth(f': RE-PAT RE" {pattern}" ;\nRE-RSP . LATEST @ >DFA .\nSEE RE-PAT')
    rsp, dfa, see = out.split(" ", 2)
    # brk is randomized, so name the only two absolute addresses SEE prints
    names = {rsp: "RE-RSP", str(int(dfa) + 20): "RE-PAT+20"}
    see = " ".join(names.get(token, token) for token in see.split())
    assert see == " ".join([SEE_HEADER, *SEE_BLOCKS[pattern], "RE-ACCEPT ;"])


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_forth_against_re(jonesforth: Callable[[str], str], seed: int) -> None:
    cases = list(itertools.islice(random_cases(seed), 150))
    source = "\n".join(
        # RE" compiles into the definition being built, so each pattern needs its
        # own word -- and ['] is compile-only, so the driver has to be one too
        f': RE-PAT{i} RE" {pattern}" ;\n'
        f': RE-RUN{i} ." {i} " Z" {s}" [\'] RE-PAT{i} TRY ;\nRE-RUN{i}'
        for i, (pattern, _, s) in enumerate(cases)
    )
    out = jonesforth(f"65536 MORECORE\n{source}")
    found = FORTH_CASE.findall(out)
    assert len(found) == len(cases), out
    bad = [
        (pattern, s)
        for (pattern, py, s), (_, n) in zip(cases, found, strict=True)
        if (int(n) if n else -1) != earliest_end(py, s)
    ]
    assert not bad, bad[:5]
