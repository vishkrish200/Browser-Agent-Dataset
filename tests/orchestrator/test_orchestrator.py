# Tests for the Orchestrator service will go here. 

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, call
import asyncio
import logging

from src.orchestrator import Orchestrator
from src.stagehand_client import StagehandAPIError
from src.browserbase_client import BrowserbaseAPIError

# Assuming 'app' is the FastAPI instance in orchestrator.py for health check test
# If it's not directly exposed or needed for Orchestrator tests, this could be cleaner.
from src.orchestrator import app

@pytest.fixture
def client(test_client_app):
    """Override the existing client fixture if it was based on TestClient(app) directly"""
    # This fixture might need to be adjusted or removed if 'app' is only for health_check
    # For Orchestrator tests, we usually use orchestrator_instance fixture directly.
    # If you still need a TestClient for the FastAPI app part:
    with TestClient(test_client_app) as c:
        yield c

@pytest.fixture
def test_client_app():
    """Provides the FastAPI app instance for TestClient."""
    return app

def test_health_check(client: TestClient):
    """Test the /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

@pytest.mark.asyncio
async def test_run_workflow_success_single_session(
    orchestrator_instance: Orchestrator, 
    mock_browserbase_client: AsyncMock, 
    mock_stagehand_client: AsyncMock, 
    sample_workflow_builder,
    sample_project_id
):
    """Test run_workflow successful execution with a single session."""
    num_sessions = 1
    workflow = sample_workflow_builder
    bb_project_id_for_run = sample_project_id

    mock_stagehand_client.create_task.return_value = {"taskId": "task_single_success"}
    mock_browserbase_client.create_session.return_value = {"sessionId": "sess_single_success_1"}
    mock_stagehand_client.execute_task.return_value = {"executionId": "exec_single_success_1", "status": "completed", "data": "some_result"}
    mock_browserbase_client.release_session.return_value = True

    results = await orchestrator_instance.run_workflow(
        workflow=workflow, 
        num_sessions=num_sessions,
        browserbase_project_id=bb_project_id_for_run
    )

    assert len(results) == num_sessions
    result = results[0]
    assert result["status"] == "completed"
    assert result["sessionId"] == "sess_single_success_1"
    assert result["stagehandTaskId"] == "task_single_success"
    assert result["stagehandExecutionId"] == "exec_single_success_1"
    assert result["error"] is None

    mock_stagehand_client.create_task.assert_called_once_with(workflow.build())
    mock_browserbase_client.create_session.assert_called_once_with(project_id=bb_project_id_for_run, **{})
    mock_stagehand_client.execute_task.assert_called_once_with(task_id="task_single_success", browser_session_id="sess_single_success_1")
    mock_browserbase_client.release_session.assert_called_once_with(session_id="sess_single_success_1", project_id=bb_project_id_for_run)

@pytest.mark.asyncio
async def test_run_workflow_success_multiple_sessions(
    orchestrator_instance: Orchestrator, 
    mock_browserbase_client: AsyncMock, 
    mock_stagehand_client: AsyncMock, 
    sample_workflow_builder,
    sample_project_id
):
    """Test run_workflow successful execution with multiple sessions."""
    num_sessions = 3
    workflow = sample_workflow_builder
    bb_project_id_for_run = sample_project_id

    mock_stagehand_client.create_task.return_value = {"taskId": "task_multi_success"}
    
    mock_browserbase_client.create_session.side_effect = [
        {"sessionId": f"sess_multi_success_{i+1}"} for i in range(num_sessions)
    ]
    mock_stagehand_client.execute_task.side_effect = [
        {"executionId": f"exec_multi_success_{i+1}", "status": "completed", "data": f"result_{i+1}"} for i in range(num_sessions)
    ]
    mock_browserbase_client.release_session.return_value = True

    results = await orchestrator_instance.run_workflow(
        workflow=workflow, 
        num_sessions=num_sessions,
        browserbase_project_id=bb_project_id_for_run
    )

    assert len(results) == num_sessions
    for i, result in enumerate(results):
        expected_session_id = f"sess_multi_success_{i+1}"
        expected_exec_id = f"exec_multi_success_{i+1}"
        assert result["status"] == "completed"
        assert result["sessionId"] == expected_session_id
        assert result["stagehandTaskId"] == "task_multi_success"
        assert result["stagehandExecutionId"] == expected_exec_id
        assert result["error"] is None

    mock_stagehand_client.create_task.assert_called_once_with(workflow.build())
    assert mock_browserbase_client.create_session.call_count == num_sessions
    for i in range(num_sessions):
        assert mock_browserbase_client.create_session.call_args_list[i] == call(project_id=bb_project_id_for_run, **{})
    
    assert mock_stagehand_client.execute_task.call_count == num_sessions
    for i in range(num_sessions):
        assert mock_stagehand_client.execute_task.call_args_list[i] == call(task_id="task_multi_success", browser_session_id=f"sess_multi_success_{i+1}")

    assert mock_browserbase_client.release_session.call_count == num_sessions
    for i in range(num_sessions):
         assert mock_browserbase_client.release_session.call_args_list[i] == call(session_id=f"sess_multi_success_{i+1}", project_id=bb_project_id_for_run)

@pytest.mark.asyncio
async def test_run_workflow_stagehand_task_creation_failure(
    orchestrator_instance: Orchestrator, 
    mock_browserbase_client: AsyncMock, 
    mock_stagehand_client: AsyncMock, 
    sample_workflow_builder,
    sample_project_id
):
    """Test run_workflow when Stagehand task creation fails."""
    workflow = sample_workflow_builder
    bb_project_id_for_run = sample_project_id

    mock_stagehand_client.create_task.side_effect = StagehandAPIError("Failed to create task", status_code=500)

    with pytest.raises(Orchestrator.TaskCreationError) as excinfo:
        await orchestrator_instance.run_workflow(
            workflow=workflow, 
            num_sessions=1,
            browserbase_project_id=bb_project_id_for_run
        )
    
    assert "Unexpected error creating Stagehand task" in str(excinfo.value)
    mock_browserbase_client.create_session.assert_not_called()
    mock_browserbase_client.release_session.assert_not_called()
    mock_stagehand_client.execute_task.assert_not_called()

@pytest.mark.asyncio
async def test_run_workflow_all_browserbase_sessions_fail(
    orchestrator_instance: Orchestrator, 
    mock_browserbase_client: AsyncMock, 
    mock_stagehand_client: AsyncMock, 
    sample_workflow_builder,
    sample_project_id
):
    """Test run_workflow when all Browserbase session creations fail."""
    num_sessions = 2
    workflow = sample_workflow_builder
    bb_project_id_for_run = sample_project_id

    mock_stagehand_client.create_task.return_value = {"taskId": "task_all_bb_fail"}
    mock_browserbase_client.create_session.side_effect = BrowserbaseAPIError("Session creation failed", status_code=503)

    results = await orchestrator_instance.run_workflow(
        workflow=workflow, 
        num_sessions=num_sessions,
        browserbase_project_id=bb_project_id_for_run
    )

    assert len(results) == num_sessions
    for result in results:
        assert result["status"] == "failed_session_creation"
        assert result["sessionId"] is None
        assert result["stagehandTaskId"] == "task_all_bb_fail"
        assert "Unexpected error creating Browserbase session" in result["error"]

    mock_stagehand_client.create_task.assert_called_once()
    assert mock_browserbase_client.create_session.call_count == num_sessions
    mock_stagehand_client.execute_task.assert_not_called()
    # Release shouldn't be called if no sessions were successfully created
    mock_browserbase_client.release_session.assert_not_called()

@pytest.mark.asyncio
async def test_run_workflow_partial_browserbase_session_failure(
    orchestrator_instance: Orchestrator, 
    mock_browserbase_client: AsyncMock, 
    mock_stagehand_client: AsyncMock, 
    sample_workflow_builder,
    sample_project_id
):
    """Test run_workflow with partial Browserbase session creation failure."""
    num_sessions = 3
    workflow = sample_workflow_builder
    bb_project_id_for_run = sample_project_id

    mock_stagehand_client.create_task.return_value = {"taskId": "task_partial_bb_fail"}
    
    # First session succeeds, second fails, third succeeds
    mock_browserbase_client.create_session.side_effect = [
        {"sessionId": "sess_partial_1"},
        BrowserbaseAPIError("Session 2 creation failed", status_code=500),
        {"sessionId": "sess_partial_3"}
    ]
    # execute_task should only be called for successful sessions
    mock_stagehand_client.execute_task.side_effect = [
        {"executionId": "exec_partial_1", "status": "completed"}, # For sess_partial_1
        {"executionId": "exec_partial_3", "status": "completed"}  # For sess_partial_3
    ]
    mock_browserbase_client.release_session.return_value = True

    results = await orchestrator_instance.run_workflow(
        workflow=workflow, 
        num_sessions=num_sessions,
        browserbase_project_id=bb_project_id_for_run
    )

    assert len(results) == num_sessions
    
    successful_results = [r for r in results if r["status"] == "completed"]
    failed_session_creation_results = [r for r in results if r["status"] == "failed_session_creation"]

    assert len(successful_results) == 2
    assert len(failed_session_creation_results) == 1

    # Check the failed one
    assert "Unexpected error creating Browserbase session" in failed_session_creation_results[0]["error"]
    assert failed_session_creation_results[0]["sessionId"] is None

    # Check successful ones - order might not be guaranteed by gather, so check for presence
    expected_success_details = [
        {"sessionId": "sess_partial_1", "executionId": "exec_partial_1"},
        {"sessionId": "sess_partial_3", "executionId": "exec_partial_3"}
    ]

    for expected in expected_success_details:
        found = False
        for res in successful_results:
            if res["sessionId"] == expected["sessionId"] and res["stagehandExecutionId"] == expected["executionId"]:
                assert res["stagehandTaskId"] == "task_partial_bb_fail"
                assert res["error"] is None
                found = True
                break
        assert found, f"Expected successful result for {expected} not found"

    mock_stagehand_client.create_task.assert_called_once()
    assert mock_browserbase_client.create_session.call_count == num_sessions
    assert mock_stagehand_client.execute_task.call_count == 2 # Only for successful sessions
    mock_stagehand_client.execute_task.assert_any_call(task_id="task_partial_bb_fail", browser_session_id="sess_partial_1")
    mock_stagehand_client.execute_task.assert_any_call(task_id="task_partial_bb_fail", browser_session_id="sess_partial_3")
    
    assert mock_browserbase_client.release_session.call_count == 2 # Only successful sessions are released
    mock_browserbase_client.release_session.assert_any_call(session_id="sess_partial_1", project_id=bb_project_id_for_run)
    mock_browserbase_client.release_session.assert_any_call(session_id="sess_partial_3", project_id=bb_project_id_for_run)

@pytest.mark.asyncio
async def test_run_workflow_stagehand_execution_failure(
    orchestrator_instance: Orchestrator, 
    mock_browserbase_client: AsyncMock, 
    mock_stagehand_client: AsyncMock, 
    sample_workflow_builder,
    sample_project_id,
    caplog # For checking logs
):
    """Test run_workflow when Stagehand task execution fails for some sessions."""
    num_sessions = 2
    workflow = sample_workflow_builder
    bb_project_id_for_run = sample_project_id

    mock_stagehand_client.create_task.return_value = {"taskId": "task_sh_exec_fail"}
    mock_browserbase_client.create_session.side_effect = [
        {"sessionId": "sess_exec_fail_1"},
        {"sessionId": "sess_exec_fail_2"}
    ]
    # First execution succeeds, second fails
    mock_stagehand_client.execute_task.side_effect = [
        {"executionId": "exec_succ_1", "status": "completed"},
        StagehandAPIError("Execution failed on session 2", status_code=500)
    ]
    mock_browserbase_client.release_session.return_value = True

    results = await orchestrator_instance.run_workflow(
        workflow=workflow, 
        num_sessions=num_sessions,
        browserbase_project_id=bb_project_id_for_run
    )

    assert len(results) == num_sessions

    # Session 1 (success)
    assert results[0]["sessionId"] == "sess_exec_fail_1"
    assert results[0]["status"] == "completed"
    assert results[0]["stagehandExecutionId"] == "exec_succ_1"
    assert results[0]["error"] is None

    # Session 2 (failure)
    assert results[1]["sessionId"] == "sess_exec_fail_2"
    assert results[1]["status"] == "failed_execution"
    assert "Execution failed on session 2" in results[1]["error"]
    assert results[1]["stagehandExecutionId"] is None
    
    assert mock_browserbase_client.release_session.call_count == num_sessions # Both should be released

@pytest.mark.asyncio
async def test_run_workflow_browserbase_release_failure(
    orchestrator_instance: Orchestrator, 
    mock_browserbase_client: AsyncMock, 
    mock_stagehand_client: AsyncMock, 
    sample_workflow_builder,
    sample_project_id,
    caplog # To check log messages
):
    """Test run_workflow when Browserbase session release fails."""
    num_sessions = 1
    workflow = sample_workflow_builder
    bb_project_id_for_run = sample_project_id

    mock_stagehand_client.create_task.return_value = {"taskId": "task_bb_release_fail"}
    mock_browserbase_client.create_session.return_value = {"sessionId": "sess_release_fail_1"}
    mock_stagehand_client.execute_task.return_value = {"executionId": "exec_release_fail_1", "status": "completed"}
    # Simulate release failure
    mock_browserbase_client.release_session.side_effect = BrowserbaseAPIError("Release failed", status_code=500)

    with caplog.at_level(logging.WARNING):
        results = await orchestrator_instance.run_workflow(
            workflow=workflow, 
            num_sessions=num_sessions,
            browserbase_project_id=bb_project_id_for_run
        )

    assert len(results) == num_sessions
    # Main execution should still be successful
    assert results[0]["status"] == "completed"
    assert results[0]["error"] is None 

    # Check that the release failure was logged as an ERROR initially from _release_browserbase_session
    assert any(
        "Unexpected error releasing Browserbase session" in record.message and # Corrected message check
        record.levelname == "ERROR" and 
        "release_browserbase_session" in getattr(record, 'action', '') # Check our custom action field
        for record in caplog.records
    )
    # Also check for the summary warning if main execution was okay but release failed
    assert any(
        "error(s) occurred during session release" in record.message and # Corrected for "error(s)"
        record.levelname == "WARNING" and 
        "run_workflow" in getattr(record, 'action', '') # Check our custom action field
        for record in caplog.records
    )

    # Ensure release was attempted
    mock_browserbase_client.release_session.assert_called_once_with(session_id="sess_release_fail_1", project_id=bb_project_id_for_run)

# TODO: Add test for case where final_bb_project_id is missing in run_workflow
# @pytest.mark.asyncio
# async def test_run_workflow_missing_project_id(...):
#     ...
#     with pytest.raises(Orchestrator.OrchestratorError, match="Browserbase Project ID is required"):
#         await orchestrator_instance.run_workflow(...) 