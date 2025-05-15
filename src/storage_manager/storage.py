import os
import logging
from typing import Optional, Tuple, Dict, Any, Union
import json # Added for serializing dicts

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

from . import config as sm_config # sm_config to avoid clash if this module also has a config object
from .exceptions import StorageManagerError, S3ConfigError, S3OperationError, LocalStorageError

logger = logging.getLogger(__name__)

# Standard file names for stored data components
HTML_FILENAME = "observation.html"
SCREENSHOT_FILENAME = "screenshot.png"  # Assuming PNG as a common default, can be made dynamic
ACTION_DATA_FILENAME = "action.json"
METADATA_FILENAME = "metadata.json"

class StorageManager:
    """Manages storage and retrieval of data from S3 or local filesystem."""

    def __init__(
        self,
        s3_bucket_name: Optional[str] = None,
        s3_region_name: Optional[str] = None,
        local_base_path: Optional[str] = None,
        prefer_s3: bool = True # If S3 is configured, prefer it. If False, or S3 not configured, use local.
    ):
        """
        Initializes the StorageManager.

        Configuration for S3 bucket, region, and local path are resolved by:
        1. Direct parameters to constructor.
        2. Environment variables (handled by sm_config getters).
        3. Default values (handled by sm_config getters).

        Args:
            s3_bucket_name: Override for S3 bucket name.
            s3_region_name: Override for S3 region name.
            local_base_path: Override for local storage base path.
            prefer_s3: If True and S3 is configured, S3 will be the primary storage.
                       If False, or if S3 is not configured (no bucket name), 
                       local storage will be used.
        """
        self.s3_bucket_name = sm_config.get_s3_bucket_name(bucket_override=s3_bucket_name)
        self.s3_region_name = sm_config.get_s3_region(region_override=s3_region_name)
        self.local_base_path = sm_config.get_local_base_path(path_override=local_base_path)
        
        self._s3_client = None
        self.use_s3 = False # Determined by prefer_s3 and if S3 is configured

        if prefer_s3 and self.s3_bucket_name:
            try:
                # Attempt to initialize S3 client to check config early
                self._get_s3_client() # This will try to create client
                self.use_s3 = True
                logger.info(
                    f"StorageManager initialized to use S3. Bucket: {self.s3_bucket_name}, "
                    f"Region: {self.s3_region_name}. Local fallback: {self.local_base_path}"
                )
            except S3ConfigError as e:
                logger.warning(
                    f"S3 preference was True, but S3 client initialization failed: {e}. "
                    f"Falling back to local storage at {self.local_base_path}."
                )
                self.use_s3 = False # Explicitly set to false on init failure
        else:
            if not self.s3_bucket_name and prefer_s3:
                logger.info("S3 bucket name not configured. Using local storage.")
            elif not prefer_s3:
                logger.info("prefer_s3 is False. Using local storage.")
            self.use_s3 = False
            logger.info(f"StorageManager initialized to use Local Storage at {self.local_base_path}.")

    def _get_s3_client(self):
        """Initializes and returns the S3 client. Raises S3ConfigError on failure."""
        if self._s3_client is None:
            if not self.s3_bucket_name:
                raise S3ConfigError("S3 bucket name is not configured.")
            try:
                # For AWS credentials, boto3 will automatically search common locations:
                # 1. Passing credentials as parameters in the boto3.client() call
                # 2. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)
                # 3. Shared credential file (~/.aws/credentials)
                # 4. AWS config file (~/.aws/config)
                # 5. Assume Role provider
                # 6. Instance IAM role (for EC2, ECS, Lambda etc.)
                # We rely on this standard chain. No explicit credential handling here.
                self._s3_client = boto3.client("s3", region_name=self.s3_region_name)
                # Perform a simple operation to test credentials and bucket access if needed, e.g., head_bucket
                # For now, client creation is the primary check.
                logger.debug(f"S3 client initialized for region {self.s3_region_name}")
            except (NoCredentialsError, PartialCredentialsError) as e:
                logger.error(f"AWS credentials not found or incomplete for S3: {e}", exc_info=True)
                raise S3ConfigError(f"AWS credentials not found or incomplete: {e}") from e
            except ClientError as e:
                # Handles other Boto3 client errors during initialization (e.g., invalid region)
                logger.error(f"Failed to initialize S3 client: {e}", exc_info=True)
                raise S3ConfigError(f"Failed to initialize S3 client: {e}") from e
            except Exception as e: # Catch any other unexpected errors
                logger.error(f"An unexpected error occurred during S3 client initialization: {e}", exc_info=True)
                raise S3ConfigError(f"Unexpected error initializing S3 client: {e}") from e
        return self._s3_client

    def _get_s3_key(self, session_id: str, step_id: str, filename: str) -> str:
        """Constructs the S3 key for a given data component."""
        return f"{session_id}/{step_id}/{filename}"

    def _get_local_path(self, session_id: str, step_id: str, filename: str) -> str:
        """Constructs the local file path for a given data component and ensures directory exists."""
        step_dir = os.path.join(self.local_base_path, session_id, step_id)
        os.makedirs(step_dir, exist_ok=True)
        return os.path.join(step_dir, filename)

    def _upload_to_s3(self, data: Union[str, bytes], s3_key: str, content_type: Optional[str] = None) -> str:
        """Uploads data (bytes or string) to S3 and returns the S3 URL."""
        s3_client = self._get_s3_client() # Ensures S3 is configured and client is available
        try:
            body_data = data.encode('utf-8') if isinstance(data, str) else data
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            s3_client.put_object(
                Bucket=self.s3_bucket_name, 
                Key=s3_key, 
                Body=body_data,
                **extra_args
            )
            s3_url = f"s3://{self.s3_bucket_name}/{s3_key}"
            logger.debug(f"Successfully uploaded data to {s3_url}")
            return s3_url
        except ClientError as e:
            logger.error(f"S3 put_object failed for key {s3_key}: {e}", exc_info=True)
            raise S3OperationError(f"S3 upload failed for key {s3_key}", operation="upload", original_exception=e) from e
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"Unexpected error during S3 upload for key {s3_key}: {e}", exc_info=True)
            raise StorageManagerError(f"Unexpected error during S3 upload for {s3_key}: {e}") from e

    def _write_to_local(self, data: Union[str, bytes], local_path: str) -> str:
        """Writes data (bytes or string) to a local file and returns the absolute path."""
        try:
            mode = 'wb' if isinstance(data, bytes) else 'w'
            encoding = None if isinstance(data, bytes) else 'utf-8'
            with open(local_path, mode, encoding=encoding) as f:
                f.write(data)
            abs_path = os.path.abspath(local_path)
            logger.debug(f"Successfully wrote data to local file: {abs_path}")
            return abs_path
        except IOError as e:
            logger.error(f"IOError writing to local file {local_path}: {e}", exc_info=True)
            raise LocalStorageError(f"Failed to write to local file {local_path}: {e}") from e
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"Unexpected error writing to local file {local_path}: {e}", exc_info=True)
            raise StorageManagerError(f"Unexpected error writing to {local_path}: {e}") from e

    def _download_from_s3(self, s3_key: str) -> bytes:
        """Downloads data from S3 and returns it as bytes."""
        s3_client = self._get_s3_client()
        try:
            response = s3_client.get_object(Bucket=self.s3_bucket_name, Key=s3_key)
            data_bytes = response['Body'].read()
            logger.debug(f"Successfully downloaded data from s3://{self.s3_bucket_name}/{s3_key}")
            return data_bytes
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"S3 object not found at key {s3_key}")
                raise S3OperationError(f"S3 object not found: {s3_key}", operation="download_not_found", original_exception=e) from e
            logger.error(f"S3 get_object failed for key {s3_key}: {e}", exc_info=True)
            raise S3OperationError(f"S3 download failed for key {s3_key}", operation="download", original_exception=e) from e
        except Exception as e:
            logger.error(f"Unexpected error during S3 download for key {s3_key}: {e}", exc_info=True)
            raise StorageManagerError(f"Unexpected error during S3 download for {s3_key}: {e}") from e

    def _read_from_local(self, local_path: str) -> bytes:
        """Reads data from a local file and returns it as bytes."""
        try:
            with open(local_path, 'rb') as f:
                data_bytes = f.read()
            logger.debug(f"Successfully read data from local file: {local_path}")
            return data_bytes
        except FileNotFoundError:
            logger.warning(f"Local file not found: {local_path}")
            raise LocalStorageError(f"Local file not found: {local_path}") from None # Explicitly from None as FileNotFoundError is the direct cause
        except IOError as e:
            logger.error(f"IOError reading from local file {local_path}: {e}", exc_info=True)
            raise LocalStorageError(f"Failed to read from local file {local_path}: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error reading from local file {local_path}: {e}", exc_info=True)
            raise StorageManagerError(f"Unexpected error reading {local_path}: {e}") from e

    def get_storage_info(self) -> Dict[str, Any]:
        """Returns a dictionary with current storage configuration info."""
        return {
            "uses_s3": self.use_s3,
            "s3_bucket": self.s3_bucket_name if self.use_s3 else None,
            "s3_region": self.s3_region_name if self.use_s3 else None,
            "local_base_path": self.local_base_path,
            "effective_storage_type": "S3" if self.use_s3 else "Local"
        }

    # Placeholder methods for core functionality - to be implemented based on subtasks
    async def store_step_data(
        self,
        session_id: str,
        step_id: str, # Or some other unique identifier for the step
        html_content: Optional[Union[str, bytes]] = None,
        screenshot_bytes: Optional[bytes] = None,
        action_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None # For any other structured data
    ) -> Dict[str, Optional[str]]:
        """
        Stores data for a single step (HTML, screenshot, action, metadata).
        Data is stored according to the bucket structure: s3://<bucket>/<session_id>/<step_id>/<file_type>.<ext>
        or local structure: <local_base_path>/<session_id>/<step_id>/<file_type>.<ext>
        Returns a dictionary of stored paths (S3 URLs or local file paths).
        """
        paths: Dict[str, Optional[str]] = {
            "html_path": None,
            "screenshot_path": None,
            "action_data_path": None,
            "metadata_path": None
        }

        try:
            if html_content is not None:
                content_type = 'text/html'
                if self.use_s3:
                    s3_key = self._get_s3_key(session_id, step_id, HTML_FILENAME)
                    paths["html_path"] = self._upload_to_s3(html_content, s3_key, content_type)
                else:
                    local_path = self._get_local_path(session_id, step_id, HTML_FILENAME)
                    paths["html_path"] = self._write_to_local(html_content, local_path)

            if screenshot_bytes is not None:
                # Assuming PNG for now, ContentType can be refined if image format is known
                content_type = 'image/png' 
                if self.use_s3:
                    s3_key = self._get_s3_key(session_id, step_id, SCREENSHOT_FILENAME)
                    paths["screenshot_path"] = self._upload_to_s3(screenshot_bytes, s3_key, content_type)
                else:
                    local_path = self._get_local_path(session_id, step_id, SCREENSHOT_FILENAME)
                    paths["screenshot_path"] = self._write_to_local(screenshot_bytes, local_path)
            
            if action_data is not None:
                action_json_str = json.dumps(action_data, indent=2)
                content_type = 'application/json'
                if self.use_s3:
                    s3_key = self._get_s3_key(session_id, step_id, ACTION_DATA_FILENAME)
                    paths["action_data_path"] = self._upload_to_s3(action_json_str, s3_key, content_type)
                else:
                    local_path = self._get_local_path(session_id, step_id, ACTION_DATA_FILENAME)
                    paths["action_data_path"] = self._write_to_local(action_json_str, local_path)

            if metadata is not None:
                metadata_json_str = json.dumps(metadata, indent=2)
                content_type = 'application/json'
                if self.use_s3:
                    s3_key = self._get_s3_key(session_id, step_id, METADATA_FILENAME)
                    paths["metadata_path"] = self._upload_to_s3(metadata_json_str, s3_key, content_type)
                else:
                    local_path = self._get_local_path(session_id, step_id, METADATA_FILENAME)
                    paths["metadata_path"] = self._write_to_local(metadata_json_str, local_path)
            
            logger.info(f"Stored data for session {session_id}, step {step_id}. Paths: {paths}")
            return paths

        except (S3OperationError, LocalStorageError) as e:
            # These are already specific and logged by helpers, re-raise
            raise
        except Exception as e:
            # Catch any other unexpected error during this orchestration
            logger.error(f"Unexpected error in store_step_data for {session_id}/{step_id}: {e}", exc_info=True)
            raise StorageManagerError(f"Failed to store data for {session_id}/{step_id}: {e}") from e

    async def retrieve_step_data(
        self, 
        session_id: str, 
        step_id: str
    ) -> Tuple[Optional[str], Optional[bytes], Optional[Dict[str, Any]], Optional[Dict[str,Any]]]:
        """
        Retrieves all data (HTML, screenshot, action, metadata) for a specific step.
        Returns a tuple: (html_content_str, screenshot_bytes, action_data_dict, metadata_dict).
        If a component is not found, its corresponding return value will be None.
        """
        html_content_str: Optional[str] = None
        screenshot_bytes_val: Optional[bytes] = None # Renamed to avoid clash with screenshot_bytes parameter name in store_step_data
        action_data_dict: Optional[Dict[str, Any]] = None
        metadata_dict_val: Optional[Dict[str, Any]] = None # Renamed for consistency

        components_to_fetch = {
            "html": HTML_FILENAME,
            "screenshot": SCREENSHOT_FILENAME,
            "action": ACTION_DATA_FILENAME,
            "metadata": METADATA_FILENAME
        }

        for component_type, filename in components_to_fetch.items():
            raw_data: Optional[bytes] = None
            try:
                if self.use_s3:
                    s3_key = self._get_s3_key(session_id, step_id, filename)
                    raw_data = self._download_from_s3(s3_key)
                else:
                    local_path = self._get_local_path(session_id, step_id, filename)
                    # _get_local_path ensures parent dirs exist, but file itself might not
                    if os.path.exists(local_path):
                        raw_data = self._read_from_local(local_path)
                    else:
                        logger.debug(f"Local file {local_path} for component {component_type} does not exist. Skipping.")
                        continue # Skip to next component if file doesn't exist
                
                # Process raw_data based on component type
                if raw_data is not None:
                    if component_type == "html":
                        html_content_str = raw_data.decode('utf-8')
                    elif component_type == "screenshot":
                        screenshot_bytes_val = raw_data
                    elif component_type == "action":
                        action_data_dict = json.loads(raw_data.decode('utf-8'))
                    elif component_type == "metadata":
                        metadata_dict_val = json.loads(raw_data.decode('utf-8'))

            except (S3OperationError, LocalStorageError) as e:
                # These errors (like S3 NoSuchKey or FileNotFoundError from helpers) indicate the file for this specific component wasn't found or couldn't be read.
                # Log it and continue to try fetching other components.
                logger.warning(f"Could not retrieve {component_type} for {session_id}/{step_id}: {e}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON for {component_type} for {session_id}/{step_id}: {e}", exc_info=True)
                # Decide if this should be a hard error or just skip this component
            except Exception as e:
                # Catch any other unexpected error during processing of a single component
                logger.error(f"Unexpected error retrieving or processing {component_type} for {session_id}/{step_id}: {e}", exc_info=True)
                # Depending on desired strictness, could re-raise or just log and continue

        logger.info(f"Retrieved data for session {session_id}, step {step_id}.")
        return html_content_str, screenshot_bytes_val, action_data_dict, metadata_dict_val

    async def list_sessions(self) -> list[str]:
        """Lists available session_ids."""
        # TODO: Implement based on Subtask 11.4 (Session and Step Listing)
        logger.warning("list_sessions is not fully implemented yet.")
        return []

    async def list_steps_for_session(self, session_id: str) -> list[str]:
        """Lists available step_ids for a given session_id."""
        # TODO: Implement based on Subtask 11.4
        logger.warning("list_steps_for_session is not fully implemented yet.")
        return []

if __name__ == '__main__':
    # Example usage / basic test
    logging.basicConfig(level=logging.DEBUG)
    
    print("--- Testing StorageManager (S3 preference, but likely no bucket env var) ---")
    # This will likely default to local storage if STORAGE_S3_BUCKET is not set
    sm_default_to_local = StorageManager(prefer_s3=True)
    print(f"Default config: {sm_default_to_local.get_storage_info()}")

    print(
        "\n--- Testing StorageManager (S3 configured via env vars - set them for this to work) ---"
    )
    # For this to truly test S3, set STORAGE_S3_BUCKET_ENV_VAR, (optionally region)
    # and ensure AWS credentials are available in the environment.
    # Example: export STORAGE_S3_BUCKET="your-actual-test-bucket-name"
    #          export STORAGE_S3_REGION="your-region"
    sm_s3_from_env = StorageManager()
    s3_info = sm_s3_from_env.get_storage_info()
    print(f"S3 from env config: {s3_info}")
    if s3_info['uses_s3']:
        print(f"Attempting to get S3 client (will raise S3ConfigError if creds are bad/missing): {sm_s3_from_env._get_s3_client()}")
    else:
        print("S3 not used, skipping S3 client get attempt.")

    print("\n--- Testing StorageManager (Local storage forced) ---")
    sm_local_forced = StorageManager(prefer_s3=False)
    print(f"Local forced config: {sm_local_forced.get_storage_info()}")

    print("\n--- Testing StorageManager (Local storage by override) ---")
    sm_local_override = StorageManager(local_base_path="./my_custom_local_storage")
    print(f"Local override config: {sm_local_override.get_storage_info()}")

    print("\n--- Testing StorageManager (S3 by override, no env vars needed for these params) ---")
    # This will still require valid AWS credentials in the environment to actually connect
    sm_s3_override = StorageManager(s3_bucket_name="my-override-bucket", s3_region_name="eu-west-1")
    s3_override_info = sm_s3_override.get_storage_info()
    print(f"S3 override config: {s3_override_info}")
    if s3_override_info['uses_s3']:
        try:
            client = sm_s3_override._get_s3_client()
            print(f"S3 client from override: {client}")
        except S3ConfigError as e:
            print(f"S3ConfigError with override: {e}")
    else:
        print("S3 not used with override (likely due to S3ConfigError during init).")

    # Example of calling a placeholder method
    # asyncio.run(sm_default_to_local.store_step_data("session1", "step1", html_content="<p>Hello</p>")) 