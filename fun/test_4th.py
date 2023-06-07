from pathlib import Path
from subprocess import run

import pytest

SYSCALL0 = int.from_bytes("SYSCALL0".encode(), byteorder="little")


@pytest.fixture(scope="module")
def cmd():
    run(["make", "4th"], capture_output=True, cwd="fun", check=True)
    yield "fun/4th"
    run(["make", "clean"], capture_output=True, cwd="fun", check=True)


@pytest.fixture(scope="function")
def test_input(request) -> str:
    return request.param.replace("#", Path("fun/4th.fs").read_text())


@pytest.fixture(scope="function")
def expected(request) -> str:
    return request.param.replace(
        "#",
        "JONESFORTH VERSION 47 \n23380 CELLS REMAINING\nOK "
    )


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("65 EMIT\n", "A"),
        ("32 DUP + 1+ EMIT\n", "A"),
        ("16 DUP 2DUP + + + 1+ EMIT\n", "A"),
        ("CHAR A EMIT\n", "A"),
        (f"{SYSCALL0:d} DSP@ 8 TELL\n", "SYSCALL0"),
        ("#VERSION .\n", "#47 "),
        ("#CR\n", "#\n"),
        ("#SEE >DFA\n", "#: >DFA >CFA 8+ EXIT ;\n"),
        ("#SEE HIDE\n", "#: HIDE WORD FIND HIDDEN ;\n"),
        ("#SEE QUIT\n", "#: QUIT R0 RSP! INTERPRET BRANCH ( -16 ) ;\n"),
    ],
    indirect=["test_input", "expected"],
)
def test_basics(cmd: str, test_input: str, expected: str):
    cp = run(cmd, input=test_input, capture_output=True, check=True, text=True)
    assert cp.stdout == expected
