import pytest
from unittest import mock

from browserbase_client import config


def test_get_api_key_from_env(monkeypatch):
    """Test API key retrieval from environment variable."""
    monkeypatch.setenv(config.BROWSERBASE_API_KEY_ENV_VAR, "env_api_key")
    assert config.get_api_key(None) == "env_api_key"

def test_get_api_key_from_explicit_param():
    """Test API key retrieval from explicit parameter, overriding env."""
    # Even if env var is set, explicit param should take precedence
    with mock.patch.dict("os.environ", {config.BROWSERBASE_API_KEY_ENV_VAR: "env_api_key"}):
        assert config.get_api_key("explicit_api_key") == "explicit_api_key"

def test_get_api_key_none():
    """Test API key retrieval returns None if not found."""
    # Ensure env var is not set for this test
    with mock.patch.dict("os.environ", clear=True):
        assert config.get_api_key(None) is None

def test_get_base_url_default():
    """Test base URL retrieval returns default if not set."""
    with mock.patch.dict("os.environ", clear=True):
        assert config.get_base_url(None) == config.DEFAULT_BASE_URL

def test_get_base_url_from_env(monkeypatch):
    """Test base URL retrieval from environment variable."""
    monkeypatch.setenv(config.BROWSERBASE_BASE_URL_ENV_VAR, "https://env.example.com")
    assert config.get_base_url(None) == "https://env.example.com"

def test_get_base_url_from_explicit_param(monkeypatch):
    """Test base URL retrieval from explicit parameter, overriding env and default."""
    monkeypatch.setenv(config.BROWSERBASE_BASE_URL_ENV_VAR, "https://env.example.com")
    assert config.get_base_url("https://explicit.example.com") == "https://explicit.example.com"

def test_get_default_timeout_seconds_default():
    """Test timeout retrieval returns default if not set."""
    with mock.patch.dict("os.environ", clear=True):
        assert config.get_default_timeout_seconds(None) == config.DEFAULT_TIMEOUT_SECONDS

def test_get_default_timeout_seconds_from_env(monkeypatch):
    """Test timeout retrieval from environment variable."""
    monkeypatch.setenv(config.BROWSERBASE_DEFAULT_TIMEOUT_SECONDS_ENV_VAR, "45.5")
    assert config.get_default_timeout_seconds(None) == 45.5

def test_get_default_timeout_seconds_from_explicit_param(monkeypatch):
    """Test timeout retrieval from explicit parameter, overriding env and default."""
    monkeypatch.setenv(config.BROWSERBASE_DEFAULT_TIMEOUT_SECONDS_ENV_VAR, "45.0")
    assert config.get_default_timeout_seconds(60.0) == 60.0

def test_get_default_timeout_seconds_invalid_env_value(monkeypatch, caplog):
    """Test timeout retrieval with invalid environment variable value."""
    monkeypatch.setenv(config.BROWSERBASE_DEFAULT_TIMEOUT_SECONDS_ENV_VAR, "invalid_value")
    timeout = config.get_default_timeout_seconds(None)
    assert timeout == config.DEFAULT_TIMEOUT_SECONDS
    # Check for key phrases in the log record
    assert f"Invalid value for env var {config.BROWSERBASE_DEFAULT_TIMEOUT_SECONDS_ENV_VAR}" in caplog.text
    assert "invalid_value" in caplog.text
    assert "Using default timeout" in caplog.text 