from typing import TypedDict, List, Any, Optional, Dict
from pydantic import BaseModel, HttpUrl, field_validator

class RawDataRecord(TypedDict):
    """Represents a raw record before transformation."""
    session_id: str
    step_id: str
    html_content: Optional[str]
    screenshot_path: Optional[str]
    action: Optional[Any] # Could be a more specific type later
    metadata: Optional[dict]

class RawS3HTMLData(TypedDict):
    s3_path: str
    content_gzipped: bytes # Or perhaps a path to the downloaded, unzipped file

class RawS3ScreenshotData(TypedDict):
    s3_path: str
    # Potentially image metadata if available

class RawStagehandAction(TypedDict):
    type: str
    selector: Optional[str]
    text: Optional[str]
    # ... other Stagehand-specific fields
    stagehand_metadata: Optional[Dict[str, Any]]

class ActionDetail(BaseModel):
    type: str
    selector: Optional[str] = None
    text: Optional[str] = None
    stagehand_metadata: Optional[Dict[str, Any]] = None
    # Add other fields from Stagehand's action output as they become clear

class ProcessedDataRecord(BaseModel):
    step_id: str # Example: "sha256:…" or a new ID scheme
    session_id: str # Example: "browserbase_session_xyz"
    stagehand_task_id: Optional[str] = None # Example: "stagehand_task_abc"
    url: HttpUrl
    ts: int # Timestamp, e.g., seconds since epoch
    action: ActionDetail
    obs_html_s3_path: Optional[str] = None # s3://chk/xyz/abc/step.htm.gz
    screenshot_s3_path: Optional[str] = None # s3://chk/xyz/abc/step.webp

    # Optional field for the actual HTML content if loaded and processed
    html_content: Optional[str] = None 
    # Optional field for a link to a locally processed/stored image if applicable
    processed_image_path: Optional[str] = None

    @field_validator('obs_html_s3_path', 'screenshot_s3_path')
    @classmethod
    def check_s3_path(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.startswith("s3://"):
            raise ValueError("S3 path must start with s3://")
        return v

class JSONLEntry(TypedDict):
    """Structure of a single line in the output JSONL file."""
    id: str # Unique ID for the entry
    text: str # The main text input for the LLM, combining DOM, action, etc.
    # Add other fields as required by the fine-tuning process
    # e.g., image: Optional[str], target: Optional[str] 

# Example of a more specific format if needed for LLM training string construction
class LLMTrainingInstance(BaseModel):
    id: str # from ProcessedDataRecord.step_id
    prompt: str # e.g., "<DOM>...html...</DOM><URL>...</URL>"
    completion: str # e.g., "<ACTION>click #button</ACTION>"
    # or just a single text field:
    # text: str # e.g. "<DOM>...html...</DOM><URL>...</URL><ACTION>click #button</ACTION>"

# Configuration types (if more complex than simple dicts)
class FilterConfig(TypedDict):
    min_length: Optional[int]
    # ... other filter params

class SplitConfig(TypedDict):
    train_ratio: float
    val_ratio: float
    test_ratio: Optional[float] 