import pytest
import responses as responses_lib


@pytest.fixture(autouse=True)
def http_mock():
    with responses_lib.RequestsMock() as rsps:
        yield rsps
