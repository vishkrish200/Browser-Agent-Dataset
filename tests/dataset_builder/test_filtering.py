'''
Tests for dataset filtering utilities.
'''
import pytest
import re
from pydantic import HttpUrl
from typing import List

from src.dataset_builder.filtering import DataFilterer, FilteringError, FilterCallable
from src.dataset_builder.types import ProcessedDataRecord, ActionDetail

@pytest.fixture
def sample_records() -> List[ProcessedDataRecord]:
    # Ensure URLs are valid HttpUrl for Pydantic model instantiation
    return [
        ProcessedDataRecord(step_id='s1', session_id='sess1', url=HttpUrl('https://example.com/page1'), ts=1, action=ActionDetail(type='click'), html_content='Hello example <p>world</p>'),
        ProcessedDataRecord(step_id='s2', session_id='sess1', url=HttpUrl('http://test.com/another/item'), ts=2, action=ActionDetail(type='input', text='test data'), html_content='Test input field here'),
        ProcessedDataRecord(step_id='s3', session_id='sess2', url=HttpUrl('https://example.com/other_page'), ts=3, action=ActionDetail(type='click', selector='#btn'), html_content='Another example page content'),
        ProcessedDataRecord(step_id='s4', session_id='sess2', url=HttpUrl('https://sub.example.com/product/1'), ts=4, action=ActionDetail(type='scroll'), html_content=None), # No HTML
        ProcessedDataRecord(step_id='s5', session_id='sess3', url=HttpUrl('http://data.test.net/path'), ts=5, action=ActionDetail(type='navigate'), html_content='Simple content on test.net'),
    ]

class TestDataFilterer:
    def test_init_no_filters(self):
        filterer = DataFilterer()
        assert len(filterer.filters) == 0

    def test_init_with_filters(self, sample_records):
        f1: FilterCallable = lambda r: "example.com" in str(r.url)
        filterer = DataFilterer(filters=[f1])
        assert len(filterer.filters) == 1
        filtered = filterer.filter_records(sample_records)
        assert len(filtered) == 3 # s1, s3, s4

    def test_add_valid_filter(self):
        filterer = DataFilterer()
        custom_filter: FilterCallable = lambda r: r.action.type == 'click'
        filterer.add_filter(custom_filter)
        assert len(filterer.filters) == 1
        assert filterer.filters[0] == custom_filter

    def test_add_invalid_filter_raises_error(self):
        filterer = DataFilterer()
        with pytest.raises(FilteringError, match="Provided filter must be a callable function."):
            filterer.add_filter("not_a_callable") # type: ignore

    def test_filter_records_no_filters(self, sample_records):
        filterer = DataFilterer()
        filtered = filterer.filter_records(sample_records)
        assert filtered == sample_records # Should return all records

    def test_filter_by_url_domain_keep(self, sample_records):
        filterer = DataFilterer()
        filterer.add_filter_by_url_domain(domains_to_keep=['example.com', 'test.net'])
        filtered = filterer.filter_records(sample_records)
        assert len(filtered) == 4 # s1, s3, s4 (example.com), s5 (test.net)
        assert all("example.com" in str(r.url) or "test.net" in str(r.url) for r in filtered)

    def test_filter_by_url_domain_exclude(self, sample_records):
        filterer = DataFilterer()
        filterer.add_filter_by_url_domain(domains_to_exclude=['test.com'])
        filtered = filterer.filter_records(sample_records)
        assert len(filtered) == 4 # s1, s3, s4, s5 (s2 excluded)
        assert all("test.com" not in str(r.url) for r in filtered)

    def test_filter_by_url_domain_keep_and_exclude(self, sample_records):
        filterer = DataFilterer()
        # Keep example.com, but exclude sub.example.com
        filterer.add_filter_by_url_domain(domains_to_keep=['example.com'], domains_to_exclude=['sub.example.com'])
        filtered = filterer.filter_records(sample_records)
        assert len(filtered) == 2 # s1, s3 (s4 excluded due to subdomain)
        assert all(r.step_id in ['s1', 's3'] for r in filtered)

    def test_filter_by_url_domain_no_criteria_raises_error(self):
        filterer = DataFilterer()
        with pytest.raises(FilteringError, match="Must provide either domains_to_keep or domains_to_exclude"):
            filterer.add_filter_by_url_domain()

    def test_filter_by_action_type_keep(self, sample_records):
        filterer = DataFilterer()
        filterer.add_filter_by_action_type(action_types_to_keep=['click', 'scroll'])
        filtered = filterer.filter_records(sample_records)
        assert len(filtered) == 3 # s1 (click), s3 (click), s4 (scroll)
        assert all(r.action.type in ['click', 'scroll'] for r in filtered)

    def test_filter_by_action_type_exclude(self, sample_records):
        filterer = DataFilterer()
        filterer.add_filter_by_action_type(action_types_to_exclude=['input', 'navigate'])
        filtered = filterer.filter_records(sample_records)
        assert len(filtered) == 3 # s1, s3, s4 (s2, s5 excluded)
        assert all(r.action.type not in ['input', 'navigate'] for r in filtered)
    
    def test_filter_by_action_type_case_insensitivity(self, sample_records):
        filterer = DataFilterer()
        filterer.add_filter_by_action_type(action_types_to_keep=['CLICK'])
        filtered = filterer.filter_records(sample_records)
        assert len(filtered) == 2 # s1, s3

    def test_filter_by_html_content_regex_present(self, sample_records):
        filterer = DataFilterer()
        filterer.add_filter_by_html_content_regex(r"<p>world</p>") # Test specific tag
        filtered = filterer.filter_records(sample_records)
        assert len(filtered) == 1 # s1
        assert filtered[0].step_id == 's1'

    def test_filter_by_html_content_regex_not_present(self, sample_records):
        filterer = DataFilterer()
        # Keep records that DO NOT contain "example"
        filterer.add_filter_by_html_content_regex(r"example", present=False)
        filtered = filterer.filter_records(sample_records)
        # s1, s3 contain "example". s2, s5 don't. s4 html_content is None.
        # If None and must NOT be present, s4 is kept.
        assert len(filtered) == 3 # s2, s4, s5
        assert all(r.step_id in ['s2', 's4', 's5'] for r in filtered)
        assert not any(r.html_content and "example" in r.html_content for r in filtered)

    def test_filter_by_html_content_regex_html_none(self, sample_records):
        filterer_present = DataFilterer()
        filterer_present.add_filter_by_html_content_regex(r"any", present=True)
        filtered_present = filterer_present.filter_records(sample_records)
        assert 's4' not in [r.step_id for r in filtered_present] # s4 has no HTML, so pattern won't be found

        filterer_not_present = DataFilterer()
        filterer_not_present.add_filter_by_html_content_regex(r"any", present=False)
        filtered_not_present = filterer_not_present.filter_records(sample_records)
        assert 's4' in [r.step_id for r in filtered_not_present] # s4 has no HTML, so pattern is not found (passes)

    def test_filter_by_html_content_invalid_regex_raises_error(self):
        filterer = DataFilterer()
        with pytest.raises(FilteringError, match="Invalid regex pattern"):
            filterer.add_filter_by_html_content_regex("[") # Invalid regex

    def test_combined_filters(self, sample_records):
        filterer = DataFilterer()
        filterer.add_filter_by_url_domain(domains_to_keep=['example.com'])
        filterer.add_filter_by_action_type(action_types_to_keep=['click'])
        filterer.add_filter_by_html_content_regex(r"world", present=True)
        filtered = filterer.filter_records(sample_records)
        assert len(filtered) == 1 # Only s1 matches all: example.com, click, and contains "world"
        assert filtered[0].step_id == 's1'

    def test_filter_function_raises_error(self, sample_records, capsys):
        filterer = DataFilterer()
        def error_filter(record: ProcessedDataRecord) -> bool:
            if record.step_id == 's2':
                raise ValueError("Intentional error for testing")
            return True
        filterer.add_filter(error_filter)
        filtered = filterer.filter_records(sample_records)
        # s2 should be excluded due to the error
        assert len(filtered) == len(sample_records) - 1 
        assert 's2' not in [r.step_id for r in filtered]
        captured = capsys.readouterr()
        assert "Warning: Filter function error_filter raised an error on record s2" in captured.out
        assert "Intentional error for testing" in captured.out

    def test_empty_input_records(self):
        filterer = DataFilterer()
        filterer.add_filter_by_action_type(action_types_to_keep=['click'])
        assert filterer.filter_records([]) == []

# Add more tests for different filtering criteria and combinations. 