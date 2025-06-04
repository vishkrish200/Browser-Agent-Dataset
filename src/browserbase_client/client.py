import httpx
import logging
from typing import List, Dict, Any, Optional, Union
import asyncio # Added for sleep

# Import tenacity for retry logic
# from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .auth import ApiKeyAuth, AuthStrategy
from .exceptions import BrowserbaseAPIError
from .types import CreateSessionKwargs
from . import config

logger = logging.getLogger(__name__)

class BrowserbaseClient:
    """Client for interacting with the Browserbase API."""
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        base_url: Optional[str] = None, 
        timeout_seconds: Optional[Union[float, int]] = None,
        max_retries: Optional[int] = None,
        retry_delay_seconds: Optional[Union[float, int]] = None,
        max_backoff_delay_seconds: Optional[Union[float, int]] = None
    ):
        """
        Initialize the BrowserbaseClient.

        Configuration is resolved in the following order of precedence:
        1. Direct parameters passed to the constructor.
        2. Environment variables (e.g., BROWSERBASE_API_KEY).
        3. Default values defined in the library.

        Args:
            api_key: Your Browserbase API key. If None, attempts to load from
                     env var BROWSERBASE_API_KEY.
            base_url: The base URL for the Browserbase API. If None, attempts to load from
                      env var BROWSERBASE_BASE_URL, then uses default.
            timeout_seconds: Default timeout in seconds for HTTP requests. If None,
                             attempts to load from env var BROWSERBASE_DEFAULT_TIMEOUT_SECONDS,
                             then uses default.
            max_retries: Maximum number of retries for failed requests. If None,
                         attempts to load from env var BROWSERBASE_MAX_RETRIES, then uses default.
            retry_delay_seconds: Delay in seconds between retries. If None,
                                 attempts to load from env var BROWSERBASE_RETRY_DELAY_SECONDS,
                                 then uses default.
            max_backoff_delay_seconds: Maximum delay in seconds for exponential backoff. If None,
                                       attempts to load from env var BROWSERBASE_MAX_BACKOFF_DELAY_SECONDS,
                                       then uses default.
        Raises:
            ValueError: If API key is not provided and cannot be found in environment variables.
        """
        resolved_api_key = config.get_api_key(api_key_override=api_key)
        if not resolved_api_key:
            raise ValueError(
                "Browserbase API key not provided and not found in environment variable "
                f"{config.BROWSERBASE_API_KEY_ENV_VAR}."
            )
        
        self.auth_strategy: AuthStrategy = ApiKeyAuth(resolved_api_key)
        self.base_url = config.get_base_url(base_url_override=base_url)
        self.timeout_seconds = config.get_default_timeout_seconds(timeout_override=timeout_seconds)
        self.max_retries = config.get_max_retries(retries_override=max_retries)
        self.retry_delay_seconds = config.get_retry_delay_seconds(delay_override=retry_delay_seconds)
        self.max_backoff_delay_seconds = config.get_max_backoff_delay_seconds(delay_override=max_backoff_delay_seconds)
        
        logger.info(
            f"BrowserbaseClient initialized. Base URL: {self.base_url}, Timeout: {self.timeout_seconds}s, "
            f"Max Retries: {self.max_retries}, Retry Delay: {self.retry_delay_seconds}s, "
            f"Max Backoff Delay: {self.max_backoff_delay_seconds}s"
        )

    def _get_headers(self) -> Dict[str, str]:
        """Internal method to get all necessary headers for a request."""
        headers = {"Content-Type": "application/json"}
        auth_headers = self.auth_strategy.get_auth_headers()
        headers.update(auth_headers)
        return headers

    async def _request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Makes an asynchronous HTTP request to the Browserbase API with retry logic."""
        headers = self._get_headers()
        url = endpoint  # endpoint is already the full URL in current methods
        request_details = f"Request: {method} {url}"
        if params:
            request_details += f" Params: {params}"
        if payload:
            # Avoid logging full payload if it's large or sensitive; consider truncation or selective logging
            request_details += f" Payload: {str(payload)[:200]}..." # Truncate payload logging
        logger.debug(request_details)

        attempts = 0
        # MAX_ATTEMPTS will use self.max_retries
        # RETRY_DELAY will use self.retry_delay_seconds as a base for exponential backoff
        # MAX_EXPONENTIAL_BACKOFF_DELAY_SECONDS = 60.0 # Cap for exponential backoff -- Will use self.max_backoff_delay_seconds

        while attempts < self.max_retries:
            try:
                logger.debug(f"Attempt {attempts + 1}/{self.max_retries} for {method} {url}")
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.request(
                        method, url, json=payload, headers=headers, params=params
                    )
                    response.raise_for_status()  # Raises HTTPStatusError for 4xx/5xx
                    
                    # Handle cases where API might return 204 No Content or other non-JSON success
                    if response.status_code == 204:
                        logger.debug(
                            f"Response: {method} {url} - Status {response.status_code} (No Content)"
                        )
                        return {}  # Return an empty dict for No Content
                    
                    response_data = response.json()
                    logger.debug(
                        f"Response: {method} {url} - Status {response.status_code} - Data: {str(response_data)[:200]}..."
                    )
                    return response_data # Success, exit loop and method

            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"API Error on attempt {attempts + 1}/{self.max_retries}: {method} {url} - Status {e.response.status_code} - Response: {e.response.text[:200]}..."
                )
                # Retry only on 5xx server errors
                if e.response.status_code >= 500 and (attempts + 1) < self.max_retries:
                    # Calculate delay for next attempt using exponential backoff
                    # attempts is 0-indexed here, so for the first retry (attempts=0), delay is base_delay * 2^0
                    # for the second retry (attempts=1), delay is base_delay * 2^1, and so on.
                    current_delay = min(self.retry_delay_seconds * (2 ** attempts), self.max_backoff_delay_seconds)
                    attempts += 1
                    logger.info(f"Retrying in {current_delay:.2f}s... (new attempt {attempts + 1}/{self.max_retries})")
                    await asyncio.sleep(current_delay)
                    continue # To next iteration of the while loop
                else:
                    # Not a 5xx error, or max attempts reached for 5xx
                    final_attempts = attempts + 1
                    logger.error(
                        f"Final API Error after {final_attempts} attempt(s): {method} {url} - Status {e.response.status_code} - Response: {e.response.text}",
                        exc_info=True,
                    )
                    raise BrowserbaseAPIError(
                        message=f"API request failed after {final_attempts} attempt(s) with status {e.response.status_code}",
                        status_code=e.response.status_code,
                        response_content=e.response.text,
                    ) from e # This will break the loop
            
            except httpx.RequestError as e: # Includes TimeoutException, ConnectError etc.
                logger.warning(
                    f"Request Error on attempt {attempts + 1}/{self.max_retries}: {method} {url} - {e}"
                )
                if (attempts + 1) < self.max_retries:
                    # Calculate delay for next attempt using exponential backoff
                    current_delay = min(self.retry_delay_seconds * (2 ** attempts), self.max_backoff_delay_seconds)
                    attempts += 1
                    logger.info(f"Retrying in {current_delay:.2f}s... (new attempt {attempts + 1}/{self.max_retries})")
                    await asyncio.sleep(current_delay)
                    continue # To next iteration of the while loop
                else:
                    final_attempts = attempts + 1
                    logger.error(
                        f"Final Request Error after {final_attempts} attempt(s): {method} {url} - {e}",
                        exc_info=True,
                    )
                    raise BrowserbaseAPIError(
                        message=f"Request failed after {final_attempts} attempt(s): {e.__class__.__name__}"
                    ) from e # This will break the loop
        
        # This line should theoretically be unreachable if the logic above is correct,
        # as any path leading to loop exhaustion should have raised an exception.
        # Adding a safeguard, though it indicates a potential logic flaw if ever hit.
        logger.critical(f"Reached end of _request method for {method} {url} after {self.max_retries} attempts without returning or raising explicitly within the loop. This should not happen.")
        raise BrowserbaseAPIError(message=f"Max retries ({self.max_retries}) reached for {method} {url} without explicit resolution.")

    async def create_session(self, project_id: str, **kwargs: CreateSessionKwargs) -> dict:
        """
        Creates a new Browserbase session with specified configurations.

        Args:
            project_id: The ID of the project to create the session under.
            **kwargs: Additional keyword arguments for session creation.
                      Refer to Browserbase API documentation for /v1/sessions POST endpoint.
                      Key options include:
                      - browserSettings (BrowserSettingsDict)
                      - proxies (List[CustomProxyConfigDict])
                      - fingerprint (FingerprintDict)
                      - metadata (Dict[str, Any])
                      - enableNetworkLogs (bool)
                      - enableDebug (bool)

        Returns:
            A dictionary containing the API response for the created session.

        Raises:
            BrowserbaseAPIError: If the API request fails.
            ValueError: If project_id is not provided.
        """
        if not project_id:
            raise ValueError("project_id must be provided")

        logger.info(f"Creating session for project {project_id} with options: {kwargs}")
        url = f"{self.base_url.rstrip('/')}/sessions"
        payload = {"projectId": project_id, **kwargs}
        return await self._request("POST", url, payload=payload)

    async def list_sessions(
        self, status: Optional[str] = None, q: Optional[str] = None
    ) -> dict:
        """
        Lists available Browserbase sessions, with optional filtering.

        Args:
            status: Filter sessions by status (e.g., "ACTIVE", "COMPLETED").
            q: Search query for filtering sessions.

        Returns:
            A dictionary containing the list of sessions and pagination info.

        Raises:
            BrowserbaseAPIError: If the API request fails.
        """
        params = {}
        if status:
            params["status"] = status
        if q:
            params["q"] = q
        logger.info(f"Listing sessions with filters: {params}")
        url = f"{self.base_url.rstrip('/')}/sessions"
        return await self._request("GET", url, params=params)

    async def get_session(self, session_id: str) -> dict:
        """
        Retrieves details for a specific Browserbase session.

        Args:
            session_id: The ID of the session to retrieve.

        Returns:
            A dictionary containing the session details.

        Raises:
            BrowserbaseAPIError: If the API request fails.
            ValueError: If session_id is not provided.
        """
        if not session_id:
            raise ValueError("session_id must be provided")
        logger.info(f"Getting session details for {session_id}")
        url = f"{self.base_url.rstrip('/')}/sessions/{session_id}"
        return await self._request("GET", url)

    async def release_session(self, session_id: str, project_id: str) -> dict:
        """
        Releases an active browser session.

        Args:
            session_id: The ID of the session to release.
            project_id: The ID of the project the session belongs to.

        Returns:
            A dictionary containing the API response.

        Raises:
            BrowserbaseAPIError: If the API request fails.
            ValueError: If session_id or project_id is not provided.
        """
        if not session_id:
            raise ValueError("session_id must be provided")
        if not project_id:
            # This was missing a raise before, but if project_id is essential for the URL or payload, it should be validated.
            # Assuming for now the API needs project_id in payload for release, or it's part of a more complex URL.
            # For now, let's assume it might be used in payload or a more specific endpoint.
            pass # Or raise ValueError("project_id must be provided for releasing a session")

        logger.info(f"Releasing session {session_id} for project {project_id}")
        # The standard Browserbase API for deleting/releasing a session is DELETE /v1/sessions/{sessionId}
        # It typically doesn't require a project_id in the URL or payload for this specific action, 
        # as the session_id is globally unique or scoped by the API key.
        # However, keeping project_id in the method signature for future flexibility if our client needs it.
        url = f"{self.base_url.rstrip('/')}/sessions/{session_id}" 
        # No payload is typically needed for a DELETE release operation.
        # If project_id were needed in a payload: payload = {"projectId": project_id}
        return await self._request("DELETE", url) # Changed to DELETE based on typical REST for release

    async def get_session_live_urls(self, session_id: str) -> dict:
        """
        Retrieves the live URLs (e.g., VNC, debug) for an active browser session.

        Args:
            session_id: The ID of the session.

        Returns:
            A dictionary containing the live URLs.

        Raises:
            BrowserbaseAPIError: If the API request fails.
            ValueError: If session_id is not provided.
        """
        if not session_id:
            raise ValueError("session_id must be provided")

        logger.info(f"Getting live URLs for session {session_id}")
        url = f"{self.base_url.rstrip('/')}/sessions/{session_id}/live"
        return await self._request("GET", url)

    async def get_session_downloads(self, session_id: str) -> dict:
        """
        Retrieves a list of files available for download from a specific session.

        Args:
            session_id: The ID of the session.

        Returns:
            A dictionary containing the list of downloadable files and their details.

        Raises:
            BrowserbaseAPIError: If the API request fails.
            ValueError: If session_id is not provided.
        """
        if not session_id:
            raise ValueError("session_id must be provided")

        logger.info(f"Getting downloads for session {session_id}")
        url = f"{self.base_url.rstrip('/')}/sessions/{session_id}/downloads"
        return await self._request("GET", url)

    async def close(self):
        """Placeholder for closing the client if it held resources like an httpx.AsyncClient instance directly."""
        logger.info("BrowserbaseClient close called (currently no persistent client to close).")
        pass # Nothing to close yet
