from .image_handler import ImageHandler
from .filtering import DataFilter
from .splitting import DataSplitter
from .formatting import JsonlFormatter
from .statistics import DatasetStatistics
from .types import ProcessedDataRecord # Assuming this will be the input type
# Add other necessary imports for data loading, file handling etc.
import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class DatasetBuilder:
    """Main class for building datasets in JSONL format."""
    def __init__(self, config=None):
        self.config = config or {}
        self.image_handler = ImageHandler() # Initialize with default config
        self.formatter = JsonlFormatter(self.image_handler) # Pass image_handler if needed by formatter
        self.filter = DataFilter(self.config.get('filtering', {}))
        self.splitter = DataSplitter()
        self.stats_generator = DatasetStatistics()
        logger.info("DatasetBuilder initialized.")

    def build_dataset(
        self,
        input_path: str, 
        output_path: str, 
        include_images: bool = False, 
        train_split: float = 0.9,
        # Add other relevant kwargs based on subtask details like filtering options
        filter_options: Optional[dict] = None
    ):
        """Builds the dataset from input_path and saves to output_path."""
        logger.info(
            f"Starting dataset build from '{input_path}' to '{output_path}'. "
            f"Include images: {include_images}, Train split: {train_split}, Filter options: {filter_options}"
        )
        
        # 1. Load data (Placeholder - needs implementation based on where ProcessedDataRecord comes from)
        # This would typically involve reading from S3 or local checkpoint files mentioned in task 5.
        # For now, assume `all_records: List[ProcessedDataRecord]` is loaded.
        # Example: all_records = self._load_processed_data(input_path)
        all_records: list[ProcessedDataRecord] = [] # Replace with actual data loading
        if not all_records:
            logger.warning(f"No records loaded from {input_path}. Output dataset will be empty.")
            # Optionally create empty output files or handle as an error
            # For now, just log and proceed to create potentially empty files.

        # 2. Filter data
        if filter_options:
            self.filter.update_config(filter_options) # Allow dynamic filter updates
        filtered_records = self.filter.filter_records(all_records)
        logger.info(f"Filtered records: {len(filtered_records)} out of {len(all_records)} total.")

        # 3. Split data
        # Ensure splitter knows about train_split if it's not globally configured
        # For now, assuming splitter might take it directly or it's a general setting.
        if not (0 < train_split < 1):
            logger.warning(f"Invalid train_split value {train_split}. Disabling train/validation split.")
            train_records = filtered_records
            validation_records = []
        else:
            train_records, validation_records = self.splitter.split_data(filtered_records, train_split)
        
        logger.info(f"Train records: {len(train_records)}, Validation records: {len(validation_records)}")

        # 4. Format and write data to JSONL
        os.makedirs(output_path, exist_ok=True)

        if train_records:
            train_output_file = os.path.join(output_path, "train.jsonl")
            self.formatter.write_to_jsonl(train_records, train_output_file, include_images)
            logger.info(f"Train dataset written to {train_output_file}")
        
        if validation_records:
            val_output_file = os.path.join(output_path, "validation.jsonl")
            self.formatter.write_to_jsonl(validation_records, val_output_file, include_images)
            logger.info(f"Validation dataset written to {val_output_file}")

        # 5. Generate and save dataset statistics
        if filtered_records: # Generate stats on all data that went into splits
            stats = self.stats_generator.calculate_statistics(filtered_records)
            stats_output_file = os.path.join(output_path, "dataset_stats.json")
            with open(stats_output_file, 'w') as f:
                json.dump(stats, f, indent=4)
            logger.info(f"Dataset statistics written to {stats_output_file}")
        else:
            logger.info("Skipping statistics generation as there are no filtered records.")

        logger.info("Dataset build completed.")
        
    # Placeholder for actual data loading logic
    def _load_processed_data(self, input_path: str) -> list[ProcessedDataRecord]:
        # This method needs to be implemented to load ProcessedDataRecord objects
        # from the location specified by input_path (e.g., S3 or local file system).
        # It would iterate through checkpoint files, parse them, and create ProcessedDataRecord instances.
        logger.warning(f"Data loading from {input_path} is not implemented yet. Returning empty list.")
        return [] 