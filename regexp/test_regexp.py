"""Check the portable C derivatives of Thompson's compiler against re."""

import ctypes
import itertools
import os
import random
import re
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest  # pyright: ignore[reportMissingImports]

HERE = Path(__file__).parent
JONESFORTH = HERE.parent / "jonesforth"
CC = os.environ.get("CC", "cc")
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
    subprocess.run([CC, "-w", *flags, "-o", out, str(HERE / source)], check=True)
    return out


def run(exe: str) -> str:
    return subprocess.run(
        [exe], capture_output=True, check=True, text=True, timeout=60
    ).stdout


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
    flags = ["-O1", "-shared", "-fPIC", "-Dmain=demo"]
    subprocess.run([CC, "-w", *flags, "-o", out, str(HERE / source)], check=True)
    return ctypes.CDLL(out)


@pytest.fixture(scope="module")
def threaded(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str, str], int]:
    lib = shared(tmp_path_factory.mktemp("threaded"), "threaded.c")
    lib.search.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    lib.search.restype = ctypes.c_void_p

    def search(pattern: str, s: str) -> int:
        buf = ctypes.create_string_buffer(s.encode())
        end = lib.search(pattern.encode(), buf)
        return -1 if end is None else end - ctypes.addressof(buf)

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
def test_bytecode_against_re(bytecode: Callable[[str, str], bool], seed: int) -> None:
    bad = [
        (pattern, s)
        for pattern, py, s in random_cases(seed)
        if bytecode(pattern, s) != bool(re.fullmatch(py, s))
    ]
    assert not bad, bad[:5]


@pytest.fixture(scope="module")
def jonesforth(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], str]:
    """Build jonesforth from jonesforth.S; run regexp.f on top of jonesforth.f."""
    prelude = [JONESFORTH / "jonesforth.f", HERE / "regexp.f"]
    if not all(path.exists() for path in [JONESFORTH / "jonesforth.S", *prelude]):
        pytest.skip("jonesforth submodule is not checked out")

    exe = tmp_path_factory.mktemp("jonesforth") / "jonesforth"
    # jonesforth's own -Wl,-Ttext,0 faults on current binutils; the Makefile omits it
    argv = [CC, "-m32", "-nostdlib", "-static", "-o", str(exe), "jonesforth.S"]
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

# one line per block: character node, KLEENE or ALTERN
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
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT BRANCH ( 4 )",
        "BRANCH ( 4 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
    ),
    "a(b|c)*d": (
        "BRANCH ( 4 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 108 ) 98 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 56 ) 99 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 20 ) XCALL RE-PAT BRANCH ( -84 )",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT BRANCH ( 4 )",
        "BRANCH ( 4 ) 100 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
    ),
    "(a|a)*": (
        "BRANCH ( 108 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 56 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "BRANCH ( 20 ) XCALL RE-PAT BRANCH ( -84 )",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT BRANCH ( 4 )",
    ),
    "a*": (
        "BRANCH ( 48 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT BRANCH ( 4 )",
    ),
    "a**": (
        "BRANCH ( 80 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT EXIT EXIT",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT BRANCH ( 4 )",
    ),
    "(a*b*)*c": (
        "BRANCH ( 148 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT EXIT EXIT",
        "BRANCH ( 48 ) 98 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT BRANCH ( 4 )",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT BRANCH ( 4 )",
        "BRANCH ( 4 ) 99 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
    ),
    "(a*|b*)*c": (
        "BRANCH ( 172 ) 97 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT EXIT EXIT",
        "BRANCH ( 88 ) 98 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT BRANCH ( -72 )",
        "BRANCH ( 20 ) XCALL RE-PAT BRANCH ( -104 )",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT BRANCH ( 4 )",
        "BRANCH ( 4 ) 99 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
    ),
    "b*(c|d)": (
        "BRANCH ( 48 ) 98 RE-CHAR? 0BRANCH ( 8 ) EXIT (NNODE)",
        "XCALL RE-PAT BRANCH ( 20 ) XCALL RE-PAT BRANCH ( 4 )",
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
