from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class AppSettings(BaseSettings):
    BROWSERBASE_API_KEY: Optional[str] = None
    STAGEHAND_API_KEY: Optional[str] = None
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    S3_BUCKET_NAME: Optional[str] = None
    S3_ENDPOINT_URL: Optional[str] = None # For MinIO or other S3-compatibles
    DEFAULT_OUTPUT_DIR: str = "output"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file='.env', 
        env_file_encoding='utf-8',
        extra='ignore' # Ignore extra fields from .env or environment
    )

settings = AppSettings() 