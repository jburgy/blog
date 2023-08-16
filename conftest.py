from typing import Collection

import pytest


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        "--target",
        choices=["4th", "4th.gcov", "4th.32", "4th.ll"],
        default="4th",
        help="Pick a target to test",
    )


@pytest.fixture(scope="module")
def target(request: pytest.FixtureRequest):
    return request.config.getoption("--target")


def pytest_configure(config: pytest.Config):
    config.addinivalue_line("markers", "start: requires _start instead of main")


def pytest_collection_modifyitems(
    config: pytest.Config, items: Collection[pytest.Item]
):
    if config.getoption("--target") != "4th.gcov":
        return
    skip_start = pytest.mark.skip(reason="gcov requires main instead of _start")
    for item in items:
        if "start" in item.keywords:
            item.add_marker(skip_start)
