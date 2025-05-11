import pytest

from browserbase_client import auth


def test_api_key_auth_initialization():
    """Test ApiKeyAuth class initialization."""
    api_key = "test_key_123"
    api_auth = auth.ApiKeyAuth(api_key)
    assert api_auth.api_key == api_key

def test_api_key_auth_get_auth_headers():
    """Test ApiKeyAuth header generation."""
    api_key = "test_key_456"
    api_auth = auth.ApiKeyAuth(api_key)
    headers = api_auth.get_auth_headers()
    assert headers == {"x-bb-api-key": api_key}

def test_api_key_auth_empty_key():
    """Test ApiKeyAuth with an empty API key raises ValueError."""
    with pytest.raises(ValueError, match="API key must be a non-empty string."):
        auth.ApiKeyAuth("")

# Placeholder for more advanced auth strategy tests if they were implemented
# class MockAuthStrategy(auth.AuthStrategy):
#     def get_auth_headers(self) -> dict:
#         return {"X-Mock-Header": "mock_value"}
#
# def test_custom_auth_strategy():
#     strategy = MockAuthStrategy()
#     assert strategy.get_auth_headers() == {"X-Mock-Header": "mock_value"} 