'''
Tests for dataset builder utility functions.
'''
import pytest
import os
import json
# from src.dataset_builder.utils import load_jsonl, save_jsonl, ensure_dir_exists # Adjust import

class TestDatasetUtils:
    def test_ensure_dir_exists(self, tmp_path):
        '''Test that ensure_dir_exists creates a directory if it doesn't exist.'''
        # new_dir = tmp_path / "new_test_dir"
        # assert not new_dir.exists()
        # ensure_dir_exists(str(new_dir))
        # assert new_dir.exists()
        # ensure_dir_exists(str(new_dir)) # Test it doesn't fail if dir already exists
        pytest.skip("Utility functions (e.g., ensure_dir_exists) not yet implemented or imported")

    def test_load_jsonl_success(self, tmp_path):
        '''Test loading data from a valid JSONL file.'''
        # file_path = tmp_path / "test_data.jsonl"
        # data_to_write = [
        #     {"id": 1, "text": "entry one"},
        #     {"id": 2, "text": "entry two"}
        # ]
        # with open(file_path, 'w') as f:
        #     for item in data_to_write:
        #         f.write(json.dumps(item) + "\n")
        # 
        # loaded_data = load_jsonl(str(file_path))
        # assert loaded_data == data_to_write
        pytest.skip("Utility functions (e.g., load_jsonl) not yet implemented or imported")

    def test_load_jsonl_file_not_found(self):
        '''Test loading from a non-existent JSONL file.'''
        # with pytest.raises(FileNotFoundError):
        #     load_jsonl("non_existent_file.jsonl")
        pytest.skip("Utility functions (e.g., load_jsonl) not yet implemented or imported")

    def test_save_jsonl_success(self, tmp_path):
        '''Test saving data to a JSONL file.'''
        # file_path = tmp_path / "output_data.jsonl"
        # data_to_save = [
        #     {"id": 3, "value": "data point A"},
        #     {"id": 4, "value": "data point B"}
        # ]
        # save_jsonl(data_to_save, str(file_path))
        # 
        # # Verify file content
        # loaded_back_data = []
        # with open(file_path, 'r') as f:
        #     for line in f:
        #         loaded_back_data.append(json.loads(line.strip()))
        # assert loaded_back_data == data_to_save
        pytest.skip("Utility functions (e.g., save_jsonl) not yet implemented or imported")

# Add more tests for other utility functions as they are developed. 