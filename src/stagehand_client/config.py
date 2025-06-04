import os
from typing import Optional
import logging

# Environment variable names for LLM providers (Stagehand library might use these directly)
# Example: OPENAI_API_KEY_ENV_VAR = "OPENAI_API_KEY"
# Example: ANTHROPIC_API_KEY_ENV_VAR = "ANTHROPIC_API_KEY"

# STAGEHAND_API_KEY_ENV_VAR = "STAGEHAND_API_KEY" # Removed, assuming Stagehand lib uses provider keys
# STAGEHAND_BASE_URL_ENV_VAR = "STAGEHAND_BASE_URL" # Removed
# STAGEHAND_DEFAULT_TIMEOUT_SECONDS_ENV_VAR = "STAGEHAND_DEFAULT_TIMEOUT_SECONDS" # Removed

# Default values
# DEFAULT_BASE_URL = "https://api.stagehand.com/v1"  # Removed
# DEFAULT_TIMEOUT_SECONDS = 30.0 # Removed

# def get_api_key(api_key_override: Optional[str] = None) -> Optional[str]: # Removed
#     \"\"\"Retrieve API key from override or environment variable.\"\"\"
#     if api_key_override:
#         return api_key_override
#     return os.environ.get(STAGEHAND_API_KEY_ENV_VAR)

# def get_base_url(base_url_override: Optional[str] = None) -> str: # Removed
#     \"\"\"Retrieve base URL from override, environment variable, or use default.\"\"\"
#     if base_url_override:
#         return base_url_override
#     return os.environ.get(STAGEHAND_BASE_URL_ENV_VAR, DEFAULT_BASE_URL)

# def get_default_timeout_seconds(timeout_override: Optional[float] = None) -> float: # Removed
#     \"\"\"Retrieve default timeout from override, environment variable, or use default.\"\"\"
#     if timeout_override is not None:
#         return timeout_override
#     env_timeout_str = os.environ.get(STAGEHAND_DEFAULT_TIMEOUT_SECONDS_ENV_VAR)
#     if env_timeout_str:
#         try:
#             return float(env_timeout_str)
#         except ValueError:
#             # Log this ideally, but for now, fallback to default
#             # print(f\"Warning: Invalid timeout value '{env_timeout_str}' in env var. Using default.\")
#             pass
#     return DEFAULT_TIMEOUT_SECONDS

# This file is now much simpler as StagehandClient is being refactored
# to not make direct remote API calls. Stagehand library itself will likely
# handle its own configuration (e.g., for LLM API keys via environment variables).

logger = logging.getLogger(__name__) # Added import
logger.info("Stagehand client config loaded (refactored for local library usage). "
            "Most configurations previously here are removed.")

# If any specific shared configurations for the *local* Stagehand library usage
# are needed across the project and are not handled by Stagehand's internal
# environment variable checks, they could be placed here.
# For now, assuming Stagehand library handles its own LLM key discovery.
