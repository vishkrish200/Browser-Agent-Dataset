'''
Handles formatting of raw data into structured ProcessedDataRecord objects
and serializing them to JSONL strings.
'''
import json
from typing import Dict, Any, Optional, Union, List
import logging
import os
from pydantic import ValidationError

from .types import ProcessedDataRecord, ActionDetail, RawStagehandAction
from .exceptions import DataFormattingError, FormattingError
from .image_handler import ImageHandler

logger = logging.getLogger(__name__)

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
        logger.error(f"Failed to serialize record (step_id: {record.step_id}) to JSON: {str(e)}", exc_info=True)
        raise DataFormattingError(f"Failed to serialize record (step_id: {record.step_id}) to JSON: {str(e)}") from e

# --- Example of how one might construct the LLM training string --- 
# This is conceptual and would live elsewhere or be part of a specific dataset generation pipeline step.

def format_for_llm_prompt_completion(
    record: ProcessedDataRecord,
    include_html: bool = True,
    include_image_path: bool = False, 
    image_handler: Optional[ImageHandler] = None
) -> Dict[str, str]:
    '''
    (Conceptual) Formats a ProcessedDataRecord into a prompt/completion pair 
    or a single text string for LLM fine-tuning, based on the PRD's example:
    `<DOM>...HTML content...</DOM><ACTION>click #selector</ACTION>`
    This is a simplified example.
    '''
    current_image_handler = image_handler if image_handler else ImageHandler()

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
    if include_image_path:
        img_ref = current_image_handler.get_image_reference(record)
        if img_ref:
            image_representation = f"<IMAGE>{img_ref}</IMAGE>"
        # else: image_representation remains "" if no valid reference found

    full_text = f"{dom_representation}{url_representation}{action_representation}{image_representation}".strip()
    full_text = ' '.join(full_text.split())
    return {"id": record.step_id, "text": full_text}

class JsonlFormatter:
    """Handles formatting and writing ProcessedDataRecord objects to JSONL files."""

    def __init__(self, image_handler: ImageHandler):
        """
        Initializes the JsonlFormatter.

        Args:
            image_handler: An instance of ImageHandler, used if image information
                           needs to be processed or included during formatting.
        """
        if not isinstance(image_handler, ImageHandler):
            # This check is more for robustness, type hinting should help.
            raise TypeError("image_handler must be an instance of ImageHandler.")
        self.image_handler = image_handler
        logger.info("JsonlFormatter initialized.")

    def format_record(self, record: ProcessedDataRecord, include_images: bool = False) -> Dict[str, Any]:
        """
        Formats a single ProcessedDataRecord into a dictionary suitable for JSONL.
        This version will primarily rely on Pydantic's model_dump, but could be
        extended to include image data or transform fields.

        Args:
            record: The ProcessedDataRecord to format.
            include_images: If True, attempts to include image-related information.
                            (Exact implementation of image inclusion depends on requirements)

        Returns:
            A dictionary representation of the record.
        """
        # Using model_dump for a dictionary representation
        # exclude_none=True is good for keeping JSONL clean
        record_dict = record.model_dump(exclude_none=True)

        if include_images:
            # Example: Add a direct reference or processed image data if required.
            # For now, let's assume image_handler.get_image_reference provides the path.
            # The ProcessedDataRecord already has screenshot_s3_path.
            # If include_images meant embedding actual image data (e.g., base64),
            # that logic would go here using self.image_handler.
            # For this iteration, we'll assume the path in the record is sufficient if present.
            # If an image was processed and a *new* path was generated, that should be in the record.
            img_ref = self.image_handler.get_image_reference(record)
            if img_ref:
                # Could add a specific field like 'image_reference_for_dataset' if different from original
                record_dict['dataset_image_reference'] = img_ref 
            logger.debug(f"Image inclusion requested for record {record.step_id}. Ref: {img_ref}")
        
        return record_dict


    def write_to_jsonl(self, records: List[ProcessedDataRecord], output_file_path: str, include_images: bool = False):
        """
        Writes a list of ProcessedDataRecord objects to a JSONL file.

        Args:
            records: A list of ProcessedDataRecord objects.
            output_file_path: The path to the output JSONL file.
            include_images: Passed to format_record if specific image handling is needed.

        Raises:
            FormattingError: If writing to the file fails.
        """
        logger.info(f"Writing {len(records)} records to JSONL file: {output_file_path}. Include images: {include_images}")
        try:
            os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
            with open(output_file_path, 'w', encoding='utf-8') as f:
                for record in records:
                    try:
                        # Using serialize_record_to_jsonl ensures Pydantic's robust JSON export
                        # which handles HttpUrl and other custom types correctly.
                        json_string = serialize_record_to_jsonl(record)
                        f.write(json_string + '\n')
                    except DataFormattingError as e:
                        logger.error(f"Skipping record {record.step_id} due to serialization error: {e}", exc_info=True)
                    except Exception as e_inner: # Catch any other unexpected error during individual record processing
                        logger.error(f"Skipping record {record.step_id} due to unexpected error during serialization: {e_inner}", exc_info=True)
            logger.info(f"Successfully wrote {len(records)} records to {output_file_path}")
        except IOError as e:
            logger.error(f"IOError writing to JSONL file {output_file_path}: {e}", exc_info=True)
            raise FormattingError(f"Could not write to JSONL file {output_file_path}: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error writing to JSONL file {output_file_path}: {e}", exc_info=True)
            raise FormattingError(f"An unexpected error occurred while writing to {output_file_path}: {e}") from e

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

        print("\n--- Serializing to JSONL string ---")
        jsonl_string = serialize_record_to_jsonl(record)
        print(jsonl_string)
        decoded_json = json.loads(jsonl_string)
        print("Decoded JSON for verification:", decoded_json)
        assert decoded_json["step_id"] == "step123"

        print("\n--- Formatting for LLM (conceptual) ---")
        llm_formatted = format_for_llm_prompt_completion(record, include_html=True, include_image_path=True)
        print(llm_formatted)

        print("\n--- Example of creating with ActionDetail directly ---")
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

        print("\n--- Example: Validation Error (invalid URL) ---")
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
        
        print("\n--- Example: Validation Error (invalid S3 path) ---")
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