import pytest
import httpx
from unittest import mock
import logging

from browserbase_client import BrowserbaseClient, BrowserbaseAPIError, config
from browserbase_client.types import (
    CreateSessionKwargs, ViewportDict, FingerprintDict, BrowserSettingsDict
)

# Basic Initialization Tests (using fixtures from conftest.py)

def test_client_initialization_with_env_key(client, mock_client_env):
    """Test client initialization using API key from environment."""
    assert client.auth_strategy.api_key == "test_fixture_api_key"
    assert client.base_url == config.DEFAULT_BASE_URL
    assert client.timeout_seconds == config.DEFAULT_TIMEOUT_SECONDS

def test_client_initialization_with_explicit_key(client_with_explicit_key):
    """Test client initialization with an explicit API key."""
    assert client_with_explicit_key.auth_strategy.api_key == "explicit_test_key"

def test_client_initialization_missing_api_key(monkeypatch):
    """Test client initialization raises ValueError if API key is missing."""
    monkeypatch.delenv(config.BROWSERBASE_API_KEY_ENV_VAR, raising=False)
    with pytest.raises(ValueError, match=f"Browserbase API key not provided and not found in environment variable {config.BROWSERBASE_API_KEY_ENV_VAR}."):
        BrowserbaseClient()

def test_client_initialization_custom_params():
    """Test client initialization with custom base_url and timeout."""
    client_custom = BrowserbaseClient(
        api_key="custom_key",
        base_url="https://custom.example.com",
        timeout_seconds=45.0
    )
    assert client_custom.auth_strategy.api_key == "custom_key"
    assert client_custom.base_url == "https://custom.example.com"
    assert client_custom.timeout_seconds == 45.0

# API Method Tests (using respx for mocking HTTP requests)

@pytest.mark.asyncio
async def test_create_session_success(client, respx_mock):
    """Test successful session creation."""
    mock_response_data = {"sessionId": "sess_123", "status": "CREATED"}
    
    session_params_kwargs: CreateSessionKwargs = {
        "browserSettings": {
            "fingerprint": {"platform": "windows"},
            "viewport": {"width": 1920, "height": 1080}
        }
    }
    project_id = "proj_abc"
    full_payload_for_mock = {"projectId": project_id, **session_params_kwargs}

    respx_mock.post(f"{client.base_url}/sessions").mock(return_value=httpx.Response(201, json=mock_response_data))

    response = await client.create_session(project_id, **session_params_kwargs)
    assert response == mock_response_data
    
    assert len(respx_mock.calls) == 1
    request_payload_bytes = respx_mock.calls.last.request.content
    import json
    assert json.loads(request_payload_bytes) == full_payload_for_mock

@pytest.mark.asyncio
async def test_create_session_api_error(client, respx_mock):
    """Test session creation API error."""
    respx_mock.post(f"{client.base_url}/sessions").mock(return_value=httpx.Response(400, json={"error": "Bad Request"}))
    with pytest.raises(BrowserbaseAPIError) as excinfo:
        await client.create_session("proj_xyz") # Passing project_id directly
    assert excinfo.value.status_code == 400
    assert "Bad Request" in str(excinfo.value)

@pytest.mark.asyncio
async def test_list_sessions_success(client, respx_mock):
    """Test successful listing of sessions."""
    mock_response_data = [{"sessionId": "sess_123"}, {"sessionId": "sess_456"}]
    respx_mock.get(f"{client.base_url}/sessions").mock(return_value=httpx.Response(200, json=mock_response_data))
    response = await client.list_sessions()
    assert response == mock_response_data

@pytest.mark.asyncio
async def test_get_session_success(client, respx_mock):
    """Test successful retrieval of a session."""
    session_id = "sess_789"
    mock_response_data = {"sessionId": session_id, "status": "ACTIVE"}
    respx_mock.get(f"{client.base_url}/sessions/{session_id}").mock(return_value=httpx.Response(200, json=mock_response_data))
    response = await client.get_session(session_id)
    assert response == mock_response_data

@pytest.mark.asyncio
async def test_release_session_success(client, respx_mock):
    """Test successful release of a session."""
    session_id = "sess_abc"
    project_id_for_release = "proj_release_test"
    expected_payload = {"projectId": project_id_for_release, "status": "REQUEST_RELEASE"}

    def check_request_content(request):
        import json
        assert json.loads(request.content) == expected_payload
        return httpx.Response(204) # Return success response after assertion

    respx_mock.post(f"{client.base_url}/sessions/{session_id}").mock(side_effect=check_request_content)
    
    response = await client.release_session(session_id, project_id_for_release)
    assert response is None

@pytest.mark.asyncio
async def test_network_error(client, respx_mock):
    """Test handling of a network error (e.g., httpx.RequestError)."""
    respx_mock.post(f"{client.base_url}/sessions").mock(side_effect=httpx.ConnectError("Connection failed"))
    with pytest.raises(BrowserbaseAPIError) as excinfo:
        await client.create_session("proj_net_error") # Pass project_id directly
    assert excinfo.value.status_code is None # No HTTP status for network errors

# Test logging (basic check)
@pytest.mark.asyncio
async def test_logging_on_request_and_error(client, respx_mock, caplog):
    """Test that logging occurs for requests and errors."""
    caplog.set_level(logging.DEBUG, logger="browserbase_client.client") # Set log level for this test

    session_id = "sess_log_test"
    # Successful request
    respx_mock.get(f"{client.base_url}/sessions/{session_id}").mock(return_value=httpx.Response(200, json={"sessionId": session_id}))
    await client.get_session(session_id)
    
    # Check for core parts of the log messages
    assert f"Request: GET {client.base_url}/sessions/{session_id}" in caplog.text
    assert f"Response: 200" in caplog.text # Simplified check for response status
    caplog.clear()

    # Error request
    respx_mock.get(f"{client.base_url}/sessions/error_sess").mock(return_value=httpx.Response(500, json={"error": "Server Error"}))
    with pytest.raises(BrowserbaseAPIError):
        await client.get_session("error_sess")
    
    assert "API request failed: GET" in caplog.text # Check for error log intro
    assert "Status: 500" in caplog.text
    assert "Server Error" in caplog.text # Check for error content in log 