from pathlib import Path
from subprocess import run

import pytest

SYSCALL0 = int.from_bytes("SYSCALL0".encode(), byteorder="little")
FORTH = ": TEST-MODE ;\n" + Path("fun/4th.fs").read_text()


@pytest.fixture(scope="module")
def cmd():
    run(["make", "4th"], capture_output=True, cwd="fun", check=True)
    yield "fun/4th"
    run(["make", "clean"], capture_output=True, cwd="fun", check=True)


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("BORK\n", "PARSE ERROR: BORK\n"),
        ("65 EMIT\n", "A"),
        ("777 65 EMIT\n", "A"),
        ("32 DUP + 1+ EMIT\n", "A"),
        ("16 DUP 2DUP + + + 1+ EMIT\n", "A"),
        ("CHAR A EMIT\n", "A"),
        (f"{SYSCALL0:d} DSP@ 8 TELL\n", "SYSCALL0"),
        (FORTH + "VERSION .\n", "47 "),
        (FORTH + "CR\n", "\n"),
        (FORTH + "SEE >DFA\n", ": >DFA >CFA 8+ EXIT ;\n"),
        (FORTH + "SEE HIDE\n", ": HIDE WORD FIND HIDDEN ;\n"),
        (FORTH + "SEE QUIT\n", ": QUIT R0 RSP! INTERPRET BRANCH ( -16 ) ;\n"),
    ],
)
def test_basics(cmd: str, test_input: str, expected: str):
    cp = run(cmd, input=test_input, capture_output=True, check=True, text=True)
    assert (cp.stdout or cp.stderr) == expected


def test_argc(cmd: str):
    assert run(
        [cmd, "foo", "bar"],
        input=FORTH + "ARGC .\n",
        capture_output=True,
        check=True,
        text=True,
    ).stdout == "3 "


def test_argv(cmd: str):
    assert run(
        [cmd, "foo", "bar"],
        input=FORTH + "0 ARGV TELL SPACE 2 ARGV TELL\n",
        capture_output=True,
        check=True,
        text=True,
    ).stdout == cmd + " bar"
