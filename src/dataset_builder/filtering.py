'''
Module for filtering ProcessedDataRecord objects based on specified criteria.
'''
from typing import List, Callable, Any, Dict, Optional, Union, Pattern
import re
from urllib.parse import urlparse

from .types import ProcessedDataRecord
from .exceptions import FilteringError

# Type alias for a filter function that takes a record and returns True if it should be kept.
FilterCallable = Callable[[ProcessedDataRecord], bool]

class DataFilterer:
    '''
    Applies a series of filters to a list of ProcessedDataRecord objects.
    Filters can be predefined (like by URL domain) or custom callables.
    '''
    def __init__(self, filters: Optional[List[FilterCallable]] = None):
        self.filters: List[FilterCallable] = filters if filters is not None else []

    def add_filter(self, filter_func: FilterCallable):
        '''Adds a custom filter function.'''
        if not callable(filter_func):
            raise FilteringError("Provided filter must be a callable function.")
        self.filters.append(filter_func)

    def filter_records(self, records: List[ProcessedDataRecord]) -> List[ProcessedDataRecord]:
        '''
        Applies all registered filters to a list of records.
        Returns a new list containing only the records that pass all filters.
        For large datasets, this should ideally be a generator or operate on iterables.
        '''
        if not self.filters:
            return records # No filters, return all records
        
        filtered_records = []
        for record in records:
            if self._passes_all_filters(record):
                filtered_records.append(record)
        return filtered_records
    
    def _passes_all_filters(self, record: ProcessedDataRecord) -> bool:
        '''Checks if a single record passes all registered filters.'''
        for filter_func in self.filters:
            try:
                if not filter_func(record):
                    return False # Record failed one of the filters
            except Exception as e:
                # Optionally log this error or handle specific exceptions
                # For now, treat filter errors as a failure for that record to be safe
                print(f"Warning: Filter function {filter_func.__name__ if hasattr(filter_func, '__name__') else 'custom_filter'} raised an error on record {record.step_id}: {e}. Record excluded.")
                return False
        return True # Record passed all filters

    # --- Predefined Filter Factories --- 
    # These methods create and add common types of filters.

    def add_filter_by_url_domain(self, domains_to_keep: Optional[List[str]] = None, domains_to_exclude: Optional[List[str]] = None):
        '''Adds a filter to keep or exclude records based on URL domain.'''
        if not domains_to_keep and not domains_to_exclude:
            raise FilteringError("Must provide either domains_to_keep or domains_to_exclude for URL domain filter.")

        def domain_filter(record: ProcessedDataRecord) -> bool:
            try:
                parsed_url = urlparse(str(record.url))
                domain = parsed_url.netloc.lower()
                if domains_to_keep:
                    if not any(kept_domain.lower() in domain for kept_domain in domains_to_keep):
                        return False # Not in the keep list
                if domains_to_exclude:
                    if any(excluded_domain.lower() in domain for excluded_domain in domains_to_exclude):
                        return False # In the exclude list
                return True
            except Exception:
                return False # Error parsing URL, exclude record
        self.add_filter(domain_filter)

    def add_filter_by_action_type(self, action_types_to_keep: Optional[List[str]] = None, action_types_to_exclude: Optional[List[str]] = None):
        '''Adds a filter based on action type (e.g., "click", "input").'''
        if not action_types_to_keep and not action_types_to_exclude:
            raise FilteringError("Must provide either action_types_to_keep or action_types_to_exclude for action type filter.")

        def action_type_filter(record: ProcessedDataRecord) -> bool:
            action_type_lower = record.action.type.lower()
            if action_types_to_keep:
                if not any(kept_type.lower() == action_type_lower for kept_type in action_types_to_keep):
                    return False
            if action_types_to_exclude:
                if any(excluded_type.lower() == action_type_lower for excluded_type in action_types_to_exclude):
                    return False
            return True
        self.add_filter(action_type_filter)

    def add_filter_by_html_content_regex(self, pattern: Union[str, Pattern], present: bool = True):
        '''
        Adds a filter based on whether a regex pattern matches the HTML content.
        Args:
            pattern: The regex pattern (string or compiled).
            present: If True, keeps records where pattern IS found. 
                     If False, keeps records where pattern IS NOT found.
        '''
        if isinstance(pattern, str):
            try:
                compiled_pattern = re.compile(pattern)
            except re.error as e:
                raise FilteringError(f"Invalid regex pattern for HTML content filter: {e}") from e
        else:
            compiled_pattern = pattern
        
        def html_regex_filter(record: ProcessedDataRecord) -> bool:
            if record.html_content is None:
                return not present # If HTML must be present and it's not, filter out. If must NOT be present and it's not, keep.
            
            match_found = bool(compiled_pattern.search(record.html_content))
            return match_found if present else not match_found
        self.add_filter(html_regex_filter)
    
    # TODO: Add filters for "workflow type" and "success/failure" when these fields are defined
    # in ProcessedDataRecord or accessible via metadata.
    # Example placeholder for success/failure if action.stagehand_metadata has a 'status' field:
    # def add_filter_by_action_status(self, required_status: str, status_field_in_metadata: str = 'status'):
    #     def status_filter(record: ProcessedDataRecord) -> bool:
    #         if record.action.stagehand_metadata:
    #             return record.action.stagehand_metadata.get(status_field_in_metadata, '').lower() == required_status.lower()
    #         return False # No metadata to check status
    #     self.add_filter(status_filter)

# Example usage:
if __name__ == '__main__':
    from .types import ActionDetail # For example instantiation

    sample_records = [
        ProcessedDataRecord(step_id='s1', session_id='sess1', url='https://example.com/page1', ts=1, action=ActionDetail(type='click'), html_content='Hello example world'),
        ProcessedDataRecord(step_id='s2', session_id='sess1', url='http://test.com/another', ts=2, action=ActionDetail(type='input'), html_content='Test input field'),
        ProcessedDataRecord(step_id='s3', session_id='sess2', url='https_example.com/other', ts=3, action=ActionDetail(type='click'), html_content='Another example page'), # Invalid URL for HttpUrl type
        ProcessedDataRecord(step_id='s4', session_id='sess2', url='https://example.com/product', ts=4, action=ActionDetail(type='scroll'), html_content=None), # No HTML
    ]
    # Correcting s3 to be a valid HttpUrl for Pydantic validation
    try:
        sample_records[2] = ProcessedDataRecord(step_id='s3', session_id='sess2', url='https://example.com/other', ts=3, action=ActionDetail(type='click'), html_content='Another example page')
    except Exception as e:
        print(f"Error correcting sample_records[2]: {e}") # Should not happen with corrected URL

    print("Original records:", len(sample_records))

    # Filter to keep only 'example.com' domains and action type 'click'
    filterer = DataFilterer()
    filterer.add_filter_by_url_domain(domains_to_keep=['example.com'])
    filterer.add_filter_by_action_type(action_types_to_keep=['click'])
    
    filtered = filterer.filter_records(sample_records)
    print(f"\nFiltered (domain='example.com', action='click'): {len(filtered)} records")
    for r in filtered: print(f"  {r.step_id} - {r.url} - {r.action.type}")
    # Expected: s1, s3 (if URL was corrected)

    # Filter to exclude 'input' actions and keep if HTML contains "world"
    filterer2 = DataFilterer()
    filterer2.add_filter_by_action_type(action_types_to_exclude=['input'])
    filterer2.add_filter_by_html_content_regex(r"world", present=True)

    filtered2 = filterer2.filter_records(sample_records)
    print(f"\nFiltered (exclude action 'input', HTML has 'world'): {len(filtered2)} records")
    for r in filtered2: print(f"  {r.step_id} - {r.url} - {r.action.type} - HTML: {r.html_content[:20]}...")
    # Expected: s1

    # Custom filter example: keep records with step_id 's4'
    def custom_step_id_filter(record: ProcessedDataRecord) -> bool:
        return record.step_id == 's4'

    filterer3 = DataFilterer()
    filterer3.add_filter(custom_step_id_filter)
    filtered3 = filterer3.filter_records(sample_records)
    print(f"\nFiltered (custom filter step_id='s4'): {len(filtered3)} records")
    for r in filtered3: print(f"  {r.step_id}")
    # Expected: s4 