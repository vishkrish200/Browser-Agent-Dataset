import random
from typing import List, Dict, Tuple
from .types import ProcessedDataRecord # Assuming ProcessedDataRecord is in types.py
from .exceptions import DataSplittingError

class DataSplitter:
    """Handles splitting of data into train, validation, and test sets."""

    def __init__(self, random_seed: int | None = None):
        """
        Initializes the DataSplitter.

        Args:
            random_seed: Seed for random number generator for reproducible splits.
        """
        self.random_seed = random_seed
        if self.random_seed is not None:
            random.seed(self.random_seed)

    def split_data(
        self,
        data_records: List[ProcessedDataRecord],
        train_ratio: float = 0.8,
        validation_ratio: float = 0.1,
        test_ratio: float = 0.1,
    ) -> Dict[str, List[ProcessedDataRecord]]:
        """
        Splits data records into training, validation, and test sets.

        Args:
            data_records: A list of ProcessedDataRecord objects.
            train_ratio: Proportion of data for the training set.
            validation_ratio: Proportion of data for the validation set.
            test_ratio: Proportion of data for the test set.

        Returns:
            A dictionary with keys 'train', 'validation', 'test' and values
            being lists of ProcessedDataRecord objects.

        Raises:
            DataSplittingError: If split ratios are invalid or data is empty.
        """
        if not data_records:
            raise DataSplittingError("Input data_records list cannot be empty.")

        if not (train_ratio >= 0 and validation_ratio >= 0 and test_ratio >= 0):
            raise DataSplittingError("Split ratios must be non-negative.")
        
        total_ratio = train_ratio + validation_ratio + test_ratio
        if abs(total_ratio - 1.0) > 1e-9: # Using tolerance for float comparison
            raise DataSplittingError(
                f"Sum of split ratios must be 1.0, but got {total_ratio}"
            )

        # Shuffle the data
        shuffled_records = list(data_records) # Create a mutable copy
        if self.random_seed is not None:
            # Re-seed here if multiple calls to split_data on the same instance
            # are intended to be independent if a seed was initially provided for the instance.
            # Or, document that the instance will always produce the same sequence of shuffles.
            # For now, we assume the initial seed dictates the shuffle for all calls on this instance.
            random.shuffle(shuffled_records)
        else:
            # If no seed, shuffle randomly each time
            current_random_state = random.getstate()
            random.seed() # Seed with system time or other source of randomness
            random.shuffle(shuffled_records)
            random.setstate(current_random_state)


        num_records = len(shuffled_records)
        train_end = int(num_records * train_ratio)
        validation_end = train_end + int(num_records * validation_ratio)

        train_set = shuffled_records[:train_end]
        validation_set = shuffled_records[train_end:validation_end]
        test_set = shuffled_records[validation_end:]
        
        # Adjust if rounding caused issues, ensure all records are assigned
        # This simple distribution might not be perfect with small N and rounding
        # A more robust way would be to calculate exact counts and distribute remainders

        return {
            "train": train_set,
            "validation": validation_set,
            "test": test_set,
        } 