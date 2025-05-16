'''
Tests for the DatasetBuilder.
'''
import pytest
import os
import json
from unittest.mock import MagicMock, patch, call
import shutil
import tempfile
import boto3 # Added for S3
from moto import mock_aws # Added for S3 mocking
from botocore.exceptions import ClientError # Added for S3 errors

from src.dataset_builder.builder import DatasetBuilder
# Assuming other components are imported if needed for mock type hinting or direct use in tests
from src.dataset_builder.image_handler import ImageHandler
from src.dataset_builder.filtering import DataFilter
from src.dataset_builder.splitting import DataSplitter
from src.dataset_builder.formatting import JsonlFormatter
from src.dataset_builder.statistics import DatasetStatistics
from src.dataset_builder.types import ProcessedDataRecord, ActionDetail # For creating mock data
from pydantic import HttpUrl
from src.storage_manager.storage import StorageManager, ACTION_DATA_FILENAME # Added for S3 tests
from src.storage_manager.exceptions import S3OperationError # Added for S3 tests

# Sample data (can be expanded)
MOCK_ACTION_1 = ActionDetail(type="click", selector="#btn1")
MOCK_ACTION_2 = ActionDetail(type="type", selector="#input", text="test value")

MOCK_RECORD_1 = ProcessedDataRecord(
    step_id="step_001", 
    session_id="sess_abc", 
    ts=1678886400, 
    action=MOCK_ACTION_1, 
    html_content="<div>Page 1</div>", 
    obs_html_s3_path="s3://bucket/dom1.html.gz",
    screenshot_s3_path="s3://bucket/img1.png", 
    url="http://example.com/page1", 
)
MOCK_RECORD_2 = ProcessedDataRecord(
    step_id="step_002", 
    session_id="sess_abc", 
    ts=1678886405, 
    action=MOCK_ACTION_2, 
    html_content="<div>Page 2</div>", 
    obs_html_s3_path="s3://bucket/dom2.html.gz",
    screenshot_s3_path="s3://bucket/img2.png", 
    url="http://example.com/page2", 
)

MOCK_RECORDS = [MOCK_RECORD_1, MOCK_RECORD_2]

@pytest.fixture
def mock_builder_components(mocker):
    """Mocks all components initialized by DatasetBuilder."""
    mock_image_handler = mocker.MagicMock(spec=ImageHandler)
    mock_formatter = mocker.MagicMock(spec=JsonlFormatter)
    mock_filter = mocker.MagicMock(spec=DataFilter)
    mock_splitter = mocker.MagicMock(spec=DataSplitter)
    mock_stats_generator = mocker.MagicMock(spec=DatasetStatistics)

    patched_image_handler_constructor = mocker.patch('src.dataset_builder.builder.ImageHandler', return_value=mock_image_handler)
    patched_formatter_constructor = mocker.patch('src.dataset_builder.builder.JsonlFormatter', return_value=mock_formatter)
    patched_filter_constructor = mocker.patch('src.dataset_builder.builder.DataFilter', return_value=mock_filter)
    patched_splitter_constructor = mocker.patch('src.dataset_builder.builder.DataSplitter', return_value=mock_splitter)
    patched_stats_constructor = mocker.patch('src.dataset_builder.builder.DatasetStatistics', return_value=mock_stats_generator)
    
    return {
        "image_handler": mock_image_handler,
        "formatter": mock_formatter,
        "filter": mock_filter,
        "splitter": mock_splitter,
        "stats_generator": mock_stats_generator,
        "PatchedImageHandlerConstructor": patched_image_handler_constructor,
        "PatchedJsonlFormatterConstructor": patched_formatter_constructor,
        "PatchedDataFilterConstructor": patched_filter_constructor,
        "PatchedDataSplitterConstructor": patched_splitter_constructor,
        "PatchedDatasetStatisticsConstructor": patched_stats_constructor
    }

class TestDatasetBuilderUnit:
    def test_initialization(self, mock_builder_components):
        """Test DatasetBuilder initializes its components."""
        builder = DatasetBuilder(config={"some_config": "value"})
        assert builder.config == {"some_config": "value"}
        assert builder.image_handler is mock_builder_components["image_handler"]
        assert builder.formatter is mock_builder_components["formatter"]
        assert builder.filter is mock_builder_components["filter"]
        assert builder.splitter is mock_builder_components["splitter"]
        assert builder.stats_generator is mock_builder_components["stats_generator"]
        
        mock_builder_components["PatchedImageHandlerConstructor"].assert_called_once()
        mock_builder_components["PatchedJsonlFormatterConstructor"].assert_called_once_with(mock_builder_components["image_handler"]) 
        mock_builder_components["PatchedDataFilterConstructor"].assert_called_once_with({'filtering': {}})
        mock_builder_components["PatchedDataSplitterConstructor"].assert_called_once()
        mock_builder_components["PatchedDatasetStatisticsConstructor"].assert_called_once()

    def test_initialization_with_filter_config(self, mock_builder_components):
        filter_conf = {"type": "include", "domains": ["example.com"]}
        builder = DatasetBuilder(config={"filtering": filter_conf})
        mock_builder_components["PatchedDataFilterConstructor"].assert_called_once_with(filter_conf)

    @patch('src.dataset_builder.builder.os.makedirs')
    @patch('src.dataset_builder.builder.open', new_callable=MagicMock)
    @patch('src.dataset_builder.builder.json.dump')
    async def test_build_dataset_flow_with_data(
        self, mock_json_dump, mock_open, mock_makedirs, mock_builder_components, tmp_path
    ):
        builder = DatasetBuilder()
        
        mock_filter = mock_builder_components["filter"]
        mock_splitter = mock_builder_components["splitter"]
        mock_formatter = mock_builder_components["formatter"]
        mock_stats_generator = mock_builder_components["stats_generator"]

        mock_input_path = "s3://input-data/"
        mock_output_dir = str(tmp_path / "output_dataset")

        builder._load_processed_data = MagicMock()
        builder._load_processed_data.return_value = MOCK_RECORDS
        
        filtered_subset = [MOCK_RECORD_1]
        mock_filter.filter_records.return_value = filtered_subset
        
        train_subset = [MOCK_RECORD_1]
        val_subset = []
        mock_splitter.split_data.return_value = (train_subset, val_subset)
        
        mock_stats_data = {"total_records": 1, "actions": {"click": 1} } 
        mock_stats_generator.calculate_statistics.return_value = mock_stats_data

        await builder.build_dataset(
            input_path=mock_input_path, 
            output_path=mock_output_dir, 
            include_images=True, 
            train_split=0.8,
            filter_options={"some_filter": "value"}
        )

        builder._load_processed_data.assert_called_once_with(mock_input_path)
        
        mock_filter.update_config.assert_called_once_with({"some_filter": "value"})
        mock_filter.filter_records.assert_called_once_with(MOCK_RECORDS)
        
        mock_splitter.split_data.assert_called_once_with(filtered_subset, 0.8)
        
        mock_makedirs.assert_called_once_with(mock_output_dir, exist_ok=True)
        
        expected_train_path = os.path.join(mock_output_dir, "train.jsonl")
        expected_stats_path = os.path.join(mock_output_dir, "dataset_stats.json")

        mock_formatter.write_to_jsonl.assert_called_once_with(train_subset, expected_train_path, True)
        mock_stats_generator.calculate_statistics.assert_called_once_with(filtered_subset)
        
        mock_open.assert_called_once_with(expected_stats_path, 'w')
        mock_json_dump.assert_called_once_with(mock_stats_data, mock_open().__enter__(), indent=4)

    @patch('src.dataset_builder.builder.os.makedirs')
    @patch('src.dataset_builder.builder.open', new_callable=MagicMock)
    @patch('src.dataset_builder.builder.json.dump')
    async def test_build_dataset_no_input_data(
        self, mock_json_dump, mock_open, mock_makedirs, mock_builder_components, tmp_path
    ):
        builder = DatasetBuilder()
        mock_output_dir = str(tmp_path / "empty_dataset")
        builder._load_processed_data = MagicMock()
        builder._load_processed_data.return_value = []
        
        mock_filter = mock_builder_components["filter"]
        mock_splitter = mock_builder_components["splitter"]
        mock_formatter = mock_builder_components["formatter"]
        mock_stats_generator = mock_builder_components["stats_generator"]
        mock_filter.filter_records.return_value = []
        mock_splitter.split_data.return_value = ([], [])

        await builder.build_dataset(input_path="any_input", output_path=mock_output_dir)

        mock_makedirs.assert_called_once_with(mock_output_dir, exist_ok=True)
        mock_formatter.write_to_jsonl.assert_not_called()
        mock_stats_generator.calculate_statistics.assert_not_called() 
        mock_json_dump.assert_not_called()

    @patch('src.dataset_builder.builder.os.makedirs')
    @patch('src.dataset_builder.builder.open', new_callable=MagicMock)
    @patch('src.dataset_builder.builder.json.dump')
    async def test_build_dataset_invalid_train_split(
        self, mock_json_dump, mock_open, mock_makedirs, mock_builder_components, tmp_path
    ):
        builder = DatasetBuilder()
        mock_output_dir = str(tmp_path / "invalid_split_dataset")
        builder._load_processed_data = MagicMock()
        builder._load_processed_data.return_value = MOCK_RECORDS
        
        mock_filter = mock_builder_components["filter"]
        mock_filter.filter_records.return_value = MOCK_RECORDS
        mock_splitter = mock_builder_components["splitter"]
        mock_formatter = mock_builder_components["formatter"]
        mock_stats_generator = mock_builder_components["stats_generator"]
        mock_stats_generator.calculate_statistics.return_value = {"total": len(MOCK_RECORDS)}

        await builder.build_dataset(input_path="any", output_path=mock_output_dir, train_split=0)
        
        mock_splitter.split_data.assert_not_called()
        expected_train_path = os.path.join(mock_output_dir, "train.jsonl")
        mock_formatter.write_to_jsonl.assert_called_once_with(MOCK_RECORDS, expected_train_path, False)
        val_path = os.path.join(mock_output_dir, "validation.jsonl")
        assert not os.path.exists(val_path)
        mock_formatter.reset_mock()

        output_dir_split1 = str(tmp_path / "invalid_split_dataset_1")
        await builder.build_dataset(input_path="any", output_path=output_dir_split1, train_split=1)
        mock_splitter.split_data.assert_not_called()
        expected_train_path_1 = os.path.join(output_dir_split1, "train.jsonl")
        mock_formatter.write_to_jsonl.assert_called_once_with(MOCK_RECORDS, expected_train_path_1, False)
        val_path_1 = os.path.join(output_dir_split1, "validation.jsonl")
        assert not os.path.exists(val_path_1)

MOCK_S3_TEST_BUCKET = "test-builder-s3-bucket"

@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    yield
    del os.environ["AWS_ACCESS_KEY_ID"]
    del os.environ["AWS_SECRET_ACCESS_KEY"]
    del os.environ["AWS_SECURITY_TOKEN"]
    del os.environ["AWS_SESSION_TOKEN"]
    del os.environ["AWS_DEFAULT_REGION"]

@pytest.fixture(scope="function")
def s3_mock(aws_credentials):
    """Sets up a mock S3 environment for a test function."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        try:
            s3.create_bucket(Bucket=MOCK_S3_TEST_BUCKET)
            print(f"Mock S3 bucket '{MOCK_S3_TEST_BUCKET}' created for test function.")
        except ClientError as e:
            if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
                print(f"Mock S3 bucket '{MOCK_S3_TEST_BUCKET}' already exists for test function.")
            else:
                raise
        yield s3 # Provides the s3 client to the test

@pytest.fixture
def s3_storage_manager(s3_mock): # Depends on s3_mock to ensure moto is active and bucket exists
    """Provides a StorageManager instance configured for S3 integration tests."""
    # s3_mock ensures that boto3.client will use the mock S3
    manager = StorageManager(
        s3_bucket_name=MOCK_S3_TEST_BUCKET,
        s3_region_name="us-east-1", # Match aws_credentials
        prefer_s3=True
    )
    assert manager.use_s3, "StorageManager should be configured to use S3 for these tests."
    return manager

@pytest.fixture
def s3_dataset_builder(s3_storage_manager) -> DatasetBuilder:
    """Provides a DatasetBuilder instance initialized with an S3-enabled StorageManager."""
    # Pass the S3-enabled storage_manager to the builder
    return DatasetBuilder(storage_manager=s3_storage_manager)

class TestDatasetBuilderIntegration:
    @pytest.fixture
    def integration_builder(self) -> DatasetBuilder:
        return DatasetBuilder(config={})

    @pytest.fixture
    def sample_records_for_integration(self) -> list[ProcessedDataRecord]:
        return [
            ProcessedDataRecord(
                step_id="integ_step1", session_id="integ_sess_A", ts=1700000000, 
                action=ActionDetail(type="click", selector="#button-shop"), 
                url="http://shop.example.com/home",
                obs_html_s3_path="s3://integ-bucket/html/s1.html.gz",
                screenshot_s3_path="s3://integ-bucket/imgs/s1.webp"
            ),
            ProcessedDataRecord(
                step_id="integ_step2", session_id="integ_sess_A", ts=1700000005, 
                action=ActionDetail(type="type", selector="#search", text="gadget"), 
                url="http://shop.example.com/search?q=gadget",
                obs_html_s3_path="s3://integ-bucket/html/s2.html.gz",
                screenshot_s3_path=None
            ),
             ProcessedDataRecord(
                step_id="integ_step3", session_id="integ_sess_B", ts=1700000010, 
                action=ActionDetail(type="click", selector="#login-link"), 
                url="http://auth.example.com/login",
                obs_html_s3_path="s3://integ-bucket/html/s3.html.gz",
                screenshot_s3_path="s3://integ-bucket/imgs/s3.webp"
            )
        ]

    @pytest.mark.asyncio # All tests in this class are now async due to build_dataset
    async def test_build_dataset_basic_flow(self, integration_builder: DatasetBuilder, sample_records_for_integration: list[ProcessedDataRecord], tmp_path):
        output_dir = tmp_path / "integration_output_basic"
        integration_builder._load_processed_data = MagicMock()
        integration_builder._load_processed_data.return_value = sample_records_for_integration

        await integration_builder.build_dataset(
            input_path="dummy_input_path",
            output_path=str(output_dir),
            include_images=False,
            train_split=1.0,
            filter_options=None
        )

        train_jsonl_path = output_dir / "train.jsonl"
        stats_json_path = output_dir / "dataset_stats.json"

        assert train_jsonl_path.exists()
        assert stats_json_path.exists()
        assert not (output_dir / "validation.jsonl").exists()

        train_lines = []
        with open(train_jsonl_path, 'r') as f:
            for line in f: train_lines.append(json.loads(line))
        assert len(train_lines) == len(sample_records_for_integration)

        with open(stats_json_path, 'r') as f:
            stats_data = json.load(f)
        assert stats_data["total_records"] == len(sample_records_for_integration)

    @pytest.mark.asyncio
    async def test_build_dataset_with_train_val_split(self, integration_builder: DatasetBuilder, sample_records_for_integration: list[ProcessedDataRecord], tmp_path):
        output_dir = tmp_path / "integration_output_split"
        integration_builder._load_processed_data = MagicMock()
        integration_builder._load_processed_data.return_value = sample_records_for_integration

        train_ratio = 0.6
        num_total = len(sample_records_for_integration)
        num_train = int(num_total * train_ratio)
        train_ratio_for_2_1_split = 2/3
        num_train_expected = 2
        num_val_expected = 1

        await integration_builder.build_dataset(
            input_path="dummy",
            output_path=str(output_dir),
            train_split=train_ratio_for_2_1_split 
        )

        train_jsonl_path = output_dir / "train.jsonl"
        val_jsonl_path = output_dir / "validation.jsonl"
        assert train_jsonl_path.exists()
        assert val_jsonl_path.exists()

        with open(train_jsonl_path, 'r') as f:
            train_lines = [json.loads(line) for line in f]
        with open(val_jsonl_path, 'r') as f:
            val_lines = [json.loads(line) for line in f]
        
        assert len(train_lines) == num_train_expected
        assert len(val_lines) == num_val_expected

    @pytest.mark.asyncio
    async def test_build_dataset_with_filtering(self, integration_builder: DatasetBuilder, sample_records_for_integration: list[ProcessedDataRecord], tmp_path):
        output_dir = tmp_path / "integration_output_filter"
        integration_builder._load_processed_data = MagicMock()
        integration_builder._load_processed_data.return_value = sample_records_for_integration
        
        filter_opts = {"domain_allowlist": ["shop.example.com"]}

        await integration_builder.build_dataset(
            input_path="dummy",
            output_path=str(output_dir),
            train_split=1.0,
            filter_options=filter_opts
        )
        
        train_jsonl_path = output_dir / "train.jsonl"
        assert train_jsonl_path.exists()
        with open(train_jsonl_path, 'r') as f:
            train_lines = [json.loads(line) for line in f]
        
        assert len(train_lines) == 2 
        for record_output in train_lines:
            assert "shop.example.com" in record_output["text"]

    @pytest.mark.asyncio
    async def test_build_dataset_include_images_flag(self, integration_builder: DatasetBuilder, tmp_path):
        mock_input_dir = tmp_path / "image_flag_input"
        mock_input_dir.mkdir()
        mock_output_dir = tmp_path / "image_flag_output"

        record_with_image = ProcessedDataRecord(
            step_id="img_step1", session_id="s1", url=HttpUrl("http://example.com/img"), ts=123,
            action=ActionDetail(type="capture"),
            screenshot_s3_path="s3://bucket/img.png"
        )
        record_no_image = ProcessedDataRecord(
            step_id="noimg_step1", session_id="s2", url=HttpUrl("http://example.com/noimg"), ts=124,
            action=ActionDetail(type="click"),
            screenshot_s3_path=None
        )
        records = [record_with_image, record_no_image]
        integration_builder._load_processed_data = MagicMock()
        integration_builder._load_processed_data.return_value = records
        
        actual_formatter = integration_builder.formatter
        
        with patch.object(actual_formatter, 'write_to_jsonl', wraps=actual_formatter.write_to_jsonl) as mock_write_method:
            await integration_builder.build_dataset(
                input_path=str(mock_input_dir),
                output_path=str(mock_output_dir),
                include_images=True, 
                train_split=1.0 
            )
            mock_write_method.assert_any_call(
                records, 
                os.path.join(str(mock_output_dir), "train.jsonl"),
                True 
            )

            mock_write_method.reset_mock()
            await integration_builder.build_dataset(
                input_path=str(mock_input_dir),
                output_path=str(mock_output_dir / "subdir"), 
                include_images=False, 
                train_split=1.0
            )
            mock_write_method.assert_any_call(
                records,
                os.path.join(str(mock_output_dir / "subdir"), "train.jsonl"),
                False 
            )

    def test_load_processed_data_local_files(self, integration_builder: DatasetBuilder, tmp_path):
        """Tests the _load_processed_data method with local JSON files."""
        sample_input_dir = tmp_path / "sample_input_data"
        sample_input_dir.mkdir()

        record1_data = {
            "step_id": "load_step1", "session_id": "s_load", "url": "http://example.com/load1", "ts": 123,
            "action": {"type": "load_click"}, "screenshot_s3_path": "s3://bucket/load1.webp"
        }
        record2_data = {
            "step_id": "load_step2", "session_id": "s_load", "url": "http://example.com/load2", "ts": 124,
            "action": {"type": "load_type", "text": "test"}
            # No screenshot_s3_path
        }
        # Malformed record
        record3_malformed = {
            "step_id": "load_step3", "url": "not_a_valid_url", "ts": "not_an_int",
            "action": {}
        }

        # File 1 with valid records
        with open(sample_input_dir / "data1.json", "w") as f:
            json.dump([record1_data, record2_data], f)

        # File 2 with one valid and one malformed record
        record_valid_in_file2 = {
            "step_id": "load_step4", "session_id": "s_load_f2", "url": "http://example.com/load4", "ts": 125,
            "action": {"type": "scroll"}, "obs_html_s3_path": "s3://bucket/html/load4.html.gz"
        }
        with open(sample_input_dir / "data2.json", "w") as f:
            json.dump([record_valid_in_file2, record3_malformed], f)

        # File 3 not a list
        with open(sample_input_dir / "data3.json", "w") as f:
            json.dump({"not_a": "list"}, f)
        
        # File 4 invalid json
        with open(sample_input_dir / "data4.json", "w") as f:
            f.write("this is not json")
        
        # Non-json file to be ignored
        with open(sample_input_dir / "data.txt", "w") as f:
            f.write("ignore me")

        loaded_records = integration_builder._load_processed_data(str(sample_input_dir))
        
        assert len(loaded_records) == 3 # record1_data, record2_data, record_valid_in_file2
        step_ids_loaded = {r.step_id for r in loaded_records}
        assert "load_step1" in step_ids_loaded
        assert "load_step2" in step_ids_loaded
        assert "load_step4" in step_ids_loaded

        # Test with a non-existent directory
        non_existent_dir = tmp_path / "non_existent"
        loaded_non_existent = integration_builder._load_processed_data(str(non_existent_dir))
        assert len(loaded_non_existent) == 0

        # Test with a file path instead of a directory
        file_instead_of_dir = sample_input_dir / "data1.json"
        loaded_file_path = integration_builder._load_processed_data(str(file_instead_of_dir))
        assert len(loaded_file_path) == 0

    @pytest.mark.asyncio
    async def test_load_processed_data_from_s3(self, s3_dataset_builder: DatasetBuilder, s3_mock):
        """Tests loading ProcessedDataRecord objects from S3 via _load_processed_data."""
        builder = s3_dataset_builder
        sm = builder.storage_manager
        assert sm is not None, "StorageManager not initialized in s3_dataset_builder"
        assert sm.use_s3, "StorageManager in s3_dataset_builder is not configured for S3"
        
        bucket_name = sm.s3_bucket_name
        assert bucket_name == MOCK_S3_TEST_BUCKET, "S3 bucket name mismatch"

        s3_base_prefix = "test_input_data_s3"

        # Prepare some mock data to upload to S3
        record_s3_1_data = {
            "step_id": "s3_step1", "session_id": "s3_sessA", "url": "http://s3.example.com/page1", "ts": 1700000100,
            "action": {"type": "s3_click"}, "screenshot_s3_path": f"s3://{bucket_name}/{s3_base_prefix}/s3_sessA/s3_step1/screen.webp"
        }
        record_s3_2_data = {
            "step_id": "s3_step2", "session_id": "s3_sessA", "url": "http://s3.example.com/page2", "ts": 1700000105,
            "action": {"type": "s3_type", "text": "from s3"}
        }
        record_s3_3_data_malformed_action = { # Missing 'type' in action
            "step_id": "s3_step3_malformed_action", "session_id": "s3_sessB", "url": "http://s3.example.com/malformed_action", "ts": 1700000110,
            "action": {"selector": "#bad"} 
        }
        record_s3_4_valid_other_session = {
            "step_id": "s3_step4_valid", "session_id": "s3_sessB", "url": "http://s3.example.com/page4", "ts": 1700000115,
            "action": {"type": "scroll_s3"}, "obs_html_s3_path": f"s3://{bucket_name}/{s3_base_prefix}/s3_sessB/s3_step4_valid/obs.html.gz"
        }

        # Upload these as action.json files to mock S3 structure
        s3_paths_to_upload = [
            (f"{s3_base_prefix}/s3_sessA/s3_step1/{ACTION_DATA_FILENAME}", record_s3_1_data),
            (f"{s3_base_prefix}/s3_sessA/s3_step2/{ACTION_DATA_FILENAME}", record_s3_2_data),
            (f"{s3_base_prefix}/s3_sessB/s3_step3_malformed_action/{ACTION_DATA_FILENAME}", record_s3_3_data_malformed_action),
            (f"{s3_base_prefix}/s3_sessB/s3_step4_valid/{ACTION_DATA_FILENAME}", record_s3_4_valid_other_session),
        ]

        for s3_key, data_dict in s3_paths_to_upload:
            s3_mock.put_object(Bucket=bucket_name, Key=s3_key, Body=json.dumps(data_dict).encode('utf-8'))
            print(f"Uploaded mock data to s3://{bucket_name}/{s3_key}")

        # Add a file that is not ACTION_DATA_FILENAME to ensure it's ignored by the listing logic if it were to list all files
        s3_mock.put_object(Bucket=bucket_name, Key=f"{s3_base_prefix}/s3_sessA/s3_step1/other_file.txt", Body="ignore_me")
        
        # Test loading from the S3 prefix
        s3_input_uri = f"s3://{bucket_name}/{s3_base_prefix}"
        loaded_records = await builder._load_processed_data(s3_input_uri)

        assert len(loaded_records) == 2, "Should load 2 valid records (s3_step1, s3_step2, s3_step4_valid) and skip 1 malformed (s3_step3_malformed_action due to Pydantic validation)"
        # Pydantic validation for ActionDetail(type=...) will fail for s3_step3_malformed_action

        loaded_step_ids = {r.step_id for r in loaded_records}
        assert "s3_step1" in loaded_step_ids
        assert "s3_step2" in loaded_step_ids
        assert "s3_step4_valid" in loaded_step_ids
        assert "s3_step3_malformed_action" not in loaded_step_ids # This should be skipped due to parsing/validation error

        # Test loading from a non-existent S3 prefix
        non_existent_s3_uri = f"s3://{bucket_name}/this_prefix_does_not_exist"
        loaded_empty = await builder._load_processed_data(non_existent_s3_uri)
        assert len(loaded_empty) == 0

        # Test with S3 list_objects error (mocking StorageManager's list_sessions to raise S3OperationError)
        with patch.object(sm, 'list_sessions', side_effect=S3OperationError("Simulated S3 list error")):
            loaded_s3_error = await builder._load_processed_data(s3_input_uri)
            assert len(loaded_s3_error) == 0 # Should return empty list on S3 listing error

        # Test with S3 download error for one of the files
        # To do this, we need to let list_sessions and list_steps_for_session succeed,
        # but make _download_from_s3 fail for a specific key.
        # This is more complex to set up without altering the original S3 mock data.
        # For now, rely on _load_processed_data_from_s3's internal try-except for download issues.
        # A more granular mock would be needed for _download_from_s3 within StorageManager.
        # The current implementation of _load_processed_data_from_s3 logs warnings for failed downloads/parses.

    @pytest.mark.asyncio
    async def test_build_dataset_s3_output(self, s3_dataset_builder: DatasetBuilder, s3_mock, sample_records_for_integration):
        """Tests build_dataset writing output to S3."""
        builder = s3_dataset_builder
        sm = builder.storage_manager
        bucket_name = sm.s3_bucket_name

        s3_output_prefix = "test_output_s3"
        s3_output_uri = f"s3://{bucket_name}/{s3_output_prefix}"

        # Mock _load_processed_data to provide consistent input
        builder._load_processed_data = MagicMock()
        builder._load_processed_data.return_value = sample_records_for_integration # Use the existing sample records

        # Run build_dataset with S3 output path
        await builder.build_dataset(
            input_path="dummy_local_or_s3_input", # This is mocked, so value doesn't strictly matter
            output_path=s3_output_uri,
            include_images=False,
            train_split=0.67 # Approx 2/3 for 3 records -> 2 train, 1 val
        )

        # Verify files were written to S3
        expected_train_key = f"{s3_output_prefix}/train.jsonl".strip("/")
        expected_val_key = f"{s3_output_prefix}/validation.jsonl".strip("/")
        expected_stats_key = f"{s3_output_prefix}/dataset_stats.json".strip("/")

        # Check train.jsonl
        try:
            train_obj = s3_mock.get_object(Bucket=bucket_name, Key=expected_train_key)
            train_content = train_obj['Body'].read().decode('utf-8')
            train_lines = [json.loads(line) for line in train_content.strip().split('\n')]
            assert len(train_lines) == 2 # Based on 3 records and ~0.67 split
        except ClientError as e:
            pytest.fail(f"Failed to get train.jsonl from S3: {e}")

        # Check validation.jsonl
        try:
            val_obj = s3_mock.get_object(Bucket=bucket_name, Key=expected_val_key)
            val_content = val_obj['Body'].read().decode('utf-8')
            val_lines = [json.loads(line) for line in val_content.strip().split('\n')]
            assert len(val_lines) == 1
        except ClientError as e:
            pytest.fail(f"Failed to get validation.jsonl from S3: {e}")

        # Check dataset_stats.json
        try:
            stats_obj = s3_mock.get_object(Bucket=bucket_name, Key=expected_stats_key)
            stats_content = json.loads(stats_obj['Body'].read().decode('utf-8'))
            assert stats_content["total_records"] == len(sample_records_for_integration)
            # Add more assertions for stats content if needed
        except ClientError as e:
            pytest.fail(f"Failed to get dataset_stats.json from S3: {e}")

        # Test case: S3 output but StorageManager not configured for S3 (should log error and not write)
        builder_no_s3_sm = DatasetBuilder() # Uses default SM, likely local
        builder_no_s3_sm._load_processed_data = MagicMock(return_value=sample_records_for_integration)
        
        s3_output_uri_fail = f"s3://another-bucket/output_fail"
        # Clear S3 mock before this call to ensure no objects are written if it tries
        # This part is tricky because s3_mock is function-scoped. We can't easily "clear" it here.
        # Instead, we check that no calls to _upload_to_s3 were made on builder_no_s3_sm.storage_manager.
        # However, that storage_manager is internal. A better test would be to configure it with a MagicMock SM.

        # For now, we can check that the original s3_mock (from the fixture) does not contain new files
        # under 'another-bucket/output_fail' after this call. This is an indirect check.
        with patch.object(builder_no_s3_sm.storage_manager, '_upload_to_s3') as mock_upload_fail_sm:
            await builder_no_s3_sm.build_dataset(
                input_path="dummy", 
                output_path=s3_output_uri_fail, 
                train_split=1.0
            )
            mock_upload_fail_sm.assert_not_called() # Ensure no S3 upload was attempted

        # Test case: S3 upload fails during write
        builder._load_processed_data = MagicMock(return_value=sample_records_for_integration)
        with patch.object(builder.storage_manager, '_upload_to_s3', side_effect=S3OperationError("Simulated S3 Upload Error")):
            # Expect it to log errors, but not necessarily raise the S3OperationError from build_dataset directly,
            # as build_dataset might catch and log it.
            # For now, just ensure it runs without unhandled exceptions here. Error handling can be refined.
            await builder.build_dataset(
                input_path="dummy",
                output_path=s3_output_uri, # Use the valid S3 URI for this test
                train_split=1.0
            )
            # Assert that logs contain warnings/errors about failed S3 uploads (requires caplog fixture)