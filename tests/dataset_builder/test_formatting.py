'''
Tests for dataset formatting utilities.
'''
import pytest
# from src.dataset_builder.formatting import DataFormatter # Adjust import
# from src.dataset_builder.types import RawEntry, FormattedEntry # Adjust import

class TestDataFormatter:
    def test_format_single_entry_success(self):
        '''Test successful formatting of a single raw data entry.'''
        # formatter = DataFormatter()
        # raw_entry: RawEntry = {"id": "1", "text": "  some text  ", "extra": "field"} # Example
        # expected_formatted_entry: FormattedEntry = {"id": "1", "processed_text": "some text"} # Example
        # formatted_entry = formatter.format_entry(raw_entry)
        # assert formatted_entry == expected_formatted_entry
        pytest.skip("DataFormatter not yet fully implemented")

    def test_format_entry_missing_required_field(self):
        '''Test formatting when a required field is missing in raw entry.'''
        # formatter = DataFormatter()
        # raw_entry_missing_text = {"id": "2"} # Missing 'text'
        # with pytest.raises(KeyError): # Or a custom FormattingError
        #     formatter.format_entry(raw_entry_missing_text)
        pytest.skip("DataFormatter not yet fully implemented")

    def test_batch_format_entries(self):
        '''Test formatting a batch of raw entries.'''
        # formatter = DataFormatter()
        # raw_entries = [
        #     {"id": "3", "text": "first example "},
        #     {"id": "4", "text": " second example"}
        # ]
        # expected_formatted_entries = [
        #     {"id": "3", "processed_text": "first example"},
        #     {"id": "4", "processed_text": "second example"}
        # ]
        # formatted_entries = formatter.format_batch(raw_entries)
        # assert formatted_entries == expected_formatted_entries
        pytest.skip("DataFormatter not yet fully implemented")

# Add more tests for various data cleaning, transformation, and normalization rules. 