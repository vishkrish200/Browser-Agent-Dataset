class StorageManagerError(Exception):
    """Base exception for StorageManager related errors."""
    pass

class S3ConfigError(StorageManagerError):
    """Raised when S3 configuration is missing or invalid."""
    pass

class LocalStorageError(StorageManagerError):
    """Raised for errors related to local filesystem storage."""
    pass

class S3OperationError(StorageManagerError):
    """Raised when an S3 operation (upload, download, list) fails."""
    def __init__(self, message, operation: str, original_exception=None):
        super().__init__(message)
        self.operation = operation
        self.original_exception = original_exception

    def __str__(self):
        base_msg = super().__str__()
        return f"{base_msg} (Operation: {self.operation}) Original: {self.original_exception}" 