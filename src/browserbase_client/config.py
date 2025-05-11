import os
import logging
from typing import Optional, Union

# Initialize logger for this module if we want to log warnings from here
logger = logging.getLogger(__name__)

BROWSERBASE_API_KEY_ENV_VAR = "BROWSERBASE_API_KEY"
BROWSERBASE_BASE_URL_ENV_VAR = "BROWSERBASE_BASE_URL"
BROWSERBASE_DEFAULT_TIMEOUT_SECONDS_ENV_VAR = "BROWSERBASE_DEFAULT_TIMEOUT_SECONDS"

DEFAULT_BASE_URL = "https://api.browserbase.com/v1"
DEFAULT_TIMEOUT_SECONDS = 30.0

def _get_env_var(name: str, default: Optional[str] = None) -> Optional[str]:
    """Helper to get an environment variable."""
    return os.getenv(name, default)

def get_api_key(api_key_override: Optional[str] = None) -> Optional[str]:
    """Resolves the API key. Prioritizes override, then environment variable."""
    if api_key_override:
        return api_key_override
    return _get_env_var(BROWSERBASE_API_KEY_ENV_VAR)

def get_base_url(base_url_override: Optional[str] = None) -> str:
    """Resolves the base URL. Prioritizes override, then environment variable, then default."""
    url = base_url_override or _get_env_var(BROWSERBASE_BASE_URL_ENV_VAR)
    return url or DEFAULT_BASE_URL

def get_default_timeout_seconds(timeout_override: Optional[Union[float, int]] = None) -> float:
    """Resolves the default timeout. Prioritizes override, then environment variable, then default."""
    if timeout_override is not None:
        try:
            return float(timeout_override)
        except (ValueError, TypeError):
            logger.warning(
                f"Invalid timeout_override value: {timeout_override}. Using default.", 
                exc_info=True
            )
            # Fall through to check env var / default if override is invalid type

    env_timeout_str = _get_env_var(BROWSERBASE_DEFAULT_TIMEOUT_SECONDS_ENV_VAR)
    if env_timeout_str:
        try:
            return float(env_timeout_str)
        except ValueError:
            logger.warning(
                f"Invalid value for env var {BROWSERBASE_DEFAULT_TIMEOUT_SECONDS_ENV_VAR}: "
                f"{env_timeout_str}. Using default timeout.",
                exc_info=True
            )
    return DEFAULT_TIMEOUT_SECONDS
