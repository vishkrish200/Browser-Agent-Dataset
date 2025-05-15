'''
Tests for the DatasetBuilder.
'''
import pytest
import os
import json
from unittest.mock import MagicMock, patch, call

from src.dataset_builder.builder import DatasetBuilder
# Assuming other components are imported if needed for mock type hinting or direct use in tests
from src.dataset_builder.image_handler import ImageHandler
from src.dataset_builder.filtering import DataFilter
from src.dataset_builder.splitting import DataSplitter
from src.dataset_builder.formatting import JsonlFormatter
from src.dataset_builder.statistics import DatasetStatistics
from src.dataset_builder.types import ProcessedDataRecord, ActionDetail # For creating mock data

# Sample data (can be expanded)
MOCK_ACTION_1 = ActionDetail(type="click", selector="#btn1")
MOCK_ACTION_2 = ActionDetail(type="type", selector="#input", text="test value")

MOCK_RECORD_1 = ProcessedDataRecord(
    step_id="step_001", 
    session_id="sess_abc", 
    ts=1678886400, 
    action=MOCK_ACTION_1, 
    html_content="<div>Page 1</div>", 
    dom_path="s3://bucket/dom1.html.gz",  # Added .gz to match Pydantic validator
    screenshot_s3_path="s3://bucket/img1.png", 
    pii_safe_html_content="<div>Page 1</div>", 
    url="http://example.com/page1", 
    action_sequence=['click #btn1']
)
MOCK_RECORD_2 = ProcessedDataRecord(
    step_id="step_002", 
    session_id="sess_abc", 
    ts=1678886405, 
    action=MOCK_ACTION_2, 
    html_content="<div>Page 2</div>", 
    dom_path="s3://bucket/dom2.html.gz", # Added .gz
    screenshot_s3_path="s3://bucket/img2.png", 
    pii_safe_html_content="<div>Page 2</div>", 
    url="http://example.com/page2", 
    action_sequence=['type #input value']
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

    # These are the mock objects that will be returned when the builder instantiates them.
    # The mocker.patch calls replace the actual classes in the builder module's namespace.
    patched_image_handler_constructor = mocker.patch('src.dataset_builder.builder.ImageHandler', return_value=mock_image_handler)
    patched_formatter_constructor = mocker.patch('src.dataset_builder.builder.JsonlFormatter', return_value=mock_formatter)
    patched_filter_constructor = mocker.patch('src.dataset_builder.builder.DataFilter', return_value=mock_filter)
    patched_splitter_constructor = mocker.patch('src.dataset_builder.builder.DataSplitter', return_value=mock_splitter)
    patched_stats_constructor = mocker.patch('src.dataset_builder.builder.DatasetStatistics', return_value=mock_stats_generator)
    
    return {
        # Instances that the builder will use
        "image_handler": mock_image_handler,
        "formatter": mock_formatter,
        "filter": mock_filter,
        "splitter": mock_splitter,
        "stats_generator": mock_stats_generator,
        # Patched constructors for asserting calls to __init__
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
        
        # Check components' constructors were called
        mock_builder_components["PatchedImageHandlerConstructor"].assert_called_once()
        mock_builder_components["PatchedJsonlFormatterConstructor"].assert_called_once_with(mock_builder_components["image_handler"])
        mock_builder_components["PatchedDataFilterConstructor"].assert_called_once_with({'filtering': {}})
        mock_builder_components["PatchedDataSplitterConstructor"].assert_called_once()
        mock_builder_components["PatchedDatasetStatisticsConstructor"].assert_called_once()

    def test_initialization_with_filter_config(self, mock_builder_components):
        filter_conf = {"type": "include", "domains": ["example.com"]}
        builder = DatasetBuilder(config={"filtering": filter_conf})
        # Check that the DataFilter constructor was called with the correct config
        mock_builder_components["PatchedDataFilterConstructor"].assert_called_once_with(filter_conf)

    @patch('src.dataset_builder.builder.os.makedirs')
    @patch('src.dataset_builder.builder.open', new_callable=MagicMock)
    @patch('src.dataset_builder.builder.json.dump')
    def test_build_dataset_flow_with_data(
        self, mock_json_dump, mock_open, mock_makedirs, mock_builder_components, tmp_path
    ):
        builder = DatasetBuilder()
        
        # Setup mocks for component methods
        mock_filter = mock_builder_components["filter"]
        mock_splitter = mock_builder_components["splitter"]
        mock_formatter = mock_builder_components["formatter"]
        mock_stats_generator = mock_builder_components["stats_generator"]

        mock_input_path = "s3://input-data/"
        mock_output_dir = str(tmp_path / "output_dataset")

        # Mock data loading
        builder._load_processed_data = MagicMock(return_value=MOCK_RECORDS)
        
        # Mock filter to return a subset of records
        filtered_subset = [MOCK_RECORD_1]
        mock_filter.filter_records.return_value = filtered_subset
        
        # Mock splitter to return train/val
        train_subset = [MOCK_RECORD_1] # Assume it all goes to train for this simple test
        val_subset = []
        mock_splitter.split_data.return_value = (train_subset, val_subset)
        
        # Mock stats generator
        mock_stats_data = {"total_records": 1, "actions": 5}
        mock_stats_generator.generate_stats.return_value = mock_stats_data

        # Call build_dataset
        builder.build_dataset(
            input_path=mock_input_path, 
            output_path=mock_output_dir, 
            include_images=True, 
            train_split=0.8,
            filter_options={"some_filter": "value"}
        )

        # Assertions
        builder._load_processed_data.assert_called_once_with(mock_input_path)
        
        mock_filter.update_config.assert_called_once_with({"some_filter": "value"})
        mock_filter.filter_records.assert_called_once_with(MOCK_RECORDS)
        
        mock_splitter.split_data.assert_called_once_with(filtered_subset, 0.8)
        
        mock_makedirs.assert_called_once_with(mock_output_dir, exist_ok=True)
        
        expected_train_path = os.path.join(mock_output_dir, "train.jsonl")
        expected_val_path = os.path.join(mock_output_dir, "validation.jsonl") # Will not be called if val_subset is empty
        expected_stats_path = os.path.join(mock_output_dir, "dataset_stats.json")

        mock_formatter.write_to_jsonl.assert_any_call(train_subset, expected_train_path, True)
        # If val_subset is empty, write_to_jsonl for validation should not be called
        # Check if it was called for validation, if val_subset was non-empty
        # For this test, val_subset is [], so no call for validation.
        
        mock_stats_generator.generate_stats.assert_called_once_with(filtered_subset, include_images=True)
        
        mock_open.assert_called_once_with(expected_stats_path, 'w')
        mock_json_dump.assert_called_once_with(mock_stats_data, mock_open().__enter__(), indent=4)

    @patch('src.dataset_builder.builder.os.makedirs')
    @patch('src.dataset_builder.builder.open', new_callable=MagicMock)
    @patch('src.dataset_builder.builder.json.dump')
    def test_build_dataset_no_input_data(
        self, mock_json_dump, mock_open, mock_makedirs, mock_builder_components, tmp_path
    ):
        builder = DatasetBuilder()
        mock_output_dir = str(tmp_path / "empty_dataset")
        builder._load_processed_data = MagicMock(return_value=[]) # No data loaded
        
        mock_filter = mock_builder_components["filter"]
        mock_splitter = mock_builder_components["splitter"]
        mock_formatter = mock_builder_components["formatter"]
        mock_stats_generator = mock_builder_components["stats_generator"]
        mock_filter.filter_records.return_value = [] # Filter will also return empty
        mock_splitter.split_data.return_value = ([], [])


        builder.build_dataset(input_path="any_input", output_path=mock_output_dir)

        mock_makedirs.assert_called_once_with(mock_output_dir, exist_ok=True)
        mock_formatter.write_to_jsonl.assert_not_called() # No records to write
        mock_stats_generator.generate_stats.assert_not_called() # No records for stats
        mock_json_dump.assert_not_called() # No stats to dump

    @patch('src.dataset_builder.builder.os.makedirs')
    @patch('src.dataset_builder.builder.open', new_callable=MagicMock)
    @patch('src.dataset_builder.builder.json.dump')
    def test_build_dataset_invalid_train_split(
        self, mock_json_dump, mock_open, mock_makedirs, mock_builder_components, tmp_path
    ):
        builder = DatasetBuilder()
        mock_output_dir = str(tmp_path / "split_test_dataset")
        builder._load_processed_data = MagicMock(return_value=MOCK_RECORDS)

        mock_filter = mock_builder_components["filter"]
        mock_splitter = mock_builder_components["splitter"] # We test its call, not its return for this
        mock_formatter = mock_builder_components["formatter"]
        
        mock_filter.filter_records.return_value = MOCK_RECORDS # Assume all pass filter

        # Test with train_split = 0 (disable split, all to train)
        builder.build_dataset(input_path="in", output_path=mock_output_dir, train_split=0.0)
        mock_splitter.split_data.assert_not_called() # Should not be called if split is invalid
        # formatter should be called with all MOCK_RECORDS for train
        expected_train_path = os.path.join(mock_output_dir, "train.jsonl")
        mock_formatter.write_to_jsonl.assert_any_call(MOCK_RECORDS, expected_train_path, False) # include_images defaults to False

        # Reset mocks for next call if necessary (or use separate tests)
        mock_splitter.reset_mock()
        mock_formatter.reset_mock()

        # Test with train_split = 1.0 (disable split, all to train)
        builder.build_dataset(input_path="in", output_path=mock_output_dir, train_split=1.0)
        mock_splitter.split_data.assert_not_called()
        mock_formatter.write_to_jsonl.assert_any_call(MOCK_RECORDS, expected_train_path, False)

        # Test with train_split > 1.0 (invalid)
        mock_splitter.reset_mock()
        mock_formatter.reset_mock()
        builder.build_dataset(input_path="in", output_path=mock_output_dir, train_split=1.1)
        mock_splitter.split_data.assert_not_called()
        mock_formatter.write_to_jsonl.assert_any_call(MOCK_RECORDS, expected_train_path, False)
        
        # Test with train_split < 0 (invalid)
        mock_splitter.reset_mock()
        mock_formatter.reset_mock()
        builder.build_dataset(input_path="in", output_path=mock_output_dir, train_split=-0.1)
        mock_splitter.split_data.assert_not_called()
        mock_formatter.write_to_jsonl.assert_any_call(MOCK_RECORDS, expected_train_path, False)

# Add more tests for different scenarios, edge cases, and integration points. 

class TestDatasetBuilderIntegration:
    """Integration tests for the DatasetBuilder pipeline."""

    @pytest.fixture
    def integration_builder(self) -> DatasetBuilder:
        """Provides a DatasetBuilder instance with real components for integration testing."""
        # For now, initialize with default config. 
        # ImageHandler will use local processing by default if s3_bucket_name is not set.
        # We can customize this further if tests need specific S3 interactions (and mock S3).
        return DatasetBuilder(config={})

    @pytest.fixture
    def sample_records_for_integration(self) -> list[ProcessedDataRecord]:
        """Provides a list of sample ProcessedDataRecord objects for integration tests."""
        action1 = ActionDetail(type="click", selector="#button-submit", text="Submit")
        record1 = ProcessedDataRecord(
            step_id="integ_step_001",
            session_id="integ_sess_alpha",
            ts=1700000000,
            action=action1,
            html_content="<html><body><button id=\"button-submit\">Submit</button></body></html>",
            screenshot_s3_path=None, # No image for this basic test
            url="http://example.com/form",
            action_sequence=['click #button-submit']
        )

        action2 = ActionDetail(type="type", selector="#username", text="testuser")
        record2 = ProcessedDataRecord(
            step_id="integ_step_002",
            session_id="integ_sess_alpha",
            ts=1700000005,
            action=action2,
            html_content="<html><body><input id=\"username\" type=\"text\"/></body></html>",
            screenshot_s3_path=None,
            url="http://example.com/login",
            action_sequence=['type #username testuser']
        )
        return [record1, record2]

    def test_build_dataset_basic_flow(self, integration_builder: DatasetBuilder, sample_records_for_integration: list[ProcessedDataRecord], tmp_path):
        """Test the basic end-to-end flow of build_dataset with real components."""
        output_dir = tmp_path / "integration_output"
        
        # Patch _load_processed_data to inject our sample records
        with patch.object(integration_builder, '_load_processed_data', return_value=sample_records_for_integration) as mock_load:
            integration_builder.build_dataset(
                input_path="dummy_input_path", # Will be ignored by the mock
                output_path=str(output_dir),
                include_images=False, # Keep it simple for the first test
                train_split=1.0,      # All data goes to train.jsonl, no validation split
                filter_options=None   # No specific filtering
            )
            mock_load.assert_called_once_with("dummy_input_path")

        # Verify output files exist
        train_jsonl_path = output_dir / "train.jsonl"
        stats_json_path = output_dir / "dataset_stats.json"
        assert train_jsonl_path.exists()
        assert stats_json_path.exists()

        # Verify train.jsonl content (basic check)
        train_lines = []
        with open(train_jsonl_path, 'r') as f:
            for line in f:
                train_lines.append(json.loads(line))
        
        assert len(train_lines) == len(sample_records_for_integration)
        assert train_lines[0]["step_id"] == sample_records_for_integration[0].step_id
        assert train_lines[1]["step_id"] == sample_records_for_integration[1].step_id
        assert train_lines[0]["action"]["selector"] == sample_records_for_integration[0].action.selector

        # Verify dataset_stats.json content (basic check)
        with open(stats_json_path, 'r') as f:
            stats_data = json.load(f)
        
        assert stats_data["total_records"] == len(sample_records_for_integration)
        assert "action_type_distribution" in stats_data
        assert stats_data["action_type_distribution"]["click"] == 1
        assert stats_data["action_type_distribution"]["type"] == 1
        assert "domain_distribution" in stats_data
        assert stats_data["domain_distribution"]["example.com"] == 2

    def test_build_dataset_with_train_val_split(self, integration_builder: DatasetBuilder, sample_records_for_integration: list[ProcessedDataRecord], tmp_path):
        """Test build_dataset creates train and validation splits correctly."""
        output_dir = tmp_path / "integration_output_split"
        train_ratio = 0.5 # Split 2 records into 1 train, 1 val

        # Add more records to make splitting more meaningful if sample_records_for_integration is too small
        # For this test, 2 records with 0.5 split is fine for a basic check.
        
        with patch.object(integration_builder, '_load_processed_data', return_value=sample_records_for_integration):
            integration_builder.build_dataset(
                input_path="dummy_input_path",
                output_path=str(output_dir),
                include_images=False,
                train_split=train_ratio,
                filter_options=None
            )

        train_jsonl_path = output_dir / "train.jsonl"
        val_jsonl_path = output_dir / "validation.jsonl"
        stats_json_path = output_dir / "dataset_stats.json"

        assert train_jsonl_path.exists()
        assert val_jsonl_path.exists()
        assert stats_json_path.exists()

        train_lines = []
        with open(train_jsonl_path, 'r') as f:
            for line in f: train_lines.append(json.loads(line))
        
        val_lines = []
        with open(val_jsonl_path, 'r') as f:
            for line in f: val_lines.append(json.loads(line))

        # Based on DataSplitter's current random split, exact counts can vary if not seeded.
        # For a robust test, we'd either need to seed DataSplitter or check total and relative counts.
        # DataSplitter is seeded by default, so this should be deterministic.
        assert len(train_lines) == 1
        assert len(val_lines) == 1
        assert len(train_lines) + len(val_lines) == len(sample_records_for_integration)

        # Verify stats still cover all (pre-split) filtered records
        with open(stats_json_path, 'r') as f:
            stats_data = json.load(f)
        assert stats_data["total_records"] == len(sample_records_for_integration)

    def test_build_dataset_with_filtering(self, integration_builder: DatasetBuilder, sample_records_for_integration: list[ProcessedDataRecord], tmp_path):
        """Test build_dataset with domain filtering."""
        output_dir = tmp_path / "integration_output_filter"
        
        # Create a more diverse sample set for filtering
        action_other_domain = ActionDetail(type="scroll", selector="window")
        record_other_domain = ProcessedDataRecord(
            step_id="integ_step_003",
            session_id="integ_sess_beta",
            ts=1700000010,
            action=action_other_domain,
            html_content="<html><body>Scrollable content</body></html>",
            url="http://otherdomain.com/scroll",
            screenshot_s3_path=None,
            action_sequence=['scroll window']
        )
        extended_samples = sample_records_for_integration + [record_other_domain] # Total 3 records

        filter_opts = {
            "rules": [
                {"field": "url", "type": "domain_match", "value": "example.com"}
            ],
            "strategy": "include_match" # Include if any rule matches
        }

        with patch.object(integration_builder, '_load_processed_data', return_value=extended_samples):
            integration_builder.build_dataset(
                input_path="dummy_input_path",
                output_path=str(output_dir),
                include_images=False,
                train_split=1.0, # All to train for simplicity
                filter_options=filter_opts
            )

        train_jsonl_path = output_dir / "train.jsonl"
        stats_json_path = output_dir / "dataset_stats.json"
        assert train_jsonl_path.exists()
        assert stats_json_path.exists()

        train_lines = []
        with open(train_jsonl_path, 'r') as f:
            for line in f: train_lines.append(json.loads(line))
        
        # Only the 2 records from example.com should remain
        assert len(train_lines) == 2 
        for record_dict in train_lines:
            assert "example.com" in record_dict["url"]
            assert record_dict["step_id"].startswith("integ_step_00") # From original sample_records_for_integration

        # Stats should reflect the count after filtering
        with open(stats_json_path, 'r') as f:
            stats_data = json.load(f)
        assert stats_data["total_records"] == 2
        assert stats_data["domain_distribution"]["example.com"] == 2
        assert "otherdomain.com" not in stats_data["domain_distribution"] 

    def test_build_dataset_include_images_flag(self, integration_builder: DatasetBuilder, tmp_path):
        """Test how include_images=True affects formatter and statistics."""
        output_dir = tmp_path / "integration_output_images"

        action1 = ActionDetail(type="click", selector="#img-link")
        record_with_image = ProcessedDataRecord(
            step_id="img_step_001", session_id="img_sess_A", ts=1700000100, action=action1,
            html_content="<body><img src='some_image.png'/></body>", url="http://imagesite.com/page1",
            screenshot_s3_path="s3://imagebucket/screenshots/image1.webp" # Has an image path
        )
        action2 = ActionDetail(type="type", selector="#text-input", text="no image here")
        record_without_image = ProcessedDataRecord(
            step_id="no_img_step_002", session_id="img_sess_A", ts=1700000105, action=action2,
            html_content="<body><input type='text'/></body>", url="http://imagesite.com/page2",
            screenshot_s3_path=None # No image path
        )
        image_test_records = [record_with_image, record_without_image]

        with patch.object(integration_builder, '_load_processed_data', return_value=image_test_records):
            integration_builder.build_dataset(
                input_path="dummy_input_path",
                output_path=str(output_dir),
                include_images=True, # Key part of this test
                train_split=1.0, 
                filter_options=None
            )
        
        train_jsonl_path = output_dir / "train.jsonl"
        stats_json_path = output_dir / "dataset_stats.json"
        assert train_jsonl_path.exists()
        assert stats_json_path.exists()

        train_lines = []
        with open(train_jsonl_path, 'r') as f:
            for line in f: train_lines.append(json.loads(line))
        
        assert len(train_lines) == 2
        
        # Check record_with_image output
        # JsonlFormatter should add 'dataset_image_reference' based on screenshot_s3_path
        # when include_images is True.
        record1_output = next(r for r in train_lines if r["step_id"] == "img_step_001")
        assert "dataset_image_reference" in record1_output
        assert record1_output["dataset_image_reference"] == record_with_image.screenshot_s3_path
        assert record1_output.get("screenshot_s3_path") == record_with_image.screenshot_s3_path # Original should also be there

        # Check record_without_image output
        record2_output = next(r for r in train_lines if r["step_id"] == "no_img_step_002")
        assert "dataset_image_reference" not in record2_output # Should not be present if original path was None
        assert record2_output.get("screenshot_s3_path") is None

        # Verify dataset_stats.json content for image stats
        with open(stats_json_path, 'r') as f:
            stats_data = json.load(f)
        
        assert stats_data["total_records"] == 2
        assert stats_data.get("records_with_images") == 1 # DatasetStatistics should count this
        assert stats_data.get("records_without_images") == 1 