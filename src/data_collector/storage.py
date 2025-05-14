# src/data_collector/storage.py

import abc
import os
import gzip
from typing import IO, Any, Union, Optional
import logging

from .types import StorageConfig
from .exceptions import StorageError, S3StorageError, LocalStorageError, ConfigurationError

# Attempt to import boto3, but make it optional so module can load without it if S3 isn't used.
try:
    import boto3
    from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None
    ClientError = None # So type hints don't break if boto3 missing
    NoCredentialsError = None
    PartialCredentialsError = None
    BOTO3_AVAILABLE = False

logger = logging.getLogger(__name__)

class StorageBackend(abc.ABC):
    """Abstract base class for storage backends (e.g., S3, local file system)."""

    def __init__(self, config: StorageConfig):
        self.config = config
        logger.info(f"StorageBackend initialized with type: {config.get('type')}")

    @abc.abstractmethod
    async def store_artifact(
        self, 
        session_id: str, 
        step_id: str, 
        artifact_name: str, # e.g., "trace.html.gz", "screenshot.webp", "action.json"
        data: Union[bytes, str, IO[Any]],
        is_gzipped: bool = False # If true, and data is bytes/IO, assumes it's already gzipped
    ) -> str:
        """
        Stores an artifact and returns its full storage path/URI.
        If data is str, it will be utf-8 encoded. If it's not pre-gzipped and name suggests gzip,
        it will be gzipped before storing (for HTML typically).
        """
        pass

    @abc.abstractmethod
    async def retrieve_artifact(self, artifact_path: str) -> bytes:
        """Retrieves an artifact from its storage path/URI."""
        pass

    @abc.abstractmethod
    def get_artifact_path(self, session_id: str, step_id: str, artifact_name: str) -> str:
        """Constructs the expected storage path/URI for an artifact without storing it."""
        pass

class LocalStorage(StorageBackend):
    """Stores artifacts on the local file system."""

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.base_path = config.get("base_path", "./collected_data")
        if not os.path.exists(self.base_path):
            try:
                os.makedirs(self.base_path, exist_ok=True)
                logger.info(f"LocalStorage: Created base directory at {self.base_path}")
            except OSError as e:
                logger.error(f"LocalStorage: Failed to create base directory {self.base_path}: {e}")
                raise LocalStorageError(f"Failed to create base directory {self.base_path}: {e}") from e
        logger.info(f"LocalStorage initialized. Base path: {self.base_path}")

    def get_artifact_path(self, session_id: str, step_id: str, artifact_name: str) -> str:
        session_path = os.path.join(self.base_path, session_id)
        step_path = os.path.join(session_path, step_id)
        return os.path.join(step_path, artifact_name)

    async def store_artifact(
        self, 
        session_id: str, 
        step_id: str, 
        artifact_name: str,
        data: Union[bytes, str, IO[Any]],
        is_gzipped: bool = False
    ) -> str:
        full_path = self.get_artifact_path(session_id, step_id, artifact_name)
        step_dir = os.path.dirname(full_path)
        if not os.path.exists(step_dir):
            try:
                os.makedirs(step_dir, exist_ok=True)
            except OSError as e:
                logger.error(f"LocalStorage: Failed to create directory {step_dir} for artifact: {e}")
                raise LocalStorageError(f"Failed to create directory {step_dir}: {e}") from e

        try:
            logger.debug(f"LocalStorage: Attempting to store artifact at {full_path}")
            
            should_gzip = artifact_name.endswith(".gz") and not is_gzipped
            
            if isinstance(data, str):
                content_bytes = data.encode('utf-8')
            elif hasattr(data, 'read'): # IO stream
                content_bytes = data.read()
                if isinstance(content_bytes, str): # some streams might read as str
                    content_bytes = content_bytes.encode('utf-8')
            else: # bytes
                content_bytes = data

            if should_gzip:
                content_bytes = gzip.compress(content_bytes)
            
            with open(full_path, 'wb') as f:
                f.write(content_bytes)
            logger.info(f"LocalStorage: Successfully stored artifact at {full_path}")
            return full_path
        except IOError as e:
            logger.error(f"LocalStorage: Failed to write artifact to {full_path}: {e}")
            raise LocalStorageError(f"Failed to write artifact to {full_path}: {e}") from e
        except Exception as e:
            logger.exception(f"LocalStorage: Unexpected error storing artifact {full_path}: {e}")
            raise LocalStorageError(f"Unexpected error storing artifact {full_path}: {e}") from e

    async def retrieve_artifact(self, artifact_path: str) -> bytes:
        logger.debug(f"LocalStorage: Attempting to retrieve artifact from {artifact_path}")
        if not os.path.exists(artifact_path):
            logger.error(f"LocalStorage: Artifact not found at {artifact_path}")
            raise LocalStorageError(f"Artifact not found at {artifact_path}")
        try:
            with open(artifact_path, 'rb') as f:
                content = f.read()
            logger.info(f"LocalStorage: Successfully retrieved artifact from {artifact_path}")
            return content
        except IOError as e:
            logger.error(f"LocalStorage: Failed to read artifact from {artifact_path}: {e}")
            raise LocalStorageError(f"Failed to read artifact from {artifact_path}: {e}") from e

class S3Storage(StorageBackend):
    """Stores artifacts in an S3 compatible bucket."""
    def __init__(self, config: StorageConfig):
        super().__init__(config)
        if not BOTO3_AVAILABLE:
            msg = "S3Storage requires boto3. Please install with `pip install boto3`."
            logger.critical(msg)
            raise ConfigurationError(msg)
        
        self.bucket_name = config.get("bucket")
        self.base_path = config.get("base_path", "").strip("/") # Optional prefix

        if not self.bucket_name:
            raise ConfigurationError("S3Storage requires 'bucket' name in config.")

        s3_endpoint_url = config.get('s3_endpoint_url')
        aws_access_key_id = config.get('aws_access_key_id')
        aws_secret_access_key = config.get('aws_secret_access_key')
        aws_region = config.get('aws_region')

        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=s3_endpoint_url,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=aws_region
            )
            # Test connection / bucket existence (optional, but good practice)
            # self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"S3Storage initialized. Bucket: {self.bucket_name}, BasePath: '{self.base_path}', Endpoint: {s3_endpoint_url or 'AWS default'}")
        except (NoCredentialsError, PartialCredentialsError) as e:
            msg = f"S3Storage: AWS credentials not found or incomplete for S3 client. Error: {e}"
            logger.error(msg)
            raise ConfigurationError(msg) from e
        except ClientError as e:
            # More specific error, e.g., bucket not found if head_bucket was called
            msg = f"S3Storage: ClientError during S3 client initialization for bucket '{self.bucket_name}'. Error: {e}"
            logger.error(msg)
            raise S3StorageError(msg) from e
        except Exception as e:
            msg = f"S3Storage: Unexpected error initializing S3 client for bucket '{self.bucket_name}'. Error: {e}"
            logger.exception(msg)
            raise S3StorageError(msg) from e

    def get_artifact_path(self, session_id: str, step_id: str, artifact_name: str) -> str:
        # S3 paths are typically s3://bucket/key
        key_parts = [self.base_path, session_id, step_id, artifact_name]
        # Filter out empty parts (e.g. if base_path is empty)
        s3_key = "/".join(filter(None, key_parts))
        return f"s3://{self.bucket_name}/{s3_key}"

    async def store_artifact(
        self, 
        session_id: str, 
        step_id: str, 
        artifact_name: str,
        data: Union[bytes, str, IO[Any]],
        is_gzipped: bool = False
    ) -> str:
        key_parts = [self.base_path, session_id, step_id, artifact_name]
        s3_key = "/".join(filter(None, key_parts))
        
        try:
            logger.debug(f"S3Storage: Attempting to store artifact at s3://{self.bucket_name}/{s3_key}")
            
            should_gzip = artifact_name.endswith(".gz") and not is_gzipped
            
            if isinstance(data, str):
                content_bytes = data.encode('utf-8')
            elif hasattr(data, 'read'): # IO stream
                # For S3, it's often better to pass the stream directly to upload_fileobj if possible
                # But for consistency with gzipping, we might read it first.
                # If data is already a file-like object (IO[bytes]), boto3 can handle it.
                if 'b' in getattr(data, 'mode', '') or isinstance(getattr(data, 'peek', lambda: b'')(), bytes):
                    # Likely a binary stream already
                    pass 
                else: # Text stream, read and encode
                    content_str = data.read()
                    content_bytes = content_str.encode('utf-8')
                    data = content_bytes # Replace stream with bytes for consistent handling below
            # else: data is bytes

            if isinstance(data, bytes): # If data was string or text stream, it's now bytes
                if should_gzip:
                    final_data_bytes = gzip.compress(data)
                else:
                    final_data_bytes = data
                self.s3_client.put_object(Bucket=self.bucket_name, Key=s3_key, Body=final_data_bytes)
            
            elif hasattr(data, 'read'): # Binary stream (IO[bytes])
                if should_gzip:
                    # Need to read, gzip, then upload. Boto3 can't gzip on the fly with upload_fileobj.
                    read_bytes = data.read()
                    gzipped_bytes = gzip.compress(read_bytes)
                    self.s3_client.put_object(Bucket=self.bucket_name, Key=s3_key, Body=gzipped_bytes)
                else:
                    # data must be seekable for upload_fileobj in some cases or provide content_length
                    # For simplicity here, we might have already read it if gzipping was an option.
                    # If it's a binary file stream that doesn't need gzipping:
                    data.seek(0) # Ensure stream is at the beginning
                    self.s3_client.upload_fileobj(data, self.bucket_name, s3_key)
            else:
                raise TypeError(f"Unsupported data type for S3 storage: {type(data)}")

            full_s3_path = f"s3://{self.bucket_name}/{s3_key}"
            logger.info(f"S3Storage: Successfully stored artifact at {full_s3_path}")
            return full_s3_path
        except ClientError as e:
            logger.error(f"S3Storage: ClientError storing artifact s3://{self.bucket_name}/{s3_key}. Error: {e}")
            raise S3StorageError(f"S3 ClientError: {e}") from e
        except Exception as e:
            logger.exception(f"S3Storage: Unexpected error storing artifact s3://{self.bucket_name}/{s3_key}. Error: {e}")
            raise S3StorageError(f"Unexpected S3 error: {e}") from e

    async def retrieve_artifact(self, artifact_path: str) -> bytes:
        if not artifact_path.startswith(f"s3://{self.bucket_name}/"):
            raise ValueError(f"Invalid S3 artifact path format: {artifact_path}")
        s3_key = artifact_path.replace(f"s3://{self.bucket_name}/", "", 1)
        logger.debug(f"S3Storage: Attempting to retrieve artifact from s3://{self.bucket_name}/{s3_key}")
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            content = response['Body'].read()
            logger.info(f"S3Storage: Successfully retrieved artifact s3://{self.bucket_name}/{s3_key}")
            return content
        except ClientError as e:
            logger.error(f"S3Storage: ClientError retrieving artifact s3://{self.bucket_name}/{s3_key}. Error: {e}")
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise S3StorageError(f"Artifact not found at {artifact_path}") from e
            raise S3StorageError(f"S3 ClientError: {e}") from e
        except Exception as e:
            logger.exception(f"S3Storage: Unexpected error retrieving artifact s3://{self.bucket_name}/{s3_key}. Error: {e}")
            raise S3StorageError(f"Unexpected S3 error: {e}") from e


def get_storage_backend(config: StorageConfig) -> StorageBackend:
    """Factory function to get a storage backend instance based on config."""
    storage_type = config.get("type", DEFAULT_STORAGE_TYPE if "DEFAULT_STORAGE_TYPE" in globals() else "local")
    if storage_type == "s3":
        return S3Storage(config)
    elif storage_type == "local":
        return LocalStorage(config)
    else:
        raise ConfigurationError(f"Unsupported storage type: {storage_type}") 