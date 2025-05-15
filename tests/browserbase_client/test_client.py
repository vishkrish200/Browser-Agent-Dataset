import pytest
import httpx
from unittest import mock
import logging
from respx import MockRouter as RESPXMock

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
    assert response == {}

@pytest.mark.asyncio
async def test_release_session_not_found(client, respx_mock):
    """Test release session not found."""
    session_id = "sess_not_found"
    project_id_for_release = "proj_release_test"
    expected_payload = {"projectId": project_id_for_release, "status": "REQUEST_RELEASE"}

    def check_request_content(request):
        import json
        assert json.loads(request.content) == expected_payload
        return httpx.Response(200, json={"sessionId": session_id})

    respx_mock.post(f"{client.base_url}/sessions/{session_id}").mock(side_effect=check_request_content)
    
    with pytest.raises(BrowserbaseAPIError) as excinfo:
        await client.release_session(session_id, project_id_for_release)
    assert excinfo.value.status_code == 404

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
    assert f"Response: GET {client.base_url}/sessions/{session_id} - Status 200" in caplog.text
    caplog.clear()

    # Error request
    error_session_id = "sess_log_error"
    respx_mock.get(f"{client.base_url}/sessions/{error_session_id}").mock(return_value=httpx.Response(500, json={"error": "Server Error"}))
    with pytest.raises(BrowserbaseAPIError):
        await client.get_session(error_session_id)
    
    assert f"API Error: GET {client.base_url}/sessions/{error_session_id}" in caplog.text
    assert "Status 500" in caplog.text
    assert "Server Error" in caplog.text

# New tests for get_session_live_urls
@pytest.mark.asyncio
async def test_get_session_live_urls_success(client: BrowserbaseClient, respx_mock: RESPXMock):
    """Test successful retrieval of session live URLs."""
    session_id = "test_session_live_id"
    live_urls_payload = {"vnc": "wss://example.com/vnc", "debug": "wss://example.com/debug"}
    expected_url = f"{client.base_url}/sessions/{session_id}/live"

    respx_mock.get(expected_url).respond(status_code=200, json=live_urls_payload)

    response = await client.get_session_live_urls(session_id)
    assert response == live_urls_payload
    assert len(respx_mock.calls) == 1
    assert respx_mock.calls[0].request.url == expected_url

@pytest.mark.asyncio
async def test_get_session_live_urls_not_found(client: BrowserbaseClient, respx_mock: RESPXMock):
    """Test get_session_live_urls when session is not found (404)."""
    session_id = "non_existent_session_id"
    expected_url = f"{client.base_url}/sessions/{session_id}/live"
    error_response = {"message": "Session not found"}

    respx_mock.get(expected_url).respond(status_code=404, json=error_response)

    with pytest.raises(BrowserbaseAPIError) as excinfo:
        await client.get_session_live_urls(session_id)
    
    assert excinfo.value.status_code == 404
    assert error_response["message"] in str(excinfo.value.response_content)

@pytest.mark.asyncio
async def test_get_session_live_urls_server_error(client: BrowserbaseClient, respx_mock: RESPXMock):
    """Test get_session_live_urls with a server error (500)."""
    session_id = "session_server_error_id"
    expected_url = f"{client.base_url}/sessions/{session_id}/live"
    error_response = {"message": "Internal Server Error"}

    respx_mock.get(expected_url).respond(status_code=500, json=error_response)

    with pytest.raises(BrowserbaseAPIError) as excinfo:
        await client.get_session_live_urls(session_id)

    assert excinfo.value.status_code == 500
    assert error_response["message"] in str(excinfo.value.response_content)

@pytest.mark.asyncio
async def test_get_session_live_urls_no_session_id(client: BrowserbaseClient):
    """Test get_session_live_urls without providing a session_id."""
    with pytest.raises(ValueError, match="session_id must be provided"):
        await client.get_session_live_urls("")

# Tests for get_session_downloads
@pytest.mark.asyncio
async def test_get_session_downloads_success(client: BrowserbaseClient, respx_mock: RESPXMock):
    """Test successful retrieval of session downloads."""
    session_id = "test_session_downloads_id"
    downloads_payload = [
        {"fileName": "file1.zip", "size": 1024, "url": "https://example.com/file1.zip"},
        {"fileName": "image.png", "size": 512, "url": "https://example.com/image.png"}
    ]
    expected_url = f"{client.base_url}/sessions/{session_id}/downloads"

    respx_mock.get(expected_url).respond(status_code=200, json=downloads_payload)

    response = await client.get_session_downloads(session_id)
    assert response == downloads_payload
    assert len(respx_mock.calls) == 1
    assert respx_mock.calls[0].request.url == expected_url

@pytest.mark.asyncio
async def test_get_session_downloads_not_found(client: BrowserbaseClient, respx_mock: RESPXMock):
    """Test get_session_downloads when session is not found (404)."""
    session_id = "non_existent_session_id_downloads"
    expected_url = f"{client.base_url}/sessions/{session_id}/downloads"
    error_response = {"message": "Session not found or no downloads available"}

    respx_mock.get(expected_url).respond(status_code=404, json=error_response)

    with pytest.raises(BrowserbaseAPIError) as excinfo:
        await client.get_session_downloads(session_id)
    
    assert excinfo.value.status_code == 404
    assert error_response["message"] in str(excinfo.value.response_content)

@pytest.mark.asyncio
async def test_get_session_downloads_server_error(client: BrowserbaseClient, respx_mock: RESPXMock):
    """Test get_session_downloads with a server error (500)."""
    session_id = "session_server_error_id_downloads"
    expected_url = f"{client.base_url}/sessions/{session_id}/downloads"
    error_response = {"message": "Internal Server Error"}

    respx_mock.get(expected_url).respond(status_code=500, json=error_response)

    with pytest.raises(BrowserbaseAPIError) as excinfo:
        await client.get_session_downloads(session_id)

    assert excinfo.value.status_code == 500
    assert error_response["message"] in str(excinfo.value.response_content)

@pytest.mark.asyncio
async def test_get_session_downloads_no_session_id(client: BrowserbaseClient):
    """Test get_session_downloads without providing a session_id."""
    with pytest.raises(ValueError, match="session_id must be provided"):
        await client.get_session_downloads("")

# Tests for _request retry mechanism

@pytest.mark.asyncio
@mock.patch("asyncio.sleep", return_value=None) # Mock asyncio.sleep
async def test_request_successful_no_retry(mock_sleep, client: BrowserbaseClient, respx_mock: RESPXMock, caplog: pytest.LogCaptureFixture):
    """Test that a successful request does not trigger any retries."""
    caplog.set_level(logging.DEBUG, logger="browserbase_client.client")
    session_id = "sess_no_retry"
    expected_url = f"{client.base_url}/sessions/{session_id}"
    mock_response_data = {"sessionId": session_id, "status": "ACTIVE"}

    respx_mock.get(expected_url).respond(status_code=200, json=mock_response_data)

    response = await client.get_session(session_id)
    assert response == mock_response_data
    mock_sleep.assert_not_called() # Ensure sleep was not called
    assert f"Attempt 1/{client.max_retries}" in caplog.text
    assert "Retrying in" not in caplog.text

@pytest.mark.asyncio
@mock.patch("asyncio.sleep", return_value=None) # Mock asyncio.sleep
async def test_retry_on_5xx_then_success(mock_sleep, client: BrowserbaseClient, respx_mock: RESPXMock, caplog: pytest.LogCaptureFixture):
    """Test retry on a 500 error, then success on the next attempt."""
    caplog.set_level(logging.INFO, logger="browserbase_client.client") # INFO to see retry messages
    session_id = "sess_5xx_retry"
    expected_url = f"{client.base_url}/sessions/{session_id}"
    success_response_data = {"sessionId": session_id, "status": "ACTIVE"}

    # Simulate 500 error then 200 success
    respx_mock.get(expected_url).mock(
        side_effect=[
            httpx.Response(500, json={"error": "Internal Server Error"}),
            httpx.Response(200, json=success_response_data),
        ]
    )

    response = await client.get_session(session_id)
    assert response == success_response_data

    # Check that sleep was called once with the base delay (2**0 * base_delay)
    mock_sleep.assert_called_once_with(client.retry_delay_seconds * (2**0))
    assert f"Attempt 1/{client.max_retries}" in caplog.text
    assert f"API Error on attempt 1/{client.max_retries}" in caplog.text
    assert f"Retrying in {client.retry_delay_seconds:.2f}s... (new attempt 2/{client.max_retries})" in caplog.text
    assert f"Attempt 2/{client.max_retries}" in caplog.text # Should show attempt 2
    assert f"Response: GET {expected_url} - Status 200" in caplog.text

@pytest.mark.asyncio
@mock.patch("asyncio.sleep", return_value=None) # Mock asyncio.sleep
async def test_no_retry_on_4xx_client_error(mock_sleep, client: BrowserbaseClient, respx_mock: RESPXMock, caplog: pytest.LogCaptureFixture):
    """Test that a 4xx client error does not trigger retries."""
    caplog.set_level(logging.DEBUG, logger="browserbase_client.client")
    session_id = "sess_4xx_no_retry"
    expected_url = f"{client.base_url}/sessions/{session_id}"
    error_response_data = {"error": "Not Found"}

    respx_mock.get(expected_url).respond(status_code=404, json=error_response_data)

    with pytest.raises(BrowserbaseAPIError) as excinfo:
        await client.get_session(session_id)
    
    assert excinfo.value.status_code == 404
    mock_sleep.assert_not_called() # Ensure sleep was not called
    assert f"Attempt 1/{client.max_retries}" in caplog.text
    assert "Retrying in" not in caplog.text
    assert f"Final API Error after 1 attempt(s)" in caplog.text

@pytest.mark.asyncio
@mock.patch("asyncio.sleep", return_value=None)
async def test_retry_on_request_error_then_success(mock_sleep, client: BrowserbaseClient, respx_mock: RESPXMock, caplog: pytest.LogCaptureFixture):
    """Test retry on httpx.RequestError (e.g., ConnectError), then success."""
    caplog.set_level(logging.INFO, logger="browserbase_client.client")
    session_id = "sess_req_err_retry"
    expected_url = f"{client.base_url}/sessions/{session_id}"
    success_response_data = {"sessionId": session_id, "status": "ACTIVE"}

    respx_mock.get(expected_url).mock(
        side_effect=[
            httpx.ConnectError("Simulated connection failed"),
            httpx.Response(200, json=success_response_data),
        ]
    )

    response = await client.get_session(session_id)
    assert response == success_response_data
    mock_sleep.assert_called_once_with(client.retry_delay_seconds * (2**0))
    assert f"Request Error on attempt 1/{client.max_retries}" in caplog.text
    assert f"Retrying in {client.retry_delay_seconds:.2f}s... (new attempt 2/{client.max_retries})" in caplog.text

@pytest.mark.asyncio
@mock.patch("asyncio.sleep", return_value=None)
async def test_retry_exhaustion_for_5xx_error(mock_sleep, client_low_retries: BrowserbaseClient, respx_mock: RESPXMock, caplog: pytest.LogCaptureFixture):
    """Test that retries are exhausted for persistent 5xx errors."""
    # Using client_low_retries fixture (max_retries=1 by default in conftest or override for this test)
    # If client_low_retries not specifically configured for 1 retry, this will use default client's max_retries
    # For this test to be meaningful, client_low_retries should have max_retries=1 or 2.
    # We will assume client_low_retries is configured for client.max_retries = 1 for this test case to be simple.
    # If not, we can create a new client with max_retries=1 for this test.
    
    # Let's create a client with specific max_retries for this test to be explicit
    client_one_retry = BrowserbaseClient(api_key="test_key_one_retry", max_retries=1, retry_delay_seconds=0.1)
    caplog.set_level(logging.INFO, logger="browserbase_client.client")
    session_id = "sess_exhaust_5xx"
    expected_url = f"{client_one_retry.base_url}/sessions/{session_id}"

    respx_mock.get(expected_url).respond(status_code=503, json={"error": "Service Unavailable"})

    with pytest.raises(BrowserbaseAPIError) as excinfo:
        await client_one_retry.get_session(session_id)
    
    assert excinfo.value.status_code == 503
    # With max_retries=1, there should be 1 attempt, and 0 calls to sleep.
    mock_sleep.assert_not_called()
    assert f"API Error on attempt 1/{client_one_retry.max_retries}" in caplog.text
    assert "Retrying in" not in caplog.text # No retry should happen as max_retries is 1
    assert f"Final API Error after {client_one_retry.max_retries} attempt(s)" in caplog.text

@pytest.mark.asyncio
@mock.patch("asyncio.sleep", return_value=None)
async def test_retry_exhaustion_for_request_error(mock_sleep, client_low_retries: BrowserbaseClient, respx_mock: RESPXMock, caplog: pytest.LogCaptureFixture):
    """Test that retries are exhausted for persistent httpx.RequestError."""
    client_one_retry = BrowserbaseClient(api_key="test_key_req_exh", max_retries=1, retry_delay_seconds=0.1)
    caplog.set_level(logging.INFO, logger="browserbase_client.client")
    session_id = "sess_exhaust_req_err"
    expected_url = f"{client_one_retry.base_url}/sessions/{session_id}"

    respx_mock.get(expected_url).mock(side_effect=httpx.TimeoutException("Simulated timeout"))

    with pytest.raises(BrowserbaseAPIError) as excinfo:
        await client_one_retry.get_session(session_id)
    
    assert excinfo.value.status_code is None # No HTTP status for this type of error
    assert "TimeoutException" in str(excinfo.value.message) 
    mock_sleep.assert_not_called() # max_retries=1 means no actual retry sleep
    assert f"Request Error on attempt 1/{client_one_retry.max_retries}" in caplog.text
    assert "Retrying in" not in caplog.text
    assert f"Final Request Error after {client_one_retry.max_retries} attempt(s)" in caplog.text

@pytest.mark.asyncio
@mock.patch("asyncio.sleep", return_value=None)
async def test_exponential_backoff_multiple_retries(mock_sleep, client: BrowserbaseClient, respx_mock: RESPXMock, caplog: pytest.LogCaptureFixture):
    """Test exponential backoff calculation over multiple retries."""
    # Ensure client used for this test has at least 3 retries
    client_three_retries = BrowserbaseClient(api_key="test_key_exp_backoff", max_retries=3, retry_delay_seconds=0.1)
    caplog.set_level(logging.INFO, logger="browserbase_client.client")
    session_id = "sess_exp_backoff"
    expected_url = f"{client_three_retries.base_url}/sessions/{session_id}"
    success_response_data = {"sessionId": session_id, "status": "ACTIVE"}

    respx_mock.get(expected_url).mock(
        side_effect=[
            httpx.Response(500, json={"error": "Server Error 1"}),
            httpx.Response(500, json={"error": "Server Error 2"}),
            httpx.Response(200, json=success_response_data), # Success on 3rd attempt (after 2 retries)
        ]
    )

    response = await client_three_retries.get_session(session_id)
    assert response == success_response_data

    expected_delays = [
        client_three_retries.retry_delay_seconds * (2**0), # Delay after 1st attempt failure
        client_three_retries.retry_delay_seconds * (2**1)  # Delay after 2nd attempt failure
    ]
    # Check that sleep was called with the correct sequence of delays
    assert mock_sleep.call_count == 2
    assert mock_sleep.call_args_list[0] == mock.call(expected_delays[0])
    assert mock_sleep.call_args_list[1] == mock.call(expected_delays[1])

    assert f"Retrying in {expected_delays[0]:.2f}s... (new attempt 2/{client_three_retries.max_retries})" in caplog.text
    assert f"Retrying in {expected_delays[1]:.2f}s... (new attempt 3/{client_three_retries.max_retries})" in caplog.text

@pytest.mark.asyncio
async def test_release_session_failure_server_error(client: BrowserbaseClient, respx_mock: RESPXMock, caplog: pytest.LogCaptureFixture):
    """Test release_session with a server error (500)."""
    session_id = "sess_server_error"
    project_id_for_release = "proj_release_test"
    error_response = {"message": "Internal Server Error"}

    def check_request_content(request):
        import json
        assert json.loads(request.content) == {"projectId": project_id_for_release, "status": "REQUEST_RELEASE"}
        return httpx.Response(500, json=error_response)

    respx_mock.post(f"{client.base_url}/sessions/{session_id}").mock(side_effect=check_request_content)
    
    with pytest.raises(BrowserbaseAPIError) as excinfo:
        await client.release_session(session_id, project_id_for_release)
    
    assert excinfo.value.status_code == 500
    assert error_response["message"] in str(excinfo.value.response_content)
    assert f"API request failed: POST {client.base_url}/sessions/{session_id}" in caplog.text
    assert "Status: 500" in caplog.text
    assert "Internal Server Error" in caplog.text 