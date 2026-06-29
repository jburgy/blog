import os
import platform
import re
import subprocess

import pytest  # pyright: ignore[reportMissingImports]


collect_ignore = [
    ".venv",
    "aoc2024",
    "aoc2025",
    "assets",
    "build",
    "emsdk-cache",
    "foo",
    "forth/combination.py",
    "forth/forth.py",
    "forth/jansforth.py",
    "forth/node_modules",
    "forth/test_4th_wasm.py",
    "fun/api_from.py",
    "fun/assemble.py",
    "fun/awslayer.py",
    "fun/challenge.py",
    "fun/html_elements.py",
    "fun/oecd.py",
    "fun/nbody.py",
    "fun/store_sa.py",
    "jonesforth",
    "linprog",
    "lisp",
    "node_modules",
    "notebooks",
    "progress",
    "TinyBasic",
    "xterm-pty",
]


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    scenarios: str | None = getattr(metafunc.cls, "scenarios", None)
    if scenarios:
        target = {
            "test_4th": "4th",
            "test_5th": "5th.ll",
            "test_6th": "zig-out/bin/6th",
        }[metafunc.function.__name__]
        scenarios = scenarios.format(
            argv0=f"./{target}",
            uid=os.getuid(),
            getuid=24 if platform.system() == "Darwin" else 102,
            setuid=23 if platform.system() == "Darwin" else 105,
            access=33 if platform.system() == "Darwin" else 21,
        )
        subprocess.run(["make", target], cwd="forth", check=True)
        cp = subprocess.run(
            [f"./{target}"],
            cwd="forth/",
            env={"SHELL": "/bin/bash"},
            capture_output=True,
            check=True,
            input=scenarios,
            text=True,
        )
        subprocess.run(["rm", target], cwd="forth", check=True)
        metafunc.parametrize(
            ["actual", "expected"],
            zip(
                cp.stdout.splitlines(),
                re.findall(r"(?<=\\ )(.+)$", scenarios, flags=re.M),
            ),
            ids=re.findall(r"^(.+?)(?= \\ )", scenarios, flags=re.M),
        )
