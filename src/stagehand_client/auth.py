from abc import ABC, abstractmethod

class AuthStrategy(ABC):
    """Abstract base class for authentication strategies."""
    @abstractmethod
    def get_auth_headers(self) -> dict:
        """Return a dictionary of headers required for authentication."""
        pass

class ApiKeyAuth(AuthStrategy):
    """Authentication strategy using an API key in a header."""
    def __init__(self, api_key: str, header_name: str = "X-Stagehand-Api-Key"):
        if not api_key or not isinstance(api_key, str):
            raise ValueError("API key must be a non-empty string.")
        if not header_name or not isinstance(header_name, str):
            raise ValueError("Header name must be a non-empty string.")
        self.api_key = api_key
        self.header_name = header_name

    def get_auth_headers(self) -> dict:
        return {self.header_name: self.api_key}
