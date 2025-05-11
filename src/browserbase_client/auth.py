from abc import ABC, abstractmethod

class AuthStrategy(ABC):
    """Abstract base class for authentication strategies."""
    @abstractmethod
    def get_auth_headers(self) -> dict:
        """Return a dictionary of headers to be included in API requests."""
        pass

class ApiKeyAuth(AuthStrategy):
    """Authentication strategy using an API key in the 'x-bb-api-key' header."""
    def __init__(self, api_key: str):
        if not api_key or not isinstance(api_key, str):
            raise ValueError("API key must be a non-empty string.")
        self.api_key = api_key

    def get_auth_headers(self) -> dict:
        """Return the authentication headers for Browserbase API key auth."""
        return {"x-bb-api-key": self.api_key}
