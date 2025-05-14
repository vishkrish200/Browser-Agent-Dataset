from typing import TypedDict, List, Any, Optional

class RawDataRecord(TypedDict):
    """Represents a raw record before transformation."""
    session_id: str
    step_id: str
    html_content: Optional[str]
    screenshot_path: Optional[str]
    action: Optional[Any] # Could be a more specific type later
    metadata: Optional[dict]

class ProcessedDataRecord(TypedDict):
    """Represents a record after initial processing and PII scrubbing."""
    session_id: str
    step_id: str
    dom_snapshot: Optional[str] # Minified, scrubbed HTML
    image_reference: Optional[str] # e.g., S3 path or relative path to image
    action_representation: Optional[str] # Standardized action string
    # Add other relevant fields as needed

class JSONLEntry(TypedDict):
    """Structure of a single line in the output JSONL file."""
    id: str # Unique ID for the entry
    text: str # The main text input for the LLM, combining DOM, action, etc.
    # Add other fields as required by the fine-tuning process
    # e.g., image: Optional[str], target: Optional[str] 