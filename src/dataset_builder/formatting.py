from typing import Dict, Any
from .types import ProcessedDataRecord, JSONLEntry
from .exceptions import FormattingError

def format_record_to_jsonl_entry(record: ProcessedDataRecord) -> JSONLEntry:
    """Formats a processed data record into a JSONL entry for LLM fine-tuning."""
    # This is a placeholder. Actual formatting logic will be more complex,
    # combining DOM, action, and potentially image references into a coherent text string.
    if not record.get("session_id") or not record.get("step_id"):
        raise FormattingError("Record missing session_id or step_id")

    text_parts = []
    if record.get("dom_snapshot"):
        text_parts.append(f"<DOM>{record['dom_snapshot']}</DOM>")
    
    # TODO: Add action representation, image reference, etc.
    if record.get("action_representation"):
        text_parts.append(f"<ACTION>{record['action_representation']}</ACTION>")

    entry_id = f"{record['session_id']}_{record['step_id']}"
    combined_text = " ".join(text_parts)

    return JSONLEntry(id=entry_id, text=combined_text) 