'''
Tests for dataset splitting utilities.
'''
import pytest
from typing import List, Dict
from src.dataset_builder.splitting import DataSplitter
from src.dataset_builder.types import ProcessedDataRecord, ActionDetail # Adjust import as needed
from src.dataset_builder.exceptions import DataSplittingError

# Dummy ProcessedDataRecord for testing
def create_dummy_record(record_id: int) -> ProcessedDataRecord:
    return ProcessedDataRecord(
        step_id=f"step_{record_id}",       # Corrected field name and made value more distinct
        session_id=f"session_abc_{record_id // 10}",  # Corrected field name and made value more distinct
        ts=1672531200 + record_id,
        url=f"http://example.com/page{record_id}",
        html_content=f"<html><body>Page {record_id}</body></html>",
        action=ActionDetail(type="click", selector=f"//button[@id='btn{record_id}']"),
        image_s3_path=f"s3://bucket/image{record_id}.webp"
    )

@pytest.fixture
def sample_records() -> List[ProcessedDataRecord]:
    return [create_dummy_record(i) for i in range(100)]

class TestDataSplitter:
    def test_split_data_default_ratios(self, sample_records: List[ProcessedDataRecord]):
        splitter = DataSplitter(random_seed=42)
        splits = splitter.split_data(sample_records)

        assert len(splits["train"]) == 80
        assert len(splits["validation"]) == 10
        assert len(splits["test"]) == 10
        # Check for no overlap and all records present
        all_split_ids = set(r.step_id for r in splits["train"]) \
                        | set(r.step_id for r in splits["validation"]) \
                        | set(r.step_id for r in splits["test"])
        original_ids = set(r.step_id for r in sample_records)
        assert all_split_ids == original_ids

    def test_split_data_custom_ratios(self, sample_records: List[ProcessedDataRecord]):
        splitter = DataSplitter(random_seed=123)
        splits = splitter.split_data(
            sample_records, train_ratio=0.7, validation_ratio=0.15, test_ratio=0.15
        )
        assert len(splits["train"]) == 70
        assert len(splits["validation"]) == 15
        assert len(splits["test"]) == 15

    def test_split_data_reproducibility(self, sample_records: List[ProcessedDataRecord]):
        splitter1 = DataSplitter(random_seed=42)
        splits1 = splitter1.split_data(sample_records)

        splitter2 = DataSplitter(random_seed=42)
        splits2 = splitter2.split_data(sample_records)

        assert [r.step_id for r in splits1["train"]] == [r.step_id for r in splits2["train"]]
        assert [r.step_id for r in splits1["validation"]] == [r.step_id for r in splits2["validation"]]
        assert [r.step_id for r in splits1["test"]] == [r.step_id for r in splits2["test"]]

    def test_split_data_no_seed(self, sample_records: List[ProcessedDataRecord]):
        # This test is statistical, might occasionally fail but should usually pass if shuffling is random
        splitter1 = DataSplitter() # No seed
        splits1 = splitter1.split_data(sample_records)

        splitter2 = DataSplitter() # No seed
        splits2 = splitter2.split_data(sample_records)

        # Highly unlikely to be the same if shuffling is truly random without a seed
        # unless the dataset is very small or random number generator cycles quickly.
        # For a dataset of 100, this should almost always be different.
        assert [r.step_id for r in splits1["train"]] != [r.step_id for r in splits2["train"]]

    def test_split_data_empty_list(self):
        splitter = DataSplitter()
        with pytest.raises(DataSplittingError, match="Input data_records list cannot be empty."):
            splitter.split_data([])

    def test_split_data_invalid_ratios_sum(self, sample_records: List[ProcessedDataRecord]):
        splitter = DataSplitter()
        with pytest.raises(DataSplittingError, match="Sum of split ratios must be 1.0"):
            splitter.split_data(sample_records, train_ratio=0.7, validation_ratio=0.1, test_ratio=0.1)

    def test_split_data_negative_ratios(self, sample_records: List[ProcessedDataRecord]):
        splitter = DataSplitter()
        with pytest.raises(DataSplittingError, match="Split ratios must be non-negative."):
            splitter.split_data(sample_records, train_ratio=-0.1, validation_ratio=1.0, test_ratio=0.1)

    def test_split_data_small_list(self):
        splitter = DataSplitter(random_seed=42)
        small_records = [create_dummy_record(i) for i in range(5)]
        splits = splitter.split_data(small_records, train_ratio=0.6, validation_ratio=0.2, test_ratio=0.2)
        # 5 * 0.6 = 3
        # 5 * 0.2 = 1
        # 5 * 0.2 = 1
        assert len(splits["train"]) == 3
        assert len(splits["validation"]) == 1
        assert len(splits["test"]) == 1
        all_split_ids = set(r.step_id for r in splits["train"]) \
                        | set(r.step_id for r in splits["validation"]) \
                        | set(r.step_id for r in splits["test"])
        original_ids = set(r.step_id for r in small_records)
        assert all_split_ids == original_ids

    def test_split_data_ratios_leading_to_zero(self, sample_records: List[ProcessedDataRecord]):
        splitter = DataSplitter(random_seed=42)
        # Ensure test_ratio results in zero records for the test set
        splits = splitter.split_data(sample_records, train_ratio=0.9, validation_ratio=0.1, test_ratio=0.0)
        assert len(splits["train"]) == 90
        assert len(splits["validation"]) == 10
        assert len(splits["test"]) == 0

# Add more tests for edge cases like small datasets, or only train/test splits. 