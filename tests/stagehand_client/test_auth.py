"""Tests for stagehand_client.auth"""

import pytest
from stagehand_client.auth import ApiKeyAuth, AuthStrategy

def test_api_key_auth_instantiation_valid():
    """Test ApiKeyAuth instantiation with valid parameters."""
    api_key = "test_api_key"
    auth = ApiKeyAuth(api_key=api_key)
    assert auth.api_key == api_key
    assert auth.header_name == "X-Stagehand-Api-Key"

def test_api_key_auth_instantiation_custom_header():
    """Test ApiKeyAuth instantiation with a custom header name."""
    api_key = "test_api_key"
    custom_header = "X-Custom-Auth"
    auth = ApiKeyAuth(api_key=api_key, header_name=custom_header)
    assert auth.api_key == api_key
    assert auth.header_name == custom_header

@pytest.mark.parametrize(
    "invalid_key, error_message",
    [
        (None, "API key must be a non-empty string."),
        ("", "API key must be a non-empty string."),
        (123, "API key must be a non-empty string."),
    ],
)
def test_api_key_auth_instantiation_invalid_key(invalid_key, error_message):
    """Test ApiKeyAuth instantiation with invalid API keys."""
    with pytest.raises(ValueError, match=error_message):
        ApiKeyAuth(api_key=invalid_key)

@pytest.mark.parametrize(
    "invalid_header, error_message",
    [
        (None, "Header name must be a non-empty string."),
        ("", "Header name must be a non-empty string."),
        (123, "Header name must be a non-empty string."),
    ],
)
def test_api_key_auth_instantiation_invalid_header_name(invalid_header, error_message):
    """Test ApiKeyAuth instantiation with invalid header names."""
    with pytest.raises(ValueError, match=error_message):
        ApiKeyAuth(api_key="valid_key", header_name=invalid_header)

def test_api_key_auth_get_auth_headers():
    """Test the get_auth_headers method of ApiKeyAuth."""
    api_key = "test_api_key_value"
    auth = ApiKeyAuth(api_key=api_key)
    expected_headers = {"X-Stagehand-Api-Key": api_key}
    assert auth.get_auth_headers() == expected_headers

def test_api_key_auth_get_auth_headers_custom_header():
    """Test get_auth_headers with a custom header name."""
    api_key = "test_api_key_value"
    custom_header = "Authorization"
    auth = ApiKeyAuth(api_key=api_key, header_name=custom_header)
    expected_headers = {custom_header: api_key}
    assert auth.get_auth_headers() == expected_headers

# Test AuthStrategy ABC (cannot be instantiated directly)
def test_auth_strategy_is_abc():
    """Ensure AuthStrategy cannot be instantiated directly."""
    with pytest.raises(TypeError):
        AuthStrategy() # type: ignore 