import random
from typing import List, Tuple, Any, Optional
from .types import ProcessedDataRecord # Or JSONLEntry, depending on when splitting occurs
from .exceptions import SplittingError

def split_dataset(records: List[Any], train_ratio: float = 0.8, val_ratio: float = 0.1, test_ratio: float = 0.1, shuffle: bool = True, seed: Optional[int] = None) -> Tuple[List[Any], List[Any], List[Any]]:
    """Splits a list of records into train, validation, and test sets."""
    if not (0.0 <= train_ratio <= 1.0 and 0.0 <= val_ratio <= 1.0 and 0.0 <= test_ratio <= 1.0):
        raise SplittingError("Ratios must be between 0.0 and 1.0")
    
    if round(train_ratio + val_ratio + test_ratio, 5) != 1.0: # Using round for float precision issues
        raise SplittingError("Sum of ratios must be 1.0")

    if shuffle:
        if seed is not None:
            random.seed(seed)
        random.shuffle(records)

    num_records = len(records)
    train_end = int(num_records * train_ratio)
    val_end = train_end + int(num_records * val_ratio)

    train_set = records[:train_end]
    val_set = records[train_end:val_end]
    test_set = records[val_end:]

    # Ensure all records are distributed if ratios cause rounding issues with small datasets
    # This is a simple redistribution; more sophisticated might be needed for edge cases.
    all_assigned_ids = {id(r) for r_list in [train_set, val_set, test_set] for r in r_list}
    if len(all_assigned_ids) != num_records and num_records > 0:
        # This indicates some records might have been missed due to rounding, especially with small datasets
        # For MVP, we can accept minor imperfections or rely on larger datasets. 
        # A more robust solution would re-distribute remaining unassigned items or adjust split points carefully.
        pass # Or log a warning

    return train_set, val_set, test_set 