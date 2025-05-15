import os
import logging
from typing import Optional, Tuple, Dict, Any, Union, List
import json # Added for serializing dicts
import shutil # Added for local directory deletion

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
    """Manages storage and retrieval of data from S3 or local filesystem.

    The manager can be configured to use AWS S3 as the primary backend or
    a local filesystem path. Configuration is resolved from constructor
    parameters, environment variables, or default values.

    Key functionalities include storing and retrieving step-specific data
    (HTML, screenshots, action data, metadata), listing sessions and steps,
    and deleting step or session data.
    """

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
        2. Environment variables (see `config.py` for details).
        3. Default values (see `config.py` for details).

        The effective storage backend (S3 or local) is determined by the
        `prefer_s3` flag and whether S3 is correctly configured (e.g.,
        bucket name provided, S3 client initializes successfully).

        Args:
            s3_bucket_name: Override for S3 bucket name. If not provided,
                            resolved from `SM_S3_BUCKET_NAME` env var or defaults to None.
            s3_region_name: Override for S3 region name. If not provided,
                            resolved from `SM_S3_REGION` env var or `DEFAULT_S3_REGION`.
            local_base_path: Override for local storage base path. If not provided,
                             resolved from `SM_LOCAL_BASE_PATH` env var or `DEFAULT_LOCAL_BASE_PATH`.
            prefer_s3: If True (default) and S3 is configured, S3 will be the
                       primary storage. If False, or if S3 is not fully configured
                       (e.g., no bucket name, client init fails), local storage will be used.
                       The local base path directory is created if it doesn't exist.
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
        """Initializes and returns the Boto3 S3 client.

        The client is cached after the first successful initialization.
        Relies on AWS credentials being available in the environment or standard
        AWS credential locations.

        Raises:
            S3ConfigError: If S3 bucket name is not configured, or if AWS
                           credentials are not found/incomplete, or if any other
                           error occurs during Boto3 client initialization.
        """
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
        """Constructs the S3 key for a given data component.

        Args:
            session_id: The ID of the session.
            step_id: The ID of the step within the session.
            filename: The name of the file (e.g., 'observation.html').

        Returns:
            The constructed S3 key string (e.g., 'session_id/step_id/filename').
        """
        return f"{session_id}/{step_id}/{filename}"

    def _get_local_path(self, session_id: str, step_id: str, filename: str) -> str:
        """Constructs the local file path for a given data component.

        Ensures that the directory structure (<local_base_path>/<session_id>/<step_id>)
        is created if it doesn't already exist.

        Args:
            session_id: The ID of the session.
            step_id: The ID of the step within the session.
            filename: The name of the file (e.g., 'observation.html').

        Returns:
            The absolute local file path string.
        """
        step_dir = os.path.join(self.local_base_path, session_id, step_id)
        os.makedirs(step_dir, exist_ok=True)
        return os.path.join(step_dir, filename)

    def _upload_to_s3(self, data: Union[str, bytes], s3_key: str, content_type: Optional[str] = None) -> str:
        """Uploads data (bytes or string) to S3.

        String data is encoded to UTF-8 before uploading.

        Args:
            data: The data to upload (string or bytes).
            s3_key: The S3 key (path) where the data will be stored.
            content_type: Optional. The MIME type of the content (e.g., 'text/html').

        Returns:
            The S3 URL of the uploaded object (e.g., 's3://bucket_name/key').

        Raises:
            S3ConfigError: If the S3 client cannot be initialized.
            S3OperationError: If the S3 `put_object` operation fails.
            StorageManagerError: For other unexpected errors during the upload process.
        """
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
        """Writes data (bytes or string) to a local file.

        String data is written as UTF-8.

        Args:
            data: The data to write (string or bytes).
            local_path: The absolute or relative local file path.

        Returns:
            The absolute path to the written file.

        Raises:
            LocalStorageError: If an IOError occurs during file writing.
            StorageManagerError: For other unexpected errors during the write process.
        """
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
        """Downloads data from S3.

        Args:
            s3_key: The S3 key (path) of the object to download.

        Returns:
            The downloaded data as bytes.

        Raises:
            S3ConfigError: If the S3 client cannot be initialized.
            S3OperationError: If the S3 `get_object` operation fails (e.g., NoSuchKey,
                              or other client errors).
            StorageManagerError: For other unexpected errors during the download process.
        """
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
        """Reads data from a local file.

        Args:
            local_path: The absolute or relative local file path to read from.

        Returns:
            The file content as bytes.

        Raises:
            LocalStorageError: If the file is not found or an IOError occurs during reading.
            StorageManagerError: For other unexpected errors during the read process.
        """
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
        """Returns a dictionary with current storage configuration information.

        This can be used to understand the active storage backend (S3 or local)
        and its associated parameters.

        Returns:
            A dictionary containing:
                - 'uses_s3' (bool): True if S3 is the active backend.
                - 's3_bucket' (Optional[str]): S3 bucket name if using S3, else None.
                - 's3_region' (Optional[str]): S3 region name if using S3, else None.
                - 'local_base_path' (str): The absolute base path for local storage.
                - 'effective_storage_type' (str): 'S3' or 'Local'.
        """
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
        Stores data components for a single browser interaction step.

        Data can include HTML content, a screenshot, structured action data (JSON),
        and other metadata (JSON). Each provided component is stored either in S3
        or the local filesystem, based on the StorageManager's configuration.

        The storage path follows a structured format:
        - S3: `s3://<bucket_name>/<session_id>/<step_id>/<component_filename>`
        - Local: `<local_base_path>/<session_id>/<step_id>/<component_filename>`

        Standard filenames (e.g., `observation.html`, `screenshot.png`) are used.

        Args:
            session_id: The unique identifier for the session.
            step_id: The unique identifier for the step within the session.
            html_content: Optional HTML content (string or bytes).
            screenshot_bytes: Optional screenshot image data (bytes).
            action_data: Optional dictionary вино action data (will be stored as JSON).
            metadata: Optional dictionary with other metadata (will be stored as JSON).

        Returns:
            A dictionary mapping component types (e.g., 'html_path') to their
            storage paths (S3 URLs or absolute local file paths). If a component
            was not provided or failed to store, its path will be None.

        Raises:
            S3OperationError: If an S3 operation (e.g., upload) fails.
            LocalStorageError: If a local filesystem operation (e.g., write) fails.
            StorageManagerError: For other unexpected errors during orchestration.
            S3ConfigError: If S3 is used but client cannot be initialized.
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
        Retrieves all data components (HTML, screenshot, action, metadata) for a specific step.

        Attempts to fetch each standard component (HTML, screenshot, action data, metadata)
        from the configured storage backend (S3 or local). If a component is not found
        or an error occurs while retrieving or processing it (e.g., JSON decoding error),
        that specific component will be returned as None in the tuple. Errors are logged,
        but the method attempts to retrieve other components.

        Args:
            session_id: The unique identifier for the session.
            step_id: The unique identifier for the step within the session.

        Returns:
            A tuple containing:
                (html_content_str, screenshot_bytes, action_data_dict, metadata_dict)
            Each element can be None if the corresponding data was not found or
            could not be processed.
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

    async def list_sessions(self) -> List[str]:
        """Lists available unique session IDs from the storage backend.

        For S3, this lists common prefixes (directories) at the root of the bucket.
        For local storage, this lists directories directly under the `local_base_path`.

        Returns:
            A sorted list of session ID strings. Returns an empty list if no
            sessions are found or if the storage path is inaccessible.

        Raises:
            S3OperationError: If listing S3 sessions fails due to a client error.
            LocalStorageError: If listing local sessions fails due to an OSError.
            S3ConfigError: If S3 is used but client cannot be initialized.
        """
        session_ids = set()
        if self.use_s3:
            s3_client = self._get_s3_client()
            paginator = s3_client.get_paginator('list_objects_v2')
            try:
                for page in paginator.paginate(Bucket=self.s3_bucket_name, Delimiter='/'):
                    for prefix_info in page.get('CommonPrefixes', []):
                        # CommonPrefixes gives paths like 'session_id/', so strip the trailing '/'
                        session_id = prefix_info.get('Prefix', '').rstrip('/')
                        if session_id: # Ensure it's not an empty string
                            session_ids.add(session_id)
                logger.debug(f"Found S3 sessions: {list(session_ids)}")
            except ClientError as e:
                logger.error(f"Error listing S3 sessions: {e}", exc_info=True)
                raise S3OperationError("Failed to list S3 sessions", operation="list_sessions", original_exception=e) from e
        else:
            if not os.path.exists(self.local_base_path) or not os.path.isdir(self.local_base_path):
                logger.warning(f"Local base path {self.local_base_path} does not exist or is not a directory. Returning empty session list.")
                return []
            try:
                for item in os.listdir(self.local_base_path):
                    if os.path.isdir(os.path.join(self.local_base_path, item)):
                        session_ids.add(item)
                logger.debug(f"Found local sessions: {list(session_ids)}")
            except OSError as e:
                logger.error(f"Error listing local sessions from {self.local_base_path}: {e}", exc_info=True)
                raise LocalStorageError(f"Failed to list local sessions: {e}") from e
        
        return sorted(list(session_ids)) # Return sorted list for consistent order

    async def list_steps_for_session(self, session_id: str) -> List[str]:
        """Lists available unique step IDs for a given session_id.

        For S3, this lists common prefixes (directories) under `session_id/`.
        For local storage, this lists directories directly under `<local_base_path>/<session_id>/`.

        Args:
            session_id: The ID of the session for which to list steps.

        Returns:
            A sorted list of step ID strings. Returns an empty list if no
            steps are found, the session does not exist, or the path is inaccessible.

        Raises:
            S3OperationError: If listing S3 steps fails due to a client error.
            LocalStorageError: If listing local steps fails due to an OSError.
            S3ConfigError: If S3 is used but client cannot be initialized.
        """
        step_ids = set()
        if self.use_s3:
            s3_client = self._get_s3_client()
            paginator = s3_client.get_paginator('list_objects_v2')
            prefix = f"{session_id}/" # Ensure trailing slash for S3 prefix
            try:
                for page in paginator.paginate(Bucket=self.s3_bucket_name, Prefix=prefix, Delimiter='/'):
                    for prefix_info in page.get('CommonPrefixes', []):
                        # Prefix will be like 'session_id/step_id/'. We need to extract 'step_id'
                        full_step_prefix = prefix_info.get('Prefix', '')
                        if full_step_prefix.startswith(prefix):
                            step_id = full_step_prefix[len(prefix):].rstrip('/')
                            if step_id: # Ensure it's not an empty string
                                step_ids.add(step_id)
                logger.debug(f"Found S3 steps for session {session_id}: {list(step_ids)}")
            except ClientError as e:
                logger.error(f"Error listing S3 steps for session {session_id}: {e}", exc_info=True)
                raise S3OperationError(f"Failed to list S3 steps for session {session_id}", operation="list_steps", original_exception=e) from e
        else:
            session_path = os.path.join(self.local_base_path, session_id)
            if not os.path.exists(session_path) or not os.path.isdir(session_path):
                logger.warning(f"Local session path {session_path} does not exist or is not a directory. Returning empty step list.")
                return []
            try:
                for item in os.listdir(session_path):
                    if os.path.isdir(os.path.join(session_path, item)):
                        step_ids.add(item)
                logger.debug(f"Found local steps for session {session_id}: {list(step_ids)}")
            except OSError as e:
                logger.error(f"Error listing local steps from {session_path}: {e}", exc_info=True)
                raise LocalStorageError(f"Failed to list local steps for session {session_id}: {e}") from e
        
        return sorted(list(step_ids)) # Return sorted list for consistent order

    async def delete_step(self, session_id: str, step_id: str) -> None:
        """Deletes all data associated with a specific step within a session.

        For S3, this involves listing all objects under the `session_id/step_id/`
        prefix and then performing a batch delete operation.
        For local storage, this removes the `local_base_path/session_id/step_id/`
        directory and all its contents.

        If the step does not exist or no objects/directory are found, the operation
        completes silently (with an informational log).

        Args:
            session_id: The ID of the session containing the step.
            step_id: The ID of the step to delete.

        Raises:
            S3OperationError: If listing or deleting S3 objects fails.
            LocalStorageError: If deleting the local step directory fails due to an OSError.
            S3ConfigError: If S3 is used but client cannot be initialized.
        """
        if self.use_s3:
            s3_client = self._get_s3_client()
            prefix_to_delete = f"{session_id}/{step_id}/"
            objects_to_delete = []
            paginator = s3_client.get_paginator('list_objects_v2')
            try:
                for page in paginator.paginate(Bucket=self.s3_bucket_name, Prefix=prefix_to_delete):
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            objects_to_delete.append({'Key': obj['Key']})
                
                if objects_to_delete:
                    delete_response = s3_client.delete_objects(
                        Bucket=self.s3_bucket_name,
                        Delete={'Objects': objects_to_delete, 'Quiet': True}
                    )
                    if 'Errors' in delete_response and delete_response['Errors']:
                        logger.error(f"Errors encountered deleting objects for step {prefix_to_delete} from S3: {delete_response['Errors']}")
                        # Convert S3 error list to a more manageable string or raise specific error
                        error_details = ", ".join([f"{err['Key']}: {err['Message']}" for err in delete_response['Errors']])
                        raise S3OperationError(f"Errors deleting from S3 for step {prefix_to_delete}: {error_details}", operation="delete_step")
                    logger.info(f"Successfully deleted {len(objects_to_delete)} objects for step {prefix_to_delete} from S3.")
                else:
                    logger.info(f"No objects found to delete for step {prefix_to_delete} in S3.")
            except ClientError as e:
                logger.error(f"ClientError deleting step {prefix_to_delete} from S3: {e}", exc_info=True)
                raise S3OperationError(f"Failed to delete S3 step {prefix_to_delete}", operation="delete_step", original_exception=e) from e
        else:
            step_path = os.path.join(self.local_base_path, session_id, step_id)
            if os.path.exists(step_path) and os.path.isdir(step_path):
                try:
                    shutil.rmtree(step_path)
                    logger.info(f"Successfully deleted local step directory: {step_path}")
                except OSError as e:
                    logger.error(f"OSError deleting local step directory {step_path}: {e}", exc_info=True)
                    raise LocalStorageError(f"Failed to delete local step {step_path}: {e}") from e
            else:
                logger.info(f"Local step directory {step_path} not found or not a directory. Nothing to delete.")

    async def delete_session(self, session_id: str) -> None:
        """Deletes all data associated with an entire session, including all its steps.

        For S3, this involves listing all objects under the `session_id/`
        prefix and then performing a batch delete operation.
        For local storage, this removes the `local_base_path/session_id/`
        directory and all its contents.

        If the session does not exist or no objects/directory are found, the operation
        completes silently (with an informational log).

        Args:
            session_id: The ID of the session to delete.

        Raises:
            S3OperationError: If listing or deleting S3 objects fails.
            LocalStorageError: If deleting the local session directory fails due to an OSError.
            S3ConfigError: If S3 is used but client cannot be initialized.
        """
        if self.use_s3:
            s3_client = self._get_s3_client()
            prefix_to_delete = f"{session_id}/"
            objects_to_delete = []
            paginator = s3_client.get_paginator('list_objects_v2')
            try:
                for page in paginator.paginate(Bucket=self.s3_bucket_name, Prefix=prefix_to_delete):
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            objects_to_delete.append({'Key': obj['Key']})
                
                if objects_to_delete:
                    # S3 delete_objects can handle up to 1000 keys at a time.
                    # Boto3's delete_objects call handles requests with more than 1000 keys by making multiple calls internally.
                    delete_response = s3_client.delete_objects(
                        Bucket=self.s3_bucket_name,
                        Delete={'Objects': objects_to_delete, 'Quiet': True}
                    )
                    if 'Errors' in delete_response and delete_response['Errors']:
                        logger.error(f"Errors encountered deleting objects for session {prefix_to_delete} from S3: {delete_response['Errors']}")
                        error_details = ", ".join([f"{err['Key']}: {err['Message']}" for err in delete_response['Errors']])
                        raise S3OperationError(f"Errors deleting from S3 for session {prefix_to_delete}: {error_details}", operation="delete_session")
                    logger.info(f"Successfully deleted {len(objects_to_delete)} objects for session {prefix_to_delete} from S3.")
                else:
                    logger.info(f"No objects found to delete for session {prefix_to_delete} in S3.")
            except ClientError as e:
                logger.error(f"ClientError deleting session {prefix_to_delete} from S3: {e}", exc_info=True)
                raise S3OperationError(f"Failed to delete S3 session {prefix_to_delete}", operation="delete_session", original_exception=e) from e
        else:
            session_path = os.path.join(self.local_base_path, session_id)
            if os.path.exists(session_path) and os.path.isdir(session_path):
                try:
                    shutil.rmtree(session_path)
                    logger.info(f"Successfully deleted local session directory: {session_path}")
                except OSError as e:
                    logger.error(f"OSError deleting local session directory {session_path}: {e}", exc_info=True)
                    raise LocalStorageError(f"Failed to delete local session {session_path}: {e}") from e
            else:
                logger.info(f"Local session directory {session_path} not found or not a directory. Nothing to delete.")

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