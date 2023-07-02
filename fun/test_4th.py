import os
from pathlib import Path
from subprocess import run

import pytest

SYSCALL0 = int.from_bytes("SYSCALL0".encode(), byteorder="little")


@pytest.fixture(scope="module")
def forth(target: str):
    filename = "fun/jonesforth.f" if target == "4th.32" else "fun/4th.fs"
    return ": TEST-MODE ;\n" + Path(filename).read_text()


@pytest.fixture(scope="module")
def cmd(target: str):
    run(["make", target], cwd="fun", check=True)
    yield "fun/" + target
    if target.startswith("c"):
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
        (f"{SYSCALL0:d} DSP@ HERE 8 CMOVE HERE 8 TELL\n", "SYSCALL0"),
        (f"{int.from_bytes('65'.encode(), 'little'):d} DSP@ 2 NUMBER DROP EMIT\n", "A"),
        ("65 >R RSP@ 1 TELL RDROP\n", "A"),
        ("65 DSP@ RSP@ SWAP C@C! RSP@ 1 TELL\n", "A"),
        ("65 >R 1 RSP@ -! RSP@ 1 TELL\n", "@"),
    ]
)
def test_basics(cmd: str, test_input: str, expected: str):
    if cmd.endswith(".32") and expected == "SYSCALL0":
        pytest.skip("SYSCALL0 requires 8 bytes")
    cp = run(cmd, input=test_input, capture_output=True, check=True, text=True)
    assert (cp.stdout or cp.stderr) == expected


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("VERSION .\n", "47 "),
        ("CR\n", "\n"),
        ("LATEST @ ID.\n", "WELCOME"),
        ("0 1 > . 1 0 > .\n", "0 -1 "),
        ("0 1 >= . 0 0 >= .\n", "0 -1 "),
        ("0 0<> . 1 0<> .\n", "0 -1 "),
        ("1 0<= . 0 0<= .\n", "0 -1 "),
        ("-1 0>= . 0 0>= .\n", "0 -1 "),
        ("0 0 OR . 0 -1 OR .\n", "0 -1 "),
        ("-1 -1 XOR . 0 -1 XOR .\n", "0 -1 "),
        ("-1 INVERT . 0 INVERT .\n", "0 -1 "),
        ("3 4 5 .S\n", "5 4 3 "),
        ("1 2 3 4 2SWAP .S\n", "2 1 4 3 "),
        ("F_IMMED F_HIDDEN .S\n", "32 128 "),
        (": CFA@ WORD FIND >CFA @ ; CFA@ >DFA DOCOL = .\n", "-1 "),
        ("3 4 5 WITHIN .\n", "0 "),
        (": GETPPID 110 SYSCALL0 ; GETPPID .\n", f"{os.getpid():d} "),
        ("18 95 SYSCALL1 .\n", "18 "),  # umask(2)
        ('O_RDONLY Z" fun/4th.c" 21 SYSCALL2 .\n', "0 "),  # access(2)
        ('S" test" SWAP 1 SYS_WRITE SYSCALL3\n', "test"),
        (
            ": FOO ( n -- ) THROW ;\n"
            ": TEST-EXCEPTIONS 25 ['] FOO CATCH ?DUP IF "
            '." FOO threw exception: " . CR DROP THEN ;\n'
            "TEST-EXCEPTIONS\n",
            "FOO threw exception: 25 \n"
        )
    ],
)
def test_advanced(cmd: str, forth: str, test_input: str, expected: str):
    if cmd.endswith(".32"):
        test_input = (
            test_input.replace("110 SYSCALL0", "64 SYSCALL0")
            .replace("95 SYSCALL1", "60 SYSCALL1")
            .replace("21 SYSCALL2", "33 SYSCALL2")
        )
    cp = run(cmd, input=forth + test_input, capture_output=True, check=True, text=True)
    assert (cp.stdout or cp.stderr) == expected


def test_syscalls(cmd: str, forth: str):
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
    arch = "-m32" if cmd.endswith(".32") else "-m64"
    values = run(
        ["gcc", arch, "-include", "sys/syscall.h", "-E", "-"],
        input=" ".join(names.values()),
        capture_output=True,
        check=True,
        text=True,
    )
    values = values.stdout.rstrip().rpartition("\n")[2]

    assert run(
        cmd,
        input=f"{forth} {' '.join(names)} .S\n",
        capture_output=True,
        check=True,
        text=True
    ).stdout == " ".join(reversed(values.split())) + " "


def test_fnctl(cmd: str, forth: str):
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
        input=f"{forth} {names} .S\n",
        capture_output=True,
        check=True,
        text=True
    ).stdout == " ".join(str(int(val, 8)) for val in reversed(values.split())) + " "


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("SEE >DFA\n", ": >DFA >CFA 8+ EXIT ;\n"),
        ("SEE HIDE\n", ": HIDE WORD FIND HIDDEN ;\n"),
        ("SEE QUIT\n", ": QUIT R0 RSP! INTERPRET BRANCH ( -16 ) ;\n"),
    ],
)
def test_decompile(cmd: str, forth: str, test_input: str, expected: str):
    if cmd.startswith("fun/c"):
        pytest.skip("Understand why SEE does not work with coverage")
    if cmd.endswith(".32"):
        expected = expected.replace("8+", "4+").replace("-16", "-8")
    assert run(
        cmd,
        input=forth + test_input,
        capture_output=True,
        check=True,
        text=True,
    ).stdout == expected


def test_argc(cmd: str, forth: str):
    if cmd.startswith("fun/c"):
        pytest.skip("ARGC requires _start, gcov requires main")
    if cmd.endswith(".32"):
        pytest.skip("Understand why ARGC doesn't work with -m32")
    assert run(
        [cmd, "foo", "bar"],
        input=forth + "ARGC .\n",
        capture_output=True,
        check=True,
        text=True,
    ).stdout == "3 "


def test_argv(cmd: str, forth: str):
    if cmd.startswith("fun/c"):
        pytest.skip("ARGV requires _start, gcov requires main")
    if cmd.endswith(".32"):
        pytest.skip("Understand why ARGV doesn't work with -m32")
    assert run(
        [cmd, "foo", "bar"],
        input=forth + "0 ARGV TELL SPACE 2 ARGV TELL\n",
        capture_output=True,
        check=True,
        text=True,
    ).stdout == cmd + " bar"
