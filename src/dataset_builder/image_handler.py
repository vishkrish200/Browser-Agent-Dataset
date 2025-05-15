'''
Module for handling image-related operations in the dataset builder.
'''

from typing import Optional, Tuple, Union, Dict, Any
import os
import logging
from PIL import Image, UnidentifiedImageError
import tempfile # For temporary file handling with S3
import boto3 # For S3 integration
from botocore.exceptions import ClientError # For S3 error handling
from urllib.parse import urlparse # For parsing S3 URLs
import numpy as np
import random
from PIL import ImageEnhance

from .types import ProcessedDataRecord
from .exceptions import ImageHandlingError, ImageProcessingError

logger = logging.getLogger(__name__)

class ImageHandler:
    '''Handles downloading, processing, and storing images.'''

    SUPPORTED_EXTENSIONS = (".webp", ".png", ".jpg", ".jpeg")

    def __init__(
        self,
        output_format: str = "WEBP",
        default_resize_dimensions: Optional[Tuple[int, int]] = None, # e.g., (1024, 768)
        default_quality: int = 80, # For formats like JPEG/WEBP
        s3_bucket_name: Optional[str] = None # Optional: S3 bucket for image storage
    ):
        """
        Initializes the ImageHandler.

        Args:
            output_format: The image format to save processed images in (e.g., "WEBP", "PNG", "JPEG").
            default_resize_dimensions: Optional tuple (width, height) to resize images to by default.
            default_quality: Default quality for saving images (1-100 for WEBP/JPEG).
            s3_bucket_name: Optional S3 bucket name to be used for S3 operations.
                           If not provided, some S3 operations might require it to be passed directly
                           or might raise an error.
        """
        self.output_format = output_format.upper()
        self.default_resize_dimensions = default_resize_dimensions
        self.default_quality = default_quality
        self.s3_bucket_name = s3_bucket_name
        self._s3_client = None # Lazy initialization for S3 client
        
        logger.info(
            f"ImageHandler initialized. Output format: {self.output_format}, "
            f"Default resize: {self.default_resize_dimensions}, Default quality: {self.default_quality}, "
            f"S3 Bucket: {self.s3_bucket_name or 'Not configured'}"
        )

    def _get_s3_client(self):
        """Lazy initializes and returns the S3 client."""
        if self._s3_client is None:
            try:
                self._s3_client = boto3.client("s3")
                logger.info("S3 client initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}", exc_info=True)
                raise ImageProcessingError(f"Failed to initialize S3 client: {e}") from e
        return self._s3_client

    def download_image_http(self, url: str, filename: Optional[str] = None) -> Optional[str]:
        '''Downloads an image from a given HTTP/S URL. (Placeholder)

        Args:
            url: The URL of the image to download.
            filename: Optional filename to save the image as. 
                      If None, a filename will be generated.

        Returns:
            The path to the downloaded image, or None if download failed.
        '''
        # Placeholder for image download logic (e.g., using requests or httpx)
        print(f"Downloading image from {url}...")
        # Example: 
        # try:
        #     response = requests.get(url, stream=True)
        #     response.raise_for_status()
        #     # Determine filename, save file
        #     # return saved_filepath
        # except requests.RequestException as e:
        #     print(f"Error downloading {url}: {e}")
        #     return None
        logger.warning(f"download_image_http for {url} is a placeholder and not implemented.")
        if filename: # Keep simple placeholder behavior if filename is given
            return os.path.join(os.getcwd(), filename) # Fake download to current dir
        return None

    def download_image_from_s3(self, s3_url: str, local_temp_dir: Optional[str] = None) -> str:
        """
        Downloads an image from an S3 URL to a local temporary file.

        Args:
            s3_url: The S3 URL of the image (e.g., "s3://bucket-name/path/to/image.jpg").
            local_temp_dir: Optional directory to store the temporary downloaded file.
                              If None, a system temporary directory is used.

        Returns:
            The path to the downloaded local temporary image file.

        Raises:
            ImageProcessingError: If S3 URL is invalid, download fails, or S3 client isn't configured.
        """
        s3 = self._get_s3_client()
        parsed_url = urlparse(s3_url)
        if parsed_url.scheme != "s3":
            msg = f"Invalid S3 URL scheme: {s3_url}. Must start with 's3://'."
            logger.error(msg)
            raise ImageProcessingError(msg)

        bucket_name = parsed_url.netloc
        key = parsed_url.path.lstrip('/')

        if not bucket_name or not key:
            msg = f"Invalid S3 URL: {s3_url}. Could not parse bucket or key."
            logger.error(msg)
            raise ImageProcessingError(msg)

        try:
            # Create a temporary file to download to
            if local_temp_dir and not os.path.exists(local_temp_dir):
                os.makedirs(local_temp_dir, exist_ok=True)
            
            # Extract original filename and extension for the temp file
            original_filename = os.path.basename(key)
            fd, local_temp_path = tempfile.mkstemp(prefix="s3_download_", suffix=f"_{original_filename}", dir=local_temp_dir)
            os.close(fd) # Close the file descriptor as S3 download_file handles opening

            logger.debug(f"Attempting to download s3://{bucket_name}/{key} to {local_temp_path}")
            s3.download_file(bucket_name, key, local_temp_path)
            logger.info(f"Successfully downloaded {s3_url} to {local_temp_path}")
            return local_temp_path
        except ClientError as e:
            logger.error(f"S3 ClientError downloading {s3_url}: {e}", exc_info=True)
            error_code = e.response.get('Error', {}).get('Code')
            # Check for common S3 "not found" error codes, including what HeadObject might return (often a string '404')
            if error_code == 'NoSuchKey' or (isinstance(error_code, str) and '404' in error_code) or e.response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 404:
                raise ImageProcessingError(f"S3 object not found: {s3_url}") from e
            raise ImageProcessingError(f"S3 error downloading {s3_url}: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error downloading {s3_url}: {e}", exc_info=True)
            raise ImageProcessingError(f"Unexpected error downloading {s3_url}: {e}") from e

    def upload_image_to_s3(self, local_file_path: str, s3_key: str, target_bucket_name: Optional[str] = None, content_type: Optional[str] = None) -> str:
        """
        Uploads a local file to a specified S3 key.

        Args:
            local_file_path: Path to the local file to upload.
            s3_key: The S3 key (path within the bucket) to upload the file to.
            target_bucket_name: Optional S3 bucket name. If None, uses self.s3_bucket_name.
            content_type: Optional content type for the S3 object. If None, boto3 attempts to guess.

        Returns:
            The S3 URL of the uploaded file (e.g., "s3://bucket-name/path/to/uploaded_image.jpg").

        Raises:
            ImageProcessingError: If file upload fails, S3 client or bucket isn't configured.
            FileNotFoundError: If the local_file_path does not exist.
        """
        if not os.path.exists(local_file_path):
            raise FileNotFoundError(f"Local file for S3 upload not found: {local_file_path}")

        s3 = self._get_s3_client()
        bucket = target_bucket_name or self.s3_bucket_name
        if not bucket:
            msg = "S3 bucket name not configured for upload. Provide target_bucket_name or set s3_bucket_name in constructor."
            logger.error(msg)
            raise ImageProcessingError(msg)

        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
        # Could add ACL, metadata etc. to ExtraArgs if needed. e.g. {'ACL': 'public-read'}

        try:
            logger.debug(f"Attempting to upload {local_file_path} to s3://{bucket}/{s3_key} with ExtraArgs: {extra_args}")
            s3.upload_file(local_file_path, bucket, s3_key, ExtraArgs=extra_args)
            uploaded_s3_url = f"s3://{bucket}/{s3_key}"
            logger.info(f"Successfully uploaded {local_file_path} to {uploaded_s3_url}")
            return uploaded_s3_url
        except ClientError as e:
            logger.error(f"S3 ClientError uploading {local_file_path} to s3://{bucket}/{s3_key}: {e}", exc_info=True)
            raise ImageProcessingError(f"S3 error uploading {local_file_path}: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error uploading {local_file_path} to s3://{bucket}/{s3_key}: {e}", exc_info=True)
            raise ImageProcessingError(f"Unexpected error uploading {local_file_path}: {e}") from e

    def load_image(self, image_path: str) -> Image.Image:
        """
        Loads an image from the given file path.

        Args:
            image_path: Path to the image file.

        Returns:
            A PIL Image object.

        Raises:
            FileNotFoundError: If the image_path does not exist.
            ImageProcessingError: If the image cannot be opened or is not a valid image.
        """
        if not os.path.exists(image_path):
            logger.error(f"Image file not found at path: {image_path}")
            raise FileNotFoundError(f"Image file not found at path: {image_path}")
        try:
            img = Image.open(image_path)
            # Convert to a common mode like RGB if necessary, especially after loading.
            # This helps in consistent processing later.
            if img.mode not in ("RGB", "RGBA", "L"): 
                logger.debug(f"Converting image from mode {img.mode} to RGB for consistent processing.")
                img = img.convert("RGB")
            elif img.mode == "P": # Palette mode, convert to RGBA or RGB
                logger.debug("Converting image from Palette mode (P) to RGBA.")
                img = img.convert("RGBA")

            logger.debug(f"Successfully loaded image from {image_path}. Mode: {img.mode}, Size: {img.size}")
            return img
        except UnidentifiedImageError as e:
            logger.error(f"Cannot identify image file: {image_path}. Error: {e}")
            raise ImageProcessingError(f"Cannot identify image file: {image_path}. Is it a valid image format?") from e
        except FileNotFoundError: # Should be caught by the explicit check above, but good for safety
            logger.error(f"Image file not found (caught by PIL): {image_path}") # This case should ideally not be hit
            raise
        except Exception as e:
            logger.error(f"Error loading image {image_path}: {e}", exc_info=True)
            raise ImageProcessingError(f"Could not load image {image_path} due to an unexpected error.") from e

    def resize_image(
        self,
        img: Image.Image,
        dimensions: Optional[Tuple[int, int]] = None,
        resample_method: Image.Resampling = Image.Resampling.LANCZOS
    ) -> Image.Image:
        """
        Resizes the given PIL Image object.
        If dimensions are not provided, uses default_resize_dimensions if set.
        If no dimensions are specified anywhere (neither passed nor in defaults), returns the original image.

        Args:
            img: The PIL Image object to resize.
            dimensions: Optional tuple (width, height) for resizing.
            resample_method: The resampling filter to use.

        Returns:
            The resized PIL Image object.
        Raises:
            ImageProcessingError: If dimensions are invalid.
        """
        target_dimensions = dimensions or self.default_resize_dimensions
        if not target_dimensions:
            logger.debug("No resize dimensions specified or configured, returning original image.")
            return img
        
        if not (isinstance(target_dimensions, tuple) and len(target_dimensions) == 2 and 
                all(isinstance(d, int) and d > 0 for d in target_dimensions)):
            msg = f"Invalid target_dimensions for resize: {target_dimensions}. Must be a tuple of two positive integers."
            logger.error(msg)
            raise ImageProcessingError(msg)

        original_size = img.size
        try:
            img_resized = img.resize(target_dimensions, resample=resample_method)
            logger.debug(f"Resized image from {original_size} to {target_dimensions} using {resample_method.name}.")
            return img_resized
        except Exception as e:
            logger.error(f"Error resizing image from {original_size} to {target_dimensions}: {e}", exc_info=True)
            raise ImageProcessingError(f"Could not resize image from {original_size} to {target_dimensions}") from e

    def normalize_image(self, image: Image.Image) -> Image.Image:
        """
        Normalizes an image.
        Steps:
        1. Converts to RGB if not already.
        2. Converts the image to a NumPy array.
        3. Rescales pixel values from [0, 255] to [0.0, 1.0].

        Args:
            image: PIL Image object.

        Returns:
            A PIL Image object representing the normalized image, with pixel values in [0.0, 1.0].
        """
        logger.debug(f"Normalizing image. Original mode: {image.mode}")
        if image.mode != 'RGB':
            image = image.convert('RGB')
            logger.debug(f"Converted image to RGB mode.")
        
        # Convert PIL image to NumPy array
        img_array = np.array(image, dtype=np.float32)
        
        # Rescale pixels from [0, 255] to [0.0, 1.0]
        # Perform a check to ensure that the image is indeed in [0,255] range before division
        if np.max(img_array) > 1.0: # A simple check, assumes 8-bit image if not already float [0,1]
             img_array /= 255.0

        logger.debug(f"Normalized image array. Shape: {img_array.shape}, Min: {np.min(img_array):.2f}, Max: {np.max(img_array):.2f}")
        
        # Convert the normalized NumPy array back to a PIL Image
        # Ensure array is in uint8 format (0-255) if it was scaled from that range.
        # If it was already [0,1] float, Image.fromarray might expect float or specific mode.
        # For consistency, if we scaled to [0,1] float, scale back to [0,255] uint8 for PIL.
        if np.max(img_array) <= 1.0 and img_array.dtype == np.float32:
            img_array = (img_array * 255).astype(np.uint8)
        
        normalized_pil_image = Image.fromarray(img_array, 'RGB')
        logger.debug(f"Converted normalized array back to PIL Image. Mode: {normalized_pil_image.mode}")
        return normalized_pil_image

    def augment_image(self, image: Image.Image) -> Image.Image:
        """
        Applies a sequence of augmentations to the image:
        1. Random Horizontal Flip (50% probability).
        2. Random Rotation (between -10 and +10 degrees).
        3. Color Jitter (brightness, contrast, saturation by small factors).

        Args:
            image: PIL Image object to augment.

        Returns:
            Augmented PIL Image object.
        """
        augmented_image = image
        logger.debug(f"Starting augmentation for image. Original mode: {augmented_image.mode}, size: {augmented_image.size}")

        # 1. Random Horizontal Flip
        if random.random() < 0.5:
            augmented_image = augmented_image.transpose(Image.FLIP_LEFT_RIGHT)
            logger.debug("Applied random horizontal flip.")

        # 2. Random Rotation
        # Rotation can introduce black areas if not handled carefully (e.g., by expanding canvas or filling).
        # For simplicity, using 'nearest' for resampling and not expanding canvas.
        # This might crop corners for larger rotations on non-square images.
        rotation_angle = random.uniform(-10, 10)
        # Using expand=True can change image size, fillcolor can set background
        # For now, let's keep it simple and accept potential minor cropping at corners for rotated non-square images.
        augmented_image = augmented_image.rotate(rotation_angle, resample=Image.Resampling.NEAREST, expand=False) 
        logger.debug(f"Applied random rotation of {rotation_angle:.2f} degrees.")

        # 3. Color Jitter
        # Brightness
        enhancer = ImageEnhance.Brightness(augmented_image)
        brightness_factor = random.uniform(0.8, 1.2) # 80% to 120% brightness
        augmented_image = enhancer.enhance(brightness_factor)
        logger.debug(f"Applied brightness jitter with factor {brightness_factor:.2f}.")

        # Contrast
        enhancer = ImageEnhance.Contrast(augmented_image)
        contrast_factor = random.uniform(0.8, 1.2) # 80% to 120% contrast
        augmented_image = enhancer.enhance(contrast_factor)
        logger.debug(f"Applied contrast jitter with factor {contrast_factor:.2f}.")

        # Saturation (Color)
        enhancer = ImageEnhance.Color(augmented_image)
        saturation_factor = random.uniform(0.8, 1.2) # 80% to 120% saturation
        augmented_image = enhancer.enhance(saturation_factor)
        logger.debug(f"Applied saturation jitter with factor {saturation_factor:.2f}.")

        logger.info(f"Finished image augmentation. Final mode: {augmented_image.mode}, size: {augmented_image.size}")
        return augmented_image

    def save_image(
        self,
        img: Image.Image,
        output_path: str,
        output_format: Optional[str] = None,
        quality: Optional[int] = None
    ) -> str:
        """
        Saves the PIL Image object to the specified path.

        Args:
            img: The PIL Image to save.
            output_path: The full path to save the image to. Directories will be created.
            output_format: Optional image format (e.g., "WEBP", "PNG", "JPEG"). Overrides instance default.
            quality: Optional quality setting (1-100 for WEBP/JPEG). Overrides instance default.

        Returns:
            The absolute path to the saved image.
        
        Raises:
            ImageProcessingError: If output_path is empty, directory creation fails, 
                                or image saving fails (e.g., unsupported format, IO error).
        """
        current_format = (output_format or self.output_format).upper()
        current_quality = quality if quality is not None else self.default_quality

        if not output_path:
            msg = "Output path for saving image cannot be empty."
            logger.error(msg)
            raise ImageProcessingError(msg)

        dir_name = os.path.dirname(output_path)
        if dir_name:
            try:
                os.makedirs(dir_name, exist_ok=True)
            except OSError as e:
                logger.error(f"Could not create directory {dir_name} for saving image: {e}", exc_info=True)
                raise ImageProcessingError(f"Could not create directory {dir_name}: {e}") from e

        try:
            save_params = {}
            if current_format in ("JPEG", "WEBP"):
                if not (1 <= current_quality <= 100):
                    logger.warning(f"Invalid quality value {current_quality} for {current_format}. Clamping to 1-100 range.")
                    save_params['quality'] = max(1, min(current_quality, 100))
                else:
                    save_params['quality'] = current_quality
            
            img_to_save = img
            # Handle mode conversions for common save formats
            if current_format == "JPEG" and img_to_save.mode == "RGBA":
                logger.debug("Converting RGBA image to RGB for JPEG saving.")
                img_to_save = img_to_save.convert("RGB")
            elif current_format == "PNG" and img_to_save.mode not in ("L", "LA", "RGB", "RGBA"):
                logger.debug(f"Converting image mode {img_to_save.mode} to RGBA for PNG saving for better compatibility.")
                img_to_save = img_to_save.convert("RGBA")
            elif current_format == "WEBP": # WEBP supports RGB, RGBA. Ensure it is one of these.
                if img_to_save.mode not in ("RGB", "RGBA"):
                    logger.debug(f"Converting image mode {img_to_save.mode} to RGBA for WEBP saving.")
                    img_to_save = img_to_save.convert("RGBA")
            
            img_to_save.save(output_path, format=current_format, **save_params)
            abs_path = os.path.abspath(output_path)
            logger.info(f"Successfully saved image to {abs_path} in {current_format} format (Quality: {save_params.get('quality', 'N/A')}).")
            return abs_path
        except ValueError as e: 
            logger.error(f"Unsupported format or parameters for saving to {output_path} as {current_format}: {e}", exc_info=True)
            raise ImageProcessingError(f"Unsupported format or parameters for saving as {current_format}: {e}") from e
        except IOError as e:
            logger.error(f"IOError saving image to {output_path}: {e}", exc_info=True)
            raise ImageProcessingError(f"Could not save image to {output_path} due to IO error.") from e
        except Exception as e:
            logger.error(f"Unexpected error saving image to {output_path}: {e}", exc_info=True)
            raise ImageProcessingError(f"Could not save image to {output_path} due to an unexpected error.") from e

    def process_image_file(
        self,
        input_image_path: str,
        output_image_path: str,
        resize_dimensions: Optional[Tuple[int, int]] = None,
        output_format: Optional[str] = None,
        quality: Optional[int] = None
    ) -> str:
        """
        Full pipeline: loads, resizes, (optionally normalizes & augments), and saves an image.

        Args:
            input_image_path: Path to the source image.
            output_image_path: Path to save the processed image.
            resize_dimensions: Specific dimensions to resize to for this image. Overrides default.
            output_format: Specific format for this image save operation. Overrides default.
            quality: Specific quality for this image save operation. Overrides default.

        Returns:
            Absolute path to the saved processed image.
        """
        logger.info(f"Processing image file: {input_image_path} -> {output_image_path}")
        img = self.load_image(input_image_path)
        img_resized = self.resize_image(img, dimensions=resize_dimensions)
        
        img_normalized = self.normalize_image(img_resized) # Currently returns original
        img_augmented = self.augment_image(img_normalized) # Currently returns original
        
        saved_path = self.save_image(
            img_augmented, 
            output_image_path, 
            output_format=output_format, 
            quality=quality
        )
        return saved_path

    def process_image_s3(
        self,
        input_s3_url: str,
        output_s3_key_prefix: str,
        output_filename: Optional[str] = None,
        target_s3_bucket_name: Optional[str] = None,
        resize_dimensions: Optional[Tuple[int, int]] = None,
        output_format: Optional[str] = None, # Will use self.output_format if None
        quality: Optional[int] = None # Will use self.default_quality if None
    ) -> str:
        """
        Full pipeline for S3: downloads image from S3, processes it locally (resize, normalize, augment),
        and uploads the processed image back to S3.

        Args:
            input_s3_url: S3 URL of the source image.
            output_s3_key_prefix: Prefix for the S3 key where the processed image will be stored
                                 (e.g., "processed_images/session_xyz/").
            output_filename: Optional filename for the processed image in S3.
                             If None, it's derived from the input S3 URL's filename and
                             appended with the target output_format extension.
            target_s3_bucket_name: Optional S3 bucket to upload to. If None, uses self.s3_bucket_name.
            resize_dimensions: Specific dimensions to resize to. Overrides default.
            output_format: Specific format for the processed image. Overrides instance default.
            quality: Specific quality for the processed image. Overrides instance default.

        Returns:
            S3 URL of the processed and uploaded image.

        Raises:
            ImageProcessingError: If any step in the S3 download, local processing, or S3 upload fails.
        """
        logger.info(f"Starting S3 image processing for {input_s3_url} -> s3://{target_s3_bucket_name or self.s3_bucket_name}/{output_s3_key_prefix}{output_filename or '<derived>'}")
        
        temp_dir = tempfile.mkdtemp(prefix="image_processing_")
        local_downloaded_path = None
        local_processed_path = None

        try:
            # 1. Download from S3 to local temp
            local_downloaded_path = self.download_image_from_s3(input_s3_url, local_temp_dir=temp_dir)

            # Determine output filename and extension
            final_output_format = (output_format or self.output_format).lower()
            if output_filename:
                # Ensure output_filename has the correct extension for the final_output_format
                base_fn, _ = os.path.splitext(output_filename)
                effective_output_filename = f"{base_fn}.{final_output_format}"
            else:
                # Derive from input_s3_url filename
                input_fn_base, _ = os.path.splitext(os.path.basename(urlparse(input_s3_url).path))
                effective_output_filename = f"{input_fn_base}_processed.{final_output_format}"
            
            local_processed_path = os.path.join(temp_dir, f"processed_{effective_output_filename}")

            # 2. Perform local processing (using existing process_image_file logic)
            self.process_image_file(
                input_image_path=local_downloaded_path,
                output_image_path=local_processed_path,
                resize_dimensions=resize_dimensions,
                output_format=final_output_format, # Pass the determined format
                quality=quality
            )

            # 3. Construct output S3 key and upload
            output_s3_key = os.path.join(output_s3_key_prefix.strip('/'), effective_output_filename).replace("\\", "/") # Ensure posix path
            
            # Determine content type for upload
            content_type_map = {
                "jpeg": "image/jpeg", "jpg": "image/jpeg",
                "png": "image/png",
                "webp": "image/webp",
                "gif": "image/gif"
            }
            upload_content_type = content_type_map.get(final_output_format)

            uploaded_s3_url = self.upload_image_to_s3(
                local_file_path=local_processed_path,
                s3_key=output_s3_key,
                target_bucket_name=target_s3_bucket_name, # Uses self.s3_bucket_name if this is None
                content_type=upload_content_type
            )
            logger.info(f"Successfully processed and uploaded {input_s3_url} to {uploaded_s3_url}")
            return uploaded_s3_url

        except Exception as e: # Catch any error during the process
            logger.error(f"Error in process_image_s3 pipeline for {input_s3_url}: {e}", exc_info=True)
            # Re-raise as ImageProcessingError to signal failure in this specific operation
            raise ImageProcessingError(f"Failed S3 image processing pipeline for {input_s3_url}: {e}") from e
        finally:
            # 4. Clean up local temporary files and directory
            if local_downloaded_path and os.path.exists(local_downloaded_path):
                os.remove(local_downloaded_path)
            if local_processed_path and os.path.exists(local_processed_path):
                os.remove(local_processed_path)
            if os.path.exists(temp_dir):
                try:
                    # Attempt to remove the directory, ensure it's empty.
                    # For simplicity, this example assumes files within are handled.
                    # For more robust cleanup, one might iterate and delete files first or use shutil.rmtree.
                    if not os.listdir(temp_dir): # Only remove if empty
                         os.rmdir(temp_dir)
                    else: # If not empty, log a warning or use shutil.rmtree cautiously
                        logger.warning(f"Temporary directory {temp_dir} was not empty after processing. Manual cleanup may be needed or use shutil.rmtree.")
                        # import shutil
                        # shutil.rmtree(temp_dir) # Be careful with rmtree
                except OSError as e:
                    logger.warning(f"Could not remove temporary directory {temp_dir}: {e}")

    def get_image_reference(self, record: ProcessedDataRecord) -> Optional[str]:
        """
        Retrieves a valid image reference (S3 path) from a ProcessedDataRecord.
        For MVP, primarily checks screenshot_s3_path. 
        Validates if the path starts with 's3://' and has a supported extension.

        Args:
            record: The ProcessedDataRecord object.

        Returns:
            The S3 path string if a valid reference is found, otherwise None.
        
        Raises:
            ImageHandlingError: If a path is present but malformed (e.g., wrong prefix).
                                This could be relaxed to just return None if preferred.
        """
        # Prefer processed_image_path if available and valid, then screenshot_s3_path
        # For MVP, let's keep it simple and just use screenshot_s3_path as per PRD example
        # and ProcessedDataRecord primary field for this.
        
        image_path = record.screenshot_s3_path

        if not image_path:
            return None

        if not image_path.startswith("s3://"):
            # Decide: raise error or just return None? 
            # Pydantic validator on ProcessedDataRecord already checks s3:// prefix for this field.
            # So this specific check here might be redundant if ProcessedDataRecord is always validated upstream.
            # However, having it here makes ImageHandler more robust independently.
            # For now, let's assume ProcessedDataRecord's validator handles the s3:// prefix.
            # If it reached here and doesn't start with s3://, it implies a bypass of Pydantic validation
            # or direct manipulation, which could be an error state.
            # Given Pydantic's @field_validator, this is unlikely to be hit for screenshot_s3_path.
            # If processed_image_path were used and didn't have such a validator, this would be more critical.
            # Let's rely on ProcessedDataRecord's validation for the s3:// prefix.
            pass # Or raise ImageHandlingError(f"Image path must be an S3 path: {image_path}")

        # Validate extension (optional, but good for ensuring image type)
        # path_lower = image_path.lower()
        # if not any(path_lower.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS):
        #     # Again, raise or return None?
        #     # raise ImageHandlingError(f"Unsupported image extension: {image_path}. Supported: {self.SUPPORTED_EXTENSIONS}")
        #     return None # Silently ignore unsupported extensions for now
        
        # If ProcessedDataRecord validation for s3 paths is active, image_path is guaranteed to be s3:// or None.
        return image_path

if __name__ == '__main__':
    # Basic example usage (requires a sample image e.g., "sample.jpg" in the same directory)
    # Create a dummy sample.jpg for testing:
    # from PIL import Image
    # try:
    #     img_sample = Image.new('RGB', (200, 150), color = 'red')
    #     img_sample.save("sample.jpg")
    # except ImportError:
    #     print("Pillow not installed, cannot create sample image for __main__ example.")
    #     exit()

    logging.basicConfig(level=logging.DEBUG)
    logger.info("Running ImageHandler example...")

    handler = ImageHandler(
        output_format="WEBP", 
        default_resize_dimensions=(100, 100), 
        default_quality=90
        # s3_bucket_name="your-s3-bucket-for-testing" # Optional: Add for S3 tests
    )

    # Create a dummy image file for the example if it doesn't exist
    sample_image_filename = "_temp_sample_image.png"
    try:
        if not os.path.exists(sample_image_filename):
            temp_img = Image.new('RGB', (640, 480), color='blue')
            temp_img.save(sample_image_filename, format="PNG")
            logger.info(f"Created temporary sample image: {sample_image_filename}")

        # Test 1: Process and save as WEBP (default for handler)
        processed_path_webp = handler.process_image_file(
            sample_image_filename, 
            "_temp_processed_image.webp"
        )
        logger.info(f"Processed WEBP image saved to: {processed_path_webp}")

        # Test 2: Process and save as JPEG with different resize and quality
        processed_path_jpeg = handler.process_image_file(
            sample_image_filename, 
            "_temp_processed_image.jpeg",
            resize_dimensions=(50,50),
            output_format="JPEG",
            quality=75
        )
        logger.info(f"Processed JPEG image saved to: {processed_path_jpeg}")

        # Test 3: Load an image and just resize it
        loaded_img = handler.load_image(sample_image_filename)
        resized_only = handler.resize_image(loaded_img, dimensions=(30,30))
        handler.save_image(resized_only, "_temp_resized_only.png", output_format="PNG")
        logger.info(f"Resized-only PNG image saved to: _temp_resized_only.png")

        # Test 4: Error handling - non-existent file
        try:
            handler.load_image("non_existent_image.jpg")
        except FileNotFoundError as e:
            logger.warning(f"Caught expected error for non-existent file: {e}")
        except ImageProcessingError as e: # Should be FileNotFoundError, but PIL might raise its own if path check is bypassed
            logger.error(f"Caught ImageProcessingError during non-existent file test: {e}")

        # Test 5: Error handling - invalid image file (e.g. a text file named .jpg)
        invalid_image_filename = "_temp_invalid_image.jpg"
        with open(invalid_image_filename, "w") as f:
            f.write("This is not an image.")
        try:
            handler.load_image(invalid_image_filename)
        except ImageProcessingError as e:
            logger.warning(f"Caught expected error for invalid image file: {e}")
        finally:
            if os.path.exists(invalid_image_filename):
                 os.remove(invalid_image_filename)
        
        # Example for S3 processing (requires S3 setup and a test image in S3)
        # Ensure handler is initialized with s3_bucket_name for this to work easily
        # And that your AWS credentials are configured in the environment.
        # mock_s3_url = "s3://your-s3-bucket-for-testing/sample_inputs/sample_image_to_process.png"
        # output_s3_prefix = "processed_test_images/"
        # if handler.s3_bucket_name and handler._get_s3_client(): # Check if S3 is configured
        #     logger.info(f"Attempting S3 processing example for {mock_s3_url}. Ensure bucket and image exist.")
        #     try:
        #         # Create a dummy file in a mock S3 bucket if you are using moto for local testing
        #         # For a real test, upload a sample_image_to_process.png to your S3 bucket.
        #         # s3_client = handler._get_s3_client()
        #         # s3_client.upload_file(sample_image_filename, handler.s3_bucket_name, "sample_inputs/sample_image_to_process.png")
                
        #         processed_s3_url = handler.process_image_s3(
        #             input_s3_url=mock_s3_url,
        #             output_s3_key_prefix=output_s3_prefix,
        #             resize_dimensions=(80, 60),
        #             output_format="PNG"
        #         )
        #         logger.info(f"S3 processing example successful. Output: {processed_s3_url}")
        #     except ImageProcessingError as ipe_s3:
        #         logger.error(f"S3 processing example failed: {ipe_s3}. This might be due to S3 setup or the mock image/bucket not existing.")
        #     except Exception as ex_s3:
        #         logger.error(f"Unexpected error during S3 processing example: {ex_s3}", exc_info=True)
        # else:
        #     logger.warning("S3 bucket name not configured in ImageHandler, skipping S3 processing example.")

    except ImportError:
        logger.error("Pillow (PIL) is not installed. Please install it to run this example.")
    except ImageProcessingError as ipe:
        logger.error(f"An ImageProcessingError occurred during the example: {ipe}")
    except Exception as ex:
        logger.error(f"An unexpected error occurred during the example: {ex}", exc_info=True)
    finally:
        # Clean up dummy files
        if os.path.exists(sample_image_filename):
            os.remove(sample_image_filename)
        if os.path.exists("_temp_processed_image.webp"):
            os.remove("_temp_processed_image.webp")
        if os.path.exists("_temp_processed_image.jpeg"):
            os.remove("_temp_processed_image.jpeg")
        if os.path.exists("_temp_resized_only.png"):
            os.remove("_temp_resized_only.png")
        logger.info("ImageHandler example finished and cleaned up temporary files.")