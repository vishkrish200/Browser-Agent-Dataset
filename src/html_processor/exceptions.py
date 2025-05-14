class HTMLProcessingError(Exception):
    """Base exception for errors during HTML processing."""
    pass

class MinificationError(HTMLProcessingError):
    """Error during HTML minification."""
    pass

class DOMDiffError(HTMLProcessingError):
    """Error during DOM diffing operations."""
    pass 