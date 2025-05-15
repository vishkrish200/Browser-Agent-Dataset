class BaseDatasetBuilderError(Exception):
    """Base exception for dataset builder errors."""
    pass

class ImageProcessingError(BaseDatasetBuilderError):
    """Exception raised for errors in image processing.
    
    Attributes:
        message -- explanation of the error
        original_exception -- the original exception that was caught, if any
    """
    def __init__(self, message, original_exception=None):
        self.message = message
        self.original_exception = original_exception
        super().__init__(self.message)

    def __str__(self):
        if self.original_exception:
            return f'{self.message}: {self.original_exception}'
        return self.message

class FilteringError(BaseDatasetBuilderError):
    """Exception raised for errors during data filtering."""
    pass

class SplittingError(BaseDatasetBuilderError):
    """Exception raised for errors during data splitting."""
    pass

class FormattingError(BaseDatasetBuilderError):
    """Exception raised for errors during data formatting (e.g., to JSONL)."""
    pass

class StatisticsError(BaseDatasetBuilderError):
    """Exception raised for errors during statistics generation."""
    pass

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

class DataStatisticsError(DatasetBuilderError):
    """Custom exception for dataset statistics calculation errors."""
    pass

class ImageHandlingError(DatasetBuilderError):
    """Custom exception for image handling errors."""
    pass 