import os
import logging
from typing import Optional, Union

# Initialize logger for this module if we want to log warnings from here
logger = logging.getLogger(__name__)

BROWSERBASE_API_KEY_ENV_VAR = "BROWSERBASE_API_KEY"
BROWSERBASE_BASE_URL_ENV_VAR = "BROWSERBASE_BASE_URL"
BROWSERBASE_DEFAULT_TIMEOUT_SECONDS_ENV_VAR = "BROWSERBASE_DEFAULT_TIMEOUT_SECONDS"
BROWSERBASE_MAX_RETRIES_ENV_VAR = "BROWSERBASE_MAX_RETRIES"
BROWSERBASE_RETRY_DELAY_SECONDS_ENV_VAR = "BROWSERBASE_RETRY_DELAY_SECONDS"
BROWSERBASE_MAX_BACKOFF_DELAY_SECONDS_ENV_VAR = "BROWSERBASE_MAX_BACKOFF_DELAY_SECONDS"

DEFAULT_BASE_URL = "https://api.browserbase.com/v1"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 1.0
DEFAULT_MAX_BACKOFF_DELAY_SECONDS = 60.0

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

def get_max_retries(retries_override: Optional[int] = None) -> int:
    """Resolves the maximum number of retries. Prioritizes override, then environment variable, then default."""
    if retries_override is not None:
        try:
            val = int(retries_override)
            if val < 0:
                logger.warning(f"Invalid retries_override value: {retries_override}. Must be non-negative. Using default.")
            else:
                return val
        except (ValueError, TypeError):
            logger.warning(
                f"Invalid retries_override type: {retries_override}. Using default.",
                exc_info=True
            )
            # Fall through for type error

    env_retries_str = _get_env_var(BROWSERBASE_MAX_RETRIES_ENV_VAR)
    if env_retries_str:
        try:
            val = int(env_retries_str)
            if val < 0:
                logger.warning(f"Invalid value for env var {BROWSERBASE_MAX_RETRIES_ENV_VAR}: {env_retries_str}. Must be non-negative. Using default.")
            else:
                return val
        except ValueError:
            logger.warning(
                f"Invalid value for env var {BROWSERBASE_MAX_RETRIES_ENV_VAR}: "
                f"{env_retries_str}. Using default retries.",
                exc_info=True
            )
    return DEFAULT_MAX_RETRIES

def get_retry_delay_seconds(delay_override: Optional[Union[float, int]] = None) -> float:
    """Resolves the retry delay in seconds. Prioritizes override, then environment variable, then default."""
    if delay_override is not None:
        try:
            val = float(delay_override)
            if val < 0:
                logger.warning(f"Invalid delay_override value: {delay_override}. Must be non-negative. Using default.")
            else:
                return val
        except (ValueError, TypeError):
            logger.warning(
                f"Invalid delay_override type: {delay_override}. Using default.",
                exc_info=True
            )
            # Fall through for type error

    env_delay_str = _get_env_var(BROWSERBASE_RETRY_DELAY_SECONDS_ENV_VAR)
    if env_delay_str:
        try:
            val = float(env_delay_str)
            if val < 0:
                logger.warning(f"Invalid value for env var {BROWSERBASE_RETRY_DELAY_SECONDS_ENV_VAR}: {env_delay_str}. Must be non-negative. Using default.")
            else:
                return val
        except ValueError:
            logger.warning(
                f"Invalid value for env var {BROWSERBASE_RETRY_DELAY_SECONDS_ENV_VAR}: "
                f"{env_delay_str}. Using default delay.",
                exc_info=True
            )
    return DEFAULT_RETRY_DELAY_SECONDS

def get_max_backoff_delay_seconds(delay_override: Optional[Union[float, int]] = None) -> float:
    """Resolves the maximum backoff delay in seconds. Prioritizes override, then environment variable, then default."""
    if delay_override is not None:
        try:
            val = float(delay_override)
            if val < 0:
                logger.warning(f"Invalid delay_override value for max backoff: {delay_override}. Must be non-negative. Using default.")
            else:
                return val
        except (ValueError, TypeError):
            logger.warning(
                f"Invalid delay_override type for max backoff: {delay_override}. Using default.",
                exc_info=True
            )
            # Fall through for type error

    env_delay_str = _get_env_var(BROWSERBASE_MAX_BACKOFF_DELAY_SECONDS_ENV_VAR)
    if env_delay_str:
        try:
            val = float(env_delay_str)
            if val < 0:
                logger.warning(f"Invalid value for env var {BROWSERBASE_MAX_BACKOFF_DELAY_SECONDS_ENV_VAR}: {env_delay_str}. Must be non-negative. Using default.")
            else:
                return val
        except ValueError:
            logger.warning(
                f"Invalid value for env var {BROWSERBASE_MAX_BACKOFF_DELAY_SECONDS_ENV_VAR}: "
                f"{env_delay_str}. Using default max backoff delay.",
                exc_info=True
            )
    return DEFAULT_MAX_BACKOFF_DELAY_SECONDS
