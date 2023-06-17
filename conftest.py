import pytest


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        "--coverage", action="store_true", help="Use gcov to capture coverage"
    )


@pytest.fixture(scope="module")
def coverage(request: pytest.FixtureRequest):
    return request.config.getoption("--coverage")
