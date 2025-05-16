import pytest
import os
from unittest.mock import patch, MagicMock, mock_open
import json
from pathlib import Path
from typing import Dict, List
import boto3

from src.storage_manager.storage import StorageManager, HTML_FILENAME, SCREENSHOT_FILENAME, ACTION_FILENAME, METADATA_FILENAME
from src.storage_manager.exceptions import S3ConfigError, S3OperationError, LocalStorageError, StorageManagerError
from src.storage_manager import config as sm_config
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError

# Store original env vars to restore them after tests that modify them
ORIGINAL_ENV = os.environ.copy()

@pytest.fixture
def sample_data():
    return {
        "html": "<html><body>Test HTML</body></html>",
        "screenshot": b"fake_screenshot_bytes",
        "action": {"type": "click", "element": "button"},
        "metadata": {"url": "http://example.com", "timestamp": "2023-01-01T00:00:00Z"}
    }

@pytest.fixture(autouse=True)
def reset_env_vars_and_config_mocks():
    """Auto-applied fixture to reset relevant env vars and config module mocks after each test."""
    # Reset os.environ to its original state before tests modifying it
    # This is a simple approach; for more complex scenarios, consider specific var management.
    # Note: This might be too broad if other tests depend on env vars set outside this scope.
    # A more targeted approach would be to only unset vars known to be set by these tests.
    
    # Clear specific env vars used by storage_manager.config
    current_test_env_vars = [
        sm_config.STORAGE_S3_BUCKET_ENV_VAR,
        sm_config.STORAGE_S3_REGION_ENV_VAR,
        sm_config.STORAGE_LOCAL_BASE_PATH_ENV_VAR
    ]
    for var_name in current_test_env_vars:
        if var_name in os.environ: # If test set it
            del os.environ[var_name]
    
    # Restore any original values for these specific vars if they existed
    for var_name in current_test_env_vars:
        if var_name in ORIGINAL_ENV:
            os.environ[var_name] = ORIGINAL_ENV[var_name]
        elif var_name in os.environ: # If it wasn't in original but is now (e.g. set by other test setup)
             del os.environ[var_name] # remove it to ensure clean state for next test

    yield # Test runs here

    # Cleanup: Re-ensure specific env vars are reset to original state or removed
    for var_name in current_test_env_vars:
        if var_name in ORIGINAL_ENV:
            os.environ[var_name] = ORIGINAL_ENV[var_name]
        elif var_name in os.environ:
            del os.environ[var_name]

@pytest.fixture(scope='session') # Changed to session scope for efficiency if shared across many tests
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1" # Moto typically defaults to us-east-1

@pytest.fixture(scope='session') # Changed to session scope
def s3_client(aws_credentials):
    """Yield a boto3 s3 client in a moto S3 mocking context."""
    with patch('boto3.DEFAULT_SESSION', None): # Ensure boto3 re-evaluates session with new env vars
        # For newer moto versions, context manager might not be strictly needed if using env vars
        # but it's good practice for ensuring isolation.
        # from moto import mock_aws # Changed from mock_s3 for broader compatibility
        # with mock_aws():
        # For moto versions >= 5.0.0, use mock_aws context manager
        # For older versions, direct client creation with env vars might suffice if moto is started globally.
        # Given our setup, relying on env vars and direct client creation is simpler if moto is active.
        # Let's assume moto is active for the session when aws_credentials are set.
        # We can use the moto context manager if issues arise. For now, direct client.
        try:
            client = boto3.client("s3", region_name=os.environ["AWS_DEFAULT_REGION"])
            yield client
        finally:
            # Clean up env vars set by aws_credentials if not using a context manager that handles it.
            # However, reset_env_vars_and_config_mocks should handle this at test level.
            pass

@pytest.fixture(scope='function') # Function scope to ensure clean bucket for each test
def s3_bucket(s3_client):
    """Create a mock S3 bucket and yield its name. Cleans up after."""
    bucket_name = "test-integration-bucket"
    try:
        s3_client.create_bucket(Bucket=bucket_name)
        yield bucket_name
    finally:
        # Cleanup: delete all objects, then delete bucket
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket_name):
                if 'Contents' in page:
                    objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                    if objects_to_delete:
                        s3_client.delete_objects(Bucket=bucket_name, Delete={'Objects': objects_to_delete})
            s3_client.delete_bucket(Bucket=bucket_name)
        except ClientError as e:
            # Allow test to pass if bucket cleanup fails (e.g., already deleted)
            print(f"Error during S3 bucket cleanup: {e}")
            pass # Or log a warning

class TestStorageManagerInitialization:

    def test_init_prefer_s3_bucket_configured_boto_success(self, tmp_path):
        """Test successful S3 initialization when bucket is provided and boto client succeeds."""
        test_bucket = "test-s3-bucket"
        test_region = "us-west-2"
        mock_s3_client_instance = MagicMock()
        
        with patch('boto3.client', return_value=mock_s3_client_instance) as mock_boto_client_constructor:
            sm = StorageManager(
                s3_bucket_name=test_bucket, 
                s3_region_name=test_region, 
                local_base_path=str(tmp_path / "local_fallback"),
                prefer_s3=True
            )
            assert sm.use_s3 is True
            assert sm.s3_bucket_name == test_bucket
            assert sm.s3_region_name == test_region
            assert sm._s3_client is mock_s3_client_instance
            mock_boto_client_constructor.assert_called_once_with("s3", region_name=test_region)
            info = sm.get_storage_info()
            assert info["effective_storage_type"] == "S3"

    def test_init_prefer_s3_no_bucket_name(self, tmp_path):
        """Test defaults to local storage if prefer_s3 is True but no bucket name is configured."""
        sm = StorageManager(
            s3_bucket_name=None, 
            local_base_path=str(tmp_path / "local_only"),
            prefer_s3=True
        )
        assert sm.use_s3 is False
        assert sm.s3_bucket_name is None
        info = sm.get_storage_info()
        assert info["effective_storage_type"] == "Local"

    def test_init_force_local_storage(self, tmp_path):
        """Test forces local storage if prefer_s3 is False, even if S3 bucket is configured."""
        sm = StorageManager(
            s3_bucket_name="some-bucket", 
            local_base_path=str(tmp_path / "forced_local"),
            prefer_s3=False
        )
        assert sm.use_s3 is False
        info = sm.get_storage_info()
        assert info["effective_storage_type"] == "Local"

    @patch('boto3.client')
    def test_init_prefer_s3_boto_fails_no_credentials(self, mock_boto_client_constructor, tmp_path):
        """Test falls back to local if S3 client init fails due to NoCredentialsError."""
        mock_boto_client_constructor.side_effect = NoCredentialsError()
        sm = StorageManager(
            s3_bucket_name="test-bucket-fail", 
            local_base_path=str(tmp_path / "fallback_creds"),
            prefer_s3=True
        )
        assert sm.use_s3 is False
        mock_boto_client_constructor.assert_called_once()
        info = sm.get_storage_info()
        assert info["effective_storage_type"] == "Local"

    @patch('boto3.client')
    def test_init_prefer_s3_boto_fails_client_error(self, mock_boto_client_constructor, tmp_path):
        """Test falls back to local if S3 client init fails due to generic ClientError."""
        mock_boto_client_constructor.side_effect = ClientError({"Error": {"Code": "InvalidAccessKeyId", "Message": "Test"}}, "TestOperation")
        sm = StorageManager(
            s3_bucket_name="test-bucket-client-error", 
            local_base_path=str(tmp_path / "fallback_client_err"),
            prefer_s3=True
        )
        assert sm.use_s3 is False
        mock_boto_client_constructor.assert_called_once()
        info = sm.get_storage_info()
        assert info["effective_storage_type"] == "Local"

    def test_get_s3_client_no_bucket_name_raises_error(self):
        """Test _get_s3_client raises S3ConfigError if bucket name is missing."""
        sm = StorageManager(s3_bucket_name=None, prefer_s3=True) # will init to local
        assert sm.use_s3 is False 
        # Manually set bucket name to then test _get_s3_client directly without it
        sm.s3_bucket_name = None # Ensure it's None before calling
        with pytest.raises(S3ConfigError, match="S3 bucket name is not configured"):
            sm._get_s3_client()

    def test_config_resolution_direct_params(self, tmp_path):
        """Test configuration is correctly picked from direct constructor parameters."""
        bucket = "direct-bucket"
        region = "eu-central-1"
        local_path = str(tmp_path / "direct_local")
        with patch('boto3.client', return_value=MagicMock()): # Assume S3 init succeeds
            sm = StorageManager(s3_bucket_name=bucket, s3_region_name=region, local_base_path=local_path)
        assert sm.s3_bucket_name == bucket
        assert sm.s3_region_name == region
        assert sm.local_base_path == os.path.abspath(local_path)

    def test_config_resolution_env_vars(self, tmp_path):
        """Test configuration is correctly picked from environment variables."""
        bucket_env = "env-bucket"
        region_env = "ap-southeast-2"
        local_path_env = str(tmp_path / "env_local")
        
        env_vars = {
            sm_config.STORAGE_S3_BUCKET_ENV_VAR: bucket_env,
            sm_config.STORAGE_S3_REGION_ENV_VAR: region_env,
            sm_config.STORAGE_LOCAL_BASE_PATH_ENV_VAR: local_path_env
        }
        with patch.dict(os.environ, env_vars):
            with patch('boto3.client', return_value=MagicMock()): # Assume S3 init succeeds
                sm = StorageManager()
        
        assert sm.s3_bucket_name == bucket_env
        assert sm.s3_region_name == region_env
        assert sm.local_base_path == os.path.abspath(local_path_env)

    def test_config_resolution_defaults(self, tmp_path):
        """Test configuration falls back to defaults when no params or env vars are set."""
        # Ensure env vars that might affect defaults are cleared for this test
        if sm_config.STORAGE_S3_BUCKET_ENV_VAR in os.environ: del os.environ[sm_config.STORAGE_S3_BUCKET_ENV_VAR]
        if sm_config.STORAGE_S3_REGION_ENV_VAR in os.environ: del os.environ[sm_config.STORAGE_S3_REGION_ENV_VAR]
        if sm_config.STORAGE_LOCAL_BASE_PATH_ENV_VAR in os.environ: del os.environ[sm_config.STORAGE_LOCAL_BASE_PATH_ENV_VAR]

        sm = StorageManager() # Will use local as no bucket is defined by default
        
        assert sm.s3_bucket_name is None # Default for bucket is None via get_s3_bucket_name
        assert sm.s3_region_name == sm_config.DEFAULT_S3_REGION
        assert sm.local_base_path == os.path.abspath(sm_config.DEFAULT_LOCAL_BASE_PATH)
        assert sm.use_s3 is False

    def test_get_storage_info_s3_mode(self, tmp_path):
        """Test get_storage_info reports correctly when in S3 mode."""
        bucket = "s3-info-bucket"
        with patch('boto3.client', return_value=MagicMock()):
            sm = StorageManager(s3_bucket_name=bucket, local_base_path=str(tmp_path / "s3_info_local"))
        info = sm.get_storage_info()
        assert info["uses_s3"] is True
        assert info["s3_bucket"] == bucket
        assert info["s3_region"] == sm_config.DEFAULT_S3_REGION # as no region override
        assert info["effective_storage_type"] == "S3"
        assert info["local_base_path"] == os.path.abspath(str(tmp_path / "s3_info_local"))

    def test_get_storage_info_local_mode(self, tmp_path):
        """Test get_storage_info reports correctly when in local mode."""
        local_p = str(tmp_path / "local_info_path")
        sm = StorageManager(prefer_s3=False, local_base_path=local_p) # Force local
        info = sm.get_storage_info()
        assert info["uses_s3"] is False
        assert info["s3_bucket"] is None
        assert info["s3_region"] is None # Changed from DEFAULT_S3_REGION as it's not used
        assert info["effective_storage_type"] == "Local"
        assert info["local_base_path"] == os.path.abspath(local_p)

    def test_local_base_path_creation(self, tmp_path):
        """Test that the local_base_path is created if it doesn't exist."""
        new_local_path = tmp_path / "newly_created_storage_dir"
        assert not new_local_path.exists()
        sm = StorageManager(local_base_path=str(new_local_path), prefer_s3=False)
        assert new_local_path.exists()
        assert new_local_path.is_dir()
        assert sm.local_base_path == str(new_local_path.resolve()) # resolve() for absolute path consistency

class TestStorageManagerUploadOperations:

    @pytest.fixture
    def mock_s3_sm(self, tmp_path):
        """Provides a StorageManager configured for S3, with a mocked S3 client."""
        test_bucket = "mocked-upload-bucket"
        mock_s3_client_instance = MagicMock()
        with patch('boto3.client', return_value=mock_s3_client_instance):
            sm = StorageManager(
                s3_bucket_name=test_bucket,
                local_base_path=str(tmp_path / "local_s3_fallback"),
                prefer_s3=True
            )
        sm._s3_client = mock_s3_client_instance # Ensure the instance uses our mock
        return sm, mock_s3_client_instance

    @pytest.fixture
    def local_sm(self, tmp_path):
        """Provides a StorageManager configured for local-only storage."""
        local_storage_path = tmp_path / "actual_local_storage"
        sm = StorageManager(prefer_s3=False, local_base_path=str(local_storage_path))
        return sm, local_storage_path

    # Test helper methods
    def test_get_s3_key(self, mock_s3_sm):
        sm, _ = mock_s3_sm
        assert sm._get_s3_key("sess1", "step1", "file.txt") == "sess1/step1/file.txt"

    def test_get_local_path(self, local_sm):
        sm, base_path = local_sm
        path = sm._get_local_path("sess2", "step2", "data.json")
        expected_path = base_path / "sess2" / "step2" / "data.json"
        assert path == str(expected_path)
        assert (base_path / "sess2" / "step2").exists() # Check directory creation

    def test_upload_to_s3_success_bytes(self, mock_s3_sm):
        sm, mock_client = mock_s3_sm
        s3_key = "test/obj.bin"
        data_bytes = b"binary data"
        expected_url = f"s3://{sm.s3_bucket_name}/{s3_key}"

        url = sm._upload_to_s3(data_bytes, s3_key, content_type="application/octet-stream")
        assert url == expected_url
        mock_client.put_object.assert_called_once_with(
            Bucket=sm.s3_bucket_name, Key=s3_key, Body=data_bytes, ContentType="application/octet-stream"
        )

    def test_upload_to_s3_success_string(self, mock_s3_sm):
        sm, mock_client = mock_s3_sm
        s3_key = "test/obj.txt"
        data_str = "text data"
        expected_url = f"s3://{sm.s3_bucket_name}/{s3_key}"

        url = sm._upload_to_s3(data_str, s3_key, content_type="text/plain")
        assert url == expected_url
        mock_client.put_object.assert_called_once_with(
            Bucket=sm.s3_bucket_name, Key=s3_key, Body=data_str.encode('utf-8'), ContentType="text/plain"
        )
    
    def test_upload_to_s3_client_error(self, mock_s3_sm):
        sm, mock_client = mock_s3_sm
        mock_client.put_object.side_effect = ClientError({"Error": {}}, "put_object")
        with pytest.raises(S3OperationError, match="S3 upload failed"):
            sm._upload_to_s3(b"data", "key")

    def test_write_to_local_success_bytes(self, local_sm):
        sm, base_path = local_sm
        local_file_path = base_path / "local_obj.bin"
        data_bytes = b"local binary"

        returned_path = sm._write_to_local(data_bytes, str(local_file_path))
        assert returned_path == str(local_file_path.resolve())
        assert local_file_path.read_bytes() == data_bytes

    def test_write_to_local_success_string(self, local_sm):
        sm, base_path = local_sm
        local_file_path = base_path / "local_obj.txt"
        data_str = "local text"

        returned_path = sm._write_to_local(data_str, str(local_file_path))
        assert returned_path == str(local_file_path.resolve())
        assert local_file_path.read_text(encoding='utf-8') == data_str

    def test_write_to_local_io_error(self, local_sm):
        sm, _ = local_sm
        with patch('builtins.open', side_effect=IOError("Disk full")):
             with pytest.raises(LocalStorageError, match="Failed to write to local file"):
                sm._write_to_local("data", "/some/mock/path.txt")

    # Test store_step_data
    @pytest.mark.asyncio
    async def test_store_step_data_s3_mode_all_types(self, mock_s3_sm):
        sm, mock_client = mock_s3_sm
        session_id, step_id = "s3_sess", "s3_step"
        html, screen, action, meta = "<p>html</p>", b"img_bytes", {"a":1}, {"m":2}

        paths = await sm.store_step_data(session_id, step_id, html, screen, action, meta)

        expected_html_key = sm._get_s3_key(session_id, step_id, sm_config.HTML_FILENAME)
        expected_screen_key = sm._get_s3_key(session_id, step_id, sm_config.SCREENSHOT_FILENAME)
        expected_action_key = sm._get_s3_key(session_id, step_id, sm_config.ACTION_DATA_FILENAME)
        expected_meta_key = sm._get_s3_key(session_id, step_id, sm_config.METADATA_FILENAME)

        assert paths["html_path"] == f"s3://{sm.s3_bucket_name}/{expected_html_key}"
        assert paths["screenshot_path"] == f"s3://{sm.s3_bucket_name}/{expected_screen_key}"
        assert paths["action_data_path"] == f"s3://{sm.s3_bucket_name}/{expected_action_key}"
        assert paths["metadata_path"] == f"s3://{sm.s3_bucket_name}/{expected_meta_key}"

        mock_client.put_object.assert_any_call(Bucket=sm.s3_bucket_name, Key=expected_html_key, Body=html.encode('utf-8'), ContentType='text/html')
        mock_client.put_object.assert_any_call(Bucket=sm.s3_bucket_name, Key=expected_screen_key, Body=screen, ContentType='image/png')
        mock_client.put_object.assert_any_call(Bucket=sm.s3_bucket_name, Key=expected_action_key, Body=json.dumps(action, indent=2).encode('utf-8'), ContentType='application/json')
        mock_client.put_object.assert_any_call(Bucket=sm.s3_bucket_name, Key=expected_meta_key, Body=json.dumps(meta, indent=2).encode('utf-8'), ContentType='application/json')
        assert mock_client.put_object.call_count == 4

    @pytest.mark.asyncio
    async def test_store_step_data_local_mode_some_types(self, local_sm):
        sm, base_path = local_sm
        session_id, step_id = "local_sess", "local_step"
        html, action = "<html></html>", {"b": "data"}

        paths = await sm.store_step_data(session_id, step_id, html_content=html, action_data=action)

        expected_html_path = base_path / session_id / step_id / sm_config.HTML_FILENAME
        expected_action_path = base_path / session_id / step_id / sm_config.ACTION_DATA_FILENAME

        assert paths["html_path"] == str(expected_html_path.resolve())
        assert paths["action_data_path"] == str(expected_action_path.resolve())
        assert paths["screenshot_path"] is None
        assert paths["metadata_path"] is None

        assert expected_html_path.read_text(encoding='utf-8') == html
        assert json.loads(expected_action_path.read_text(encoding='utf-8')) == action

    @pytest.mark.asyncio
    async def test_store_step_data_s3_upload_fails_propagates(self, mock_s3_sm, sample_data):
        """Test that if S3 upload fails, the error propagates."""
        mock_s3_sm._s3_client.put_object.side_effect = ClientError({"Error": {"Code": "AccessDenied", "Message": "Details"}}, "put_object")
        with pytest.raises(S3OperationError) as excinfo:
            await mock_s3_sm.store_step_data(
                session_id="session1",
                step_id="step1",
                html_content=sample_data["html"],
            )
        assert "Failed to upload data to S3 for session1/step1/html.html" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_store_step_data_local_write_fails_propagates(self, local_sm_real_fs, sample_data):
        """Test that if local write fails, the error propagates."""
        # Simulate a write failure
        with patch("builtins.open", mock_open()) as mocked_open:
            mocked_open.side_effect = IOError("Disk full")
            with pytest.raises(LocalStorageError) as excinfo:
                await local_sm_real_fs.store_step_data(
                    session_id="session1",
                    step_id="step1",
                    html_content=sample_data["html"],
                    screenshot_bytes=sample_data["screenshot"],
                    action_data=sample_data["action"],
                    metadata=sample_data["metadata"],
                )
            assert "Failed to write data to local storage for session1/step1/html.html" in str(excinfo.value)
            assert isinstance(excinfo.value.__cause__, IOError)

class TestStorageManagerDownloadOperations:
    """Tests for download operations in StorageManager."""

    @pytest.fixture
    def sample_file_content(self):
        return "Test content"

    @pytest.fixture
    def sample_json_content(self):
        return {"key": "value"}

    @pytest.fixture
    def sample_bytes_content(self):
        return b"Test bytes"

    # Tests for _download_from_s3
    async def test_download_from_s3_success_text(self, mock_s3_sm, sample_file_content):
        mock_s3_sm._s3_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=sample_file_content.encode("utf-8")))
        }
        content = await mock_s3_sm._download_from_s3("test_key")
        assert content == sample_file_content
        mock_s3_sm._s3_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="test_key")

    async def test_download_from_s3_success_json(self, mock_s3_sm, sample_json_content):
        mock_s3_sm._s3_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps(sample_json_content).encode("utf-8")))
        }
        content = await mock_s3_sm._download_from_s3("test_key.json", is_json=True)
        assert content == sample_json_content

    async def test_download_from_s3_success_bytes(self, mock_s3_sm, sample_bytes_content):
        mock_s3_sm._s3_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=sample_bytes_content))
        }
        content = await mock_s3_sm._download_from_s3("test_key.png", is_bytes=True)
        assert content == sample_bytes_content

    async def test_download_from_s3_client_error(self, mock_s3_sm):
        mock_s3_sm._s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Details"}}, "get_object"
        )
        with pytest.raises(S3OperationError) as excinfo:
            await mock_s3_sm._download_from_s3("test_key")
        assert "Failed to download data from S3 for key test_key. Error: An error occurred (NoSuchKey)" in str(excinfo.value)

    async def test_download_from_s3_json_decode_error(self, mock_s3_sm):
        mock_s3_sm._s3_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=b"invalid json"))
        }
        with pytest.raises(S3OperationError) as excinfo:
            await mock_s3_sm._download_from_s3("test_key.json", is_json=True)
        assert "Failed to decode JSON from S3 for key test_key.json" in str(excinfo.value)

    # Tests for _read_from_local
    async def test_read_from_local_success_text(self, local_sm_real_fs, sample_file_content, tmp_path):
        file_path = tmp_path / "test_file.txt"
        with open(file_path, "w") as f:
            f.write(sample_file_content)
        
        local_sm_real_fs._local_base_path = tmp_path # Ensure correct base path for the test
        
        content = await local_sm_real_fs._read_from_local(Path("test_file.txt"))
        assert content == sample_file_content

    async def test_read_from_local_success_json(self, local_sm_real_fs, sample_json_content, tmp_path):
        file_path = tmp_path / "test_file.json"
        with open(file_path, "w") as f:
            json.dump(sample_json_content, f)
        local_sm_real_fs._local_base_path = tmp_path
        content = await local_sm_real_fs._read_from_local(Path("test_file.json"), is_json=True)
        assert content == sample_json_content

    async def test_read_from_local_success_bytes(self, local_sm_real_fs, sample_bytes_content, tmp_path):
        file_path = tmp_path / "test_file.png"
        with open(file_path, "wb") as f:
            f.write(sample_bytes_content)
        local_sm_real_fs._local_base_path = tmp_path
        content = await local_sm_real_fs._read_from_local(Path("test_file.png"), is_bytes=True)
        assert content == sample_bytes_content

    async def test_read_from_local_file_not_found(self, local_sm_real_fs, tmp_path):
        local_sm_real_fs._local_base_path = tmp_path
        with pytest.raises(LocalStorageError) as excinfo:
            await local_sm_real_fs._read_from_local(Path("non_existent_file.txt"))
        assert "File not found at local path" in str(excinfo.value)
        assert "non_existent_file.txt" in str(excinfo.value)

    async def test_read_from_local_io_error(self, local_sm_real_fs, tmp_path):
        local_sm_real_fs._local_base_path = tmp_path
        # Use a real file path that we can't read from (e.g. a directory) or mock open
        # For simplicity, mocking open to raise IOError is cleaner
        with patch("builtins.open", mock_open()) as mocked_open_read:
            mocked_open_read.side_effect = IOError("Permission denied")
            with pytest.raises(LocalStorageError) as excinfo:
                # The path doesn't strictly matter here as open is mocked, but use a valid looking one
                await local_sm_real_fs._read_from_local(Path("any_file.txt")) 
            assert "Failed to read data from local storage for path any_file.txt" in str(excinfo.value)

    async def test_read_from_local_json_decode_error(self, local_sm_real_fs, tmp_path):
        file_path = tmp_path / "invalid.json"
        with open(file_path, "w") as f:
            f.write("invalid json")
        local_sm_real_fs._local_base_path = tmp_path
        with pytest.raises(LocalStorageError) as excinfo:
            await local_sm_real_fs._read_from_local(Path("invalid.json"), is_json=True)
        assert "Failed to decode JSON from local path invalid.json" in str(excinfo.value)

    # Tests for retrieve_step_data
    @pytest.mark.asyncio
    async def test_retrieve_step_data_s3_all_present(self, mock_s3_sm, sample_data):
        async def mock_download(key, is_json=False, is_bytes=False):
            if HTML_FILENAME in key: return sample_data["html"]
            if SCREENSHOT_FILENAME in key: return sample_data["screenshot"]
            if ACTION_FILENAME in key: return sample_data["action"]
            if METADATA_FILENAME in key: return sample_data["metadata"]
            pytest.fail(f"Unexpected key for S3 download: {key}") # Fail if unexpected key
            return None 

        with patch.object(mock_s3_sm, "_download_from_s3", side_effect=mock_download) as mock_downloader:
            retrieved_data = await mock_s3_sm.retrieve_step_data("session1", "step1")
            assert retrieved_data["html_content"] == sample_data["html"]
            assert retrieved_data["screenshot_bytes"] == sample_data["screenshot"]
            assert retrieved_data["action_data"] == sample_data["action"]
            assert retrieved_data["metadata"] == sample_data["metadata"]
            assert retrieved_data["retrieved_all"] is True
            assert mock_downloader.call_count == 4


    @pytest.mark.asyncio
    async def test_retrieve_step_data_s3_some_missing_or_error(self, mock_s3_sm, sample_data, caplog):
        async def mock_download(key, is_json=False, is_bytes=False):
            if HTML_FILENAME in key: return sample_data["html"]
            # screenshot is missing - _download_from_s3 would raise S3OperationError if NoSuchKey
            if SCREENSHOT_FILENAME in key: raise S3OperationError(f"Simulated S3 Error for {key} (NoSuchKey)")
            if ACTION_FILENAME in key: return sample_data["action"]
            # metadata has a different kind of error
            if METADATA_FILENAME in key: raise S3OperationError(f"Simulated S3 Error for {key} (AccessDenied)")
            return None

        with patch.object(mock_s3_sm, "_download_from_s3", side_effect=mock_download):
            retrieved_data = await mock_s3_sm.retrieve_step_data("session1", "step1")
            assert retrieved_data["html_content"] == sample_data["html"]
            assert retrieved_data["screenshot_bytes"] is None
            assert retrieved_data["action_data"] == sample_data["action"]
            assert retrieved_data["metadata"] is None
            assert retrieved_data["retrieved_all"] is False
            # Check warnings
            assert "Failed to retrieve screenshot_bytes for session1/step1 from S3. Error: Simulated S3 Error for session1/step1/screenshot.png (NoSuchKey)" in caplog.text
            assert "Failed to retrieve metadata for session1/step1 from S3. Error: Simulated S3 Error for session1/step1/metadata.json (AccessDenied)" in caplog.text


    @pytest.mark.asyncio
    async def test_retrieve_step_data_local_all_present(self, local_sm_real_fs, sample_data, tmp_path):
        local_sm_real_fs._local_base_path = tmp_path
        session_step_path = tmp_path / "session1" / "step1"
        session_step_path.mkdir(parents=True, exist_ok=True)
        with open(session_step_path / HTML_FILENAME, "w") as f: f.write(sample_data["html"])
        with open(session_step_path / SCREENSHOT_FILENAME, "wb") as f: f.write(sample_data["screenshot"])
        with open(session_step_path / ACTION_FILENAME, "w") as f: json.dump(sample_data["action"], f)
        with open(session_step_path / METADATA_FILENAME, "w") as f: json.dump(sample_data["metadata"], f)

        retrieved_data = await local_sm_real_fs.retrieve_step_data("session1", "step1")
        assert retrieved_data["html_content"] == sample_data["html"]
        assert retrieved_data["screenshot_bytes"] == sample_data["screenshot"]
        assert retrieved_data["action_data"] == sample_data["action"]
        assert retrieved_data["metadata"] == sample_data["metadata"]
        assert retrieved_data["retrieved_all"] is True

    @pytest.mark.asyncio
    async def test_retrieve_step_data_local_some_missing_or_error(self, local_sm_real_fs, sample_data, tmp_path, caplog):
        local_sm_real_fs._local_base_path = tmp_path
        session_step_path = tmp_path / "session1" / "step1"
        session_step_path.mkdir(parents=True, exist_ok=True)
        
        # HTML is present
        with open(session_step_path / HTML_FILENAME, "w") as f: f.write(sample_data["html"])
        # Screenshot is missing (no file created)
        # Action data will cause a JSON decode error
        with open(session_step_path / ACTION_FILENAME, "w") as f: f.write("this is not json")
        # Metadata will cause a generic read error (mocked)
        
        async def mock_read_local_with_errors(path_obj, is_json=False, is_bytes=False):
            relative_path_str = str(path_obj) # path_obj is already relative to local_base_path
            
            if HTML_FILENAME in relative_path_str:
                # Correctly read the HTML file created for this test
                actual_file_path = local_sm_real_fs._local_base_path / path_obj
                with open(actual_file_path, 'r') as f_html:
                    return f_html.read()
            if SCREENSHOT_FILENAME in relative_path_str:
                raise LocalStorageError(f"File not found at local path {path_obj}", original_exception=FileNotFoundError()) 
            if ACTION_FILENAME in relative_path_str:
                 # This will be hit for action_data.json, raise decode error
                actual_file_path = local_sm_real_fs._local_base_path / path_obj
                with open(actual_file_path, 'r') as f_action_bad: # Read the bad json
                    content = f_action_bad.read() 
                raise LocalStorageError(f"Failed to decode JSON from local path {path_obj}", original_exception=json.JSONDecodeError("err",content,0))

            if METADATA_FILENAME in relative_path_str:
                raise LocalStorageError(f"Simulated I/O Error for {path_obj}", original_exception=IOError("Disk read error"))
            
            # Fallback for any unexpected calls, though retrieve_step_data should only call for known components
            pytest.fail(f"Unexpected local read for: {path_obj}")
            return None

        with patch.object(local_sm_real_fs, "_read_from_local", side_effect=mock_read_local_with_errors):
            retrieved_data = await local_sm_real_fs.retrieve_step_data("session1", "step1")

            assert retrieved_data["html_content"] == sample_data["html"] 
            assert retrieved_data["screenshot_bytes"] is None
            assert retrieved_data["action_data"] is None
            assert retrieved_data["metadata"] is None
            assert retrieved_data["retrieved_all"] is False
            
            assert "Failed to retrieve screenshot_bytes for session1/step1 from local. Error: File not found at local path session1/step1/screenshot.png" in caplog.text
            assert "Failed to retrieve action_data for session1/step1 from local. Error: Failed to decode JSON from local path session1/step1/action.json" in caplog.text
            assert "Failed to retrieve metadata for session1/step1 from local. Error: Simulated I/O Error for session1/step1/metadata.json" in caplog.text


    @pytest.mark.asyncio
    async def test_retrieve_step_data_empty_session_step(self, mock_s3_sm, local_sm_real_fs, caplog):
        # Test S3
        async def s3_download_always_fail(key, is_json=False, is_bytes=False):
            raise S3OperationError(f"Simulated S3 NoSuchKey for {key}")

        with patch.object(mock_s3_sm, "_download_from_s3", side_effect=s3_download_always_fail):
            s3_retrieved = await mock_s3_sm.retrieve_step_data("empty_session", "empty_step")
            assert s3_retrieved["html_content"] is None
            assert s3_retrieved["screenshot_bytes"] is None
            assert s3_retrieved["action_data"] is None
            assert s3_retrieved["metadata"] is None
            assert s3_retrieved["retrieved_all"] is False
            assert "Failed to retrieve html_content for empty_session/empty_step from S3." in caplog.text # Check one
        
        caplog.clear() # Clear logs for local test
        
        # Test Local
        async def local_read_always_fail(path_obj, is_json=False, is_bytes=False):
            raise LocalStorageError(f"Simulated Local FileNotFoundError for {path_obj}")

        with patch.object(local_sm_real_fs, "_read_from_local", side_effect=local_read_always_fail):
            local_retrieved = await local_sm_real_fs.retrieve_step_data("empty_session", "empty_step")
            assert local_retrieved["html_content"] is None
            assert local_retrieved["screenshot_bytes"] is None
            assert local_retrieved["action_data"] is None
            assert local_retrieved["metadata"] is None
            assert local_retrieved["retrieved_all"] is False
            assert "Failed to retrieve html_content for empty_session/empty_step from local." in caplog.text # Check one 

class TestStorageManagerListingOperations:
    """Tests for listing operations in StorageManager."""

    @pytest.mark.asyncio
    async def test_list_sessions_s3_success(self, mock_s3_sm):
        s3_client = mock_s3_sm._get_s3_client()
        s3_client.put_object(Bucket=mock_s3_sm.s3_bucket_name, Key="session1/step1/file.txt", Body="test")
        s3_client.put_object(Bucket=mock_s3_sm.s3_bucket_name, Key="session2/stepA/data.html", Body="test")
        s3_client.put_object(Bucket=mock_s3_sm.s3_bucket_name, Key="prefix/session3/stepB/obs.png", Body="test")
        s3_client.put_object(Bucket=mock_s3_sm.s3_bucket_name, Key="prefix/session4/stepC/act.json", Body="test")

        # Test listing at root
        sessions = await mock_s3_sm.list_sessions()
        assert sorted(sessions) == sorted(["session1", "session2", "prefix"])
        
        # Test listing with prefix
        sessions_with_prefix = await mock_s3_sm.list_sessions(path_prefix="prefix")
        assert sorted(sessions_with_prefix) == sorted(["session3", "session4"])

        # Test listing with non-existent prefix
        sessions_non_existent_prefix = await mock_s3_sm.list_sessions(path_prefix="nonexistent")
        assert sessions_non_existent_prefix == []

    @pytest.mark.asyncio
    async def test_list_sessions_s3_no_sessions(self, mock_s3_sm):
        sessions = await mock_s3_sm.list_sessions()
        assert sessions == []
        sessions_with_prefix = await mock_s3_sm.list_sessions(path_prefix="some_prefix")
        assert sessions_with_prefix == []

    @pytest.mark.asyncio
    async def test_list_sessions_s3_client_error(self, mock_s3_sm):
        s3_client = mock_s3_sm._get_s3_client()
        s3_client.list_objects_v2 = MagicMock(side_effect=ClientError({}, 'ListObjectsV2'))
        with pytest.raises(S3OperationError):
            await mock_s3_sm.list_sessions()
        with pytest.raises(S3OperationError):
            await mock_s3_sm.list_sessions(path_prefix="error_prefix")

    @pytest.mark.asyncio
    async def test_list_sessions_local_success(self, local_sm_real_fs, tmp_path):
        base_path = Path(local_sm_real_fs.local_base_path)
        (base_path / "sessionA").mkdir()
        (base_path / "sessionB").mkdir()
        (base_path / "prefix1" / "sessionC").mkdir(parents=True, exist_ok=True)
        (base_path / "prefix1" / "sessionD").mkdir(parents=True, exist_ok=True)
        (base_path / "prefix2" / "sessionE").mkdir(parents=True, exist_ok=True)
        (base_path / "not_a_dir.txt").write_text("ignore")
        (base_path / "prefix1" / "not_a_session_dir.txt").write_text("ignore")

        sessions = await local_sm_real_fs.list_sessions()
        assert sorted(sessions) == sorted(["sessionA", "sessionB", "prefix1", "prefix2"]) # prefix1 and prefix2 are dirs too

        sessions_prefix1 = await local_sm_real_fs.list_sessions(path_prefix="prefix1")
        assert sorted(sessions_prefix1) == sorted(["sessionC", "sessionD"])

        sessions_non_existent_prefix = await local_sm_real_fs.list_sessions(path_prefix="nonexistent")
        assert sessions_non_existent_prefix == []

    @pytest.mark.asyncio
    async def test_list_sessions_local_empty(self, local_sm_real_fs, tmp_path):
        # Ensure base path exists but is empty
        Path(local_sm_real_fs.local_base_path).mkdir(exist_ok=True)
        sessions = await local_sm_real_fs.list_sessions()
        assert sessions == []
        sessions_with_prefix = await local_sm_real_fs.list_sessions(path_prefix="some_prefix")
        assert sessions_with_prefix == []

    @pytest.mark.asyncio
    async def test_list_sessions_local_base_path_does_not_exist(self, local_sm_real_fs):
        # Ensure local_base_path points to something that doesn't exist by re-initing SM
        sm_non_existent_path = StorageManager(local_base_path=str(Path(local_sm_real_fs.local_base_path) / "truly_gone"), prefer_s3=False)
        sessions = await sm_non_existent_path.list_sessions()
        assert sessions == []
        sessions_with_prefix = await sm_non_existent_path.list_sessions(path_prefix="any")
        assert sessions_with_prefix == []

    @pytest.mark.asyncio
    async def test_list_sessions_local_os_error(self, local_sm_real_fs, tmp_path):
        with patch('os.listdir', side_effect=OSError("Permission denied")):
            with pytest.raises(LocalStorageError):
                await local_sm_real_fs.list_sessions()
            with pytest.raises(LocalStorageError):
                await local_sm_real_fs.list_sessions(path_prefix="any_prefix")

    @pytest.mark.asyncio
    async def test_list_steps_for_session_s3_success(self, mock_s3_sm):
        s3_client = mock_s3_sm._get_s3_client()
        s3_client.put_object(Bucket=mock_s3_sm.s3_bucket_name, Key="session1/step1/file.txt", Body="test")
        s3_client.put_object(Bucket=mock_s3_sm.s3_bucket_name, Key="session1/step2/data.html", Body="test")
        s3_client.put_object(Bucket=mock_s3_sm.s3_bucket_name, Key="prefix/sessionX/stepA/obs.png", Body="test")
        s3_client.put_object(Bucket=mock_s3_sm.s3_bucket_name, Key="prefix/sessionX/stepB/act.json", Body="test")

        # Test listing steps at root level session
        steps_session1 = await mock_s3_sm.list_steps_for_session("session1")
        assert sorted(steps_session1) == sorted(["step1", "step2"])

        # Test listing steps for session under a prefix
        steps_sessionX_prefix = await mock_s3_sm.list_steps_for_session("sessionX", path_prefix="prefix")
        assert sorted(steps_sessionX_prefix) == sorted(["stepA", "stepB"])

        # Test non-existent session or prefix
        assert await mock_s3_sm.list_steps_for_session("nonexistent_session") == []
        assert await mock_s3_sm.list_steps_for_session("session1", path_prefix="nonexistent_prefix") == []
        assert await mock_s3_sm.list_steps_for_session("nonexistent_session", path_prefix="prefix") == []

    @pytest.mark.asyncio
    async def test_list_steps_for_session_s3_no_steps(self, mock_s3_sm):
        # Create session but no steps
        s3_client = mock_s3_sm._get_s3_client()
        s3_client.put_object(Bucket=mock_s3_sm.s3_bucket_name, Key="empty_session/", Body="") # Create a common prefix for session
        steps = await mock_s3_sm.list_steps_for_session("empty_session")
        assert steps == []

        # With prefix
        s3_client.put_object(Bucket=mock_s3_sm.s3_bucket_name, Key="pfx/empty_session_pfx/", Body="")
        steps_pfx = await mock_s3_sm.list_steps_for_session("empty_session_pfx", path_prefix="pfx")
        assert steps_pfx == []

    @pytest.mark.asyncio
    async def test_list_steps_for_session_s3_client_error(self, mock_s3_sm):
        s3_client = mock_s3_sm._get_s3_client()
        s3_client.list_objects_v2 = MagicMock(side_effect=ClientError({}, 'ListObjectsV2'))
        with pytest.raises(S3OperationError):
            await mock_s3_sm.list_steps_for_session("session1")
        with pytest.raises(S3OperationError):
            await mock_s3_sm.list_steps_for_session("session1", path_prefix="any_prefix")

    @pytest.mark.asyncio
    async def test_list_steps_for_session_local_success(self, local_sm_real_fs, tmp_path):
        base_path = Path(local_sm_real_fs.local_base_path)
        (base_path / "sessionAlpha" / "stepX").mkdir(parents=True, exist_ok=True)
        (base_path / "sessionAlpha" / "stepY").mkdir(parents=True, exist_ok=True)
        (base_path / "prefixA" / "sessionBeta" / "stepZ").mkdir(parents=True, exist_ok=True)
        (base_path / "prefixA" / "sessionBeta" / "not_a_step_dir.txt").write_text("ignore")

        steps_alpha = await local_sm_real_fs.list_steps_for_session("sessionAlpha")
        assert sorted(steps_alpha) == sorted(["stepX", "stepY"])

        steps_beta_prefixA = await local_sm_real_fs.list_steps_for_session("sessionBeta", path_prefix="prefixA")
        assert sorted(steps_beta_prefixA) == ["stepZ"]

        assert await local_sm_real_fs.list_steps_for_session("nonexistent_session") == []
        assert await local_sm_real_fs.list_steps_for_session("sessionAlpha", path_prefix="nonexistent_prefix") == []

    @pytest.mark.asyncio
    async def test_list_steps_for_session_local_empty(self, local_sm_real_fs, tmp_path):
        base_path = Path(local_sm_real_fs.local_base_path)
        (base_path / "session_no_steps").mkdir(exist_ok=True)
        steps = await local_sm_real_fs.list_steps_for_session("session_no_steps")
        assert steps == []

        (base_path / "pfx" / "session_no_steps_pfx").mkdir(parents=True, exist_ok=True)
        steps_pfx = await local_sm_real_fs.list_steps_for_session("session_no_steps_pfx", path_prefix="pfx")
        assert steps_pfx == []

    @pytest.mark.asyncio
    async def test_list_steps_for_session_local_session_path_does_not_exist(self, local_sm_real_fs, tmp_path):
        steps = await local_sm_real_fs.list_steps_for_session("non_existent_session")
        assert steps == []
        steps_pfx = await local_sm_real_fs.list_steps_for_session("non_existent_session", path_prefix="any_prefix")
        assert steps_pfx == []

    @pytest.mark.asyncio
    async def test_list_steps_for_session_local_os_error(self, local_sm_real_fs, tmp_path):
        session_path = Path(local_sm_real_fs.local_base_path) / "error_session"
        session_path.mkdir(exist_ok=True)
        with patch('os.listdir', side_effect=OSError("Permission denied")):
            with pytest.raises(LocalStorageError):
                await local_sm_real_fs.list_steps_for_session("error_session")
            with pytest.raises(LocalStorageError):
                await local_sm_real_fs.list_steps_for_session("error_session", path_prefix="any_prefix")

class TestStorageManagerDeletionOperations:
    """Tests for deletion operations in StorageManager."""

    def _setup_local_dir_structure(self, base_path: Path, structure: Dict[str, List[str]]):
        """Helper to create a session/step directory structure locally."""
        for session_id, steps in structure.items():
            session_dir = base_path / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            for step_id in steps:
                step_dir = session_dir / step_id
                step_dir.mkdir(parents=True, exist_ok=True)
                # Create some dummy files in each step dir
                (step_dir / HTML_FILENAME).write_text(f"html for {session_id}/{step_id}")
                (step_dir / SCREENSHOT_FILENAME).write_text(f"screen for {session_id}/{step_id}")

    @pytest.mark.asyncio
    async def test_delete_step_s3_success(self, mock_s3_sm):
        sm, mock_client = mock_s3_sm
        session_id, step_id = "sessDel1", "stepDelA"
        prefix_to_delete = f"{session_id}/{step_id}/"

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": f"{prefix_to_delete}file1.txt"},
                    {"Key": f"{prefix_to_delete}file2.png"},
                ]
            }
        ]
        mock_client.delete_objects.return_value = {} # Successful deletion, no errors

        await sm.delete_step(session_id, step_id)

        mock_client.get_paginator.assert_called_once_with('list_objects_v2')
        mock_paginator.paginate.assert_called_once_with(Bucket=sm.s3_bucket_name, Prefix=prefix_to_delete)
        mock_client.delete_objects.assert_called_once_with(
            Bucket=sm.s3_bucket_name,
            Delete={
                'Objects': [
                    {'Key': f"{prefix_to_delete}file1.txt"},
                    {'Key': f"{prefix_to_delete}file2.png"},
                ],
                'Quiet': True
            }
        )

    @pytest.mark.asyncio
    async def test_delete_step_s3_no_objects_found(self, mock_s3_sm):
        sm, mock_client = mock_s3_sm
        session_id, step_id = "sessDelEmpty", "stepDelEmpty"
        prefix_to_delete = f"{session_id}/{step_id}/"

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{}] # No 'Contents' key

        await sm.delete_step(session_id, step_id)
        mock_client.delete_objects.assert_not_called() # Should not be called if no objects

    @pytest.mark.asyncio
    async def test_delete_step_s3_delete_errors(self, mock_s3_sm):
        sm, mock_client = mock_s3_sm
        session_id, step_id = "sessDelErr", "stepDelErr"
        prefix_to_delete = f"{session_id}/{step_id}/"
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {"Contents": [{"Key": f"{prefix_to_delete}file1.txt"}] }
        ]
        mock_client.delete_objects.return_value = {
            'Errors': [{'Key': f"{prefix_to_delete}file1.txt", 'Code': 'AccessDenied', 'Message': 'Access Denied'}]
        }
        with pytest.raises(S3OperationError, match=f"Errors deleting from S3 for step {prefix_to_delete}"):
            await sm.delete_step(session_id, step_id)

    @pytest.mark.asyncio
    async def test_delete_step_s3_list_client_error(self, mock_s3_sm):
        sm, mock_client = mock_s3_sm
        session_id, step_id = "sessListErr", "stepListErr"
        prefix_to_delete = f"{session_id}/{step_id}/"
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = ClientError({"Error": {}}, "list_objects_v2")

        with pytest.raises(S3OperationError, match=f"Failed to delete S3 step {prefix_to_delete}"):
            await sm.delete_step(session_id, step_id)
        mock_client.delete_objects.assert_not_called()


    @pytest.mark.asyncio
    async def test_delete_step_local_success(self, local_sm_real_fs, tmp_path):
        sm = local_sm_real_fs
        sm._local_base_path = tmp_path
        session_id, step_id = "localSessDel1", "localStepDelA"
        self._setup_local_dir_structure(tmp_path, {session_id: [step_id, "otherStep"]})
        
        step_path_to_delete = tmp_path / session_id / step_id
        other_step_path = tmp_path / session_id / "otherStep"
        assert step_path_to_delete.exists()
        assert other_step_path.exists()

        await sm.delete_step(session_id, step_id)

        assert not step_path_to_delete.exists()
        assert other_step_path.exists() # Ensure only specified step is deleted

    @pytest.mark.asyncio
    async def test_delete_step_local_not_found(self, local_sm_real_fs, tmp_path):
        sm = local_sm_real_fs
        sm._local_base_path = tmp_path
        session_id, step_id = "localSessNonExist", "localStepNonExist"
        # Ensure path does not exist
        step_path_to_delete = tmp_path / session_id / step_id
        assert not step_path_to_delete.exists()

        await sm.delete_step(session_id, step_id) # Should not raise, just log
        assert not step_path_to_delete.exists()

    @pytest.mark.asyncio
    async def test_delete_step_local_os_error(self, local_sm_real_fs, tmp_path):
        sm = local_sm_real_fs
        sm._local_base_path = tmp_path
        session_id, step_id = "localSessOSError", "localStepOSError"
        self._setup_local_dir_structure(tmp_path, {session_id: [step_id]})
        step_path_to_delete = tmp_path / session_id / step_id

        with patch("shutil.rmtree", side_effect=OSError("Permission denied")):
             with pytest.raises(LocalStorageError, match=f"Failed to delete local step {str(step_path_to_delete)}"):
                await sm.delete_step(session_id, step_id)
        assert step_path_to_delete.exists() # Should still exist if rmtree failed

    @pytest.mark.asyncio
    async def test_delete_session_s3_success(self, mock_s3_sm):
        sm, mock_client = mock_s3_sm
        session_id = "fullSessDel1"
        prefix_to_delete = f"{session_id}/"
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {"Contents": [{"Key": f"{prefix_to_delete}step1/fileA.txt"}, {"Key": f"{prefix_to_delete}step2/fileB.txt"}] }
        ]
        mock_client.delete_objects.return_value = {}

        await sm.delete_session(session_id)
        mock_client.delete_objects.assert_called_once_with(
            Bucket=sm.s3_bucket_name,
            Delete={
                'Objects': [
                    {'Key': f"{prefix_to_delete}step1/fileA.txt"},
                    {'Key': f"{prefix_to_delete}step2/fileB.txt"},
                ],
                'Quiet': True
            }
        )

    @pytest.mark.asyncio
    async def test_delete_session_local_success(self, local_sm_real_fs, tmp_path):
        sm = local_sm_real_fs
        sm._local_base_path = tmp_path
        session_to_delete = "localFullSessDel1"
        other_session = "localOtherSess"
        self._setup_local_dir_structure(tmp_path, {
            session_to_delete: ["stepA", "stepB"],
            other_session: ["stepC"]
        })
        
        session_path_to_delete = tmp_path / session_to_delete
        other_session_path = tmp_path / other_session
        assert session_path_to_delete.exists()
        assert other_session_path.exists()

        await sm.delete_session(session_to_delete)

        assert not session_path_to_delete.exists()
        assert other_session_path.exists() # Ensure other session is untouched 

@pytest.mark.usefixtures("aws_credentials") # Ensure moto S3 mocking is active via env vars
class TestStorageManagerS3Integration:
    """Integration-style tests for StorageManager using a mocked S3 (moto)."""

    @pytest.fixture
    def s3_integration_sm(self, s3_bucket, s3_client): # s3_client is implicitly used by SM
        """Provides a StorageManager instance configured to use the s3_bucket for integration tests."""
        # We pass s3_client to ensure it's initialized within the moto context if SM relies on it implicitly,
        # but SM should pick up credentials via env vars and create its own client.
        # The main thing is that s3_bucket fixture ensures the bucket exists in moto's S3.
        sm = StorageManager(
            s3_bucket_name=s3_bucket, 
            s3_region_name=os.environ["AWS_DEFAULT_REGION"], # Use region from aws_credentials
            prefer_s3=True
        )
        assert sm.use_s3 is True # Verify it's in S3 mode
        return sm

    @pytest.mark.asyncio
    async def test_s3_full_lifecycle_single_session_step(self, s3_integration_sm: StorageManager, sample_data):
        """Test storing, listing, and deleting a single step and then the session in S3."""
        sm = s3_integration_sm
        session_id = "integ_sess_1"
        step_id_1 = "integ_step_1"

        # 1. Store data for a step
        await sm.store_step_data(
            session_id, 
            step_id_1, 
            html_content=sample_data["html"],
            screenshot_bytes=sample_data["screenshot"],
            action_data=sample_data["action"],
            metadata=sample_data["metadata"]
        )

        # 2. List sessions and steps
        sessions = await sm.list_sessions()
        assert sessions == [session_id]

        steps_in_session = await sm.list_steps_for_session(session_id)
        assert steps_in_session == [step_id_1]

        # 3. Retrieve and verify some data (optional, but good check)
        html, screen, action, meta = await sm.retrieve_step_data(session_id, step_id_1)
        assert html == sample_data["html"]
        assert screen == sample_data["screenshot"]
        assert action == sample_data["action"]
        assert meta == sample_data["metadata"]

        # 4. Delete the step
        await sm.delete_step(session_id, step_id_1)

        # 5. Verify step is deleted (listing should be empty)
        steps_after_delete = await sm.list_steps_for_session(session_id)
        assert steps_after_delete == []

        # 6. Attempt to retrieve deleted step data (should return Nones, log warnings)
        with pytest.warns(None) as record: # Check for S3OperationError/NoSuchKey related warnings if retrieve handles it that way
                                        # Or check logs if it only logs
            html_del, screen_del, _, _ = await sm.retrieve_step_data(session_id, step_id_1)
        assert html_del is None
        assert screen_del is None
        # Verify logs (example, adjust based on actual logging in retrieve_step_data for missing items)
        # For now, just checking Nones is sufficient as a basic deletion check for this lifecycle test.

        # 7. Delete the session
        await sm.delete_session(session_id)

        # 8. Verify session is deleted
        sessions_after_delete = await sm.list_sessions()
        assert sessions_after_delete == [] 

        # Test object_exists_s3
        html_key = s3_integration_sm._get_s3_key(session_id, step_id, HTML_FILENAME)
        non_existent_key = "non/existent/key.txt"
        assert s3_integration_sm.object_exists_s3(html_key) is True
        assert s3_integration_sm.object_exists_s3(non_existent_key) is False

        # Test object_exists_s3 when S3 is not in use by the manager
        local_only_sm = StorageManager(local_base_path=str(tmp_path / "local_sm_exist_test"), prefer_s3=False)
        assert local_only_sm.object_exists_s3(html_key) is False # Should return False as S3 not used

        # Test object_exists_s3 with S3 client error (other than 404)
        mock_s3_client = MagicMock()
        mock_s3_client.head_object.side_effect = ClientError({"Error": {"Code": "500", "Message": "Internal Server Error"}}, "HeadObject")
        
        with patch.object(s3_integration_sm, '_s3_client', mock_s3_client): # Inject mock client
             with pytest.raises(S3OperationError, match="Failed to check existence of S3 object"):
                s3_integration_sm.object_exists_s3("some/key")

        # Cleanup (already done by test fixture and method itself)
        await s3_integration_sm.delete_step(session_id, step_id)
        assert s3_integration_sm.object_exists_s3(html_key) is False

    # Add other S3 integration tests here if any

# You might want a dedicated TestStorageManagerUtilities class if you add more utils
# For now, adding to TestStorageManagerS3Integration is okay as it requires S3 setup.

# Example of how it could be structured if in its own test, reusing s3_integration_sm:
# class TestStorageManagerS3Utilities:
#     @pytest.mark.asyncio
#     async def test_object_exists_s3_various_cases(self, s3_integration_sm: StorageManager, sample_data, tmp_path):
#         session_id = "util_sess_exists"
#         step_id = "util_step_exists"
#         await s3_integration_sm.store_step_data(session_id, step_id, html_content=sample_data["html"])
#         html_key = s3_integration_sm._get_s3_key(session_id, step_id, HTML_FILENAME)
#         non_existent_key = "this/key/does/not/exist.dat"

#         assert s3_integration_sm.object_exists_s3(html_key) is True
#         assert s3_integration_sm.object_exists_s3(non_existent_key) is False

#         
#         # Test S3 not in use case
#         local_sm = StorageManager(local_base_path=str(tmp_path / "local_obj_exist"), prefer_s3=False)
#         assert local_sm.object_exists_s3(html_key) is False
        
#         # Test S3 client error during head_object
#         mock_client_error = MagicMock()
#         mock_client_error.head_object.side_effect = ClientError(
#             {"Error": {"Code": "ExpiredToken", "Message": "Token expired"}}, "HeadObject"
#         )
#         with patch.object(s3_integration_sm, '_s3_client', mock_client_error):
#             with pytest.raises(S3OperationError):
#                 s3_integration_sm.object_exists_s3(html_key)
        
#         await s3_integration_sm.delete_step(session_id, step_id)
        
#         assert s3_integration_sm.object_exists_s3(html_key) is False 