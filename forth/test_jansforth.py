"""Minimal regression coverage for jansforth.c/recurse.c.

Unlike 4th.c/5th.c (test_4th.py) and the wasm ports (web/4th.test.ts), these
two have no automated test harness at all, so a C@C! regression here would
otherwise go unnoticed. This pins its copy direction and address-increment
semantics: ( source dest -- source+1 dest+1 ), matching jonesforth.S.

recurse.c's key() lacks jansforth.c's EOF check (see its comment), so it
spins reading EOF forever instead of exiting; a short timeout works around
that without trying to fix the unrelated bug here.
"""

import subprocess
from pathlib import Path

import pytest

TARGETS = ["jansforth", "recurse", "recurse-chicken"]
CHICKEN = ["recurse-chicken"]


@pytest.mark.parametrize("target", TARGETS)
def test_c_at_c_store(target: str) -> None:
    subprocess.run(["make", target], cwd="forth", check=True)
    try:
        try:
            cp = subprocess.run(
                [f"./{target}"],
                cwd="forth/",
                capture_output=True,
                input="64 DSP@ RSP@ C@C! RSP@ 1 TELL\n",
                text=True,
                timeout=2,
            )
            stdout = cp.stdout
        except subprocess.TimeoutExpired as timeout:
            # TimeoutExpired.stdout comes back as bytes even with text=True.
            stdout = (timeout.stdout or b"").decode()
        assert stdout == "@"
    finally:
        subprocess.run(["rm", "-f", target], cwd="forth", check=True)


@pytest.mark.parametrize("target", TARGETS)
def test_mandel(target: str) -> None:
    """4th.fs's MANDEL easter egg only uses words jonesforth actually has
    (no DO/LOOP/2*/shifts), but nothing else loads 4th.fs itself -- a PARSE
    ERROR means it regressed; '*' in the output means it actually rendered.
    """
    subprocess.run(["make", target], cwd="forth", check=True)
    try:
        preamble = Path("forth/4th.fs").read_text()
        cp = subprocess.run(
            [f"./{target}"],
            cwd="forth/",
            capture_output=True,
            input=preamble + "MANDEL\nBYE\n",
            text=True,
            timeout=10,
        )
        assert "PARSE ERROR" not in cp.stdout
        assert "*" in cp.stdout
    finally:
        subprocess.run(["rm", "-f", target], cwd="forth", check=True)


@pytest.mark.parametrize("target", TARGETS)
def test_catch_throw(target: str) -> None:
    """THROW unwinds nested calls to the matching CATCH and execution carries
    on.  jansforth keeps its return stack in 2048 cells, so it only gets a
    shallow recursion; the others go thousands deep."""
    subprocess.run(["make", target], cwd="forth", check=True)
    try:
        depth = 100 if target == "jansforth" else 5000
        program = Path("jonesforth/jonesforth.f").read_text() + (
            ": DEEP DUP 0= IF DROP 42 THROW THEN 1- RECURSE ;\n"
            f": T {depth} ['] DEEP CATCH . 77 . ;\n"
            "T\nBYE\n"
        )
        cp = subprocess.run(
            [f"./{target}"],
            cwd="forth/",
            capture_output=True,
            input=program,
            text=True,
            timeout=10,
        )
        assert "42 77" in cp.stdout
    finally:
        subprocess.run(["rm", "-f", target], cwd="forth", check=True)


def run_forth(target: str, program: str | bytes) -> subprocess.CompletedProcess[str]:
    """Run program after jonesforth.f; a timeout raises, so EOF must exit."""
    subprocess.run(["make", target], cwd="forth", check=True)
    try:
        data = Path("jonesforth/jonesforth.f").read_bytes()
        cp = subprocess.run(
            [f"./{target}"],
            cwd="forth/",
            capture_output=True,
            input=data + (program.encode() if isinstance(program, str) else program),
            timeout=10,
        )
        return subprocess.CompletedProcess(
            cp.args,
            cp.returncode,
            cp.stdout.decode(errors="replace"),
            cp.stderr.decode(errors="replace"),
        )
    finally:
        subprocess.run(["rm", "-f", target], cwd="forth", check=True)


@pytest.mark.parametrize("target", CHICKEN)
def test_inline_data_via_return_stack(target: str) -> None:
    """R> reaches the caller's return address, so a word can read the cell
    after its call and skip it."""
    cp = run_forth(target, ": LIT2 R> DUP 4+ >R @ ; : T LIT2 [ 99 , ] . ; T\n")
    assert "99" in cp.stdout


@pytest.mark.parametrize("target", CHICKEN)
def test_eof_exits(target: str) -> None:
    cp = run_forth(target, ": T 1 . ; T\n")
    assert cp.returncode == 0
    assert "1" in cp.stdout


@pytest.mark.parametrize("target", CHICKEN)
def test_redefined_catch_throw_not_intercepted(target: str) -> None:
    cp = run_forth(
        target,
        ": CATCH DROP 123 ; : T ['] DUP CATCH . ; T\n"
        ": THROW DROP 456 . ; : U 1 THROW 7 . ; U\n",
    )
    assert "123" in cp.stdout
    assert "456 7" in cp.stdout


@pytest.mark.parametrize("target", CHICKEN)
def test_deep_data_stack(target: str) -> None:
    """The data stack gets the old return stack region: 3000 cells fit."""
    cp = run_forth(
        target,
        ": D DUP IF DUP 1- RECURSE THEN ; 3000 D S0 @ DSP@ - 4 / . 42 .\n",
    )
    assert int(cp.stdout.split()[-2]) >= 3000
    assert cp.stdout.split()[-1] == "42"


@pytest.mark.parametrize("target", CHICKEN)
def test_print_stack_trace(target: str) -> None:
    cp = run_forth(
        target,
        ": A PRINT-STACK-TRACE ; : B A ; : T B ; T\n",
    )
    assert "A+" in cp.stdout
    assert "B+" in cp.stdout


@pytest.mark.parametrize("target", CHICKEN)
def test_long_token_truncated(target: str) -> None:
    """A token longer than the 32-byte buffer is cut, not written over DROP."""
    cp = run_forth(target, f": {'X' * 40} 7 . ;\n5 .\n")
    assert cp.returncode == 0
    assert cp.stdout.split()[-1] == "5"


@pytest.mark.parametrize("target", CHICKEN)
def test_division_by_zero_and_min_over_minus_one(target: str) -> None:
    cp = run_forth(target, "1 0 /MOD . . -2147483648 -1 /MOD -2147483648 = . 0= .\n")
    assert "DIVISION BY ZERO" in cp.stderr
    assert cp.stdout.split()[-4:] == ["0", "1", "1", "1"]


@pytest.mark.parametrize("target", CHICKEN)
def test_arithmetic_wraps(target: str) -> None:
    cp = run_forth(
        target,
        "2147483647 1+ -2147483648 = . 2147483647 2147483647 * . -2147483648 1- .\n",
    )
    assert cp.stdout.split()[-3:] == ["1", "1", "2147483647"]


@pytest.mark.parametrize("target", CHICKEN)
def test_bytes_above_ascii_are_not_blank(target: str) -> None:
    cp = run_forth(target, b"KEY \xc3 . CHAR \xe9 .\n")
    assert cp.stdout.split()[-2:] == ["195", "233"]


@pytest.mark.parametrize("target", CHICKEN)
def test_open_file_returns_errno(target: str) -> None:
    cp = run_forth(target, 'S" /nonexistent" R/O OPEN-FILE . .\n')
    assert cp.stdout.split()[-2:] == ["2", "-2"]


@pytest.mark.parametrize("target", CHICKEN)
def test_data_stack_bounds(target: str) -> None:
    cp = run_forth(target, ": F 1 BEGIN DUP AGAIN ;\nF\n5 .\nDROP DROP DROP\n6 .\n")
    assert "STACK OVERFLOW" in cp.stderr
    assert "STACK UNDERFLOW" in cp.stderr
    assert cp.stdout.split()[-2:] == ["5", "6"]


@pytest.mark.parametrize("target", CHICKEN)
def test_out_of_memory(target: str) -> None:
    cp = run_forth(target, ": H BEGIN 1 , AGAIN ;\nH\n8 .\n")
    assert "OUT OF MEMORY" in cp.stderr
    assert cp.stdout.split()[-1] == "8"


@pytest.mark.parametrize("target", CHICKEN)
def test_lone_sign_and_empty_are_not_numbers(target: str) -> None:
    cp = run_forth(target, ': T S" -" NUMBER . . S" " NUMBER . . ; T\n')
    assert cp.stdout.split()[-4:] == ["1", "0", "1", "0"]
