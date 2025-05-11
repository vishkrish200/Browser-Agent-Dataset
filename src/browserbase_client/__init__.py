from .auth import ApiKeyAuth, AuthStrategy
from .client import BrowserbaseClient
from .exceptions import BrowserbaseAPIError
from .types import (
    ViewportDict,
    ScreenDict,
    FingerprintDict,
    BrowserContextDict,
    BrowserSettingsDict,
    CustomProxyConfigDict,
    CreateSessionKwargs
)

__all__ = [
    "BrowserbaseClient",
    "ApiKeyAuth",
    "AuthStrategy",
    "BrowserbaseAPIError",
    # Exported types for constructing session parameters
    "ViewportDict",
    "ScreenDict",
    "FingerprintDict",
    "BrowserContextDict",
    "BrowserSettingsDict",
    "CustomProxyConfigDict",
    "CreateSessionKwargs"
]
