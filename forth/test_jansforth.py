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

import pytest

TARGETS = ["jansforth", "recurse"]


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
