import pytest
from respx import MockRouter
from unittest import mock

from browserbase_client import BrowserbaseClient

@pytest.fixture
def respx_mock() -> MockRouter:
    """Provides a RESPX mock router for mocking HTTPX requests."""
    # assert_all_called=False because not all defined routes might be used in every single test function.
    # Tests that need to assert all its own routes were called can do so on the router instance.
    router = MockRouter(assert_all_called=False)
    with router:
        yield router 

@pytest.fixture
def mock_client_env(monkeypatch):
    """Fixture to mock environment variables for client tests."""
    monkeypatch.setenv("BROWSERBASE_API_KEY", "test_fixture_api_key")
    # Clear other potentially interfering env vars if necessary
    monkeypatch.delenv("BROWSERBASE_BASE_URL", raising=False)
    monkeypatch.delenv("BROWSERBASE_DEFAULT_TIMEOUT_SECONDS", raising=False)
    return monkeypatch # Return monkeypatch for potential further use in tests

@pytest.fixture
def client(mock_client_env):
    """Fixture to provide a BrowserbaseClient instance with mocked env."""
    # mock_client_env ensures BROWSERBASE_API_KEY is set
    return BrowserbaseClient() 

@pytest.fixture
def client_with_explicit_key():
    """Fixture to provide a BrowserbaseClient instance with an explicit API key."""
    return BrowserbaseClient(api_key="explicit_test_key")

@pytest.fixture
def mock_httpx_client():
    """Fixture to mock httpx.AsyncClient for deeper client method testing."""
    with mock.patch("httpx.AsyncClient", autospec=True) as mock_async_client_constructor:
        mock_instance = mock.AsyncMock() # This will be the instance of AsyncClient
        mock_async_client_constructor.return_value = mock_instance
        yield mock_instance # Yield the mock instance for tests to use 