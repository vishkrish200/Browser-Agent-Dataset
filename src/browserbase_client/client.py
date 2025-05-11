import httpx
from typing import List, Dict, Any, Optional

from .auth import ApiKeyAuth, AuthStrategy
from .exceptions import BrowserbaseAPIError

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
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(method, url, headers=headers, **kwargs)
                response.raise_for_status() # Raises HTTPStatusError for 4xx/5xx responses
                if response.status_code == 204: # No content
                    return None
                return response.json()
            except httpx.HTTPStatusError as e:
                raise BrowserbaseAPIError(
                    message=f"API request failed: {e.request.method} {e.request.url}", 
                    status_code=e.response.status_code,
                    response_content=e.response.text
                ) from e
            except httpx.RequestError as e:
                raise BrowserbaseAPIError(f"Request failed: {e.request.method} {e.request.url}") from e

    async def create_session(self, project_id: str, **kwargs) -> Dict[str, Any]:
        """Creates a new Browserbase session."""
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

    async def release_session(self, session_id: str, project_id: str) -> Dict[str, Any]:
        """Requests the release of a specific Browserbase session."""
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
