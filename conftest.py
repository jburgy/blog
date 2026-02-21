import os
import re
import subprocess

import pytest  # pyright: ignore[reportMissingImports]


collect_ignore = [
    "aoc2024",
    "aoc2025",
    "emsdk-cache",
    "forth/combination.py",
    "forth/forth.py",
    "forth/test_4th_wasm.py",
    "fun/api_from.py",
    "fun/assemble.py",
    "fun/awslayer.py",
    "fun/store_sa.py",
    "progress/__init__.py",
    "notebooks/dataframe_formatting.py",
    "notebooks/nbody.py",
]


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    scenarios: str | None = getattr(metafunc.cls, "scenarios", None)
    if scenarios:
        target = {
            "test_4th": "4th",
            "test_5th": "5th.ll",
        }[metafunc.function.__name__]
        scenarios = scenarios.format(
            argv0=f"./{target}",
            uid=os.getuid(),
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
                re.findall(r"(?<=\\ )(.+)$", scenarios, re.M),
            ),
        )
