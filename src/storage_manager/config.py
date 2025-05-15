import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Environment variable names
STORAGE_S3_BUCKET_ENV_VAR = "STORAGE_S3_BUCKET"
STORAGE_S3_REGION_ENV_VAR = "STORAGE_S3_REGION"
STORAGE_LOCAL_BASE_PATH_ENV_VAR = "STORAGE_LOCAL_BASE_PATH"

# Default values
DEFAULT_S3_REGION = "us-east-1"
DEFAULT_LOCAL_BASE_PATH = "./storage_fallback_data"

def get_s3_bucket_name(bucket_override: Optional[str] = None) -> Optional[str]:
    """Gets the S3 bucket name from override or environment variable."""
    if bucket_override:
        logger.debug(f"Using S3 bucket from override: {bucket_override}")
        return bucket_override
    bucket_name = os.getenv(STORAGE_S3_BUCKET_ENV_VAR)
    if bucket_name:
        logger.debug(f"Using S3 bucket from env var {STORAGE_S3_BUCKET_ENV_VAR}: {bucket_name}")
    else:
        logger.debug(f"S3 bucket name not found in env var {STORAGE_S3_BUCKET_ENV_VAR}.")
    return bucket_name

def get_s3_region(region_override: Optional[str] = None) -> str:
    """Gets the S3 region from override, environment variable, or default."""
    if region_override:
        logger.debug(f"Using S3 region from override: {region_override}")
        return region_override
    region = os.getenv(STORAGE_S3_REGION_ENV_VAR, DEFAULT_S3_REGION)
    logger.debug(f"Using S3 region: {region} (from env var {STORAGE_S3_REGION_ENV_VAR} or default)")
    return region

def get_local_base_path(path_override: Optional[str] = None) -> str:
    """Gets the local base storage path from override, environment variable, or default."""
    if path_override:
        logger.debug(f"Using local base path from override: {path_override}")
        base_path = path_override
    else:
        base_path = os.getenv(STORAGE_LOCAL_BASE_PATH_ENV_VAR, DEFAULT_LOCAL_BASE_PATH)
        logger.debug(f"Using local base path: {base_path} (from env var {STORAGE_LOCAL_BASE_PATH_ENV_VAR} or default)")
    
    # Ensure the path is absolute and created
    abs_base_path = os.path.abspath(base_path)
    try:
        os.makedirs(abs_base_path, exist_ok=True)
        logger.debug(f"Ensured local base path exists: {abs_base_path}")
    except OSError as e:
        logger.error(f"Could not create local base path {abs_base_path}: {e}", exc_info=True)
        # Depending on strictness, could raise an error here or let it fail on first use
        # For now, just log, assuming it might be pre-created or permissions issue.
    return abs_base_path 