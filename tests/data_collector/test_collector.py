import pytest
import uuid
import datetime
from unittest import mock # For patching and AsyncMock
from typing import Optional, Dict, Any
import logging
import json

from src.data_collector import DataCollector, StepData, DataCollectionError, StorageConfig, ConfigurationError
from src.data_collector.types import ActionData # Import ActionData explicitly
from src.data_collector.storage import StorageBackend, LocalStorage # Import LocalStorage for type check
from src.data_collector.exceptions import StorageError
from src.browserbase_client import BrowserbaseClient
from src.stagehand_client import StagehandClient
from src.data_collector import config as collector_module_config # For default configs

@pytest.fixture
def mock_bb_client():
    return mock.AsyncMock(spec=BrowserbaseClient)

@pytest.fixture
def mock_sh_client():
    return mock.AsyncMock(spec=StagehandClient)

@pytest.fixture
def mock_storage_backend():
    mock_be = mock.AsyncMock(spec=StorageBackend)
    mock_be.store_artifact = mock.AsyncMock(return_value="mock/stored/path/to/artifact")
    return mock_be

@pytest.fixture
def basic_storage_config() -> StorageConfig:
    return {"type": "local", "base_path": "./test_collector_output"} # Path for dummy local storage

@pytest.fixture
@mock.patch('src.data_collector.collector.get_storage_backend')
def data_collector_with_mocks(mock_get_storage, mock_bb_client, mock_sh_client, mock_storage_backend, basic_storage_config: StorageConfig):
    mock_get_storage.return_value = mock_storage_backend
    return DataCollector(
        browserbase_client=mock_bb_client, 
        stagehand_client=mock_sh_client,
        storage_config=basic_storage_config
    )


# --- Initialization Tests ---
def test_datacollector_initialization(data_collector_with_mocks: DataCollector, mock_bb_client, mock_sh_client, mock_storage_backend):
    assert data_collector_with_mocks.browserbase_client == mock_bb_client
    assert data_collector_with_mocks.stagehand_client == mock_sh_client
    assert data_collector_with_mocks.storage_backend == mock_storage_backend
    assert data_collector_with_mocks.artifact_settings == collector_module_config.DEFAULT_ARTIFACT_COLLECTION_CONFIG

def test_datacollector_init_default_storage(mock_bb_client, mock_sh_client):
    # Test that it defaults to local storage if no config provided
    with mock.patch('src.data_collector.collector.get_storage_backend') as mock_get_be:
        mock_local_be = mock.AsyncMock(spec=LocalStorage)
        mock_get_be.return_value = mock_local_be
        
        collector = DataCollector(browserbase_client=mock_bb_client, stagehand_client=mock_sh_client, storage_config=None)
        assert isinstance(collector.storage_backend, mock.AsyncMock) # Check it's the mock
        mock_get_be.assert_called_once()
        called_config = mock_get_be.call_args[0][0]
        assert called_config['type'] == collector_module_config.DEFAULT_STORAGE_TYPE
        if collector_module_config.DEFAULT_STORAGE_TYPE == 'local':
            assert called_config['base_path'] == collector_module_config.DEFAULT_LOCAL_STORAGE_BASE_PATH

def test_datacollector_init_invalid_clients():
    with pytest.raises(ConfigurationError, match="requires a valid BrowserbaseClient"):
        DataCollector(browserbase_client=None, stagehand_client=mock.AsyncMock(spec=StagehandClient)) # type: ignore
    with pytest.raises(ConfigurationError, match="requires a valid StagehandClient"):
        DataCollector(browserbase_client=mock.AsyncMock(spec=BrowserbaseClient), stagehand_client=None) # type: ignore

# --- Helper Method Tests ---
def test_generate_step_id(data_collector_with_mocks: DataCollector):
    with mock.patch('uuid.uuid4', return_value=uuid.UUID('12345678-1234-5678-1234-567812345678')) as mock_uuid:
        step_id = data_collector_with_mocks._generate_step_id()
        assert step_id == "12345678-1234-5678-1234-567812345678"
        mock_uuid.assert_called_once()

# --- configure_browserbase_session_for_recording Tests ---
@pytest.mark.asyncio
async def test_configure_browserbase_session(data_collector_with_mocks: DataCollector, caplog):
    # It's a placeholder, so just check it logs and returns True
    with caplog.at_level(logging.INFO): # Ensure INFO level logs are captured
        result = await data_collector_with_mocks.configure_browserbase_session_for_recording("sess_test_config")
    
    assert result is True
    
    # Check for specific records
    assert any(
        "Placeholder: Configuring Browserbase session sess_test_config for recording" in record.message and 
        record.levelname == "INFO"
        for record in caplog.records
    )
    assert any(
        "configure_browserbase_session_for_recording is a placeholder and not yet implemented" in record.message and 
        record.levelname == "WARNING"
        for record in caplog.records
    )

# --- collect_step_data Tests ---
@pytest.fixture
def sample_action_data() -> ActionData:
    return ActionData(type="click", selector="#button", text=None, url=None, stagehand_metadata={"foo": "bar"})

@pytest.mark.asyncio
async def test_collect_step_data_success_all_artifacts(
    data_collector_with_mocks: DataCollector, 
    mock_storage_backend: mock.AsyncMock, 
    sample_action_data: ActionData
):
    session_id = "sess_collect_all"
    url = "https://example.com/page1"
    html_content = "<html></html>"
    screenshot_bytes = b"webp_image_data"

    # Ensure store_artifact returns unique paths for different artifacts for verification
    def store_side_effect(session_id, step_id, artifact_name, data, is_gzipped=False):
        return f"mock_path/{artifact_name}"
    mock_storage_backend.store_artifact.side_effect = store_side_effect

    step_data = await data_collector_with_mocks.collect_step_data(
        browserbase_session_id=session_id,
        current_url=url,
        action_data=sample_action_data,
        stagehand_task_id="sh_task_1",
        stagehand_execution_id="sh_exec_1",
        html_content=html_content,
        screenshot_bytes=screenshot_bytes
    )

    assert step_data["session_id"] == session_id
    assert step_data["url"] == url
    assert step_data["action"] == sample_action_data
    assert step_data["stagehand_task_id"] == "sh_task_1"
    assert step_data["stagehand_execution_id"] == "sh_exec_1"
    assert isinstance(uuid.UUID(step_data["step_id"]), uuid.UUID) # Check it's a valid UUID string
    assert isinstance(datetime.datetime.fromisoformat(step_data["ts"]), datetime.datetime)

    expected_html_name = f"{step_data['step_id']}_page.html.gz"
    expected_ss_name = f"{step_data['step_id']}_screenshot.webp"
    expected_action_name = f"{step_data['step_id']}_action.json"

    assert step_data["obs_html_gz_path"] == f"mock_path/{expected_html_name}"
    assert step_data["screenshot_webp_path"] == f"mock_path/{expected_ss_name}"
    # Action JSON is stored, its path would be in logs, not directly in StepData by default per current StepData type

    mock_storage_backend.store_artifact.assert_any_call(
        session_id=session_id, step_id=step_data["step_id"], artifact_name=expected_html_name, data=html_content, is_gzipped=False
    )
    mock_storage_backend.store_artifact.assert_any_call(
        session_id=session_id, step_id=step_data["step_id"], artifact_name=expected_ss_name, data=screenshot_bytes, is_gzipped=False
    )
    mock_storage_backend.store_artifact.assert_any_call(
        session_id=session_id, step_id=step_data["step_id"], artifact_name=expected_action_name, data=mock.ANY # json string
    )
    assert mock_storage_backend.store_artifact.call_count == 3

@pytest.mark.asyncio
async def test_collect_step_data_partial_collection(
    data_collector_with_mocks: DataCollector, 
    mock_storage_backend: mock.AsyncMock, 
    sample_action_data: ActionData
):
    """Test collection when some artifacts are None or settings disable them."""
    data_collector_with_mocks.artifact_settings = {"html_content": True, "screenshot_webp": False, "action_data": True}
    
    step_data = await data_collector_with_mocks.collect_step_data(
        browserbase_session_id="sess_partial",
        current_url="https://example.com/partial",
        action_data=sample_action_data,
        html_content="<p>only html</p>",
        screenshot_bytes=None # No screenshot provided
    )
    assert step_data["obs_html_gz_path"] is not None
    assert step_data["screenshot_webp_path"] is None # Due to setting or None input
    
    calls = mock_storage_backend.store_artifact.call_args_list
    assert len(calls) == 2 # HTML and Action JSON
    assert any(expected_html_name in call_args[1]['artifact_name'] for call_args in calls for expected_html_name in [f"{step_data['step_id']}_page.html.gz"])
    assert any(expected_action_name in call_args[1]['artifact_name'] for call_args in calls for expected_action_name in [f"{step_data['step_id']}_action.json"])

@pytest.mark.asyncio
async def test_collect_step_data_storage_failure_one_artifact(
    data_collector_with_mocks: DataCollector, 
    mock_storage_backend: mock.AsyncMock, 
    sample_action_data: ActionData,
    caplog
):
    """Test when storing one artifact fails, others should still be attempted."""
    html_content = "<html></html>"
    screenshot_bytes = b"webp_data"
    
    # Setup for a more robust side_effect function
    side_effect_call_tracker = {'count': 0}
    predictable_step_id_for_effect = str(uuid.uuid4()) # Fixed step_id for this test
    
    # Mock _generate_step_id on the instance to return our predictable_step_id
    data_collector_with_mocks._generate_step_id = mock.MagicMock(return_value=predictable_step_id_for_effect)

    # Corrected signature to match keyword arguments from store_artifact call
    def store_side_effect_func(session_id, step_id, artifact_name, data, is_gzipped=False):
        side_effect_call_tracker['count'] += 1
        current_call = side_effect_call_tracker['count']
        
        assert step_id == predictable_step_id_for_effect # Check against the predictable_step_id_for_effect

        if current_call == 1: # HTML call
            assert "_page.html.gz" in artifact_name, f"Expected HTML artifact, got {artifact_name}"
            raise StorageError("Failed to store HTML")
        elif current_call == 2: # Screenshot call
            assert "_screenshot.webp" in artifact_name, f"Expected screenshot, got {artifact_name}"
            return f"mock_path/{artifact_name}"
        elif current_call == 3: # Action JSON call
            assert "_action.json" in artifact_name, f"Expected action JSON, got {artifact_name}"
            return f"mock_path/{artifact_name}"
        else:
            pytest.fail(f"store_artifact called unexpectedly {current_call} times.")
    
    mock_storage_backend.store_artifact.side_effect = store_side_effect_func

    with caplog.at_level(logging.ERROR):
        step_data = await data_collector_with_mocks.collect_step_data(
            browserbase_session_id="sess_store_fail",
            current_url="https://example.com/store_fail",
            action_data=sample_action_data,
            html_content=html_content,
            screenshot_bytes=screenshot_bytes
        )

    assert step_data["obs_html_gz_path"] is None # Failed due to raise in side_effect
    assert step_data["screenshot_webp_path"] == f"mock_path/{predictable_step_id_for_effect}_screenshot.webp"
    # Action JSON path isn't directly in StepData by default, but its storage call should have succeeded.
    # The side_effect_func would have asserted its artifact_name.

    assert "Failed to store HTML artifact: Failed to store HTML" in caplog.text
    assert mock_storage_backend.store_artifact.call_count == 3 # All 3 attempted
    # Verify the arguments for the successful calls (screenshot and action json)
    # Call args are (session_id, step_id, artifact_name, data, is_gzipped)
    
    # Screenshot call (was the 2nd call to the mock)
    screenshot_call_args = mock_storage_backend.store_artifact.call_args_list[1].kwargs # Check kwargs
    assert screenshot_call_args['session_id'] == "sess_store_fail"
    assert screenshot_call_args['step_id'] == predictable_step_id_for_effect
    assert screenshot_call_args['artifact_name'] == f"{predictable_step_id_for_effect}_screenshot.webp"
    assert screenshot_call_args['data'] == screenshot_bytes
    assert screenshot_call_args['is_gzipped'] is False

    # Action JSON call (was the 3rd call to the mock)
    action_json_call_args = mock_storage_backend.store_artifact.call_args_list[2].kwargs # Check kwargs
    assert action_json_call_args['session_id'] == "sess_store_fail"
    assert action_json_call_args['step_id'] == predictable_step_id_for_effect
    assert action_json_call_args['artifact_name'] == f"{predictable_step_id_for_effect}_action.json"
    assert isinstance(action_json_call_args['data'], str)
    # A more robust check for action data content:
    action_data_dict_from_call = json.loads(action_json_call_args['data'])
    assert action_data_dict_from_call == sample_action_data # Compare the dicts 