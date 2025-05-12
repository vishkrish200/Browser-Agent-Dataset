"""Configuration for stagehand_client tests."""

import pytest
from respx import MockRouter

@pytest.fixture
def respx_router() -> MockRouter:
    """Provides a MockRouter instance for mocking HTTP requests."""
    return MockRouter(assert_all_called=False) # assert_all_called can be True for stricter tests 