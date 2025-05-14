# src/data_collector/exceptions.py

class DataCollectionError(Exception):
    """Base exception for errors during data collection."""
    pass

class StorageError(DataCollectionError):
    """Base exception for errors related to storage operations (S3, local file system)."""
    pass

class S3StorageError(StorageError):
    """Specific exception for S3 storage errors."""
    pass

class LocalStorageError(StorageError):
    """Specific exception for local file system storage errors."""
    pass

class ConfigurationError(DataCollectionError):
    """Error related to invalid or missing configuration for the data collector or its components."""
    pass 