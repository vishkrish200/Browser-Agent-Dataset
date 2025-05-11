class StagehandError(Exception):
    """Base exception for all Stagehand client errors."""
    pass

class StagehandAPIError(StagehandError):
    """Raised when the Stagehand API returns an error."""
    def __init__(self, message: str, status_code: int = None, response_content: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_content = response_content

    def __str__(self):
        if self.status_code:
            return f"API Error {self.status_code}: {super().__str__()} - {self.response_content if self.response_content else 'No additional content'}"
        return super().__str__()

class StagehandConfigError(StagehandError):
    """Raised for configuration-related errors in the Stagehand client."""
    pass
