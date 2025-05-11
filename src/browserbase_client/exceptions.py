class BrowserbaseAPIError(Exception):
    """Base exception class for Browserbase API errors."""
    def __init__(self, message: str, status_code: int = None, response_content: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_content = response_content

    def __str__(self):
        base_str = super().__str__()
        if self.status_code:
            base_str += f" (Status Code: {self.status_code})"
        if self.response_content:
            base_str += f"\nResponse: {self.response_content[:500]}..." # Truncate long responses
        return base_str

# Placeholder for more specific exceptions if needed later
# class SessionNotFoundError(BrowserbaseAPIError):
#     pass

# class AuthenticationError(BrowserbaseAPIError):
#     pass
