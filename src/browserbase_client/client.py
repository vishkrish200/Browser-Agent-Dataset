import httpx
import logging
from typing import List, Dict, Any, Optional

from .auth import ApiKeyAuth, AuthStrategy
from .exceptions import BrowserbaseAPIError
from .types import CreateSessionKwargs # Import the new type

logger = logging.getLogger(__name__)

class BrowserbaseClient:
    """Client for interacting with the Browserbase API."""
    def __init__(self, api_key: str, base_url: str = "https://api.browserbase.com/v1"):
        """
        Initialize the BrowserbaseClient.

        Args:
            api_key: Your Browserbase API key.
            base_url: The base URL for the Browserbase API. Defaults to v1.
        """
        if not api_key or not isinstance(api_key, str):
            raise ValueError("API key must be a non-empty string.")
        
        self.auth_strategy: AuthStrategy = ApiKeyAuth(api_key)
        self.base_url = base_url
        logger.info(f"BrowserbaseClient initialized for base URL: {self.base_url}")
        # It's good practice to manage the client lifecycle, 
        # e.g. by using it as a context manager or explicitly closing it.
        # For simplicity here, we'll create it as needed, but a persistent client is often better.

    def _get_headers(self) -> Dict[str, str]:
        """Internal method to get all necessary headers for a request."""
        headers = {"Content-Type": "application/json"}
        auth_headers = self.auth_strategy.get_auth_headers()
        headers.update(auth_headers)
        return headers

    async def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Internal helper for making HTTP requests."""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        
        # Prepare log data (payload might be in 'json' or 'data' kwargs)
        payload_to_log = kwargs.get('json', kwargs.get('data'))
        # Basic redaction for now, assuming payload is a dict. Can be expanded.
        # We are not redacting project_id as it's generally not secret.
        # If other sensitive keys appear in **kwargs for create_session, they would need redaction.
        # For now, Browserbase session creation doesn't seem to take highly sensitive data in payload beyond project_id.
        
        logger.debug(f"Request: {method} {url} Payload: {payload_to_log}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(method, url, headers=headers, **kwargs)
                # Log response before raising for status, so we capture error responses too
                response_summary = response.text[:500] + '...' if response.text and len(response.text) > 500 else response.text
                logger.debug(f"Response: {response.status_code} {response_summary}")
                response.raise_for_status()
                if response.status_code == 204: # No content
                    return None
                return response.json()
            except httpx.HTTPStatusError as e:
                # Already logged response text above, here we log the error context specifically
                logger.error(
                    f"API request failed: {e.request.method} {e.request.url} - Status: {e.response.status_code}",
                    exc_info=True # Add exception info to log
                )
                raise BrowserbaseAPIError(
                    message=f"API request failed: {e.request.method} {e.request.url}", 
                    status_code=e.response.status_code,
                    response_content=e.response.text
                ) from e
            except httpx.RequestError as e:
                logger.error(
                    f"Request failed: {e.request.method} {e.request.url} - Error: {str(e)}",
                    exc_info=True # Add exception info to log
                )
                raise BrowserbaseAPIError(f"Request failed: {e.request.method} {e.request.url}") from e

    async def create_session(self, project_id: str, **kwargs: Any) -> Dict[str, Any]: # Using Any for kwargs for now
        """Creates a new Browserbase session.

        Args:
            project_id: The Project ID. Can be found in Browserbase Settings.
            **kwargs: Additional parameters for session creation. 
                      These are passed directly to the Browserbase API.
                      Refer to `src.browserbase_client.types.CreateSessionKwargs` for the expected structure
                      and the official Browserbase API documentation for /v1/sessions (POST).
                      Key options include:
                      - `extensionId` (str): Uploaded Extension ID.
                      - `browserSettings` (BrowserSettingsDict): Detailed browser configurations.
                          - `context` (BrowserContextDict): Context ID and persistence.
                          - `fingerprint` (FingerprintDict): HTTP version, browser types, devices, locales, OS, screen.
                          - `viewport` (ViewportDict): Width and height.
                          - `blockAds` (bool): Enable/disable ad blocking.
                          - `solveCaptchas` (bool): Enable/disable captcha solving.
                          - `recordSession` (bool): Enable/disable session recording.
                          - `logSession` (bool): Enable/disable session logging.
                          - `advancedStealth` (bool): Enable/disable advanced stealth mode.
                      - `timeout` (int): Duration in seconds after which the session will automatically end.
                      - `keepAlive` (bool): Keep session alive after disconnections (Startup plan only).
                      - `proxies` (Union[bool, List[CustomProxyConfigDict]]): True for default, or list of custom proxies.
                      - `region` (Literal['us-west-2', ...]): Region for the session.
                      - `userMetadata` (Dict[str, Any]): Arbitrary user metadata.

        Returns:
            A dictionary containing the API response for the created session.

        Raises:
            BrowserbaseAPIError: If the API request fails.
            ValueError: If `project_id` is invalid.
        """
        if not project_id or not isinstance(project_id, str):
            raise ValueError("Project ID must be a non-empty string.")
        payload = {"projectId": project_id, **kwargs}
        return await self._request("POST", "/sessions", json=payload)

    async def list_sessions(self, status: Optional[str] = None, q: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists Browserbase sessions."""
        params: Dict[str, Any] = {}
        if status:
            params["status"] = status
        if q:
            params["q"] = q
        return await self._request("GET", "/sessions", params=params if params else None)

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """Retrieves details for a specific Browserbase session."""
        return await self._request("GET", f"/sessions/{session_id}")

    async def release_session(self, session_id: str, project_id: str) -> Optional[Dict[str, Any]]: # Endpoint might return 204
        """Requests the release of a specific Browserbase session."""
        if not project_id or not isinstance(project_id, str):
            raise ValueError("Project ID must be a non-empty string for releasing a session.")
        payload = {"projectId": project_id, "status": "REQUEST_RELEASE"}
        return await self._request("POST", f"/sessions/{session_id}", json=payload)

    # Example of how headers would be used in a request method (actual methods for endpoints to be added later)
    # async def list_sessions(self):
    #     headers = self._get_headers()
    #     # import httpx # or requests
    #     # async with httpx.AsyncClient() as client:
    #     #     response = await client.get(f"{self.base_url}/sessions", headers=headers)
    #     #     response.raise_for_status() # Raise an exception for bad status codes
    #     #     return response.json()
    #     pass
