from typing import Optional, Union, Any, Dict
import httpx
import logging

from . import config
from .auth import AuthStrategy, ApiKeyAuth
# from .exceptions import StagehandAPIError # To be defined later
# from .types import SomeStagehandType # To be defined later

logger = logging.getLogger(__name__)

class StagehandClient:
    """Client for interacting with the Stagehand API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[Union[float, int]] = None,
    ):
        """
        Initialize the StagehandClient.

        Args:
            api_key: Your Stagehand API key. If None and no auth_strategy is provided,
                     attempts to load from env var STAGEHAND_API_KEY.
            auth_strategy: An instance of an AuthStrategy subclass. If provided, api_key is ignored.
            base_url: The base URL for the Stagehand API.
            timeout_seconds: Default timeout in seconds for HTTP requests.
        Raises:
            ValueError: If API key/auth_strategy is not provided and API key cannot be found.
        """
        self.base_url = config.get_base_url(base_url_override=base_url)
        self.timeout_seconds = config.get_default_timeout_seconds(timeout_override=timeout_seconds)

        if auth_strategy:
            self.auth_strategy = auth_strategy
        else:
            resolved_api_key = config.get_api_key(api_key_override=api_key)
            if not resolved_api_key:
                raise ValueError(
                    "Stagehand API key not provided and not found in environment variable "
                    f"{config.STAGEHAND_API_KEY_ENV_VAR}. "
                    "Alternatively, provide an auth_strategy instance."
                )
            self.auth_strategy = ApiKeyAuth(api_key=resolved_api_key)
        
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Provides an httpx.AsyncClient instance, creating one if it doesn't exist."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                headers=self.auth_strategy.get_auth_headers()
            )
        return self._http_client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # Placeholder for a generic request method, to be expanded later
    async def _request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> Dict[str, Any]: # Assuming JSON response for now
        logger.debug(f"Request: {method} {self.base_url}{endpoint} Payload: {kwargs.get('json')}")
        try:
            response = await self.http_client.request(method, endpoint, **kwargs)
            response.raise_for_status() # Raise HTTPStatusError for 4xx/5xx responses
            logger.debug(f"Response: {response.status_code} {response.text}")
            return response.json() # Or response.text, response.content based on API
        except httpx.HTTPStatusError as e:
            logger.error(
                f"API request failed: {method} {self.base_url}{endpoint} - Status: {e.response.status_code}",
                exc_info=True
            )
            # Re-raise as a custom StagehandAPIError later, e.g.:
            # raise StagehandAPIError(str(e), status_code=e.response.status_code, response_content=e.response.text) from e
            raise # For now, re-raise the original httpx error
        except httpx.RequestError as e:
            logger.error(
                f"Network request failed: {method} {self.base_url}{endpoint}", exc_info=True
            )
            # Re-raise as a custom StagehandAPIError later
            # raise StagehandAPIError(f"Network error: {str(e)}") from e
            raise # For now, re-raise

    async def create_task(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a new task/workflow in Stagehand.
        The actual endpoint and response structure are based on common API patterns
        and the example in the parent task, and may need adjustment.
        """
        # Assuming the API endpoint for creating tasks is /tasks or /workflows
        # The example from Task 3 details used client.create_task(workflow)
        return await self._request("POST", "/tasks", json=workflow_data)

    async def execute_task(self, task_id: str, browser_session_id: str) -> Dict[str, Any]:
        """
        Executes a previously created Stagehand task within a specific Browserbase session.
        The actual endpoint, payload, and response structure are based on common API patterns
        and the example in the parent task, and may need adjustment.
        """
        # Assuming the API endpoint for executing tasks is POST /tasks/{task_id}/execute
        # And the payload needs the browserbase_session_id
        payload = {"browserSessionId": browser_session_id}
        return await self._request("POST", f"/tasks/{task_id}/execute", json=payload)

    async def get_task_logs(self, task_id: str) -> Dict[str, Any]:
        """
        Retrieves execution logs for a specific Stagehand task.
        The actual endpoint and response structure are based on common API patterns
        and may need adjustment based on the Stagehand API.
        """
        # Assuming the API endpoint for fetching logs is GET /tasks/{task_id}/logs
        return await self._request("GET", f"/tasks/{task_id}/logs")

    # Example API method (to be defined in later subtasks)
    # async def get_task_status(self, task_id: str) -> dict:
    #     return await self._request("GET", f"/tasks/{task_id}/status")
