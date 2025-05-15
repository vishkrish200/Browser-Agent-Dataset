import pytest
import os
from typing import Optional
from pydantic import HttpUrl
from PIL import Image, ImageChops, ImageEnhance, UnidentifiedImageError
import shutil # For cleaning up test directories
import boto3 # For S3
from moto import mock_aws # For mocking S3
from botocore.exceptions import ClientError # For S3 errors
import tempfile # For temporary files with S3 tests
from unittest.mock import patch, ANY, MagicMock # For mocking
import numpy as np
import random # Added for augmentation tests that mock random.uniform
import io
from pathlib import Path

from src.dataset_builder.image_handler import ImageHandler, ImageProcessingError, DEFAULT_IMAGE_FORMAT, SUPPORTED_FORMATS
from src.dataset_builder.types import ProcessedDataRecord, ActionDetail
# Assuming ImageHandlingError might be used in future or for other S3-related specific errors
# from src.dataset_builder.exceptions import ImageHandlingError

# Helper to create dummy records for get_image_reference tests
def create_image_test_record(
    screenshot_s3_path: Optional[str],
    step_id: str = "test_step",
) -> ProcessedDataRecord:
    return ProcessedDataRecord(
        step_id=step_id,
        session_id="sess_img_test",
        ts=1672531200,
        url=HttpUrl("http://example.com/img_test"),
        action=ActionDetail(type="screenshot_action"),
        screenshot_s3_path=screenshot_s3_path
    )

@pytest.fixture(scope="module")
def temp_test_dir():
    """Creates a temporary directory for test images and cleans it up afterwards."""
    dir_path = "_temp_test_images_output_module" # Changed name to avoid conflict if run with old states
    os.makedirs(dir_path, exist_ok=True)
    yield dir_path
    shutil.rmtree(dir_path)

@pytest.fixture
def sample_image_rgb(temp_test_dir) -> str:
    img_path = os.path.join(temp_test_dir, "sample_rgb.png")
    img = Image.new('RGB', (60, 30), color = 'red')
    img.save(img_path)
    return img_path

@pytest.fixture
def sample_image_rgba(temp_test_dir) -> str:
    img_path = os.path.join(temp_test_dir, "sample_rgba.png")
    img = Image.new('RGBA', (50, 40), color = (0, 255, 0, 128))
    img.save(img_path)
    return img_path

@pytest.fixture
def sample_image_palette(temp_test_dir) -> str:
    img_path = os.path.join(temp_test_dir, "sample_palette.gif")
    rgb_img = Image.new('RGB', (40, 20), color='blue')
    palette_img = rgb_img.convert("P", palette=Image.Palette.ADAPTIVE, colors=16)
    palette_img.save(img_path, format='GIF')
    return img_path

@pytest.fixture
def invalid_image_file(temp_test_dir) -> str:
    file_path = os.path.join(temp_test_dir, "not_an_image.jpg")
    with open(file_path, "w") as f:
        f.write("This is definitely not an image.")
    return file_path

@pytest.fixture
def image_handler_default() -> ImageHandler:
    return ImageHandler()

@pytest.fixture(scope="module")
def sample_image_asymmetric_2x1(tmp_path_factory) -> str:
    """Creates a simple 2x1 asymmetric image (Red, Blue) for testing flips/rotations."""
    img_dir = tmp_path_factory.mktemp("asymmetric_images_module")
    img_path = img_dir / "asymmetric_2x1.png"
    # Create a 2x1 image. Pixel (0,0) is Red, Pixel (1,0) is Blue.
    img = Image.new('RGB', (2, 1), color = 'red')
    img.putpixel((1, 0), (0, 0, 255)) # Set (1,0) to Blue
    img.save(img_path, format="PNG")
    return str(img_path)

class TestImageHandlerLocalProcessing: # Renamed for clarity
    # Existing tests for local processing (load, resize, save, process_image_file)
    # from the previous session would go here.
    # For brevity, I'm assuming they exist and are correct.
    # I will add the get_image_reference tests here as they don't involve S3.

    def test_get_image_reference_valid_s3_path(self):
        handler = ImageHandler()
        valid_path = "s3://my-bucket/screenshots/image.webp"
        record = create_image_test_record(screenshot_s3_path=valid_path)
        assert handler.get_image_reference(record) == valid_path

    def test_get_image_reference_none_path(self):
        handler = ImageHandler()
        record = create_image_test_record(screenshot_s3_path=None)
        assert handler.get_image_reference(record) is None

    @pytest.mark.skip(reason="ProcessedDataRecord validation prevents empty string for s3_path")
    def test_get_image_reference_empty_string_path(self):
        handler = ImageHandler()
        record = create_image_test_record(screenshot_s3_path="") 
        assert handler.get_image_reference(record) is None

    def test_get_image_reference_different_supported_extensions(self):
        handler = ImageHandler()
        paths = [
            "s3://bucket/img.webp", "s3://bucket/img.png",
            "s3://bucket/img.jpg", "s3://bucket/img.jpeg",
        ]
        for path in paths:
            record = create_image_test_record(screenshot_s3_path=path)
            assert handler.get_image_reference(record) == path
            
    # Initialization Tests
    def test_image_handler_initialization(self, image_handler_default: ImageHandler):
        assert image_handler_default.output_format == "WEBP"
        assert image_handler_default.default_resize_dimensions is None
        assert image_handler_default.default_quality == 80
        assert image_handler_default.s3_bucket_name is None # Check S3 default

    def test_image_handler_custom_initialization(self):
        handler = ImageHandler(output_format="PNG", default_resize_dimensions=(100,100), default_quality=95, s3_bucket_name="custom-bucket")
        assert handler.output_format == "PNG"
        assert handler.default_resize_dimensions == (100,100)
        assert handler.default_quality == 95
        assert handler.s3_bucket_name == "custom-bucket"

    # Load Image Tests
    def test_load_image_success_rgb(self, image_handler_default: ImageHandler, sample_image_rgb: str):
        img = image_handler_default.load_image(sample_image_rgb)
        assert img is not None; assert img.format == "PNG"; assert img.mode == "RGB"; assert img.size == (60, 30)

    def test_load_image_success_rgba(self, image_handler_default: ImageHandler, sample_image_rgba: str):
        img = image_handler_default.load_image(sample_image_rgba)
        assert img is not None; assert img.format == "PNG"; assert img.mode == "RGBA"; assert img.size == (50, 40)

    def test_load_image_palette_conversion(self, image_handler_default: ImageHandler, sample_image_palette: str):
        img = image_handler_default.load_image(sample_image_palette)
        assert img is not None
        # After conversion from palette, format becomes None, mode should be RGB or RGBA
        assert img.format is None 
        assert img.mode in ("RGBA", "RGB")
        assert img.size == (40, 20)

    def test_load_image_file_not_found(self, image_handler_default: ImageHandler):
        with pytest.raises(FileNotFoundError): image_handler_default.load_image("non_existent_file.jpg")

    def test_load_image_invalid_image(self, image_handler_default: ImageHandler, invalid_image_file: str):
        with pytest.raises(ImageProcessingError, match="Cannot identify image file"): image_handler_default.load_image(invalid_image_file)

    # Resize Image Tests (copied from previous state, ensure they are correct)
    def test_resize_image_specific_dimensions(self, image_handler_default: ImageHandler, sample_image_rgb: str):
        img = image_handler_default.load_image(sample_image_rgb)
        resized_img = image_handler_default.resize_image(img, dimensions=(30, 15))
        assert resized_img.size == (30, 15)

    def test_resize_image_default_dimensions(self, sample_image_rgb: str): # Added sample_image_rgb dependency
        handler = ImageHandler(default_resize_dimensions=(20,10))
        pil_img = handler.load_image(sample_image_rgb) # Load the image first
        resized_img = handler.resize_image(pil_img)
        assert resized_img.size == (20, 10)

    def test_resize_image_no_dimensions(self, image_handler_default: ImageHandler, sample_image_rgb: str):
        img = image_handler_default.load_image(sample_image_rgb)
        resized_img = image_handler_default.resize_image(img)
        assert resized_img.size == img.size

    @pytest.mark.parametrize("invalid_dims", [(30, -15), (0, 15), (30,), "30x15"])
    def test_resize_image_invalid_dimensions(self, image_handler_default: ImageHandler, sample_image_rgb: str, invalid_dims):
        img = image_handler_default.load_image(sample_image_rgb)
        with pytest.raises(ImageProcessingError, match="Invalid target_dimensions for resize"):
            image_handler_default.resize_image(img, dimensions=invalid_dims)
    
    # Save Image Tests (copied from previous state)
    @pytest.mark.parametrize("save_format, expected_mode_after_load_if_alpha", [
        ("PNG", "RGBA"), ("JPEG", "RGB"), ("WEBP", "RGBA")
    ])
    def test_save_image_formats_rgba_input(self, image_handler_default: ImageHandler, sample_image_rgba: str, temp_test_dir: str, save_format: str, expected_mode_after_load_if_alpha: str):
        img_to_save = image_handler_default.load_image(sample_image_rgba) # Input is RGBA
        output_filename = f"saved_test_rgba_input.{save_format.lower()}"
        save_path = os.path.join(temp_test_dir, output_filename)
        
        returned_path = image_handler_default.save_image(img_to_save, save_path, output_format=save_format)
        assert os.path.exists(save_path); assert returned_path == os.path.abspath(save_path)

        loaded_saved_img = Image.open(save_path)
        assert loaded_saved_img.format == save_format
        if save_format == "JPEG": assert loaded_saved_img.mode == "RGB"
        else: assert loaded_saved_img.mode == expected_mode_after_load_if_alpha


    @pytest.mark.parametrize("quality_val, is_low_quality", [(10, True), (95, False)])
    def test_save_image_quality_jpeg(self, image_handler_default: ImageHandler, sample_image_rgb: str, temp_test_dir: str, quality_val: int, is_low_quality: bool):
        img = image_handler_default.load_image(sample_image_rgb)
        save_path = os.path.join(temp_test_dir, f"quality_test_{quality_val}.jpeg")
        image_handler_default.save_image(img, save_path, output_format="JPEG", quality=quality_val)
        assert os.path.exists(save_path)
        # Store size for comparison in a later test or manually inspect
        setattr(self, f"jpeg_size_q{quality_val}", os.path.getsize(save_path))
        if hasattr(self, "jpeg_size_q10") and hasattr(self, "jpeg_size_q95"):
            assert self.jpeg_size_q10 < self.jpeg_size_q95


    @pytest.mark.parametrize("quality_val, is_low_quality", [(10, True), (95, False)])
    def test_save_image_quality_webp(self, image_handler_default: ImageHandler, sample_image_rgba: str, temp_test_dir: str, quality_val: int, is_low_quality: bool): # Use RGBA for WEBP
        img_rgba = image_handler_default.load_image(sample_image_rgba)
        save_path = os.path.join(temp_test_dir, f"quality_test_{quality_val}.webp")
        image_handler_default.save_image(img_rgba, save_path, output_format="WEBP", quality=quality_val)
        assert os.path.exists(save_path)
        setattr(self, f"webp_size_q{quality_val}", os.path.getsize(save_path))
        if hasattr(self, "webp_size_q10") and hasattr(self, "webp_size_q95"):
            assert self.webp_size_q10 < self.webp_size_q95


    def test_save_image_empty_output_path(self, image_handler_default: ImageHandler, sample_image_rgb: str):
        img = image_handler_default.load_image(sample_image_rgb)
        with pytest.raises(ImageProcessingError, match="Output path for saving image cannot be empty"):
            image_handler_default.save_image(img, "")

    def test_save_image_create_directory(self, image_handler_default: ImageHandler, sample_image_rgb: str, temp_test_dir: str):
        img = image_handler_default.load_image(sample_image_rgb)
        nested_dir = os.path.join(temp_test_dir, "nested", "deeply")
        save_path = os.path.join(nested_dir, "img_in_nested.png")
        assert not os.path.exists(nested_dir)
        image_handler_default.save_image(img, save_path, output_format="PNG")
        assert os.path.exists(save_path)

    # Process Image File Tests
    def test_process_image_file_pipeline(self, image_handler_default: ImageHandler, sample_image_rgb: str, temp_test_dir: str):
        output_filename = "processed_pipeline.webp"; output_path = os.path.join(temp_test_dir, output_filename)
        resize_dims = (20, 10)
        returned_path = image_handler_default.process_image_file(sample_image_rgb, output_path, resize_dimensions=resize_dims, output_format="WEBP", quality=70)
        assert os.path.exists(output_path); assert returned_path == os.path.abspath(output_path)
        processed_img = Image.open(output_path)
        assert processed_img.format == "WEBP"; assert processed_img.size == resize_dims

    # Normalization Tests
    def test_normalize_image_rgb(self, image_handler_default: ImageHandler, sample_image_rgb: str):
        img_pil_input = image_handler_default.load_image(sample_image_rgb)
        normalized_pil_output = image_handler_default.normalize_image(img_pil_input)
        
        assert isinstance(normalized_pil_output, Image.Image)
        assert normalized_pil_output.mode == 'RGB'
        assert normalized_pil_output.size == img_pil_input.size
        
        # To check values, convert back to array and verify normalization was applied and reversed for PIL compatibility
        # The normalize_image method now returns a PIL image scaled to 0-255 (uint8)
        # after internal [0,1] float processing.
        output_array = np.array(normalized_pil_output)
        # Original red (255,0,0) should remain (255,0,0) in the output PIL image if no other transformation applied
        # The internal [0,1] scaling is an intermediate step. The final PIL image is uint8.
        assert np.allclose(output_array[0,0], [255, 0, 0]) 

    def test_normalize_image_rgba_to_rgb(self, image_handler_default: ImageHandler, sample_image_rgba: str):
        img_pil_rgba_input = image_handler_default.load_image(sample_image_rgba)
        normalized_pil_output = image_handler_default.normalize_image(img_pil_rgba_input)

        assert isinstance(normalized_pil_output, Image.Image)
        assert normalized_pil_output.mode == 'RGB' # Should be converted to RGB
        assert normalized_pil_output.size == img_pil_rgba_input.size

        output_array = np.array(normalized_pil_output)
        # Original green (0,255,0,A) should become (0,255,0) in RGB PIL image
        assert np.allclose(output_array[0,0], [0, 255, 0])

    def test_normalize_image_already_normalized_logic_pil_output(self, image_handler_default: ImageHandler):
        # This test checks if the internal scaling logic is correct. 
        # The output is always a PIL Image (uint8, 0-255).

        # Test case 1: Low intensity image (e.g., max value 100 out of 255)
        # Internally, this becomes ~100/255.0 (approx 0.39). 
        # Then it's converted back to uint8 by * 255, so it should be ~100.
        low_intensity_array_uint8 = (np.random.rand(30, 60, 3) * 100).astype(np.uint8)
        pil_low_intensity_input = Image.fromarray(low_intensity_array_uint8, 'RGB')
        normalized_pil_low_output = image_handler_default.normalize_image(pil_low_intensity_input)
        
        output_array_low = np.array(normalized_pil_low_output)
        assert np.allclose(output_array_low, low_intensity_array_uint8, atol=1) # Allow for minor precision diffs

        # Test case 2: Mocking internal array to be pre-normalized [0,1] float.
        # The method should scale this by 255 to make it uint8 for PIL output.
        class MockPILImage:
            def __init__(self, array_data, mode='RGB'):
                self.array_data = array_data
                self.mode = mode
                self.width = array_data.shape[1]
                self.height = array_data.shape[0]
                self.info = {}
            def convert(self, mode):
                if mode == 'RGB' and self.mode == 'RGB':
                    return self
                # Simplified mock convert, not handling actual data change for this test
                return MockPILImage(self.array_data, mode)

        # This array simulates the state *after* np.array(image, dtype=np.float32) / 255.0
        internal_float_array = np.random.rand(30, 60, 3).astype(np.float32) 
        # Create a mock PIL image that would produce this internal_float_array *if* it was scaled down
        # For the sake of the test, we create a mock that will be passed to np.array()
        # We want to test the path where `img_array` (after np.array) is already [0,1]
        # This means the `if np.max(img_array) > 1.0:` condition is FALSE.
        # Then it proceeds to `if np.max(img_array) <= 1.0 and img_array.dtype == np.float32: img_array = (img_array * 255).astype(np.uint8)`
        # So, the final output array should be internal_float_array * 255.

        mock_pil_for_internal_float = MockPILImage(internal_float_array) # This mock isn't perfect for np.array but works for .convert and .mode

        # We need to patch np.array to return our `internal_float_array` when called with `mock_pil_for_internal_float`
        # And also ensure the initial `if np.max(img_array) > 1.0:` check passes correctly for this scenario
        # (i.e., if the original PIL was somehow float 0-1, then `np.array` would yield float 0-1)
        
        # Let np.array return the float array directly to simulate it being already scaled
        with patch('numpy.array', return_value=internal_float_array) as mock_np_array_call:
            result_pil = image_handler_default.normalize_image(mock_pil_for_internal_float) # Pass the mock PIL
            mock_np_array_call.assert_called_once_with(mock_pil_for_internal_float, dtype=np.float32)
        
        result_array = np.array(result_pil)
        expected_uint8_array = (internal_float_array * 255).astype(np.uint8)
        assert np.allclose(result_array, expected_uint8_array, atol=1) # Check it's scaled back up to 0-255

    # Augmentation Tests
    def test_augment_image_output_properties(self, image_handler_default: ImageHandler, sample_image_rgb: str):
        img_pil = image_handler_default.load_image(sample_image_rgb)
        augmented_img = image_handler_default.augment_image(img_pil)
        assert isinstance(augmented_img, Image.Image)
        assert augmented_img.mode == img_pil.mode
        assert augmented_img.size == img_pil.size # Assuming rotation expand=False

    def test_augment_image_content_can_change(self, image_handler_default: ImageHandler, sample_image_rgb: str):
        img_pil = image_handler_default.load_image(sample_image_rgb)
        # Run augmentation multiple times; high probability of change
        changed = False
        original_bytes = img_pil.tobytes()
        for _ in range(10): # Run a few times to increase chance of seeing a change
            augmented_img = image_handler_default.augment_image(img_pil)
            if augmented_img.tobytes() != original_bytes:
                changed = True
                break
        assert changed, "Augmentation did not change the image content after several attempts."

    def test_augment_image_forced_flip(self, image_handler_default: ImageHandler, sample_image_asymmetric_2x1: str):
        img_pil = image_handler_default.load_image(sample_image_asymmetric_2x1)
        original_img_bytes = img_pil.tobytes()

        # This side effect function will be called for all random.uniform calls
        def mock_uniform_for_flip_test(a, b):
            if (a, b) == (-10, 10):  # Rotation angle range
                return 0.0  # No rotation
            elif (a, b) == (0.8, 1.2):  # Jitter factor range
                return 1.0  # No change from jitter
            return random.uniform(a, b) # Fallback to original for any other calls (shouldn't happen here)

        with \
            patch('random.random', return_value=0.2) as mock_rand_random, \
            patch('src.dataset_builder.image_handler.random.uniform', side_effect=mock_uniform_for_flip_test) as mock_rand_uniform \
        :
            # Ensure random.uniform is patched in the module where it's used (image_handler.py)
            flipped_img = image_handler_default.augment_image(img_pil)
        
        mock_rand_random.assert_called_once() # Check that random.random for flip was called

        assert flipped_img.tobytes() != original_img_bytes, "Image should have flipped but content is identical."
        manually_flipped = img_pil.transpose(Image.FLIP_LEFT_RIGHT)
        assert flipped_img.tobytes() == manually_flipped.tobytes(), "Augmented image with forced flip does not match manually flipped image."

    def test_augment_image_forced_rotation(self, image_handler_default: ImageHandler, sample_image_asymmetric_2x1: str):
        img_pil = image_handler_default.load_image(sample_image_asymmetric_2x1)
        original_img_bytes = img_pil.tobytes()

        forced_rotation_angle = 90.0 # Increased angle further

        def mock_uniform_for_rotation_test(a, b):
            if (a, b) == (-10, 10):  # Rotation angle range
                return forced_rotation_angle
            elif (a, b) == (0.8, 1.2):  # Jitter factor range
                return 1.0  # No change from jitter
            return random.uniform(a, b) # Fallback

        with \
            patch('random.random', return_value=0.7) as mock_rand_random, \
            patch('src.dataset_builder.image_handler.random.uniform', side_effect=mock_uniform_for_rotation_test) as mock_rand_uniform \
        :
            rotated_img = image_handler_default.augment_image(img_pil)
        
        assert rotated_img.tobytes() != original_img_bytes, f"Image should have rotated by {forced_rotation_angle} deg but content is identical."
        manually_rotated = img_pil.rotate(forced_rotation_angle, resample=Image.Resampling.NEAREST, expand=False)
        assert rotated_img.tobytes() == manually_rotated.tobytes()


# S3 Tests
MOCK_S3_BUCKET_NAME = "test-mock-bucket-imagehandler-s3tests" # Unique name for S3 tests bucket

@pytest.fixture(scope="class") # Class scope for S3 mock for this test class
def mock_s3_environment_for_class(request):
    # Using request to potentially pass class-level bucket name if needed later
    # For now, use the MOCK_S3_BUCKET_NAME constant
    with mock_aws():
        s3_client = boto3.client("s3", region_name="us-east-1")
        try:
            s3_client.create_bucket(Bucket=MOCK_S3_BUCKET_NAME)
            print(f"Mock S3 bucket '{MOCK_S3_BUCKET_NAME}' created for TestImageHandlerS3 class.")
        except ClientError as e:
            if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
                print(f"Mock S3 bucket '{MOCK_S3_BUCKET_NAME}' already exists for TestImageHandlerS3.")
            else: raise
        yield s3_client

@pytest.fixture
def s3_client_fixture(mock_s3_environment_for_class):
     # mock_s3_environment_for_class ensures the mock is active and bucket exists
    return boto3.client("s3", region_name="us-east-1")

@pytest.fixture
def image_handler_with_s3(mock_s3_environment_for_class):
    return ImageHandler(s3_bucket_name=MOCK_S3_BUCKET_NAME)

@pytest.fixture
def sample_image_s3_upload_source(temp_test_dir) -> str: # Specific for S3 source
    img_path = os.path.join(temp_test_dir, "s3_upload_source_content.png")
    img = Image.new('RGB', (30, 20), color = 'cyan')
    img.save(img_path, format="PNG")
    return img_path

# Helper to put a dummy object in S3
def _put_dummy_s3_object(s3_client, bucket_name: str, key: str, content: bytes = b"dummy s3 content"):
    s3_client.put_object(Bucket=bucket_name, Key=key, Body=content)
    return f"s3://{bucket_name}/{key}"

# Helper to get S3 object content
def _get_s3_object_content(s3_client, bucket_name: str, key: str) -> Optional[bytes]:
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        return response['Body'].read()
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey': return None
        raise

@pytest.mark.usefixtures("mock_s3_environment_for_class") # Ensure mock S3 is active for all tests in this class
class TestImageHandlerS3:

    def test_get_s3_client_initialization(self, image_handler_with_s3: ImageHandler):
        client1 = image_handler_with_s3._get_s3_client(); assert client1 is not None
        client2 = image_handler_with_s3._get_s3_client(); assert client1 is client2

    @patch('boto3.client')
    def test_get_s3_client_init_failure(self, mock_boto_client):
        mock_boto_client.side_effect = Exception("AWS credentials not found")
        handler = ImageHandler(s3_bucket_name="any-bucket") # New handler instance, not using fixture
        with pytest.raises(ImageProcessingError, match="Failed to initialize S3 client"):
            handler._get_s3_client()

    def test_download_image_from_s3_success(self, image_handler_with_s3: ImageHandler, s3_client_fixture, temp_test_dir: str):
        sample_content = b"s3 download success content"; s3_key = "downloads/sample.dat"
        s3_url = _put_dummy_s3_object(s3_client_fixture, MOCK_S3_BUCKET_NAME, s3_key, content=sample_content)
        
        local_path = image_handler_with_s3.download_image_from_s3(s3_url, local_temp_dir=temp_test_dir)
        assert os.path.exists(local_path)
        # Ensure temp_test_dir is absolute for comparison with absolute local_path
        abs_temp_test_dir = os.path.abspath(temp_test_dir)
        assert local_path.startswith(abs_temp_test_dir)
        with open(local_path, "rb") as f: assert f.read() == sample_content
        os.remove(local_path)

    def test_download_image_from_s3_no_such_key(self, image_handler_with_s3: ImageHandler, temp_test_dir: str):
        s3_url = f"s3://{MOCK_S3_BUCKET_NAME}/non_existent/object.png"
        with pytest.raises(ImageProcessingError, match="S3 object not found"):
            image_handler_with_s3.download_image_from_s3(s3_url, local_temp_dir=temp_test_dir)

    @pytest.mark.parametrize("invalid_url,error_match", [
        (f"http://{MOCK_S3_BUCKET_NAME}/k.png", r"Invalid S3 URL scheme"),
        (f"s3a://{MOCK_S3_BUCKET_NAME}/k.png", r"Invalid S3 URL scheme"),
        ("s3:///", r"Invalid S3 URL.*Could not parse bucket or key"),
        (f"s3://{MOCK_S3_BUCKET_NAME}", r"Invalid S3 URL.*Could not parse bucket or key"), # Missing key
        (f"s3:///keyonly", r"Invalid S3 URL.*Could not parse bucket or key") # Missing bucket
    ])
    def test_download_image_from_s3_invalid_url_format(self, image_handler_with_s3: ImageHandler, temp_test_dir: str, invalid_url: str, error_match: str):
        with pytest.raises(ImageProcessingError, match=error_match):
            image_handler_with_s3.download_image_from_s3(invalid_url, local_temp_dir=temp_test_dir)

    def test_upload_image_to_s3_success(self, image_handler_with_s3: ImageHandler, s3_client_fixture, sample_image_s3_upload_source: str):
        s3_key = "uploads/uploaded_via_test.png"
        uploaded_s3_url = image_handler_with_s3.upload_image_to_s3(sample_image_s3_upload_source, s3_key, content_type="image/png")
        assert uploaded_s3_url == f"s3://{MOCK_S3_BUCKET_NAME}/{s3_key}"
        
        s3_content = _get_s3_object_content(s3_client_fixture, MOCK_S3_BUCKET_NAME, s3_key)
        assert s3_content is not None
        with open(sample_image_s3_upload_source, "rb") as f: assert s3_content == f.read()

    def test_upload_image_to_s3_local_file_not_found(self, image_handler_with_s3: ImageHandler):
        with pytest.raises(FileNotFoundError):
            image_handler_with_s3.upload_image_to_s3("non_existent_local.png", "uploads/key.png")

    def test_upload_image_to_s3_bucket_not_configured(self, sample_image_s3_upload_source: str):
        handler_no_bucket = ImageHandler() # No s3_bucket_name
        with pytest.raises(ImageProcessingError, match="S3 bucket name not configured"):
            handler_no_bucket.upload_image_to_s3(sample_image_s3_upload_source, "uploads/key.png")

    @patch.object(ImageHandler, 'download_image_from_s3')
    @patch.object(ImageHandler, 'process_image_file')
    @patch.object(ImageHandler, 'upload_image_to_s3')
    def test_process_image_s3_pipeline_success_mocked(
        self, mock_upload: patch, mock_process: patch, mock_download: patch,
        image_handler_with_s3: ImageHandler, temp_test_dir: str
    ):
        input_s3_url = f"s3://{MOCK_S3_BUCKET_NAME}/inputs/original_for_pipe.png"
        output_s3_key_prefix = "pipe_processed/"
        output_filename = "pipe_final.webp"
        
        mock_local_download_path = os.path.join(temp_test_dir, "pipe_downloaded.png")
        with open(mock_local_download_path, "wb") as f: f.write(b"pipe dummy dl")
        mock_download.return_value = mock_local_download_path
        
        # This is the path that process_image_s3 will construct for process_image_file's output
        # It's based on a new temp dir created by process_image_s3 and the effective_output_filename
        # We need to mock process_image_file to "create" this file and return its path.
        # The actual name of the temp dir created by process_image_s3 is unknown here.
        
        # Simulate process_image_file creating its output and returning the path
        def process_side_effect(input_image_path, output_image_path, **kwargs):
            with open(output_image_path, "wb") as f: f.write(b"pipe processed data")
            return output_image_path # Return the path it was given to save to
        mock_process.side_effect = process_side_effect

        expected_output_s3_key = f"{output_s3_key_prefix.strip('/')}/{output_filename}"
        expected_final_s3_url = f"s3://{MOCK_S3_BUCKET_NAME}/{expected_output_s3_key}"
        mock_upload.return_value = expected_final_s3_url

        result_s3_url = image_handler_with_s3.process_image_s3(
            input_s3_url=input_s3_url, output_s3_key_prefix=output_s3_key_prefix,
            output_filename=output_filename, output_format="WEBP"
        )
        assert result_s3_url == expected_final_s3_url

        mock_download.assert_called_once_with(input_s3_url, local_temp_dir=ANY)
        
        # Get the temp_dir used by process_image_s3 from download_image_from_s3's call args
        actual_temp_dir_for_processing = mock_download.call_args[1]['local_temp_dir']

        mock_process.assert_called_once()
        process_call_args = mock_process.call_args[1]
        assert process_call_args['input_image_path'] == mock_local_download_path
        assert process_call_args['output_image_path'].startswith(actual_temp_dir_for_processing)
        assert process_call_args['output_image_path'].endswith("processed_pipe_final.webp")
        assert process_call_args['output_format'] == "webp"

        mock_upload.assert_called_once()
        upload_call_args = mock_upload.call_args[1]
        # The local_file_path for upload should be what mock_process returned (its output_image_path argument)
        assert upload_call_args['local_file_path'] == process_call_args['output_image_path']
        assert upload_call_args['s3_key'] == expected_output_s3_key
        assert upload_call_args['content_type'] == "image/webp"

        if os.path.exists(mock_local_download_path): os.remove(mock_local_download_path)
        # Further cleanup checks (e.g., that process_call_args['output_image_path'] was deleted) are complex
        # due to tempfile.mkdtemp and are better for integration tests.

    def test_process_image_s3_derived_output_filename_integration(self, image_handler_with_s3: ImageHandler, s3_client_fixture, temp_test_dir: str, sample_image_s3_upload_source: str):
        input_s3_key = "integrations/source_file.png"; input_file_content = open(sample_image_s3_upload_source, "rb").read()
        input_s3_url = _put_dummy_s3_object(s3_client_fixture, MOCK_S3_BUCKET_NAME, input_s3_key, content=input_file_content)
        output_s3_key_prefix = "integrations_processed_derived/"
        
        returned_s3_url = image_handler_with_s3.process_image_s3(
            input_s3_url=input_s3_url, output_s3_key_prefix=output_s3_key_prefix,
            output_filename=None, output_format="jpeg", resize_dimensions=(10, 5) 
        )
        expected_output_filename = "source_file_processed.jpeg"
        expected_output_s3_key = f"{output_s3_key_prefix.strip('/')}/{expected_output_filename}"
        assert returned_s3_url == f"s3://{MOCK_S3_BUCKET_NAME}/{expected_output_s3_key}"

        s3_processed_content = _get_s3_object_content(s3_client_fixture, MOCK_S3_BUCKET_NAME, expected_output_s3_key)
        assert s3_processed_content is not None
        
        # Validate the content (basic check for format and size)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpeg") as tmp_f:
            tmp_f.write(s3_processed_content)
            tmp_f_path = tmp_f.name
        try:
            img = Image.open(tmp_f_path); assert img.format == "JPEG"; assert img.size == (10, 5)
        finally:
            if os.path.exists(tmp_f_path): os.remove(tmp_f_path)

    def test_process_image_s3_output_filename_no_prefix_integration(self, image_handler_with_s3: ImageHandler, s3_client_fixture, temp_test_dir: str, sample_image_s3_upload_source: str):
        """Tests process_image_s3 when output_filename is given but output_s3_key_prefix is None."""
        input_s3_key = "integrations/source_for_no_prefix.png"
        input_file_content = open(sample_image_s3_upload_source, "rb").read()
        input_s3_url = _put_dummy_s3_object(s3_client_fixture, MOCK_S3_BUCKET_NAME, input_s3_key, content=input_file_content)
        
        specific_output_filename = "final_image_at_root.jpeg"
        
        returned_s3_url = image_handler_with_s3.process_image_s3(
            input_s3_url=input_s3_url,
            output_s3_key_prefix=None, # Explicitly None
            output_filename=specific_output_filename,
            output_format="jpeg",
            resize_dimensions=(15, 8) 
        )
        
        # The key should be exactly the output_filename at the root of the bucket
        expected_output_s3_key = specific_output_filename 
        assert returned_s3_url == f"s3://{MOCK_S3_BUCKET_NAME}/{expected_output_s3_key}"

        s3_processed_content = _get_s3_object_content(s3_client_fixture, MOCK_S3_BUCKET_NAME, expected_output_s3_key)
        assert s3_processed_content is not None
        
        # Validate the content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpeg") as tmp_f:
            tmp_f.write(s3_processed_content)
            tmp_f_path = tmp_f.name
        try:
            img = Image.open(tmp_f_path)
            assert img.format == "JPEG"
            assert img.size == (15, 8)
        finally:
            if os.path.exists(tmp_f_path): os.remove(tmp_f_path)

    @pytest.mark.parametrize("failure_stage, mock_target, error_message_part", [
        ("download", 'download_image_from_s3', "S3 Download Failed"),
        ("process", 'process_image_file', "Local Processing Failed"),
        ("upload", 'upload_image_to_s3', "S3 Upload Failed")
    ])
    def test_process_image_s3_pipeline_failures(
        self, image_handler_with_s3: ImageHandler, failure_stage: str, mock_target: str, error_message_part: str,
        temp_test_dir: str, sample_image_s3_upload_source: str
    ):
        input_s3_url = f"s3://{MOCK_S3_BUCKET_NAME}/failures/input.png"
        output_prefix = "failures_processed/"

        # Setup mocks up to the point of failure
        mock_download_path = os.path.join(temp_test_dir, "fail_dl.png")
        
        # This path will be constructed by process_image_s3 for process_image_file output
        # It will be inside a temp dir created by process_image_s3.
        # We don't need its exact value if process_image_file is mocked before it's used by upload.
        
        # If download fails, process and upload aren't called.
        # If process fails, upload isn't called.

        patches = {}
        if failure_stage != "download": # If download is not failing, it needs to succeed
            patches['download_image_from_s3'] = patch.object(ImageHandler, 'download_image_from_s3', return_value=mock_download_path)
            # Create the dummy downloaded file if process_image_file is expected to run
            if failure_stage != "process":
                 with open(mock_download_path, "wb") as f: f.write(b"dummy content")


        if failure_stage != "process" and 'download_image_from_s3' in patches: # If process is not failing (and download succeeded)
            def mock_process_effect(input_image_path, output_image_path, **kwargs):
                # Simulate process_image_file creating its output file
                with open(output_image_path, "wb") as f: f.write(b"processed dummy")
                return output_image_path
            patches['process_image_file'] = patch.object(ImageHandler, 'process_image_file', side_effect=mock_process_effect)
        
        # The actual failing mock
        patches[mock_target] = patch.object(ImageHandler, mock_target, side_effect=ImageProcessingError(error_message_part))

        active_patches = [p.start() for p in patches.values()]
        
        try:
            with pytest.raises(ImageProcessingError, match=f"Failed S3 image processing pipeline.*{error_message_part}"):
                image_handler_with_s3.process_image_s3(input_s3_url, output_prefix)
        finally:
            for p in active_patches: p.stop()
            if os.path.exists(mock_download_path): os.remove(mock_download_path)
            # Add cleanup for mock_processed_path if it was created by a successful mock_process_effect
            # This is complex because its name depends on the internal temp dir.
            # For this test structure, rely on process_image_s3's finally block for such internal temp files.

# --- S3 Test Fixtures ---
@pytest.fixture(scope='function')
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1' # Example region

@pytest.fixture(scope='function')
def s3_client(aws_credentials):
    """Yield a mocked S3 client that works with moto."""
    with mock_aws():
        yield boto3.client('s3', region_name='us-east-1')

@pytest.fixture(scope='function')
def s3_bucket(s3_client):
    """Create a mock S3 bucket and yield its name."""
    bucket_name = "test-image-bucket"
    s3_client.create_bucket(Bucket=bucket_name)
    return bucket_name
