import functools
import os
import subprocess

import pytest


@pytest.fixture(scope="module", autouse=True)
def cmd(target: str = "4th.js"):
    subprocess.run(["make", target], cwd="forth", check=True)
    yield functools.partial(
        subprocess.run,
        args=["node", target],
        capture_output=True,
        check=True,
        cwd="forth",
        env={"PATH": str(os.getenv("PATH"))},
        text=True,
    )
    subprocess.run(["make", "clean"], cwd="forth", check=True)


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ("65 EMIT\n", "A\n"),
        ("777 65 EMIT\n", "A\n"),
        ("32 DUP + 1+ EMIT\n", "A\n"),
        ("16 DUP 2DUP + + + 1+ EMIT\n", "A\n"),
        ("8 DUP * 1+ EMIT\n", "A\n"),
        ("CHAR A EMIT\n", "A\n"),
        (": SLOW WORD FIND >CFA EXECUTE ; 65 SLOW EMIT\n", "A\n"),
        (
            f"{int.from_bytes('65'.encode(), 'little'):d} DSP@ 2 NUMBER DROP EMIT\n",
            "A\n",
        ),
        ("64 >R RSP@ 1 TELL RDROP\n", "@\n"),
        ("65 DSP@ RSP@ SWAP C@C! RSP@ 1 TELL\n", "A\n"),
        ("64 >R 1 RSP@ +! RSP@ 1 TELL\n", "A\n"),
        (
            """
: <BUILDS WORD CREATE DODOES , 0 , ;
: DOES> R> LATEST @ >DFA ! ;
: CONST <BUILDS , DOES> @ ;

65 CONST FOO
FOO EMIT
""",
            "A\n",
        ),
    ],
)
def test_has_title(cmd: functools.partial, test_input: str, expected: str):
    # Expect a title "to contain" a substring.
    assert cmd(input=test_input).stdout == expected
