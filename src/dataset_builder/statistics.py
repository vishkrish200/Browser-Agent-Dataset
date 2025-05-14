'''
Module for dataset statistics calculation.
'''

from collections import Counter
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from .types import ProcessedDataRecord
from .exceptions import DataStatisticsError

class DatasetStatistics:
    '''Handles calculation and reporting of dataset statistics.'''

    def __init__(self):
        pass

    def calculate(self, data):
        '''Calculate statistics for the given data.'''
        # Placeholder for statistics calculation logic
        print("Calculating dataset statistics...")
        return {}

    def report(self, stats):
        '''Report the calculated statistics.'''
        # Placeholder for statistics reporting logic
        print(f"Dataset Statistics: {stats}")

    def calculate_statistics(self, records: List[ProcessedDataRecord]) -> Dict[str, Any]:
        """
        Calculates various statistics for the given list of records.

        Args:
            records: A list of ProcessedDataRecord objects.

        Returns:
            A dictionary containing dataset statistics.
            Example: 
            {
                "total_records": 100,
                "action_type_distribution": {"click": 50, "input": 30, "scroll": 20},
                "unique_domains_count": 5,
                "domains_distribution": {"example.com": 60, "test.com": 40}
            }

        Raises:
            DataStatisticsError: If the input records list is empty (or other calculation errors).
        """
        if not records:
            # Option 1: Raise an error
            # raise DataStatisticsError("Input records list cannot be empty to calculate statistics.")
            # Option 2: Return empty/zeroed statistics
            return {
                "total_records": 0,
                "action_type_distribution": {},
                "unique_domains_count": 0,
                "domains_distribution": {}
                # Potentially add html_content_stats with zero/None values if implemented
            }

        total_records = len(records)
        
        # Action type distribution
        action_types = [record.action.type for record in records]
        action_type_distribution = dict(Counter(action_types))

        # Unique domains and their distribution
        domains = []
        for record in records:
            try:
                parsed_url = urlparse(str(record.url))
                domains.append(parsed_url.netloc.lower())
            except Exception as e:
                # Log or handle records with unparseable URLs if necessary
                print(f"Warning: Could not parse URL {record.url} for record {record.step_id}: {e}")
                continue # Skip this record for domain stats
        
        domains_distribution = dict(Counter(domains))
        unique_domains_count = len(domains_distribution)

        # TODO (Optional for MVP, based on original plan):
        # Basic statistics on HTML content length if available (min, max, mean, median)
        # html_lengths = [len(r.html_content) for r in records if r.html_content is not None]
        # html_content_stats = {}
        # if html_lengths:
        #     html_content_stats["min_length"] = min(html_lengths)
        #     html_content_stats["max_length"] = max(html_lengths)
        #     html_content_stats["mean_length"] = sum(html_lengths) / len(html_lengths)
        #     # For median, you might need a library like numpy or statistics.median
        #     # import statistics
        #     # html_content_stats["median_length"] = statistics.median(html_lengths)
        # else:
        #     html_content_stats = {"min_length": 0, "max_length": 0, "mean_length": 0, "median_length": 0}

        return {
            "total_records": total_records,
            "action_type_distribution": action_type_distribution,
            "unique_domains_count": unique_domains_count,
            "domains_distribution": domains_distribution,
            # "html_content_stats": html_content_stats # Uncomment if implemented
        }

if __name__ == '__main__':
    # Example Usage
    stats_calculator = DatasetStatistics()
    example_data = [] # Replace with actual data
    calculated_stats = stats_calculator.calculate(example_data)
    stats_calculator.report(calculated_stats) 