import logging
import uuid
import datetime
from typing import Optional, Dict, Any

# Clients are expected to be injected
from src.browserbase_client import BrowserbaseClient #, BrowserbaseAPIError
from src.stagehand_client import StagehandClient #, StagehandAPIError

from .types import StorageConfig, StepData, ActionData
from .storage import StorageBackend, get_storage_backend # S3Storage, LocalStorage
from .exceptions import DataCollectionError, ConfigurationError, StorageError
from . import config as collector_config # Default configurations for the collector

logger = logging.getLogger(__name__)
DEFAULT_LOG_EXTRA_DC = {"action": "data_collector_op"} # Specific to DataCollector actions

class DataCollector:
    """
    Handles the collection of data (HTML, screenshots, action metadata) 
    for each step of an interaction workflow and stores it.
    """

    def __init__(
        self, 
        browserbase_client: BrowserbaseClient, 
        stagehand_client: StagehandClient, 
        storage_config: Optional[StorageConfig] = None,
        # Możemy dodać tu więcej konfiguracji specyficznych dla kolektora
        # np. jakie typy artefaktów zbierać domyślnie
        artifact_collection_settings: Optional[Dict[str, bool]] = None
    ):
        """
        Initializes the DataCollector.

        Args:
            browserbase_client: An instance of BrowserbaseClient.
            stagehand_client: An instance of StagehandClient.
            storage_config: Configuration for the storage backend (S3 or local).
                            If None, defaults to local storage with settings from `config.py`.
            artifact_collection_settings: Optional dict specifying which artifacts to collect 
                                          (e.g., {"html_content": True, "screenshot_webp": True}).
                                          Defaults from `config.py`.
        """
        log_extra = {**DEFAULT_LOG_EXTRA_DC, "sub_action": "__init__"}
        logger.info("Initializing DataCollector...", extra=log_extra)

        if not isinstance(browserbase_client, BrowserbaseClient):
            raise ConfigurationError("DataCollector requires a valid BrowserbaseClient instance.")
        if not isinstance(stagehand_client, StagehandClient):
            raise ConfigurationError("DataCollector requires a valid StagehandClient instance.")
        
        self.browserbase_client = browserbase_client
        self.stagehand_client = stagehand_client

        effective_storage_config: StorageConfig = storage_config or {}
        if not effective_storage_config.get('type'):
            effective_storage_config['type'] = collector_config.DEFAULT_STORAGE_TYPE
            logger.info(
                f"Storage type not specified, defaulting to '{effective_storage_config['type']}'.", 
                extra=log_extra
            )
        if effective_storage_config['type'] == 'local' and not effective_storage_config.get('base_path'):
            effective_storage_config['base_path'] = collector_config.DEFAULT_LOCAL_STORAGE_BASE_PATH
        elif effective_storage_config['type'] == 's3' and not effective_storage_config.get('bucket'):
            effective_storage_config['bucket'] = collector_config.DEFAULT_S3_BUCKET_NAME
        
        self.storage_backend: StorageBackend = get_storage_backend(effective_storage_config)
        logger.info(f"Storage backend initialized: {type(self.storage_backend).__name__}", extra=log_extra)

        self.artifact_settings = artifact_collection_settings or collector_config.DEFAULT_ARTIFACT_COLLECTION_CONFIG
        logger.info(f"Artifact collection settings: {self.artifact_settings}", extra=log_extra)
        logger.info("DataCollector initialized successfully.", extra=log_extra)

    def _generate_step_id(self) -> str:
        """Generates a unique ID for a collection step (e.g., using UUID)."""
        return str(uuid.uuid4())

    async def configure_browserbase_session_for_recording(
        self, 
        session_id: str, 
        recording_options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Placeholder: Configures a Browserbase session for optimal data recording if needed.
        Actual implementation depends on BrowserbaseClient capabilities to modify active sessions
        or if recording is set at session creation by the Orchestrator.

        Args:
            session_id: The ID of the Browserbase session to configure.
            recording_options: Specific recording options. Defaults from `collector_config`.

        Returns:
            True if configuration was successful or deemed unnecessary, False otherwise.
        """
        log_extra = {**DEFAULT_LOG_EXTRA_DC, "sub_action": "configure_bb_session", "session_id": session_id}
        options = recording_options or collector_config.DEFAULT_BROWSERBASE_RECORDING_OPTIONS
        logger.info(f"Placeholder: Configuring Browserbase session {session_id} for recording with options: {options}", extra=log_extra)
        # Example: If BrowserbaseClient had a method like `set_recording_options`:
        # try:
        #     await self.browserbase_client.set_recording_options(session_id, options)
        #     logger.info(f"Successfully applied recording options to session {session_id}", extra=log_extra)
        #     return True
        # except BrowserbaseAPIError as e:
        #     logger.error(f"Failed to configure recording for session {session_id}: {e}", extra=log_extra)
        #     return False
        logger.warning("configure_browserbase_session_for_recording is a placeholder and not yet implemented.", extra=log_extra)
        return True # Assuming for now that Orchestrator handles this at session creation

    async def collect_step_data(
        self,
        browserbase_session_id: str,
        current_url: str,
        action_data: ActionData, # Structured action data
        stagehand_task_id: Optional[str] = None,
        stagehand_execution_id: Optional[str] = None,
        # Optional direct data (if not fetching via client methods)
        html_content: Optional[str] = None, 
        screenshot_bytes: Optional[bytes] = None, # Assume webp bytes
    ) -> StepData:
        """
        Collects data for a single interaction step, stores artifacts, and returns structured StepData.

        Args:
            browserbase_session_id: ID of the active Browserbase session.
            current_url: The URL of the page at the time of action/collection.
            action_data: A dictionary representing the action performed (aligns with ActionData type).
            stagehand_task_id: Optional ID of the parent Stagehand task.
            stagehand_execution_id: Optional ID of the specific Stagehand execution.
            html_content: Optional. If provided, this HTML string is used. Otherwise, might attempt to fetch.
            screenshot_bytes: Optional. If provided, these image bytes (expected WebP) are used. Otherwise, might attempt to fetch.

        Returns:
            A StepData dictionary containing metadata and paths to stored artifacts.

        Raises:
            DataCollectionError: If critical data cannot be collected or stored.
        """
        step_id = self._generate_step_id()
        log_extra = {
            **DEFAULT_LOG_EXTRA_DC, 
            "sub_action": "collect_step_data", 
            "session_id": browserbase_session_id, 
            "step_id": step_id,
            "url": current_url
        }
        logger.info(f"Starting data collection for step.", extra=log_extra)

        # Artifact paths will be populated based on successful storage
        html_path: Optional[str] = None
        screenshot_path: Optional[str] = None

        # 1. Handle HTML Content
        if self.artifact_settings.get("html_content", False):
            if html_content is not None:
                logger.debug("Using provided HTML content.", extra=log_extra)
            # else: # Future: Fetch HTML from Browserbase session if not provided
            #     logger.debug("Attempting to fetch HTML content...", extra=log_extra)
            #     # html_content = await self.browserbase_client.get_page_html(browserbase_session_id)
            
            if html_content:
                try:
                    artifact_name = f"{step_id}_page.html.gz"
                    html_path = await self.storage_backend.store_artifact(
                        session_id=browserbase_session_id, 
                        step_id=step_id, 
                        artifact_name=artifact_name, 
                        data=html_content, # store_artifact will handle gzipping if name ends .gz
                        is_gzipped=False 
                    )
                    logger.info(f"Stored HTML artifact: {html_path}", extra=log_extra)
                except StorageError as e:
                    logger.error(f"Failed to store HTML artifact: {e}", extra=log_extra)
                    # Decide if this is a critical failure or if we continue
            else:
                logger.warning("HTML content not available/fetched for step.", extra=log_extra)

        # 2. Handle Screenshot
        if self.artifact_settings.get("screenshot_webp", False):
            if screenshot_bytes is not None:
                logger.debug("Using provided screenshot bytes.", extra=log_extra)
            # else: # Future: Fetch screenshot from Browserbase session if not provided
            #     logger.debug("Attempting to fetch screenshot...", extra=log_extra)
            #     # screenshot_bytes = await self.browserbase_client.take_screenshot(browserbase_session_id, format="webp")
            
            if screenshot_bytes:
                try:
                    artifact_name = f"{step_id}_screenshot.webp"
                    screenshot_path = await self.storage_backend.store_artifact(
                        session_id=browserbase_session_id, 
                        step_id=step_id, 
                        artifact_name=artifact_name, 
                        data=screenshot_bytes,
                        is_gzipped=False # Screenshots are not gzipped here by default
                    )
                    logger.info(f"Stored screenshot artifact: {screenshot_path}", extra=log_extra)
                except StorageError as e:
                    logger.error(f"Failed to store screenshot artifact: {e}", extra=log_extra)
            else:
                logger.warning("Screenshot bytes not available/fetched for step.", extra=log_extra)

        # 3. Store Action Data (as JSON)
        action_json_path: Optional[str] = None
        if self.artifact_settings.get("action_data", False) and action_data:
            try:
                import json # Standard library, safe to import here
                action_json_str = json.dumps(action_data, indent=2)
                artifact_name = f"{step_id}_action.json"
                action_json_path = await self.storage_backend.store_artifact(
                    session_id=browserbase_session_id,
                    step_id=step_id,
                    artifact_name=artifact_name,
                    data=action_json_str
                )
                logger.info(f"Stored action JSON artifact: {action_json_path}", extra=log_extra)
            except (StorageError, TypeError, json.JSONDecodeError) as e:
                logger.error(f"Failed to store action_data JSON artifact: {e}", extra=log_extra)
        elif not action_data:
            logger.warning("Action data not provided for step.", extra=log_extra)


        # 4. Construct StepData
        # Ensure timestamp is in ISO 8601 format with timezone info (UTC preferred)
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        step_data_entry: StepData = {
            "step_id": step_id,
            "session_id": browserbase_session_id,
            "stagehand_task_id": stagehand_task_id,
            "stagehand_execution_id": stagehand_execution_id,
            "url": current_url,
            "ts": timestamp,
            "action": action_data, # The raw action data dictionary
            "obs_html_gz_path": html_path,
            "screenshot_webp_path": screenshot_path,
            # "action_json_path": action_json_path # If we decide to store action separately AND reference it
        }
        
        logger.info(f"Data collection for step completed. HTML: {html_path is not None}, Screenshot: {screenshot_path is not None}", extra=log_extra)
        return step_data_entry 