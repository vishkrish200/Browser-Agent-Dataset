'''
Handles formatting of raw data into structured ProcessedDataRecord objects
and serializing them to JSONL strings.
'''
import json
from typing import Dict, Any, Optional, Union
from pydantic import ValidationError

from .types import ProcessedDataRecord, ActionDetail, RawStagehandAction
from .exceptions import DataFormattingError

def create_processed_data_record(
    step_id: str,
    session_id: str,
    url: str,
    ts: int,
    action_data: Union[RawStagehandAction, Dict[str, Any]], # Can be raw dict or pre-parsed
    obs_html_s3_path: Optional[str] = None,
    screenshot_s3_path: Optional[str] = None,
    html_content: Optional[str] = None,
    stagehand_task_id: Optional[str] = None,
) -> ProcessedDataRecord:
    '''
    Creates a ProcessedDataRecord from individual data components.
    Performs validation using Pydantic models.

    Raises:
        DataFormattingError: If validation fails or input data is malformed.
    '''
    try:
        # Ensure action_data is in a suitable format for ActionDetail
        if not isinstance(action_data, ActionDetail):
            try:
                action_detail = ActionDetail(**action_data)
            except TypeError as e:
                raise DataFormattingError(f"Could not parse action_data into ActionDetail: {e}. Data: {action_data}")
        else:
            action_detail = action_data

        record_data = {
            "step_id": step_id,
            "session_id": session_id,
            "url": url,
            "ts": ts,
            "action": action_detail,
            "obs_html_s3_path": obs_html_s3_path,
            "screenshot_s3_path": screenshot_s3_path,
            "html_content": html_content,
            "stagehand_task_id": stagehand_task_id,
        }
        
        processed_record = ProcessedDataRecord(**record_data)
        return processed_record
    except ValidationError as e:
        error_details = e.errors()
        raise DataFormattingError(f"Validation failed for data record (step_id: {step_id}): {error_details}") from e
    except Exception as e:
        raise DataFormattingError(f"An unexpected error occurred while creating ProcessedDataRecord (step_id: {step_id}): {str(e)}") from e

def serialize_record_to_jsonl(record: ProcessedDataRecord) -> str:
    '''
    Serializes a ProcessedDataRecord to a JSON string (for a line in a JSONL file).
    Uses Pydantic's .model_dump_json() for robust serialization.

    Raises:
        DataFormattingError: If serialization fails.
    '''
    try:
        return record.model_dump_json(exclude_none=True)
    except Exception as e:
        raise DataFormattingError(f"Failed to serialize record (step_id: {record.step_id}) to JSON: {str(e)}") from e

# --- Example of how one might construct the LLM training string --- 
# This is conceptual and would live elsewhere or be part of a specific dataset generation pipeline step.

def format_for_llm_prompt_completion(
    record: ProcessedDataRecord,
    include_html: bool = True,
    include_image_path: bool = False 
) -> Dict[str, str]:
    '''
    (Conceptual) Formats a ProcessedDataRecord into a prompt/completion pair 
    or a single text string for LLM fine-tuning, based on the PRD's example:
    `<DOM>...HTML content...</DOM><ACTION>click #selector</ACTION>`
    This is a simplified example.
    '''
    if not record.html_content and include_html:
        dom_representation = "<DOM>HTML content not available</DOM>"
    elif include_html:
        dom_representation = f"<DOM>{record.html_content}</DOM>"
    else:
        dom_representation = ""
    
    action_parts = [f"type: {record.action.type}"]
    if record.action.selector:
        action_parts.append(f"selector: {record.action.selector}")
    if record.action.text:
        action_parts.append(f"text: \"{record.action.text}\"")
    action_str = ", ".join(action_parts)
    action_representation = f"<ACTION>{action_str}</ACTION>"
    
    url_representation = f"<URL>{record.url}</URL>"

    image_representation = ""
    if include_image_path and record.screenshot_s3_path:
        image_representation = f"<IMAGE>{record.screenshot_s3_path}</IMAGE>"
    elif include_image_path and record.processed_image_path:
         image_representation = f"<IMAGE>{record.processed_image_path}</IMAGE>"

    full_text = f"{dom_representation}{url_representation}{action_representation}{image_representation}".strip()
    full_text = ' '.join(full_text.split())
    return {"id": record.step_id, "text": full_text}


if __name__ == '__main__':
    # Example Usage:
    sample_action_data_raw: RawStagehandAction = {
        "type": "click",
        "selector": "#button-id",
        "text": "Submit Form",
        "stagehand_metadata": {"confidence": 0.9, "element_visible": True}
    }

    sample_action_detail = ActionDetail(
        type="type", 
        selector="#elem", 
        text="Hello world", 
        stagehand_metadata={"ts": 123}
    )

    print("--- Creating ProcessedDataRecord ---")
    try:
        record = create_processed_data_record(
            step_id="step123",
            session_id="sessABC",
            url="https://example.com",
            ts=1678886400,
            action_data=sample_action_data_raw,
            obs_html_s3_path="s3://mybucket/path/to/page.html.gz",
            screenshot_s3_path="s3://mybucket/path/to/image.webp",
            html_content="<html><body><h1>Hello</h1></body></html>",
            stagehand_task_id="taskXYZ"
        )
        print("Record created successfully:", record)

        print("\\n--- Serializing to JSONL string ---")
        jsonl_string = serialize_record_to_jsonl(record)
        print(jsonl_string)
        decoded_json = json.loads(jsonl_string)
        print("Decoded JSON for verification:", decoded_json)
        assert decoded_json["step_id"] == "step123"

        print("\\n--- Formatting for LLM (conceptual) ---")
        llm_formatted = format_for_llm_prompt_completion(record, include_html=True, include_image_path=True)
        print(llm_formatted)

        print("\\n--- Example of creating with ActionDetail directly ---")
        record_with_action_detail = create_processed_data_record(
            step_id="step456",
            session_id="sessDEF",
            url="http://another.example.com/path",
            ts=1678886500,
            action_data=sample_action_detail,
            html_content="<div>Test</div>"
        )
        print("Record with ActionDetail:", record_with_action_detail)
        print(serialize_record_to_jsonl(record_with_action_detail))

        print("\\n--- Example: Validation Error (invalid URL) ---")
        invalid_action_data = {"type": "scroll"}
        try:
            create_processed_data_record(
                step_id="stepErrHost",
                session_id="sessErr",
                url="not_a_valid_url", # Invalid URL
                ts=1678886400,
                action_data=invalid_action_data
            )
        except DataFormattingError as e:
            print(f"Caught expected formatting error (invalid URL): {e}")
        
        print("\\n--- Example: Validation Error (invalid S3 path) ---")
        try:
            create_processed_data_record(
                step_id="stepErrS3",
                session_id="sessErrS3",
                url="https://example.com/s3error",
                ts=1678886400,
                action_data=sample_action_detail,
                obs_html_s3_path="http://mybucket/path/to/page.html.gz" # Invalid s3 path
            )
        except DataFormattingError as e:
            print(f"Caught expected formatting error (invalid S3): {e}")

    except DataFormattingError as e:
        print(f"An error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error: {e}")