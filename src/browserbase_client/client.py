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
        timeout_seconds: Optional[Union[float, int]] = None
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
        
        logger.info(
            f"BrowserbaseClient initialized. Base URL: {self.base_url}, Timeout: {self.timeout_seconds}s"
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
        """Makes an asynchronous HTTP request to the Browserbase API."""
        headers = self._get_headers()
        url = endpoint  # endpoint is already the full URL in current methods
        request_details = f"Request: {method} {url}"
        if params:
            request_details += f" Params: {params}"
        if payload:
            # Avoid logging full payload if it's large or sensitive; consider truncation or selective logging
            request_details += f" Payload: {payload}"
        logger.debug(request_details)

        try:
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
                return response_data
        except httpx.HTTPStatusError as e:
            logger.error(
                f"API Error: {method} {url} - Status {e.response.status_code} - Response: {e.response.text}",
                exc_info=True,
            )
            raise BrowserbaseAPIError(
                message=f"API request failed: {e.response.status_code}",
                status_code=e.response.status_code,
                response_content=e.response.text,
            ) from e
        except httpx.RequestError as e:
            logger.error(f"Request Error: {method} {url} - {e}", exc_info=True)
            raise BrowserbaseAPIError(
                message=f"Request failed: {e.__class__.__name__}"
            ) from e

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
        url = f"{self.base_url}/sessions"
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
        url = f"{self.base_url}/sessions"
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
        url = f"{self.base_url}/sessions/{session_id}"
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
            raise ValueError("project_id must be provided")

        logger.info(f"Releasing session {session_id} for project {project_id}")
        url = f"{self.base_url}/sessions/{session_id}"
        payload = {"status": "REQUEST_RELEASE", "projectId": project_id}
        return await self._request("POST", url, payload=payload)

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
        url = f"{self.base_url}/sessions/{session_id}/live"
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
        url = f"{self.base_url}/sessions/{session_id}/downloads"
        return await self._request("GET", url)

    async def close(self):
        """Placeholder for closing the client if it held resources like an httpx.AsyncClient instance directly."""
        logger.info("BrowserbaseClient close called (currently no persistent client to close).")
        pass # Nothing to close yet
