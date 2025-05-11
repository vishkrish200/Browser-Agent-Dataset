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
from .config import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    BROWSERBASE_API_KEY_ENV_VAR,
    BROWSERBASE_BASE_URL_ENV_VAR,
    BROWSERBASE_DEFAULT_TIMEOUT_SECONDS_ENV_VAR
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
    "CreateSessionKwargs",
    # Exported config constants
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT_SECONDS",
    "BROWSERBASE_API_KEY_ENV_VAR",
    "BROWSERBASE_BASE_URL_ENV_VAR",
    "BROWSERBASE_DEFAULT_TIMEOUT_SECONDS_ENV_VAR"
]
