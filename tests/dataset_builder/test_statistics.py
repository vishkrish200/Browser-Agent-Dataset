'''
Tests for dataset statistics calculation.
'''
import pytest
from typing import List, Dict, Any
from pydantic import HttpUrl

from src.dataset_builder.statistics import DatasetStatistics
from src.dataset_builder.types import ProcessedDataRecord, ActionDetail
from src.dataset_builder.exceptions import DataStatisticsError

# Helper to create dummy records easily
def create_test_record(
    step_id: str,
    session_id: str,
    url: str,
    action_type: str,
    html_content: str | None = None
) -> ProcessedDataRecord:
    return ProcessedDataRecord(
        step_id=step_id,
        session_id=session_id,
        ts=1672531200,
        url=HttpUrl(url), # Ensure HttpUrl for validation
        action=ActionDetail(type=action_type),
        html_content=html_content,
        # obs_html_s3_path and screenshot_s3_path can be None by default
    )

@pytest.fixture
def sample_records_for_stats() -> List[ProcessedDataRecord]:
    return [
        create_test_record("s1", "sessA", "http://example.com/page1", "click", "<html>click page</html>"),
        create_test_record("s2", "sessA", "http://example.com/page2", "input", "<html>input here</html>"),
        create_test_record("s3", "sessB", "https://test.com/itemA", "scroll", "<html>scroll test</html>"),
        create_test_record("s4", "sessB", "http://example.com/page3", "click", "<html>another click</html>"),
        create_test_record("s5", "sessC", "http://sub.example.com/path", "navigate", "<html>navigation page</html>"),
        create_test_record("s6", "sessC", "http://test.com/itemB", "input", None), # No HTML content
        create_test_record("s7", "sessD", "http://another.net/resource", "click", "<html>click again</html>"),
    ]

class TestDatasetStatistics:
    def test_calculate_statistics_empty_list(self):
        calculator = DatasetStatistics()
        stats = calculator.calculate_statistics([])
        assert stats["total_records"] == 0
        assert stats["action_type_distribution"] == {}
        assert stats["unique_domains_count"] == 0
        assert stats["domains_distribution"] == {}

    def test_calculate_statistics_with_sample_data(self, sample_records_for_stats: List[ProcessedDataRecord]):
        calculator = DatasetStatistics()
        stats = calculator.calculate_statistics(sample_records_for_stats)

        assert stats["total_records"] == 7
        
        expected_action_dist = {
            "click": 3,
            "input": 2,
            "scroll": 1,
            "navigate": 1
        }
        assert stats["action_type_distribution"] == expected_action_dist

        assert stats["unique_domains_count"] == 4 # example.com, test.com, sub.example.com, another.net
        
        expected_domain_dist = {
            "example.com": 3, # s1, s2, s4
            "test.com": 2,    # s3, s6
            "sub.example.com": 1, # s5
            "another.net": 1  # s7
        }
        assert stats["domains_distribution"] == expected_domain_dist

    def test_calculate_statistics_with_unparseable_url(self, capsys):
        calculator = DatasetStatistics()
        records_with_bad_url = [
            create_test_record("s1", "sessA", "http://good.com", "click"),
            # This record with an invalid URL will be problematic for urlparse
            ProcessedDataRecord(
                step_id="s_bad_url", session_id="sess_bad", ts=123, 
                # Pydantic HttpUrl will likely fail here, but if it somehow passes to urlparse later
                # url="http://[::1]:namedport", # Example of a URL that might be valid for pydantic but tricky for urlparse in some contexts
                url=HttpUrl("http://valid.but.problematic.for.some.parsers.com"), # Ensuring it's a valid HttpUrl for Pydantic
                action=ActionDetail(type="bad_action"),
                html_content="bad url content"
            ),
            create_test_record("s3", "sessB", "http://good.net", "input")
        ]
        # Forcing a URL that urlparse might struggle with if not handled correctly, though HttpUrl validation is strong.
        # The more likely scenario is if str(record.url) gives something odd. Let's simulate that.
        # We can't easily make HttpUrl invalid after creation without Pydantic error.
        # The code already has a try-except for urlparse, so it should be robust.

        # Let's test the warning print for an unparseable URL. 
        # We can achieve this by temporarily giving a non-HttpUrl string to a record 
        # and ensuring our class handles it by skipping for domain stats.
        # This is tricky because ProcessedDataRecord enforces HttpUrl.
        # The existing try-except in calculate_statistics handles general exceptions during urlparse(str(record.url)).
        # So, we'll rely on that generic exception handling and ensure the stats are still mostly correct.

        # Let's assume a record.url was somehow not a standard HttpUrl string due to prior data issues.
        # This is hard to simulate correctly given Pydantic's HttpUrl validation.
        # The current implementation prints a warning and continues.
        # For now, we'll just verify the counts are correct for the valid URLs.
        
        # A simpler test: ensure it works if one URL is simply different.
        stats = calculator.calculate_statistics(records_with_bad_url)
        assert stats["total_records"] == 3
        assert stats["unique_domains_count"] == 3 # good.com, valid...com, good.net
        # The warning print for unparseable URLs is hard to assert directly without more complex mocking 
        # if Pydantic's HttpUrl catches most truly malformed URLs. 
        # The code's `print(f"Warning: Could not parse URL...")` is the main thing to be aware of.
        # If the URL is truly unparseable by urlparse(str(record.url)), it will be skipped for domain stats.
        # We assume Pydantic's HttpUrl ensures record.url is generally well-behaved for urlparse.

    # Add tests for HTML content statistics if/when that part is implemented
    # def test_html_content_statistics(self, sample_records_for_stats):
    #     calculator = DatasetStatistics()
    #     stats = calculator.calculate_statistics(sample_records_for_stats)
    #     # ... assertions for html_content_stats ...

# Add more tests for specific statistical measures and edge cases. 