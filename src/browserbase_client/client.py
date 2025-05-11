from .auth import ApiKeyAuth, AuthStrategy

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
        # In a real client, you might also want to validate base_url format
        
        self.auth_strategy: AuthStrategy = ApiKeyAuth(api_key)
        self.base_url = base_url

    def _get_headers(self) -> dict:
        """Internal method to get all necessary headers for a request."""
        headers = {"Content-Type": "application/json"}
        auth_headers = self.auth_strategy.get_auth_headers()
        headers.update(auth_headers)
        return headers

    # Example of how headers would be used in a request method (actual methods for endpoints to be added later)
    # async def list_sessions(self):
    #     headers = self._get_headers()
    #     # import httpx # or requests
    #     # async with httpx.AsyncClient() as client:
    #     #     response = await client.get(f"{self.base_url}/sessions", headers=headers)
    #     #     response.raise_for_status() # Raise an exception for bad status codes
    #     #     return response.json()
    #     pass
