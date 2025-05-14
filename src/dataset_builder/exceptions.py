class DatasetBuilderError(Exception):
    """Base exception for errors in the dataset builder module."""
    pass

class DataFormattingError(DatasetBuilderError):
    """Exception for errors during data formatting."""
    pass

# class FilteringError(DatasetBuilderError):
#     """Exception for errors during data filtering."""
#     pass
#
# class SplittingError(DatasetBuilderError):
#     """Exception for errors during data splitting."""
#     pass

class DataFilteringError(DatasetBuilderError):
    """Custom exception for data filtering errors."""
    pass

class DataSplittingError(DatasetBuilderError):
    """Custom exception for data splitting errors."""
    pass 