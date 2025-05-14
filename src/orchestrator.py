"""Core Orchestration Service"""

import asyncio
import logging
from typing import Optional, Dict, List
from threading import Lock # For potential thread-safe state management
from fastapi import FastAPI
import uvicorn

# Import clients (adjust based on final install structure)
from browserbase_client import BrowserbaseClient, BrowserbaseAPIError
from stagehand_client import StagehandClient, StagehandAPIError, StagehandConfigError, WorkflowBuilder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    logger.info("Health check endpoint called.")
    return {"status": "healthy"}

# --- Custom Exceptions (Moved to Orchestrator scope) ---

class Session:
    """Represents an active browser session managed by the orchestrator."""
    def __init__(self, browserbase_id: str, state: str = "idle", task_id: Optional[str] = None):
        self.browserbase_id: str = browserbase_id
        self.state: str = state # e.g., idle, busy, error
        self.task_id: Optional[str] = task_id # Stagehand task ID currently using this session

    def __repr__(self):
        return f"Session(id={self.browserbase_id}, state={self.state}, task_id={self.task_id})"

class Orchestrator:
    """
    Coordinates Browserbase sessions and Stagehand task execution.
    """
    # --- Custom Exceptions (Defined within Orchestrator) ---
    class OrchestratorError(Exception):
        """Base exception for Orchestrator errors."""
        pass

    class SessionCreationError(OrchestratorError):
        """Error during Browserbase session creation."""
        pass

    class TaskCreationError(OrchestratorError):
        """Error during Stagehand task creation."""
        pass

    class TaskExecutionError(OrchestratorError):
        """Error during Stagehand task execution."""
        pass

    def __init__(self, config=None):
        """Initialize the Orchestrator."""
        self.config = config or {}
        logger.info("Orchestrator initialized.")

    async def close(self):
        """Closes underlying clients gracefully."""
        logger.info("Closing Orchestrator clients...")
        await self.browserbase_client.close()
        await self.stagehand_client.close()
        logger.info("Orchestrator clients closed.")

    # --- Session Management Methods ---

    async def _create_browserbase_session(self, config: Optional[Dict] = None) -> str:
        """Creates a new Browserbase session and tracks it."""
        config = config or {}
        logger.info(f"Attempting to create Browserbase session with config: {config}")
        try:
            response = await self.browserbase_client.create_session(**config)
            session_id = response.get("sessionId") # Assuming response format
            if not session_id:
                 logger.error(f"Browserbase create_session response missing 'sessionId': {response}")
                 raise ValueError("Failed to extract sessionId from Browserbase response")

            logger.info(f"Browserbase session created successfully: {session_id}")
            new_session = Session(browserbase_id=session_id, state="idle")
            with self._session_lock:
                self._active_sessions[session_id] = new_session
            return session_id
        except BrowserbaseAPIError as e:
            logger.error(f"Failed to create Browserbase session: {e}")
            # Decide how to handle: raise specific Orchestrator error? Return None?
            raise # Re-raise for now
        except Exception as e:
            logger.exception(f"Unexpected error creating Browserbase session: {e}")
            raise # Re-raise unexpected errors

    async def _release_browserbase_session(self, session_id: str) -> bool:
        """Releases a Browserbase session and removes it from tracking."""
        logger.info(f"Attempting to release Browserbase session: {session_id}")
        if session_id not in self._active_sessions:
             logger.warning(f"Attempted to release untracked session: {session_id}")
             # Optionally try to release anyway if it might exist in Browserbase
             # return False # Or raise error?

        try:
            await self.browserbase_client.release_session(session_id)
            logger.info(f"Browserbase session released successfully: {session_id}")
            with self._session_lock:
                if session_id in self._active_sessions:
                    del self._active_sessions[session_id]
            return True
        except BrowserbaseAPIError as e:
            logger.error(f"Failed to release Browserbase session {session_id}: {e}")
            # Maybe remove from tracking anyway if release failed?
            with self._session_lock:
                if session_id in self._active_sessions:
                    # Mark as error or remove? Mark as error for potential retry/cleanup.
                    self._active_sessions[session_id].state = "error"
                    logger.warning(f"Marked session {session_id} as error due to release failure.")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error releasing Browserbase session {session_id}: {e}")
            # Mark as error?
            with self._session_lock:
                 if session_id in self._active_sessions:
                     self._active_sessions[session_id].state = "error"
            return False

    def get_session_info(self, session_id: str) -> Optional[Session]:
         """Get information about a tracked session."""
         with self._session_lock:
             return self._active_sessions.get(session_id)

    def list_active_sessions(self) -> List[Session]:
        """List all currently tracked active sessions."""
        with self._session_lock:
            return list(self._active_sessions.values())

    # --- Task Execution Methods ---

    async def run_workflow(self, workflow: WorkflowBuilder, num_sessions: int = 1, session_config: Optional[Dict] = None):
        """
        Runs a defined Stagehand workflow across one or more Browserbase sessions.

        Args:
            workflow: A Stagehand WorkflowBuilder instance defining the interaction.
            num_sessions: The number of parallel Browserbase sessions to use.
            session_config: Optional configuration for Browserbase session creation.

        Returns:
            A list of results, one for each session execution attempt. Each result is a dict
            containing 'sessionId', 'stagehandTaskId', 'stagehandExecutionId', 'status', and 'error' (if any).

        Raises:
            TaskCreationError: If the Stagehand task cannot be created.
            OrchestratorError: For other orchestration-level issues.
        """
        logger.info(f"Running workflow '{workflow.workflow_name}' across {num_sessions} sessions.")
        session_config = session_config or {}
        stagehand_task_id = None
        browserbase_sessions_created = [] # Keep track of ALL sessions attempted to be created for release
        execution_results = []
        main_exception = None # Track the primary exception if one occurs

        try:
            # 1. Create Stagehand Task
            logger.info(f"Creating Stagehand task for workflow: {workflow.workflow_name}")
            try:
                task_response = await self.stagehand_client.create_task(workflow.build())
                stagehand_task_id = task_response.get("taskId")
                if not stagehand_task_id:
                    # Use the specific Orchestrator exception
                    raise self.TaskCreationError(f"Stagehand create_task response missing 'taskId': {task_response}")
                logger.info(f"Stagehand task created successfully: {stagehand_task_id}")
            except StagehandAPIError as e:
                logger.error(f"Failed to create Stagehand task due to API error: {e}")
                raise self.TaskCreationError(f"Failed to create Stagehand task: {e}") from e
            except Exception as e:
                 logger.exception(f"Unexpected error creating Stagehand task: {e}")
                 # Use the specific Orchestrator exception
                 raise self.TaskCreationError(f"Unexpected error creating Stagehand task: {e}") from e


            # 2. Provision Browserbase Sessions Concurrently
            logger.info(f"Provisioning {num_sessions} Browserbase sessions...")
            session_creation_tasks = [
                self._create_browserbase_session(session_config) for _ in range(num_sessions)
            ]
            # Use return_exceptions=True to capture all outcomes
            session_results = await asyncio.gather(*session_creation_tasks, return_exceptions=True)

            successful_session_ids = []
            # Process results immediately to track created sessions for cleanup
            for i, result in enumerate(session_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to create Browserbase session {i+1}/{num_sessions}: {result}")
                    execution_results.append({
                        "sessionId": None,
                        "stagehandTaskId": stagehand_task_id,
                        "stagehandExecutionId": None,
                        "status": "failed_session_creation",
                        "error": str(result)
                    })
                else:
                    session_id = result
                    successful_session_ids.append(session_id)
                    browserbase_sessions_created.append(session_id) # Track successfully created sessions
                    session_info = self.get_session_info(session_id)
                    if session_info: # Should always exist if creation succeeded
                         session_info.state = "busy"
                         session_info.task_id = stagehand_task_id
                    else:
                         # This case should theoretically not happen if _create_browserbase_session is correct
                         logger.error(f"Session {session_id} created but not found in tracker!")

            if not successful_session_ids:
                 logger.warning("No Browserbase sessions were created successfully. Aborting workflow execution.")
                 # No sessions to execute on, skip to finally block for cleanup
                 # Return the collected session creation errors
                 return execution_results

            logger.info(f"Successfully provisioned {len(successful_session_ids)}/{num_sessions} Browserbase sessions.")

            # 3. Execute Stagehand Task on Successfully Created Sessions Concurrently
            logger.info(f"Executing Stagehand task {stagehand_task_id} on {len(successful_session_ids)} sessions...")
            execution_tasks = [
                self.stagehand_client.execute_task(task_id=stagehand_task_id, browser_session_id=session_id)
                for session_id in successful_session_ids
            ]
            # Use return_exceptions=True
            task_execution_outputs = await asyncio.gather(*execution_tasks, return_exceptions=True)

            # 4. Collect and Process Execution Results
            logger.info(f"Processing execution results for {len(successful_session_ids)} sessions...")
            for i, output in enumerate(task_execution_outputs):
                session_id = successful_session_ids[i]
                session_info = self.get_session_info(session_id)
                result_entry = {
                    "sessionId": session_id,
                    "stagehandTaskId": stagehand_task_id,
                    "stagehandExecutionId": None,
                    "status": "unknown", # Default status
                    "error": None
                }
                if isinstance(output, Exception):
                    logger.error(f"Stagehand task execution failed for session {session_id}: {output}")
                    result_entry["status"] = "failed_execution"
                    result_entry["error"] = str(output)
                    if session_info: session_info.state = "error"
                else:
                    # Assuming success response format
                    execution_id = output.get("executionId")
                    status = output.get("status", "success") # Assume success if status missing but no exception
                    logger.info(f"Stagehand task execution completed for session {session_id}. Execution ID: {execution_id}, Status: {status}")
                    result_entry["stagehandExecutionId"] = execution_id
                    result_entry["status"] = status
                    # Mark as idle after successful execution, ready for release
                    if session_info: session_info.state = "idle"

                execution_results.append(result_entry)

            logger.info("Finished processing all task executions for successfully created sessions.")
            return execution_results

        except (self.TaskCreationError, self.SessionCreationError, self.TaskExecutionError, self.OrchestratorError) as e:
            # Catch known Orchestrator errors
            logger.error(f"Orchestration failed: {e}", exc_info=True)
            main_exception = e # Store the primary exception
            # Depending on where the error occurred, execution_results might already contain partial data
            # Ensure the final return reflects the overall failure state if needed.
            # For now, we let the finally block handle cleanup and re-raise the caught exception.
            raise
        except Exception as e:
            # Catch any other unexpected errors during orchestration
            logger.exception(f"Unexpected error during workflow execution: {e}")
            main_exception = e # Store the primary exception
            # Wrap in a generic OrchestratorError before re-raising
            raise self.OrchestratorError(f"Unexpected orchestration error: {e}") from e

        finally:
            # 5. Release ALL successfully created Browserbase Sessions, regardless of execution outcome
            if browserbase_sessions_created:
                logger.info(f"Ensuring release of {len(browserbase_sessions_created)} created Browserbase sessions...")
                release_tasks = [self._release_browserbase_session(sid) for sid in browserbase_sessions_created]
                release_results = await asyncio.gather(*release_tasks, return_exceptions=True)
                release_errors = []
                for i, res in enumerate(release_results):
                    session_id_to_release = browserbase_sessions_created[i]
                    if isinstance(res, Exception) or not res:
                        # Log release failure but don't let it mask the main execution error
                        error_msg = f"Failed to release Browserbase session {session_id_to_release}: {res}"
                        logger.error(error_msg)
                        release_errors.append(error_msg)
                    else:
                         logger.info(f"Successfully released session {session_id_to_release}.")
                
                if release_errors and main_exception:
                     # If there was a main error AND release errors, log the release errors clearly
                     logger.error(f"Additionally, errors occurred during session release: {'; '.join(release_errors)}")
                elif release_errors and not main_exception:
                     # If the main execution succeeded but release failed, maybe raise an error?
                     # For now, just logging is likely sufficient.
                     logger.warning("Workflow execution succeeded, but errors occurred during session release.")

    def start_api_server(self, host: str = "0.0.0.0", port: int = 8000):
        """Starts the FastAPI server for the Orchestrator's API (e.g., health check)."""
        logger.info(f"Starting Orchestrator API server on {host}:{port}")
        uvicorn.run(app, host=host, port=port)

# Example usage (if run directly, for testing)
async def main():
    # Load secrets from .env (requires python-dotenv)
    # from dotenv import load_dotenv
    # load_dotenv()
    # bb_key = os.getenv("BROWSERBASE_API_KEY")
    # sh_key = os.getenv("STAGEHAND_API_KEY")

    # For testing without .env:
    bb_key = "dummy_bb_key" # Replace with actual if testing live
    sh_key = "dummy_sh_key" # Replace with actual if testing live

    if not bb_key or not sh_key:
        print("API keys not found. Set BROWSERBASE_API_KEY and STAGEHAND_API_KEY env vars or provide directly.")
        return

    orchestrator = Orchestrator(
        browserbase_api_key=bb_key,
        stagehand_api_key=sh_key
    )

    try:
        print("Attempting to create a session...")
        session_id = await orchestrator._create_browserbase_session()
        print(f"Session created: {session_id}")

        print("Active sessions:", orchestrator.list_active_sessions())
        info = orchestrator.get_session_info(session_id)
        print("Session info:", info)

        print("Attempting to release the session...")
        released = await orchestrator._release_browserbase_session(session_id)
        print(f"Session released: {released}")
        print("Active sessions after release:", orchestrator.list_active_sessions())

    except (BrowserbaseAPIError, StagehandAPIError, BrowserbaseConfigError, StagehandConfigError) as e:
        print(f"API or Config Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        await orchestrator.close()

if __name__ == "__main__":
    # Note: Running __main__ requires mocking or actual API keys
    # asyncio.run(main())
    print("Orchestrator module loaded. Run main() with appropriate keys/mocks for testing.")
    # This is primarily for standalone testing of the API server.
    # In a real deployment, a process manager (like gunicorn with uvicorn workers) would be used.
    print("Starting Orchestrator API server directly...")
    # In a real scenario, you might instantiate Orchestrator and then call start_api_server
    # For now, just running the app directly for the health check endpoint.
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info") 