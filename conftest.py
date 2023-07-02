import pytest


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        "--target",
        choices=["4th", "c4th", "4th.32"],
        default="4th",
        help="Pick a target to test",
    )


@pytest.fixture(scope="module")
def target(request: pytest.FixtureRequest):
    return request.config.getoption("--target")
