import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.orchestrator import Orchestrator
# Assuming StagehandClient and WorkflowBuilder are importable for type hints / instantiation
# If they are in src.stagehand_client, the import would be:
from src.stagehand_client import StagehandClient, WorkflowBuilder, StagehandAPIError
from src.browserbase_client import BrowserbaseClient, BrowserbaseAPIError

@pytest.fixture
def mock_browserbase_client():
    """Provides a mock BrowserbaseClient instance with async methods."""
    mock_client = AsyncMock(spec=BrowserbaseClient)
    # Ensure async methods return awaitables by default, or specific mock coroutines
    mock_client.create_session = AsyncMock(return_value={"sessionId": "mock_bb_session_123"})
    mock_client.release_session = AsyncMock(return_value=True)
    mock_client.close = AsyncMock()
    return mock_client

@pytest.fixture
def mock_stagehand_client():
    """Provides a mock StagehandClient instance with async methods."""
    mock_client = AsyncMock(spec=StagehandClient)
    mock_client.create_task = AsyncMock(return_value={"taskId": "mock_sh_task_456"})
    mock_client.execute_task = AsyncMock(return_value={"executionId": "mock_sh_exec_789", "status": "completed"})
    mock_client.close = AsyncMock()
    return mock_client

@pytest.fixture
def sample_project_id():
    """Provides a sample Browserbase project ID."""
    return "test_project_xyz789"

@pytest.fixture
def orchestrator_instance(mock_browserbase_client, mock_stagehand_client, sample_project_id):
    """Provides an Orchestrator instance initialized with mock clients and a sample project ID."""
    config = {"browserbase_project_id": sample_project_id}
    # Pass the mock instances directly to the Orchestrator constructor
    return Orchestrator(
        config=config,
        browserbase_client=mock_browserbase_client, 
        stagehand_client=mock_stagehand_client
    )

@pytest.fixture
def sample_workflow_builder():
    """Provides a sample WorkflowBuilder instance with a basic workflow."""
    # Mock the WorkflowBuilder and its build() method
    builder = MagicMock(spec=WorkflowBuilder)
    builder.workflow_name = "SampleTestWorkflow"
    # build() should return a dict that create_task expects
    builder.build.return_value = {
        "name": "SampleTestWorkflow",
        "steps": [
            {"type": "action", "actionType": "navigate", "url": "https://example.com"},
            {"type": "action", "actionType": "extract_text", "selector": "h1"}
        ]
    }
    return builder

# Fixture to ensure a fresh event loop for each async test if not handled by pytest-asyncio defaults
# This might be handled by pytest-asyncio's auto mode, but can be explicit if issues arise.
# @pytest.fixture(scope="function")
# def event_loop():
#     loop = asyncio.get_event_loop_policy().new_event_loop()
#     yield loop
#     loop.close() 