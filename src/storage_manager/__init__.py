# __init__.py for storage_manager module

from .storage import StorageManager
from .exceptions import StorageManagerError

__all__ = ["StorageManager", "StorageManagerError"] 