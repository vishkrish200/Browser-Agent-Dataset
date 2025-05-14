'''
Tests for dataset formatting utilities.
'''
import pytest
import json
from pydantic import HttpUrl

from src.dataset_builder.formatting import (
    create_processed_data_record,
    serialize_record_to_jsonl,
    format_for_llm_prompt_completion,
    DataFormattingError
)
from src.dataset_builder.types import ProcessedDataRecord, ActionDetail, RawStagehandAction

@pytest.fixture
def sample_raw_action_data() -> RawStagehandAction:
    return {
        "type": "click",
        "selector": "#submit-button",
        "text": "Submit",
        "stagehand_metadata": {"element_is_visible": True, "confidence_score": 0.95}
    }

@pytest.fixture
def sample_action_detail() -> ActionDetail:
    return ActionDetail(
        type="input",
        selector="input[name='email']",
        text="test@example.com",
        stagehand_metadata={"source": "human-annotated"}
    )

@pytest.fixture
def valid_record_params(sample_raw_action_data) -> dict:
    return {
        "step_id": "test_step_001",
        "session_id": "test_session_abc",
        "url": "https://example.com/page1",
        "ts": 1678886400,
        "action_data": sample_raw_action_data,
        "obs_html_s3_path": "s3://my-bucket/html/step001.html.gz",
        "screenshot_s3_path": "s3://my-bucket/screenshots/step001.webp",
        "html_content": "<html><body><p>Test HTML content</p></body></html>",
        "stagehand_task_id": "task_12345"
    }

class TestDataFormatting:
    def test_create_processed_data_record_success(self, valid_record_params):
        record = create_processed_data_record(**valid_record_params)
        assert isinstance(record, ProcessedDataRecord)
        assert record.step_id == valid_record_params["step_id"]
        assert record.url == HttpUrl(valid_record_params["url"]) # Pydantic converts to HttpUrl
        assert isinstance(record.action, ActionDetail)
        assert record.action.type == valid_record_params["action_data"]["type"]
        assert record.html_content is not None

    def test_create_record_with_action_detail_instance(self, valid_record_params, sample_action_detail):
        params = valid_record_params.copy()
        params["action_data"] = sample_action_detail # Pass pre-validated ActionDetail
        record = create_processed_data_record(**params)
        assert isinstance(record, ProcessedDataRecord)
        assert record.action == sample_action_detail

    def test_create_record_optional_fields_none(self, valid_record_params):
        params = valid_record_params.copy()
        params["obs_html_s3_path"] = None
        params["screenshot_s3_path"] = None
        params["html_content"] = None
        params["stagehand_task_id"] = None
        record = create_processed_data_record(**params)
        assert record.obs_html_s3_path is None
        assert record.html_content is None
        assert record.stagehand_task_id is None

    def test_create_record_invalid_url(self, valid_record_params):
        params = valid_record_params.copy()
        params["url"] = "ftp://invalid-url-scheme.com"
        with pytest.raises(DataFormattingError) as exc_info:
            create_processed_data_record(**params)
        assert "Validation failed" in str(exc_info.value)
        # Simpler check for the relevant error message parts
        error_string = str(exc_info.value)
        assert "url" in error_string and "URL scheme not permitted" in error_string

    def test_create_record_invalid_s3_path(self, valid_record_params):
        params = valid_record_params.copy()
        params["obs_html_s3_path"] = "http://my-bucket/html/step001.html.gz" # Invalid scheme
        with pytest.raises(DataFormattingError) as exc_info:
            create_processed_data_record(**params)
        assert "Validation failed" in str(exc_info.value)
        # Simpler check for the relevant error message parts
        error_string = str(exc_info.value)
        assert "obs_html_s3_path" in error_string and "S3 path must start with s3://" in error_string

    def test_create_record_malformed_action_data(self, valid_record_params):
        params = valid_record_params.copy()
        params["action_data"] = {"type": "click", "unexpected_field": "some_value"} # type is ActionDetail so ActionDetail(**action_data) will fail
        # ActionDetail does not have `unexpected_field`
        with pytest.raises(DataFormattingError) as exc_info:
             create_processed_data_record(**params)
        assert "Could not parse action_data into ActionDetail" in str(exc_info.value) 
        
    def test_serialize_record_to_jsonl_success(self, valid_record_params):
        record = create_processed_data_record(**valid_record_params)
        jsonl_string = serialize_record_to_jsonl(record)
        assert isinstance(jsonl_string, str)
        try:
            data = json.loads(jsonl_string)
        except json.JSONDecodeError:
            pytest.fail("Serialized string is not valid JSON")
        
        assert data["step_id"] == valid_record_params["step_id"]
        assert data["url"] == valid_record_params["url"] # Pydantic serializes HttpUrl to str
        assert data["action"]["type"] == valid_record_params["action_data"]["type"]
        assert "html_content" in data # exclude_none=True by default in Pydantic 2.x model_dump_json if field is None
        assert data["html_content"] == valid_record_params["html_content"]
        assert "stagehand_task_id" in data

    def test_serialize_record_optional_fields_none(self, valid_record_params):
        params = valid_record_params.copy()
        params["html_content"] = None
        params["obs_html_s3_path"] = None # This will be excluded by exclude_none=True
        params["screenshot_s3_path"] = None # Excluded
        params["stagehand_task_id"] = None # Excluded

        record = create_processed_data_record(**params)
        jsonl_string = serialize_record_to_jsonl(record)
        data = json.loads(jsonl_string)

        assert "html_content" not in data # If it was None and exclude_none=True
        assert "obs_html_s3_path" not in data
        assert "screenshot_s3_path" not in data
        assert "stagehand_task_id" not in data
        assert data["step_id"] == params["step_id"]
        
    def test_format_for_llm_prompt_completion_basic(self, valid_record_params):
        record = create_processed_data_record(**valid_record_params)
        llm_data = format_for_llm_prompt_completion(record, include_html=True, include_image_path=False)
        assert llm_data["id"] == record.step_id
        assert "<DOM>" in llm_data["text"]
        assert record.html_content in llm_data["text"]
        assert "<ACTION>" in llm_data["text"]
        assert record.action.type in llm_data["text"]
        assert "<URL>" in llm_data["text"]
        assert str(record.url) in llm_data["text"]
        assert "<IMAGE>" not in llm_data["text"]

    def test_format_for_llm_include_image(self, valid_record_params):
        record = create_processed_data_record(**valid_record_params)
        llm_data = format_for_llm_prompt_completion(record, include_html=False, include_image_path=True)
        assert "<DOM>" not in llm_data["text"]
        assert "<IMAGE>" in llm_data["text"]
        assert record.screenshot_s3_path in llm_data["text"]

    def test_format_for_llm_html_not_available(self, valid_record_params):
        params = valid_record_params.copy()
        params["html_content"] = None
        record = create_processed_data_record(**params)
        llm_data = format_for_llm_prompt_completion(record, include_html=True)
        assert "<DOM>HTML content not available</DOM>" in llm_data["text"]

# Add more tests for various data cleaning, transformation, and normalization rules. 