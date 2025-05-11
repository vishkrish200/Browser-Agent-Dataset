import os
from typing import Optional

# Environment variable names
STAGEHAND_API_KEY_ENV_VAR = "STAGEHAND_API_KEY"
STAGEHAND_BASE_URL_ENV_VAR = "STAGEHAND_BASE_URL"
STAGEHAND_DEFAULT_TIMEOUT_SECONDS_ENV_VAR = "STAGEHAND_DEFAULT_TIMEOUT_SECONDS"

# Default values
DEFAULT_BASE_URL = "https://api.stagehand.com/v1"  # Placeholder URL
DEFAULT_TIMEOUT_SECONDS = 30.0

def get_api_key(api_key_override: Optional[str] = None) -> Optional[str]:
    """Retrieve API key from override or environment variable."""
    if api_key_override:
        return api_key_override
    return os.environ.get(STAGEHAND_API_KEY_ENV_VAR)

def get_base_url(base_url_override: Optional[str] = None) -> str:
    """Retrieve base URL from override, environment variable, or use default."""
    if base_url_override:
        return base_url_override
    return os.environ.get(STAGEHAND_BASE_URL_ENV_VAR, DEFAULT_BASE_URL)

def get_default_timeout_seconds(timeout_override: Optional[float] = None) -> float:
    """Retrieve default timeout from override, environment variable, or use default."""
    if timeout_override is not None:
        return timeout_override
    env_timeout_str = os.environ.get(STAGEHAND_DEFAULT_TIMEOUT_SECONDS_ENV_VAR)
    if env_timeout_str:
        try:
            return float(env_timeout_str)
        except ValueError:
            # Log this ideally, but for now, fallback to default
            # print(f"Warning: Invalid timeout value '{env_timeout_str}' in env var. Using default.")
            pass
    return DEFAULT_TIMEOUT_SECONDS
