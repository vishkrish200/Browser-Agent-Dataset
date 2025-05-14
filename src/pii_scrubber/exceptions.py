# src/pii_scrubber/exceptions.py

class PIIScrubbingError(Exception):
    """Base exception for errors encountered during PII scrubbing."""
    pass

class RegexCompilationError(PIIScrubbingError):
    """Raised when a PII detection regex fails to compile."""
    pass

class HTMLParsingError(PIIScrubbingError):
    """Raised when HTML content cannot be parsed for scrubbing."""
    pass 