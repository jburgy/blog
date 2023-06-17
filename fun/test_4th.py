from pathlib import Path
from subprocess import run

import pytest

SYSCALL0 = int.from_bytes("SYSCALL0".encode(), byteorder="little")
FORTH = ": TEST-MODE ;\n" + Path("fun/4th.fs").read_text()


@pytest.fixture(scope="module")
def cmd(coverage: bool):
    run(["make", "c4th" if coverage else "4th"], cwd="fun", check=True)
    yield "fun/c4th" if coverage else "fun/4th"
    if coverage:
        run(["gcov", "4th.c"], cwd="fun", check=True)
    run(["make", "clean"], cwd="fun", check=True)


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("BORK\n", "PARSE ERROR: BORK\n"),
        ("65 EMIT\n", "A"),
        ("777 65 EMIT\n", "A"),
        ("32 DUP + 1+ EMIT\n", "A"),
        ("16 DUP 2DUP + + + 1+ EMIT\n", "A"),
        ("8 DUP * 1+ EMIT\n", "A"),
        ("CHAR A EMIT\n", "A"),
        (": SLOW WORD FIND >CFA EXECUTE ; 65 SLOW EMIT\n", "A"),
        (f"{SYSCALL0:d} DSP@ 8 TELL\n", "SYSCALL0"),
        (FORTH + "VERSION .\n", "47 "),
        (FORTH + "CR\n", "\n"),
        (FORTH + "SEE >DFA\n", ": >DFA >CFA 8+ EXIT ;\n"),
        (FORTH + "SEE HIDE\n", ": HIDE WORD FIND HIDDEN ;\n"),
        (FORTH + "SEE QUIT\n", ": QUIT R0 RSP! INTERPRET BRANCH ( -16 ) ;\n"),
    ],
)
def test_basics(cmd: str, test_input: str, expected: str, coverage: True):
    if coverage and test_input[-9:].startswith("SEE"):
        return
    cp = run(cmd, input=test_input, capture_output=True, check=True, text=True)
    assert (cp.stdout or cp.stderr) == expected


def test_argc(cmd: str, coverage: bool):
    if coverage:
        return
    assert run(
        [cmd, "foo", "bar"],
        input=FORTH + "ARGC .\n",
        capture_output=True,
        check=True,
        text=True,
    ).stdout == "3 "


def test_argv(cmd: str, coverage: bool):
    if coverage:
        return
    assert run(
        [cmd, "foo", "bar"],
        input=FORTH + "0 ARGV TELL SPACE 2 ARGV TELL\n",
        capture_output=True,
        check=True,
        text=True,
    ).stdout == cmd + " bar"
