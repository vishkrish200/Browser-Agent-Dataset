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
from typing import Optional, Tuple
from ..storage_manager.storage import StorageManager, ACTION_DATA_FILENAME # Assuming ACTION_DATA_FILENAME is what we look for

logger = logging.getLogger(__name__)

class DatasetBuilder:
    """Main class for building datasets in JSONL format."""
    def __init__(self, config: Optional[dict] = None, storage_manager: Optional[StorageManager] = None):
        self.config = config if config is not None else {}
        self.filter_config = self.config.get("filtering", {})
        
        # Initialize components
        self.image_handler = ImageHandler(self.config.get("image_processing", {}))
        self.formatter = JsonlFormatter(self.image_handler)
        self.filter = DataFilter(self.filter_config)
        self.splitter = DataSplitter()
        self.stats_generator = DatasetStatistics()

        if storage_manager:
            self.storage_manager = storage_manager
        else:
            # Default initialization of StorageManager if not provided.
            # This makes DatasetBuilder usable standalone but allows injection for better control/testing.
            logger.info("StorageManager not provided to DatasetBuilder, initializing a default one.")
            self.storage_manager = StorageManager() # Uses its own default config resolution

        logger.info("DatasetBuilder initialized.")

    def _parse_s3_uri(self, s3_uri: str) -> Tuple[str, str]:
        """Helper to parse s3://bucket/prefix into (bucket, prefix)."""
        if not s3_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI: {s3_uri}")
        parts = s3_uri[5:].split('/', 1)
        bucket = parts[0]
        prefix = parts[1] if len(parts) > 1 else ""
        return bucket, prefix.strip("/")

    async def _load_processed_data_from_s3(self, s3_input_prefix: str) -> list[ProcessedDataRecord]:
        """Loads ProcessedDataRecord objects from S3 given a base prefix."""
        all_records: list[ProcessedDataRecord] = []
        if not self.storage_manager or not self.storage_manager.use_s3:
            logger.warning("S3 input path provided, but StorageManager is not configured for S3.")
            return all_records
        
        try:
            logger.info(f"Listing sessions from S3 under prefix: s3://{self.storage_manager.s3_bucket_name}/{s3_input_prefix}")
            session_ids = await self.storage_manager.list_sessions(path_prefix=s3_input_prefix)
            logger.debug(f"Found S3 sessions: {session_ids} under prefix '{s3_input_prefix}'")

            for session_id in session_ids:
                logger.debug(f"Listing steps for S3 session: {session_id} under prefix '{s3_input_prefix}'")
                step_ids = await self.storage_manager.list_steps_for_session(session_id, path_prefix=s3_input_prefix)
                logger.debug(f"Found S3 steps for session {session_id}: {step_ids}")

                for step_id in step_ids:
                    # Construct the key for the action data file within the StorageManager's S3 structure
                    # The key is relative to StorageManager's root, so we use its _get_s3_key method pattern.
                    # If path_prefix is used, session_id and step_id are already relative to it.
                    # We need to reconstruct the full key from s3_input_prefix, session_id, step_id
                    action_file_s3_key = f"{s3_input_prefix}/{session_id}/{step_id}/{ACTION_DATA_FILENAME}"
                    logger.debug(f"Attempting to download S3 object: s3://{self.storage_manager.s3_bucket_name}/{action_file_s3_key}")
                    try:
                        # Use a generic download method from StorageManager if available, or its internal _download_from_s3
                        # Assuming _download_from_s3 is accessible and appropriate here.
                        action_data_bytes = await self.storage_manager._download_from_s3(action_file_s3_key) # Made async for consistency
                        if action_data_bytes:
                            raw_data = json.loads(action_data_bytes.decode('utf-8'))
                            # Ensure essential fields from S3 structure are present if not in action.json
                            # For now, assume action.json IS the ProcessedDataRecord
                            record = ProcessedDataRecord(**raw_data)
                            all_records.append(record)
                            logger.debug(f"Successfully loaded and parsed record from {action_file_s3_key}")
                        else:
                            logger.warning(f"No data returned from S3 for {action_file_s3_key}")
                    except json.JSONDecodeError as e_json:
                        logger.warning(f"JSON decode error for S3 object {action_file_s3_key}: {e_json}")
                    except S3OperationError as e_s3_op:
                        if "NoSuchKey" in str(e_s3_op) or "404" in str(e_s3_op):
                             logger.debug(f"Action file not found (NoSuchKey/404) at S3 path: {action_file_s3_key}")
                        else:
                            logger.warning(f"S3OperationError for S3 object {action_file_s3_key}: {e_s3_op}")
                    except Exception as e_load_step:
                        logger.warning(f"Failed to load or parse record from S3 object {action_file_s3_key}: {e_load_step}")
        except S3OperationError as e_list:
            logger.error(f"S3OperationError while listing sessions/steps under {s3_input_prefix}: {e_list}")
        except Exception as e_outer:
            logger.error(f"Generic error while loading data from S3 under {s3_input_prefix}: {e_outer}", exc_info=True)
        return all_records

    async def _load_processed_data_from_local(self, local_input_path: str) -> list[ProcessedDataRecord]:
        """Loads ProcessedDataRecord objects from a local directory."""
        all_records: list[ProcessedDataRecord] = []
        logger.info(f"Loading processed data from local directory: {local_input_path}")
        if not os.path.isdir(local_input_path):
            logger.warning(f"Local input path {local_input_path} is not a directory.")
            return all_records
        
        for filename in os.listdir(local_input_path):
            if filename.endswith(".json"):
                file_path = os.path.join(local_input_path, filename)
                logger.debug(f"Attempting to load records from local file: {file_path}")
                try:
                    with open(file_path, 'r') as f:
                        raw_data_list = json.load(f)
                        if isinstance(raw_data_list, list):
                            for i, raw_data in enumerate(raw_data_list):
                                try:
                                    record = ProcessedDataRecord(**raw_data)
                                    all_records.append(record)
                                except Exception as e_record:
                                    logger.warning(f"Could not parse record #{i} in {file_path}: {e_record}")
                        else:
                            logger.warning(f"File {file_path} does not contain a list of records.")
                except json.JSONDecodeError as e_json:
                    logger.error(f"Error decoding JSON from {file_path}: {e_json}")
                except Exception as e_file:
                    logger.error(f"Error reading or processing file {file_path}: {e_file}")
        return all_records

    async def _load_processed_data(self, input_path: str) -> list[ProcessedDataRecord]: # Made async
        """
        Loads processed data records from the given input path.
        If input_path is an S3 URI (s3://bucket/prefix), it lists session/step 
        structures and attempts to load a manifest file (ACTION_DATA_FILENAME) 
        from each step, assuming it contains ProcessedDataRecord data.
        If input_path is a local directory, it reads JSON files from that directory.
        """
        all_records: list[ProcessedDataRecord] = []
        
        if input_path.startswith("s3://"):
            _bucket, s3_prefix = self._parse_s3_uri(input_path)
            # We assume storage_manager is configured for the correct bucket.
            # The parsed _bucket from URI is mostly for validation/info here.
            if self.storage_manager and self.storage_manager.s3_bucket_name != _bucket:
                logger.warning(f"Input S3 URI bucket '{_bucket}' differs from StorageManager's configured bucket '{self.storage_manager.s3_bucket_name}'. Using StorageManager's bucket with prefix '{s3_prefix}'.")
            
            all_records = await self._load_processed_data_from_s3(s3_prefix)
        elif os.path.isdir(input_path): # Local directory loading
            all_records = await self._load_processed_data_from_local(input_path)
        else:
            logger.warning(f"Input path {input_path} is not a recognized S3 URI or local directory. Cannot load data.")
            
        logger.info(f"Loaded {len(all_records)} records from {input_path}")
        return all_records

    async def build_dataset( # Made async
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
        
        # 1. Load data (now async)
        processed_records = await self._load_processed_data(input_path)

        if not processed_records:
            logger.warning(f"No records loaded from {input_path}. Output dataset will be empty.")
            # Optionally create empty output files or handle as an error
            # For now, just log and proceed to create potentially empty files.

        # 2. Filter data
        if filter_options:
            self.filter.update_config(filter_options) # Allow dynamic filter updates
        filtered_records = self.filter.filter_records(processed_records)
        logger.info(f"Filtered records: {len(filtered_records)} out of {len(processed_records)} total.")

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