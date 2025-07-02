import pytest


collect_ignore = [
    "aoc2024",
    "forth/combination.py",
    "forth/forth.py",
    "fun/api_from.py",
    "fun/assemble.py",
    "fun/store_sa.py",
    "progress/__init__.py",
]

def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        "--target",
        choices=["4th", "4th.gcov", "4th.32", "4th.ll", "5th.ll"],
        default="4th",
        help="Pick a target to test",
    )


@pytest.fixture(scope="module")
def target(request: pytest.FixtureRequest):
    return request.config.getoption("--target")
