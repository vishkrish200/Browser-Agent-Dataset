"""Tests for stagehand_client.config"""

import pytest
import os
from unittest import mock

from stagehand_client import config

@pytest.fixture(autouse=True)
def clear_env_vars():
    """Clear relevant environment variables before each test and restore after."""
    original_api_key = os.environ.pop(config.STAGEHAND_API_KEY_ENV_VAR, None)
    original_base_url = os.environ.pop(config.STAGEHAND_BASE_URL_ENV_VAR, None)
    original_timeout = os.environ.pop(config.STAGEHAND_DEFAULT_TIMEOUT_SECONDS_ENV_VAR, None)
    yield
    if original_api_key is not None:
        os.environ[config.STAGEHAND_API_KEY_ENV_VAR] = original_api_key
    if original_base_url is not None:
        os.environ[config.STAGEHAND_BASE_URL_ENV_VAR] = original_base_url
    if original_timeout is not None:
        os.environ[config.STAGEHAND_DEFAULT_TIMEOUT_SECONDS_ENV_VAR] = original_timeout

# Tests for get_api_key
def test_get_api_key_with_override():
    override_key = "override_test_key"
    assert config.get_api_key(api_key_override=override_key) == override_key

def test_get_api_key_with_env_var():
    env_key = "env_test_key"
    with mock.patch.dict(os.environ, {config.STAGEHAND_API_KEY_ENV_VAR: env_key}):
        assert config.get_api_key() == env_key

def test_get_api_key_override_takes_precedence():
    override_key = "override_priority_key"
    env_key = "env_should_be_ignored_key"
    with mock.patch.dict(os.environ, {config.STAGEHAND_API_KEY_ENV_VAR: env_key}):
        assert config.get_api_key(api_key_override=override_key) == override_key

def test_get_api_key_no_override_no_env_var():
    assert config.get_api_key() is None

# Tests for get_base_url
def test_get_base_url_with_override():
    override_url = "https://override.example.com"
    assert config.get_base_url(base_url_override=override_url) == override_url

def test_get_base_url_with_env_var():
    env_url = "https://env.example.com"
    with mock.patch.dict(os.environ, {config.STAGEHAND_BASE_URL_ENV_VAR: env_url}):
        assert config.get_base_url() == env_url

def test_get_base_url_override_takes_precedence():
    override_url = "https://override-priority.example.com"
    env_url = "https://env-ignored.example.com"
    with mock.patch.dict(os.environ, {config.STAGEHAND_BASE_URL_ENV_VAR: env_url}):
        assert config.get_base_url(base_url_override=override_url) == override_url

def test_get_base_url_no_override_no_env_var_uses_default():
    assert config.get_base_url() == config.DEFAULT_BASE_URL

# Tests for get_default_timeout_seconds
def test_get_default_timeout_seconds_with_override():
    override_timeout = 15.5
    assert config.get_default_timeout_seconds(timeout_override=override_timeout) == override_timeout

def test_get_default_timeout_seconds_with_env_var():
    env_timeout_str = "45.0"
    env_timeout_float = 45.0
    with mock.patch.dict(os.environ, {config.STAGEHAND_DEFAULT_TIMEOUT_SECONDS_ENV_VAR: env_timeout_str}):
        assert config.get_default_timeout_seconds() == env_timeout_float

def test_get_default_timeout_seconds_override_takes_precedence():
    override_timeout = 25.0
    env_timeout_str = "35.0"
    with mock.patch.dict(os.environ, {config.STAGEHAND_DEFAULT_TIMEOUT_SECONDS_ENV_VAR: env_timeout_str}):
        assert config.get_default_timeout_seconds(timeout_override=override_timeout) == override_timeout

def test_get_default_timeout_seconds_no_override_no_env_var_uses_default():
    assert config.get_default_timeout_seconds() == config.DEFAULT_TIMEOUT_SECONDS

def test_get_default_timeout_seconds_with_invalid_env_var_uses_default():
    env_timeout_invalid_str = "not_a_float"
    with mock.patch.dict(os.environ, {config.STAGEHAND_DEFAULT_TIMEOUT_SECONDS_ENV_VAR: env_timeout_invalid_str}):
        # Optionally check for a log warning here if logging was implemented in config.py
        assert config.get_default_timeout_seconds() == config.DEFAULT_TIMEOUT_SECONDS

def test_get_default_timeout_seconds_with_empty_env_var_uses_default():
    env_timeout_empty_str = ""
    with mock.patch.dict(os.environ, {config.STAGEHAND_DEFAULT_TIMEOUT_SECONDS_ENV_VAR: env_timeout_empty_str}):
        assert config.get_default_timeout_seconds() == config.DEFAULT_TIMEOUT_SECONDS 