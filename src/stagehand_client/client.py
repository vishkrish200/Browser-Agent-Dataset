from typing import Optional, Union, Any, Dict
import httpx
import logging
import asyncio # Added for sleep

# Import tenacity for retry logic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from . import config
from .auth import AuthStrategy, ApiKeyAuth
from .exceptions import StagehandError, StagehandAPIError, StagehandConfigError
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
                # Use StagehandConfigError for configuration issues
                raise StagehandConfigError(
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
        request_url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        logger.debug(f"Request: {method} {request_url} Payload: {kwargs.get('json') or kwargs.get('data')}")

        # TEMPORARY DEBUGGING - Can remove later
        # print(f"[DEBUG] httpx request: method='{method}', endpoint='{endpoint}'")
        # print(f"[DEBUG] http_client base_url='{self.http_client.base_url}'")

        # Define retry conditions
        # Retry on connection errors, timeouts, and 5xx server errors
        retry_conditions = retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)) | \
                           retry_if_exception_type(StagehandAPIError) # Retry on our custom API error as well

        @retry(stop=stop_after_attempt(3), # Retry up to 3 times
               wait=wait_exponential(multiplier=1, min=1, max=10), # Exponential backoff: 1s, 2s, 4s...
               retry=retry_conditions,
               before_sleep=lambda retry_state: logger.warning(
                   f"Retrying {method} {request_url} due to {retry_state.outcome.exception()}. Attempt #{retry_state.attempt_number}"
               ))
        async def _make_request_with_retry():
            try:
                # Use the potentially recreated client property inside the retry loop
                response = await self.http_client.request(method, endpoint, **kwargs)
                response_summary = response.text[:500] + '...' if response.text and len(response.text) > 500 else response.text
                logger.debug(f"Response: {response.status_code} {response_summary}")
                
                # Check for specific status codes that warrant a retry (e.g., 5xx)
                if 500 <= response.status_code < 600:
                     raise StagehandAPIError(
                        message=f"API request failed with server error: {method} {request_url}",
                        status_code=response.status_code,
                        response_content=response.text
                     )

                response.raise_for_status() # Raise HTTPStatusError for other 4xx/5xx responses
                if response.status_code == 204: # No content
                    return None
                return response.json()
            except httpx.HTTPStatusError as e:
                # Re-raise as StagehandAPIError for consistent handling, but don't retry 4xx here
                logger.error(
                    f"API request failed (non-retryable status): {e.request.method} {e.request.url} - Status: {e.response.status_code}",
                    exc_info=True
                )
                raise StagehandAPIError(
                    message=f"API call to {e.request.method} {e.request.url} failed with status {e.response.status_code}",
                    status_code=e.response.status_code,
                    response_content=e.response.text
                ) from e
            except (httpx.RequestError, httpx.TimeoutException) as e: # Covers network errors, timeouts, etc.
                logger.warning(
                    f"Network request failed: {method} {request_url} - Error: {type(e).__name__} - {str(e)}"
                )
                raise # Re-raise to be caught by tenacity
            except StagehandAPIError as e:
                # Raised manually for 5xx status codes, re-raise for tenacity
                raise 
            except Exception as e: # Catch any other unexpected errors during request processing
                logger.exception(f"An unexpected error occurred during request to {request_url}")
                # Wrap in StagehandError (base class) - maybe don't retry?
                raise StagehandError(f"An unexpected error occurred: {str(e)}") from e
        
        try:
            return await _make_request_with_retry()
        except Exception as e:
            # Log the final error after all retries fail
            logger.error(f"Request failed permanently after retries: {method} {request_url} - Error: {e}")
            # Re-raise the exception caught by tenacity or the final non-retryable error
            raise

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
