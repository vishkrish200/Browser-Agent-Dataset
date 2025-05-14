# tests/data_collector/test_storage.py
import pytest
import os
import gzip
import shutil
from unittest import mock # For patching os.makedirs, open, etc.
import io

from src.data_collector.storage import LocalStorage, S3Storage, get_storage_backend, StorageBackend # Boto3 might be an issue for direct test
from src.data_collector.types import StorageConfig
from src.data_collector.exceptions import LocalStorageError, S3StorageError, ConfigurationError

# --- LocalStorage Tests ---

@pytest.fixture
def local_storage_config(tmp_path):
    """Provides a config for LocalStorage using a temporary path."""
    # tmp_path is a pytest fixture providing a pathlib.Path object unique to each test
    return StorageConfig(type="local", base_path=str(tmp_path / "test_collected_data"))

@pytest.fixture
def local_storage(local_storage_config: StorageConfig) -> LocalStorage:
    """Creates a LocalStorage instance, ensuring the base path is clean for each test."""
    base_p = local_storage_config.get("base_path")
    if base_p and os.path.exists(base_p):
        shutil.rmtree(base_p) # Clean up before test if it exists from a previous failed run
    return LocalStorage(config=local_storage_config)

def test_local_storage_init(local_storage: LocalStorage, local_storage_config: StorageConfig):
    assert local_storage.base_path == local_storage_config["base_path"]
    assert os.path.exists(local_storage.base_path)

def test_local_storage_init_creates_dir(tmp_path):
    new_base_path = str(tmp_path / "new_data_dir")
    assert not os.path.exists(new_base_path)
    storage_config = StorageConfig(type="local", base_path=new_base_path)
    ls = LocalStorage(config=storage_config)
    assert os.path.exists(ls.base_path)

@mock.patch("os.makedirs")
def test_local_storage_init_dir_creation_fails(mock_makedirs, tmp_path):
    mock_makedirs.side_effect = OSError("Test permission denied")
    fail_path = str(tmp_path / "cant_create_this")
    storage_config = StorageConfig(type="local", base_path=fail_path)
    with pytest.raises(LocalStorageError, match="Failed to create base directory"):
        LocalStorage(config=storage_config)

def test_local_storage_get_artifact_path(local_storage: LocalStorage):
    path = local_storage.get_artifact_path("sess1", "step1", "data.txt")
    expected_path = os.path.join(local_storage.base_path, "sess1", "step1", "data.txt")
    assert path == expected_path

@pytest.mark.asyncio
async def test_local_storage_store_str_data(local_storage: LocalStorage):
    artifact_name = "test.txt"
    data_str = "Hello, world!"
    stored_path = await local_storage.store_artifact("sess_str", "step_str", artifact_name, data_str)
    
    assert os.path.exists(stored_path)
    with open(stored_path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert content == data_str

@pytest.mark.asyncio
async def test_local_storage_store_bytes_data(local_storage: LocalStorage):
    artifact_name = "test.bin"
    data_bytes = b"\x00\x01\xFAHello"
    stored_path = await local_storage.store_artifact("sess_bytes", "step_bytes", artifact_name, data_bytes)
    
    assert os.path.exists(stored_path)
    with open(stored_path, 'rb') as f:
        content = f.read()
    assert content == data_bytes

@pytest.mark.asyncio
async def test_local_storage_store_stringio_data(local_storage: LocalStorage):
    artifact_name = "test_io.txt"
    data_str = "Text from StringIO"
    string_io = io.StringIO(data_str)
    stored_path = await local_storage.store_artifact("sess_io_str", "step_io_str", artifact_name, string_io)
    
    assert os.path.exists(stored_path)
    with open(stored_path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert content == data_str

@pytest.mark.asyncio
async def test_local_storage_store_bytesio_data(local_storage: LocalStorage):
    artifact_name = "test_io.bin"
    data_bytes = b"Bytes from BytesIO \xFF"
    bytes_io = io.BytesIO(data_bytes)
    stored_path = await local_storage.store_artifact("sess_io_bytes", "step_io_bytes", artifact_name, bytes_io)
    
    assert os.path.exists(stored_path)
    with open(stored_path, 'rb') as f:
        content = f.read()
    assert content == data_bytes

@pytest.mark.asyncio
async def test_local_storage_store_gzipped_html(local_storage: LocalStorage):
    artifact_name = "page.html.gz"
    html_str = "<html><body><h1>Hello Gzip</h1></body></html>"
    stored_path = await local_storage.store_artifact("sess_gz", "step_gz", artifact_name, html_str, is_gzipped=False)
    
    assert os.path.exists(stored_path)
    with gzip.open(stored_path, 'rt', encoding='utf-8') as f:
        content = f.read()
    assert content == html_str

@pytest.mark.asyncio
async def test_local_storage_store_already_gzipped_bytes(local_storage: LocalStorage):
    artifact_name = "data.bin.gz"
    original_data = b"Some binary data to be gzipped"
    gzipped_data = gzip.compress(original_data)
    stored_path = await local_storage.store_artifact("sess_pre_gz", "step_pre_gz", artifact_name, gzipped_data, is_gzipped=True)
    
    assert os.path.exists(stored_path)
    # Read raw bytes and compare, as it should not have been double-gzipped
    with open(stored_path, 'rb') as f:
        file_content_bytes = f.read()
    assert file_content_bytes == gzipped_data
    # Optionally, decompress to verify original content
    assert gzip.decompress(file_content_bytes) == original_data

@pytest.mark.asyncio
async def test_local_storage_store_no_gzip_for_non_gz_name(local_storage: LocalStorage):
    artifact_name = "image.png"
    data_bytes = b"png_image_data_here"
    stored_path = await local_storage.store_artifact("sess_no_gz", "step_no_gz", artifact_name, data_bytes, is_gzipped=False)

    assert os.path.exists(stored_path)
    with open(stored_path, 'rb') as f:
        content = f.read()
    assert content == data_bytes # Should be stored as is

@pytest.mark.asyncio
async def test_local_storage_store_creates_nested_dirs(local_storage: LocalStorage):
    stored_path = await local_storage.store_artifact("deep/session", "even/deeper/step", "artifact.dat", b"deep data")
    assert os.path.exists(stored_path)
    assert os.path.exists(os.path.dirname(stored_path))
    assert os.path.exists(os.path.dirname(os.path.dirname(stored_path)))

@mock.patch("os.makedirs")
@pytest.mark.asyncio
async def test_local_storage_store_dir_creation_fail_on_store(mock_makedirs, local_storage_config: StorageConfig):
    # Need to re-init LocalStorage for this test as the fixture might have already created the base_path
    ls = LocalStorage(local_storage_config) # Base path might be created here
    
    # Simulate failure only for the deeper nested directory specific to the artifact
    def makedirs_side_effect(path, exist_ok=False):
        if "specific_fail_dir" in path:
            raise OSError("Cannot create this specific dir")
        else:
            return os.path.realpath(os.makedirs)(path, exist_ok=True) # Call original for other paths
    mock_makedirs.side_effect = makedirs_side_effect

    with pytest.raises(LocalStorageError, match="Failed to create directory"):
        await ls.store_artifact("sess_fail", "specific_fail_dir", "data.txt", b"test")


@pytest.mark.asyncio
async def test_local_storage_retrieve_artifact(local_storage: LocalStorage):
    artifact_name = "retrievable.txt"
    data_str = "Data to retrieve"
    stored_path = await local_storage.store_artifact("sess_retr", "step_retr", artifact_name, data_str)
    
    retrieved_data = await local_storage.retrieve_artifact(stored_path)
    assert retrieved_data.decode('utf-8') == data_str

@pytest.mark.asyncio
async def test_local_storage_retrieve_not_found(local_storage: LocalStorage):
    non_existent_path = local_storage.get_artifact_path("sess_miss", "step_miss", "missing.dat")
    with pytest.raises(LocalStorageError, match="Artifact not found"):
        await local_storage.retrieve_artifact(non_existent_path)

# --- S3Storage Tests (Placeholders - require mocking boto3) ---

@pytest.fixture
def s3_storage_config():
    return StorageConfig(
        type="s3", 
        bucket="test-bucket", 
        aws_access_key_id="test_key_id", 
        aws_secret_access_key="test_secret_key", 
        aws_region="us-east-1"
    )

@mock.patch('src.data_collector.storage.BOTO3_AVAILABLE', True) # This patches the boolean in the storage module
@mock.patch('src.data_collector.storage.boto3') # This mocks the imported boto3 module in storage.py
def test_get_storage_backend_s3(mock_boto3_module_in_storage, s3_storage_config: StorageConfig):
    # mock_boto3_module_in_storage is the mock for the `boto3` module *as imported in storage.py*
    # s3_storage_config is the fixture
    
    mock_s3_client = mock.MagicMock()
    mock_boto3_module_in_storage.client.return_value = mock_s3_client
    # mock_s3_client.head_bucket.return_value = {} # If head_bucket is called for validation

    backend = get_storage_backend(s3_storage_config)
    assert isinstance(backend, S3Storage)
    assert backend.bucket_name == s3_storage_config["bucket"]
    mock_boto3_module_in_storage.client.assert_called_once_with(
        's3',
        endpoint_url=s3_storage_config.get('s3_endpoint_url'),
        aws_access_key_id=s3_storage_config['aws_access_key_id'],
        aws_secret_access_key=s3_storage_config['aws_secret_access_key'],
        region_name=s3_storage_config['aws_region']
    )

def test_get_storage_backend_unsupported():
    config = StorageConfig(type="ftp", base_path="/foo")
    with pytest.raises(ConfigurationError, match="Unsupported storage type: ftp"):
        get_storage_backend(config)

def test_get_storage_backend_default_is_local(tmp_path):
    # Test that if type is missing, it defaults to local
    config = StorageConfig(base_path=str(tmp_path / "default_local")) 
    backend = get_storage_backend(config)
    assert isinstance(backend, LocalStorage)
    assert backend.base_path == str(tmp_path / "default_local") 