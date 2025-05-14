from typing import TypedDict, Optional, Dict, Any
import datetime

class StorageConfig(TypedDict, total=False):
    """Configuration for the storage backend."""
    type: str  # e.g., "s3", "local"
    bucket: Optional[str] # For S3
    base_path: Optional[str] # For local storage, or prefix in S3 bucket
    # Add other S3 specific configs like region, endpoint_url if needed
    aws_access_key_id: Optional[str]
    aws_secret_access_key: Optional[str]
    aws_region: Optional[str]
    s3_endpoint_url: Optional[str] # For MinIO or other S3-compatible services

class ActionData(TypedDict):
    """Represents the structure of action data, primarily from Stagehand."""
    type: str # e.g., click, type, navigate
    selector: Optional[str]
    text: Optional[str] # For type actions, or matched text for click
    url: Optional[str] # For navigate actions
    # Add any other fields Stagehand might output in its action results
    stagehand_metadata: Optional[Dict[str, Any]]

class StepData(TypedDict):
    """
    Represents the data collected for a single step in an interaction workflow.
    Aligns with the PRD's Data Model per step.
    """
    step_id: str # Unique ID for this step
    session_id: str # Browserbase session ID
    stagehand_task_id: Optional[str] # Stagehand Task ID that this step belongs to
    stagehand_execution_id: Optional[str] # Stagehand Execution ID, if applicable per step
    
    url: str # Current URL when the step was recorded
    ts: str # Timestamp in ISO 8601 format (e.g., datetime.utcnow().isoformat())
    
    action: ActionData # The action performed at this step
    
    # Paths to stored artifacts; could be S3 URIs or local file paths
    # The actual file names will include the step_id for uniqueness.
    obs_html_gz_path: Optional[str] 
    screenshot_webp_path: Optional[str]
    # Add other potential artifact paths here, e.g., network logs
    # network_log_har_path: Optional[str] 