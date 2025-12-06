import pytest  # pyright: ignore[reportMissingImports]


collect_ignore = [
    "aoc2024",
    "aoc2025",
    "emsdk-cache",
    "forth/combination.py",
    "forth/forth.py",
    "fun/api_from.py",
    "fun/assemble.py",
    "fun/awslayer.py",
    "fun/store_sa.py",
    "progress/__init__.py",
    "notebooks/dataframe_formatting.py",
    "notebooks/nbody.py",
]

def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--target",
        choices=[
            "", "4th", "4th.gcov", "4th.32", "4th.ll", "5th.ll", "zig-out/bin/6th"
        ],
        default="",
        help="Pick a target to test",
    )


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "target" in metafunc.fixturenames:
        target = metafunc.config.getoption("target")
        metafunc.parametrize(
            "target",
            [target] if target else ["4th", "5th.ll", "zig-out/bin/6th"],
            scope="module"
        )
