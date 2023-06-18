import os
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
        (f"{int.from_bytes('65'.encode(), 'little'):d} DSP@ 2 NUMBER DROP EMIT\n", "A"),
        (FORTH + "VERSION .\n", "47 "),
        (FORTH + "CR\n", "\n"),
        (FORTH + "LATEST @ ID.\n", "WELCOME"),
        (FORTH + "3 4 5 .S\n", "5 4 3 "),
        (FORTH + "3 4 5 WITHIN .\n", "0 "),
        (FORTH + ": GETPPID 110 SYSCALL0 ; GETPPID .\n", f"{os.getpid():d} "),
        (
            FORTH + ": FOO ( n -- ) THROW ;\n"
            ": TEST-EXCEPTIONS 25 ['] FOO CATCH ?DUP IF "
            '." FOO threw exception: " . CR DROP THEN ;\n'
            "TEST-EXCEPTIONS\n",
            "FOO threw exception: 25 \n"
        )
    ],
)
def test_basics(cmd: str, test_input: str, expected: str):
    cp = run(cmd, input=test_input, capture_output=True, check=True, text=True)
    assert (cp.stdout or cp.stderr) == expected


def test_syscalls(cmd: str):
    names = {
        "SYS_EXIT": "__NR_exit",
        "SYS_OPEN": "__NR_open",
        "SYS_CLOSE": "__NR_close",
        "SYS_READ": "__NR_read",
        "SYS_WRITE": "__NR_write",
        "SYS_CREAT": "__NR_creat",
        "SYS_BRK": "__NR_brk",
    }
    # https://unix.stackexchange.com/a/254700
    values = run(
        ["gcc", "-include", "sys/syscall.h", "-E", "-"],
        input=" ".join(names.values()),
        capture_output=True,
        check=True,
        text=True,
    )
    values = values.stdout.rstrip().rpartition("\n")[2]

    assert run(
        cmd,
        input=f"{FORTH} {' '.join(names)} .S\n",
        capture_output=True,
        check=True,
        text=True
    ).stdout == " ".join(reversed(values.split())) + " "


def test_fnctl(cmd: str):
    names = "O_RDONLY O_WRONLY O_RDWR O_CREAT O_EXCL O_TRUNC O_APPEND O_NONBLOCK"
    # https://unix.stackexchange.com/a/254700
    values = run(
        ["gcc", "-include", "fcntl.h", "-E", "-"],
        input=names,
        capture_output=True,
        check=True,
        text=True,
    )
    values = values.stdout.rstrip().rpartition("\n")[2]

    assert run(
        cmd,
        input=f"{FORTH} {names} .S\n",
        capture_output=True,
        check=True,
        text=True
    ).stdout == " ".join(str(int(val, 8)) for val in reversed(values.split())) + " "


@pytest.mark.parametrize(
    "test_input,expected",
    [
        (FORTH + "SEE >DFA\n", ": >DFA >CFA 8+ EXIT ;\n"),
        (FORTH + "SEE HIDE\n", ": HIDE WORD FIND HIDDEN ;\n"),
        (FORTH + "SEE QUIT\n", ": QUIT R0 RSP! INTERPRET BRANCH ( -16 ) ;\n"),
    ],
)
def test_decompile(cmd: str, test_input: str, expected: str, coverage: bool):
    if coverage:
        pytest.skip("Understand why SEE does not work with coverage")
    assert run(
        cmd,
        input=test_input,
        capture_output=True,
        check=True,
        text=True,
    ).stdout == expected


def test_argc(cmd: str, coverage: bool):
    if coverage:
        pytest.skip("ARGC requires _start, gcov requires main")
    assert run(
        [cmd, "foo", "bar"],
        input=FORTH + "ARGC .\n",
        capture_output=True,
        check=True,
        text=True,
    ).stdout == "3 "


def test_argv(cmd: str, coverage: bool):
    if coverage:
        pytest.skip("ARGC requires _start, gcov requires main")
    assert run(
        [cmd, "foo", "bar"],
        input=FORTH + "0 ARGV TELL SPACE 2 ARGV TELL\n",
        capture_output=True,
        check=True,
        text=True,
    ).stdout == cmd + " bar"
