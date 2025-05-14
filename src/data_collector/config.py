# src/data_collector/config.py

# Placeholder for data collector specific configurations.
# These might include things like:
# - Default S3 bucket name (if not provided in StorageConfig)
# - Default local storage base path
# - What data types to collect by default (e.g., {"html": True, "screenshot": True, "actions": True})
# - Screenshot resolution or WebP quality settings
# - Retry mechanism defaults for storage operations

DEFAULT_STORAGE_TYPE = "local" # or "s3"
DEFAULT_LOCAL_STORAGE_BASE_PATH = "./collected_data"
DEFAULT_S3_BUCKET_NAME = "browser-agent-dataset-checkpoints" # Example

# Example: Default set of artifacts to try and collect
# Actual collection depends on availability from Browserbase/Stagehand
DEFAULT_ARTIFACT_COLLECTION_CONFIG = {
    "html_content": True,
    "screenshot_webp": True,
    "action_data": True, # From Stagehand
    # "network_log_har": False, # Example of a potential future artifact
}

# Example: Default recording options to *suggest* to Browserbase if configurable via client
# The specifics of this would depend heavily on BrowserbaseClient's capabilities.
DEFAULT_BROWSERBASE_RECORDING_OPTIONS = {
    "record_html": True,
    "record_screenshots": True, # or specific screenshot config
    "screenshot_type": "webp", # Assuming Browserbase can be told this
    "screenshot_quality": 80,  # Example for WebP
    # "record_network_trace": False,
} 