import os
from functools import partial
from pathlib import Path
from subprocess import run
from typing import Iterable, Mapping

import pytest
from _pytest import fixtures


@pytest.fixture(scope="module")
def mapping(target: str) -> Mapping[str, str]:
    names = {
        "SYS_EXIT": "__NR_exit",
        "SYS_READ": "__NR_read",
        "SYS_WRITE": "__NR_write",
        "SYS_OPEN": "__NR_open",
        "SYS_CLOSE": "__NR_close",
        "SYS_CREAT": "__NR_creat",
        "access": "__NR_access",
        "SYS_BRK": "__NR_brk",
        "getppid": "__NR_getppid",
        "umask": "__NR_umask",
        "O_RDONLY": "O_RDONLY",
        "O_WRONLY": "O_WRONLY",
        "O_RDWR": "O_RDWR",
        "O_CREAT": "O_CREAT",
        "O_EXCL": "O_EXCL",
        "O_TRUNC": "O_TRUNC",
        "O_APPEND": "O_APPEND",
        "O_NONBLOCK": "O_NONBLOCK",
    }
    arch = "-m32" if target == "4th.32" else "-m64"
    # https://unix.stackexchange.com/a/254700
    rc = run(
        ["gcc", arch, "-include", "sys/syscall.h", "-include", "fcntl.h", "-E", "-"],
        input=" ".join(names.values()),
        capture_output=True,
        check=True,
        text=True,
    )
    values = (
        str(int(value, 8 if value.startswith("0") else 10))
        for value in rc.stdout.rstrip().rpartition("\n")[2].split()
    )
    result = dict(zip(names.keys(), values))

    syscall0 = int.from_bytes("SYSCALL0".encode(), byteorder="little")
    result["syscall0"] = (
        "{:d} {:d}".format(*divmod(syscall0, 2**32))
        if target == "4th.32"
        else "{:d}".format(syscall0)
    )
    filename = "forth/4th.32.fs" if target == "4th.32" else "forth/4th.fs"
    result["forth"] = ": TEST-MODE ;\n" + Path(filename).read_text()
    return result


@pytest.fixture(scope="module")
def cmd(target: str) -> Iterable[partial]:
    run(["make", target], cwd="forth", check=True)
    yield partial(
        run,
        args=["forth/" + target, "foo", "bar"],
        capture_output=True,
        check=True,
        env={"SHELL": "/bin/bash"},
        text=True,
    )
    if target == "4th.gcov":
        run(["gcov", "4th.c"], cwd="forth", check=True)
    run(["make", "clean"], cwd="forth", check=True)


def test_error(cmd: partial):
    assert cmd(input="BORK\n").stderr == "PARSE ERROR: BORK\n"


@pytest.fixture(scope="function")
def test_input(request: fixtures.SubRequest, mapping: dict):
    assert isinstance(request.param, str)
    return request.param.format_map(mapping)


@pytest.fixture(scope="function")
def expected(request: fixtures.SubRequest, target: str):
    assert isinstance(request.param, str)
    return (
        request.param.replace("8+", "4+").replace("-16", "-8")
        if target == "4th.32"
        else request.param
    )


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("65 EMIT\n", "A"),
        ("777 65 EMIT\n", "A"),
        ("32 DUP + 1+ EMIT\n", "A"),
        ("16 DUP 2DUP + + + 1+ EMIT\n", "A"),
        ("8 DUP * 1+ EMIT\n", "A"),
        ("CHAR A EMIT\n", "A"),
        (": SLOW WORD FIND >CFA EXECUTE ; 65 SLOW EMIT\n", "A"),
        ("{syscall0} DSP@ 8 TELL\n", "SYSCALL0"),
        ("{syscall0} DSP@ HERE @ 8 CMOVE HERE @ 8 TELL\n", "SYSCALL0"),
        (f"{int.from_bytes('65'.encode(), 'little'):d} DSP@ 2 NUMBER DROP EMIT\n", "A"),
        ("65 >R RSP@ 1 TELL RDROP\n", "A"),
        ("65 DSP@ RSP@ SWAP C@C! RSP@ 1 TELL\n", "A"),
        ("65 >R 1 RSP@ -! RSP@ 1 TELL\n", "@"),
        (
            """
: <BUILDS WORD CREATE DODOES , 0 , ;
: DOES> R> LATEST @ >DFA ! ;
: CONST <BUILDS , DOES> @ ;

65 CONST FOO
FOO EMIT
""",
            "A",
        ),
        ("{forth}VERSION .\n", "47 "),
        ("{forth}CR\n", "\n"),
        ("{forth}LATEST @ ID.\n", "WELCOME"),
        ("{forth}0 1 > . 1 0 > .\n", "0 -1 "),
        ("{forth}0 1 >= . 0 0 >= .\n", "0 -1 "),
        ("{forth}0 0<> . 1 0<> .\n", "0 -1 "),
        ("{forth}1 0<= . 0 0<= .\n", "0 -1 "),
        ("{forth}-1 0>= . 0 0>= .\n", "0 -1 "),
        ("{forth}0 0 OR . 0 -1 OR .\n", "0 -1 "),
        ("{forth}-1 -1 XOR . 0 -1 XOR .\n", "0 -1 "),
        ("{forth}-1 INVERT . 0 INVERT .\n", "0 -1 "),
        ("{forth}3 4 5 .S\n", "5 4 3 "),
        ("{forth}1 2 3 4 2SWAP .S\n", "2 1 4 3 "),
        ("{forth}F_IMMED F_HIDDEN .S\n", "32 128 "),
        ("{forth}: CFA@ WORD FIND >CFA @ ; CFA@ >DFA DOCOL = .\n", "-1 "),
        ("{forth}3 4 5 WITHIN .\n", "0 "),
        ("{forth}: GETPPID {getppid} SYSCALL0 ; GETPPID .\n", f"{os.getpid():d} "),
        ("{forth}18 {umask} SYSCALL1 .\n", "18 "),
        ('{forth}O_RDONLY Z" forth/4th.c" {access} SYSCALL2 .\n', "0 "),
        ('{forth}S" test" SWAP 1 SYS_WRITE SYSCALL3\n', "test"),
        ("{forth}ARGC .\n", "3 "),
        ("{forth}ENVIRON @ DUP STRLEN TELL\n", "SHELL=/bin/bash"),
        ("{forth}SEE >DFA\n", ": >DFA >CFA 8+ EXIT ;\n"),
        ("{forth}SEE HIDE\n", ": HIDE WORD FIND HIDDEN ;\n"),
        ("{forth}SEE QUIT\n", ": QUIT R0 RSP! INTERPRET BRANCH ( -16 ) ;\n"),
        (
            "{forth}: FOO ( n -- ) THROW ;\n"
            ": TEST-EXCEPTIONS 25 ['] FOO CATCH ?DUP IF "
            '." FOO threw exception: " . CR DROP THEN ;\n'
            "TEST-EXCEPTIONS\n",
            "FOO threw exception: 25 \n",
        ),
    ],
    indirect=["test_input", "expected"],
)
def test_advanced(cmd: partial, test_input: str, expected: str):
    assert cmd(input=test_input).stdout == expected


def test_syscalls(mapping: Mapping[str, str], cmd: partial):
    values = {key: value for key, value in mapping.items() if key.startswith("SYS_")}
    test_input = f"{mapping['forth']} {' '.join(values)} .S\n"
    expected = " ".join(reversed(values.values())) + " "
    assert cmd(input=test_input).stdout == expected


def test_fnctl(mapping: Mapping[str, str], cmd: partial):
    values = {key: value for key, value in mapping.items() if key.startswith("O_")}
    test_input = f"{mapping['forth']} {' '.join(values)} .S\n"
    expected = " ".join(reversed(values.values())) + " "
    assert cmd(input=test_input).stdout == expected


def test_argv(mapping: dict, cmd: partial):
    assert (
        cmd(
            input="{forth}0 ARGV TELL SPACE 2 ARGV TELL\n".format_map(mapping),
        ).stdout
        == " ".join(cmd.keywords["args"][i] for i in (0, 2))
    )
