"""Tests for the Orchestrator's task execution capabilities."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock, call

# Import necessary classes from your project
# Adjust the import path based on your project structure
from src.orchestrator import Orchestrator, TaskCreationError, OrchestratorError
from src.stagehand_client import WorkflowBuilder, StagehandAPIError
from src.browserbase_client import BrowserbaseAPIError


@pytest.fixture
def mock_browserbase_client():
    """Fixture for a mocked BrowserbaseClient."""
    mock = AsyncMock()
    # Mock session creation success
    mock.create_session.return_value = {"sessionId": "bb_session_123"}
    # Mock session release success
    mock.release_session.return_value = None # Typically doesn't return content on success
    return mock

@pytest.fixture
def mock_stagehand_client():
    """Fixture for a mocked StagehandClient."""
    mock = AsyncMock()
    # Mock task creation success
    mock.create_task.return_value = {"taskId": "sh_task_abc", "status": "created"}
    # Mock task execution success
    mock.execute_task.return_value = {"executionId": "exec_xyz", "status": "running"}
    return mock

@pytest.fixture
async def orchestrator_instance(mock_browserbase_client, mock_stagehand_client):
    """Fixture for an Orchestrator instance with mocked clients."""
    # Use patch to temporarily replace the actual clients within the Orchestrator init
    with patch('src.orchestrator.BrowserbaseClient', return_value=mock_browserbase_client):
        with patch('src.orchestrator.StagehandClient', return_value=mock_stagehand_client):
            orchestrator = Orchestrator(
                browserbase_api_key="dummy_bb",
                stagehand_api_key="dummy_sh"
            )
            yield orchestrator # Yield the instance for the test
            # Cleanup: Close the orchestrator (and thus the mocked clients)
            await orchestrator.close()


@pytest.fixture
def sample_workflow():
    """Fixture for a sample WorkflowBuilder."""
    builder = WorkflowBuilder(workflow_name="Test Workflow")
    builder.add_step("navigate", {"url": "https://example.com"})
    builder.add_step("click", {"selector": "#button"})
    return builder


@pytest.mark.asyncio
async def test_run_workflow_success_single_session(orchestrator_instance, sample_workflow, mock_browserbase_client, mock_stagehand_client):
    """Test successful execution of run_workflow with a single session."""
    num_sessions = 1
    session_config = {"userDataDir": "/path/to/data"}

    results = await orchestrator_instance.run_workflow(sample_workflow, num_sessions, session_config)

    # Assertions
    mock_stagehand_client.create_task.assert_awaited_once_with(sample_workflow.build())
    mock_browserbase_client.create_session.assert_awaited_once_with(**session_config)
    mock_stagehand_client.execute_task.assert_awaited_once_with(task_id="sh_task_abc", browser_session_id="bb_session_123")
    mock_browserbase_client.release_session.assert_awaited_once_with("bb_session_123")

    assert len(results) == 1
    assert results[0] == {
        "sessionId": "bb_session_123",
        "stagehandTaskId": "sh_task_abc",
        "stagehandExecutionId": "exec_xyz",
        "status": "running", # Or "success" depending on mock execute_task
        "error": None
    }

    # Check internal session state (optional, depends on visibility/need)
    # assert len(orchestrator_instance.list_active_sessions()) == 0 # Should be released

@pytest.mark.asyncio
async def test_run_workflow_success_multiple_sessions(orchestrator_instance, sample_workflow, mock_browserbase_client, mock_stagehand_client):
    """Test successful execution of run_workflow with multiple sessions."""
    num_sessions = 3
    session_config = {}

    # Mock create_session to return different IDs
    mock_browserbase_client.create_session.side_effect = [
        {"sessionId": "bb_session_1"},
        {"sessionId": "bb_session_2"},
        {"sessionId": "bb_session_3"},
    ]
    # Mock execute_task to return different IDs
    mock_stagehand_client.execute_task.side_effect = [
        {"executionId": "exec_1", "status": "running"},
        {"executionId": "exec_2", "status": "running"},
        {"executionId": "exec_3", "status": "running"},
    ]

    results = await orchestrator_instance.run_workflow(sample_workflow, num_sessions, session_config)

    # Assertions
    mock_stagehand_client.create_task.assert_awaited_once_with(sample_workflow.build())
    assert mock_browserbase_client.create_session.await_count == num_sessions
    assert mock_stagehand_client.execute_task.await_count == num_sessions
    # Check calls to execute_task with specific session IDs
    execute_calls = [
        call(task_id="sh_task_abc", browser_session_id="bb_session_1"),
        call(task_id="sh_task_abc", browser_session_id="bb_session_2"),
        call(task_id="sh_task_abc", browser_session_id="bb_session_3"),
    ]
    mock_stagehand_client.execute_task.assert_has_awaits(execute_calls, any_order=True)

    # Check calls to release_session
    assert mock_browserbase_client.release_session.await_count == num_sessions
    release_calls = [
        call("bb_session_1"),
        call("bb_session_2"),
        call("bb_session_3"),
    ]
    mock_browserbase_client.release_session.assert_has_awaits(release_calls, any_order=True)


    assert len(results) == num_sessions
    expected_results = [
         {'sessionId': 'bb_session_1', 'stagehandTaskId': 'sh_task_abc', 'stagehandExecutionId': 'exec_1', 'status': 'running', 'error': None},
         {'sessionId': 'bb_session_2', 'stagehandTaskId': 'sh_task_abc', 'stagehandExecutionId': 'exec_2', 'status': 'running', 'error': None},
         {'sessionId': 'bb_session_3', 'stagehandTaskId': 'sh_task_abc', 'stagehandExecutionId': 'exec_3', 'status': 'running', 'error': None}
    ]
    # Sort results by sessionId for consistent comparison
    assert sorted(results, key=lambda x: x['sessionId']) == sorted(expected_results, key=lambda x: x['sessionId'])


@pytest.mark.asyncio
async def test_run_workflow_stagehand_task_creation_fails(orchestrator_instance, sample_workflow, mock_stagehand_client, mock_browserbase_client):
    """Test run_workflow when Stagehand task creation fails."""
    mock_stagehand_client.create_task.side_effect = StagehandAPIError("Creation Failed", 500, "Server Error")

    with pytest.raises(TaskCreationError, match="Failed to create Stagehand task: API call to"):
        await orchestrator_instance.run_workflow(sample_workflow, num_sessions=1)

    # Ensure no browser sessions were attempted or released
    mock_browserbase_client.create_session.assert_not_awaited()
    mock_browserbase_client.release_session.assert_not_awaited()

@pytest.mark.asyncio
async def test_run_workflow_browserbase_session_creation_fails_all(orchestrator_instance, sample_workflow, mock_browserbase_client, mock_stagehand_client):
    """Test run_workflow when all Browserbase session creations fail."""
    num_sessions = 2
    mock_browserbase_client.create_session.side_effect = BrowserbaseAPIError("Session Failed", 400, "Bad Config")

    results = await orchestrator_instance.run_workflow(sample_workflow, num_sessions)

    # Assertions
    mock_stagehand_client.create_task.assert_awaited_once() # Task creation should still happen first
    assert mock_browserbase_client.create_session.await_count == num_sessions
    mock_stagehand_client.execute_task.assert_not_awaited() # Execution shouldn't be attempted
    mock_browserbase_client.release_session.assert_not_awaited() # No sessions to release

    assert len(results) == num_sessions
    assert all(r['status'] == "failed_session_creation" for r in results)
    assert all("Session Failed" in r['error'] for r in results)


@pytest.mark.asyncio
async def test_run_workflow_browserbase_session_creation_fails_partial(orchestrator_instance, sample_workflow, mock_browserbase_client, mock_stagehand_client):
    """Test run_workflow when some Browserbase session creations fail."""
    num_sessions = 3
    session_config = {}
    # Simulate one failure and two successes
    mock_browserbase_client.create_session.side_effect = [
        BrowserbaseAPIError("Session Failed 1", 400, "Bad Config"),
        {"sessionId": "bb_session_2"},
        {"sessionId": "bb_session_3"},
    ]
    # Mock execute for the successful sessions
    mock_stagehand_client.execute_task.side_effect = [
        {"executionId": "exec_2", "status": "running"},
        {"executionId": "exec_3", "status": "running"},
    ]


    results = await orchestrator_instance.run_workflow(sample_workflow, num_sessions, session_config)

    # Assertions
    mock_stagehand_client.create_task.assert_awaited_once()
    assert mock_browserbase_client.create_session.await_count == num_sessions
    assert mock_stagehand_client.execute_task.await_count == 2 # Only for successful sessions
    # Check calls to execute_task with specific session IDs
    execute_calls = [
        call(task_id="sh_task_abc", browser_session_id="bb_session_2"),
        call(task_id="sh_task_abc", browser_session_id="bb_session_3"),
    ]
    mock_stagehand_client.execute_task.assert_has_awaits(execute_calls, any_order=True)

    # Check that only the successful sessions were released
    assert mock_browserbase_client.release_session.await_count == 2
    release_calls = [
        call("bb_session_2"),
        call("bb_session_3"),
    ]
    mock_browserbase_client.release_session.assert_has_awaits(release_calls, any_order=True)

    assert len(results) == num_sessions
    # Check specific results
    assert results[0]['status'] == "failed_session_creation"
    assert "Session Failed 1" in results[0]['error']
    assert results[1]['status'] == "running"
    assert results[1]['sessionId'] == "bb_session_2"
    assert results[2]['status'] == "running"
    assert results[2]['sessionId'] == "bb_session_3"

@pytest.mark.asyncio
async def test_run_workflow_stagehand_execution_fails_partial(orchestrator_instance, sample_workflow, mock_browserbase_client, mock_stagehand_client):
    """Test run_workflow when some Stagehand task executions fail."""
    num_sessions = 3
    # Mock session creation success for all
    mock_browserbase_client.create_session.side_effect = [
        {"sessionId": "bb_session_1"},
        {"sessionId": "bb_session_2"},
        {"sessionId": "bb_session_3"},
    ]
    # Mock one execution failure and two successes
    mock_stagehand_client.execute_task.side_effect = [
        StagehandAPIError("Exec Failed 1", 503, "Service Unavailable"),
        {"executionId": "exec_2", "status": "running"},
        {"executionId": "exec_3", "status": "running"},
    ]

    results = await orchestrator_instance.run_workflow(sample_workflow, num_sessions)

    # Assertions
    mock_stagehand_client.create_task.assert_awaited_once()
    assert mock_browserbase_client.create_session.await_count == num_sessions
    assert mock_stagehand_client.execute_task.await_count == num_sessions # Execution attempted for all

    # Check release calls - ALL sessions should be released regardless of exec failure
    assert mock_browserbase_client.release_session.await_count == num_sessions
    release_calls = [
        call("bb_session_1"),
        call("bb_session_2"),
        call("bb_session_3"),
    ]
    mock_browserbase_client.release_session.assert_has_awaits(release_calls, any_order=True)

    assert len(results) == num_sessions
    # Check specific results (order depends on gather, sort for safety)
    results.sort(key=lambda x: x['sessionId'])
    assert results[0]['status'] == "failed_execution"
    assert "Exec Failed 1" in results[0]['error']
    assert results[0]['sessionId'] == "bb_session_1"
    assert results[1]['status'] == "running"
    assert results[1]['sessionId'] == "bb_session_2"
    assert results[2]['status'] == "running"
    assert results[2]['sessionId'] == "bb_session_3"

@pytest.mark.asyncio
async def test_run_workflow_browserbase_release_fails(orchestrator_instance, sample_workflow, mock_browserbase_client, mock_stagehand_client, caplog):
    """Test run_workflow when Browserbase session release fails (should still complete)."""
    num_sessions = 1
    # Mock successful creation and execution
    mock_browserbase_client.create_session.return_value = {"sessionId": "bb_session_fail_release"}
    mock_stagehand_client.execute_task.return_value = {"executionId": "exec_xyz", "status": "success"}
    # Mock release failure
    mock_browserbase_client.release_session.side_effect = BrowserbaseAPIError("Release Failed", 500, "Internal Error")

    # Capture logs
    import logging
    caplog.set_level(logging.ERROR, logger="src.orchestrator")

    # Run the workflow - should not raise an exception here
    results = await orchestrator_instance.run_workflow(sample_workflow, num_sessions)

    # Assertions
    mock_stagehand_client.create_task.assert_awaited_once()
    mock_browserbase_client.create_session.assert_awaited_once()
    mock_stagehand_client.execute_task.assert_awaited_once()
    mock_browserbase_client.release_session.assert_awaited_once_with("bb_session_fail_release") # Release was attempted

    # Check result is still success despite release failure
    assert len(results) == 1
    assert results[0]['status'] == "success"
    assert results[0]['sessionId'] == "bb_session_fail_release"

    # Check logs for the release error
    assert "Failed to release Browserbase session bb_session_fail_release" in caplog.text
    assert "Release Failed" in caplog.text
