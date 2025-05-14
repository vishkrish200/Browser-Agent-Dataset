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
# Basic config is set here, can be overridden by applications importing this module
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - Action: %(action)s - %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S%z' 
)
# Create a logger instance for this module.
# For structured logging, we'll often pass `extra` to logger calls.
logger = logging.getLogger(__name__)

# Default extra values for logs, can be overridden in logger calls
DEFAULT_LOG_EXTRA = {"action": "unknown"}

app = FastAPI()

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    logger.info("Health check endpoint called.", extra={"action": "health_check_invoked"})
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

    def __init__(self, config: Optional[Dict] = None, browserbase_client: Optional[BrowserbaseClient] = None, stagehand_client: Optional[StagehandClient] = None):
        """
        Initialize the Orchestrator.
        Accepts optional pre-configured client instances for better testability and flexibility.
        """
        self.config = config or {}
        log_extra = {**DEFAULT_LOG_EXTRA, "action": "orchestrator_init"}
        
        if browserbase_client:
            self.browserbase_client = browserbase_client
            logger.info("Orchestrator initialized with pre-configured BrowserbaseClient.", extra=log_extra)
        else:
            # Attempt to get API key from config or fall back to client's default (env var)
            bb_api_key = self.config.get("browserbase_api_key")
            self.browserbase_client = BrowserbaseClient(api_key=bb_api_key)
            logger.info(f"Orchestrator initialized. BrowserbaseClient created. API key source: {'config' if bb_api_key else 'env/default'}.", extra=log_extra)

        if stagehand_client:
            self.stagehand_client = stagehand_client
            logger.info("Orchestrator initialized with pre-configured StagehandClient.", extra=log_extra)
        else:
            sh_api_key = self.config.get("stagehand_api_key")
            self.stagehand_client = StagehandClient(api_key=sh_api_key) # Assuming StagehandClient takes api_key
            logger.info(f"Orchestrator initialized. StagehandClient created. API key source: {'config' if sh_api_key else 'env/default'}.", extra=log_extra)

        self._active_sessions: Dict[str, Session] = {}
        self._session_lock = Lock()
        logger.info("Orchestrator fully initialized.", extra=log_extra)


    async def close(self):
        """Closes underlying clients gracefully."""
        log_extra = {**DEFAULT_LOG_EXTRA, "action": "orchestrator_close"}
        logger.info("Closing Orchestrator clients...", extra=log_extra)
        try:
            if hasattr(self.browserbase_client, 'close') and asyncio.iscoroutinefunction(self.browserbase_client.close):
                await self.browserbase_client.close()
            logger.info("BrowserbaseClient closed (if applicable).", extra=log_extra)
        except Exception as e:
            logger.exception("Error closing BrowserbaseClient.", extra={**log_extra, "error": str(e)})
        
        try:
            if hasattr(self.stagehand_client, 'close') and asyncio.iscoroutinefunction(self.stagehand_client.close):
                 await self.stagehand_client.close()
            logger.info("StagehandClient closed (if applicable).", extra=log_extra)
        except Exception as e:
            logger.exception("Error closing StagehandClient.", extra={**log_extra, "error": str(e)})
        
        logger.info("Orchestrator clients closed procedure completed.", extra=log_extra)

    # --- Session Management Methods ---

    async def _create_browserbase_session(self, project_id: Optional[str] = None, session_params: Optional[Dict] = None) -> str:
        """
        Creates a new Browserbase session and tracks it.
        Args:
            project_id: The project ID for Browserbase. Defaults to config or None.
            session_params: Additional parameters for session creation.
        """
        session_params = session_params or {}
        # Prefer project_id from argument, then config, then client's internal default if any
        final_project_id = project_id or self.config.get("browserbase_project_id")
        
        log_extra = {
            **DEFAULT_LOG_EXTRA, 
            "action": "create_browserbase_session", 
            "project_id": final_project_id,
            "session_params": session_params
        }
        logger.info(f"Attempting to create Browserbase session.", extra=log_extra)
        
        if not final_project_id:
            logger.error("Cannot create Browserbase session: project_id is missing.", extra=log_extra)
            raise self.SessionCreationError("Browserbase project_id is required to create a session.")

        try:
            # Pass project_id directly to create_session if it expects it, or include in session_params
            # Based on browserbase_client.py, it expects project_id as first arg, then **kwargs
            response = await self.browserbase_client.create_session(project_id=final_project_id, **session_params)
            session_id = response.get("sessionId")
            
            if not session_id:
                 logger.error(f"Browserbase create_session response missing 'sessionId'. Response: {response}", extra=log_extra)
                 raise self.SessionCreationError(f"Failed to extract sessionId from Browserbase response: {response}")

            new_session = Session(browserbase_id=session_id, state="idle")
            with self._session_lock:
                self._active_sessions[session_id] = new_session
            logger.info(f"Browserbase session created successfully.", extra={**log_extra, "session_id": session_id, "status": "success"})
            return session_id
        except BrowserbaseAPIError as e:
            logger.error(f"Failed to create Browserbase session due to API error.", exc_info=True, extra={**log_extra, "error": str(e), "status_code": e.status_code, "status": "failed_api_error"})
            raise self.SessionCreationError(f"API error creating Browserbase session: {e}") from e
        except Exception as e:
            logger.exception(f"Unexpected error creating Browserbase session.", extra={**log_extra, "error": str(e), "status": "failed_unexpected_error"})
            raise self.SessionCreationError(f"Unexpected error creating Browserbase session: {e}") from e

    async def _release_browserbase_session(self, session_id: str, project_id: Optional[str] = None) -> bool:
        """
        Releases a Browserbase session and removes it from tracking.
        Args:
            session_id: The ID of the session to release.
            project_id: The project ID for Browserbase. Defaults to config or None.
        """
        final_project_id = project_id or self.config.get("browserbase_project_id")
        log_extra = {
            **DEFAULT_LOG_EXTRA,
            "action": "release_browserbase_session", 
            "session_id": session_id,
            "project_id": final_project_id
        }

        if not final_project_id:
            logger.error("Cannot release Browserbase session: project_id is missing.", extra=log_extra)
            # Don't raise if we're trying to clean up, but log error.
            # If session is tracked, mark as error locally.
            with self._session_lock:
                if session_id in self._active_sessions:
                    self._active_sessions[session_id].state = "error_release_failed_no_project_id"
            return False

        logger.info(f"Attempting to release Browserbase session.", extra=log_extra)
        
        session_exists_locally = False
        with self._session_lock:
            if session_id in self._active_sessions:
                session_exists_locally = True
            else:
                logger.warning(f"Attempted to release untracked or already removed session.", extra=log_extra)
                # Proceed with release attempt as it might exist in Browserbase

        try:
            # Assuming release_session needs project_id.
            await self.browserbase_client.release_session(session_id=session_id, project_id=final_project_id)
            logger.info(f"Browserbase session released successfully via API.", extra={**log_extra, "status": "success_api"})
            
            with self._session_lock:
                if session_id in self._active_sessions:
                    del self._active_sessions[session_id]
                    logger.info(f"Session removed from active tracking.", extra={**log_extra, "status": "success_local_removed"})
            return True
        except BrowserbaseAPIError as e:
            logger.error(f"Failed to release Browserbase session due to API error.", exc_info=True, extra={**log_extra, "error": str(e), "status_code": e.status_code, "status": "failed_api_error"})
            with self._session_lock:
                if session_id in self._active_sessions:
                    self._active_sessions[session_id].state = "error_release_api_failed"
                    logger.warning(f"Marked session as error due to API release failure.", extra=log_extra)
            return False
        except Exception as e:
            logger.exception(f"Unexpected error releasing Browserbase session.", extra={**log_extra, "error": str(e), "status": "failed_unexpected_error"})
            with self._session_lock:
                 if session_id in self._active_sessions:
                     self._active_sessions[session_id].state = "error_release_unexpected"
                     logger.warning(f"Marked session as error due to unexpected release failure.", extra=log_extra)
            return False

    def get_session_info(self, session_id: str) -> Optional[Session]:
         """Get information about a tracked session."""
         log_extra = {**DEFAULT_LOG_EXTRA, "action": "get_session_info", "session_id": session_id}
         with self._session_lock:
             session = self._active_sessions.get(session_id)
             if session:
                 logger.debug(f"Session info retrieved.", extra=log_extra)
             else:
                 logger.debug(f"Session not found in active tracking.", extra=log_extra)
             return session

    def list_active_sessions(self) -> List[Session]:
        """List all currently tracked active sessions."""
        log_extra = {**DEFAULT_LOG_EXTRA, "action": "list_active_sessions"}
        with self._session_lock:
            sessions = list(self._active_sessions.values())
            logger.debug(f"Listed {len(sessions)} active sessions.", extra=log_extra)
            return sessions

    # --- Task Execution Methods ---

    async def run_workflow(
        self, 
        workflow: WorkflowBuilder, 
        num_sessions: int = 1, 
        browserbase_project_id: Optional[str] = None,
        browserbase_session_params: Optional[Dict] = None
    ):
        """
        Runs a defined Stagehand workflow across one or more Browserbase sessions.

        Args:
            workflow: A Stagehand WorkflowBuilder instance defining the interaction.
            num_sessions: The number of parallel Browserbase sessions to use.
            browserbase_project_id: Project ID for Browserbase sessions. Overrides orchestrator config.
            browserbase_session_params: Optional configuration for Browserbase session creation.

        Returns:
            A list of results, one for each session execution attempt. Each result is a dict
            containing 'sessionId', 'stagehandTaskId', 'stagehandExecutionId', 'status', and 'error' (if any).
        """
        workflow_name = workflow.workflow_name if hasattr(workflow, 'workflow_name') else "UnnamedWorkflow"
        log_extra_base = {
            **DEFAULT_LOG_EXTRA, 
            "action": "run_workflow", 
            "workflow_name": workflow_name,
            "num_requested_sessions": num_sessions,
            "browserbase_project_id_arg": browserbase_project_id,
            "browserbase_session_params": browserbase_session_params
        }
        logger.info(f"Attempting to run workflow.", extra=log_extra_base)

        # Determine project_id for Browserbase session creation/release
        final_bb_project_id = browserbase_project_id or self.config.get("browserbase_project_id")
        if not final_bb_project_id:
            logger.critical("Workflow execution failed: Browserbase Project ID not provided or configured.", extra={**log_extra_base, "status": "failed_missing_project_id"})
            raise self.OrchestratorError("Browserbase Project ID is required for run_workflow.")

        stagehand_task_id = None
        browserbase_sessions_created_ids = [] 
        execution_results = []
        main_exception = None

        try:
            # 1. Create Stagehand Task
            log_st_create = {**log_extra_base, "sub_action": "create_stagehand_task"}
            logger.info(f"Creating Stagehand task.", extra=log_st_create)
            try:
                task_payload = workflow.build() # Assuming this returns the dict payload for Stagehand
                task_response = await self.stagehand_client.create_task(task_payload) # Assuming create_task takes dict
                stagehand_task_id = task_response.get("taskId")
                if not stagehand_task_id:
                    logger.error(f"Stagehand create_task response missing 'taskId'. Response: {task_response}", extra=log_st_create)
                    raise self.TaskCreationError(f"Stagehand create_task response missing 'taskId': {task_response}")
                logger.info(f"Stagehand task created successfully.", extra={**log_st_create, "stagehand_task_id": stagehand_task_id, "status": "success"})
            except StagehandAPIError as e:
                logger.error(f"Failed to create Stagehand task due to API error.", exc_info=True, extra={**log_st_create, "error": str(e), "status_code": e.status_code, "status": "failed_api_error"})
                raise self.TaskCreationError(f"API error creating Stagehand task: {e}") from e
            except Exception as e: # Includes WorkflowBuilder.build() errors or other unexpected issues
                 logger.exception(f"Unexpected error creating Stagehand task.", extra={**log_st_create, "error": str(e), "status": "failed_unexpected_error"})
                 raise self.TaskCreationError(f"Unexpected error creating Stagehand task: {e}") from e

            # 2. Provision Browserbase Sessions Concurrently
            log_bb_provision = {**log_extra_base, "sub_action": "provision_browserbase_sessions", "stagehand_task_id": stagehand_task_id}
            logger.info(f"Provisioning {num_sessions} Browserbase sessions.", extra=log_bb_provision)
            
            session_creation_tasks = [
                self._create_browserbase_session(project_id=final_bb_project_id, session_params=browserbase_session_params) 
                for _ in range(num_sessions)
            ]
            session_creation_outcomes = await asyncio.gather(*session_creation_tasks, return_exceptions=True)

            for i, outcome in enumerate(session_creation_outcomes):
                if isinstance(outcome, Exception):
                    logger.error(f"Failed to create Browserbase session {i+1}/{num_sessions}.", exc_info=outcome, extra={**log_bb_provision, "session_index": i, "error": str(outcome), "status": "failed"})
                    execution_results.append({
                        "sessionId": None, "stagehandTaskId": stagehand_task_id, "stagehandExecutionId": None,
                        "status": "failed_session_creation", "error": str(outcome)
                    })
                else: # Success
                    session_id = outcome
                    browserbase_sessions_created_ids.append(session_id)
                    session_info = self.get_session_info(session_id) # Should exist
                    if session_info:
                         session_info.state = "busy"
                         session_info.task_id = stagehand_task_id
                    logger.info(f"Browserbase session {i+1}/{num_sessions} provisioned successfully: {session_id}", extra={**log_bb_provision, "session_index": i, "session_id": session_id, "status": "success"})
            
            if not browserbase_sessions_created_ids:
                 logger.warning("No Browserbase sessions were created successfully. Aborting workflow execution.", extra={**log_bb_provision, "status": "aborted_no_sessions"})
                 return execution_results # Contains only session creation failures

            logger.info(f"Successfully provisioned {len(browserbase_sessions_created_ids)}/{num_sessions} Browserbase sessions.", extra=log_bb_provision)

            # 3. Execute Stagehand Task on Successfully Created Sessions Concurrently
            log_st_execute = {**log_extra_base, "sub_action": "execute_stagehand_task", "stagehand_task_id": stagehand_task_id, "num_sessions_to_run": len(browserbase_sessions_created_ids)}
            logger.info(f"Executing Stagehand task on {len(browserbase_sessions_created_ids)} sessions.", extra=log_st_execute)
            
            task_execution_tasks = [
                self.stagehand_client.execute_task(task_id=stagehand_task_id, browser_session_id=session_id)
                for session_id in browserbase_sessions_created_ids
            ]
            task_execution_outcomes = await asyncio.gather(*task_execution_tasks, return_exceptions=True)

            # 4. Collect and Process Execution Results
            logger.info(f"Processing {len(task_execution_outcomes)} Stagehand execution results...", extra=log_st_execute)
            for i, outcome in enumerate(task_execution_outcomes):
                session_id = browserbase_sessions_created_ids[i]
                session_info = self.get_session_info(session_id)
                current_log_extra = {**log_st_execute, "session_id": session_id}
                
                result_entry = {"sessionId": session_id, "stagehandTaskId": stagehand_task_id, "stagehandExecutionId": None, "status": "unknown", "error": None}
                if isinstance(outcome, Exception):
                    logger.error(f"Stagehand task execution failed for session.", exc_info=outcome, extra={**current_log_extra, "error": str(outcome), "status": "failed"})
                    result_entry["status"] = "failed_execution"
                    result_entry["error"] = str(outcome)
                    if session_info: session_info.state = "error_execution_failed"
                else: # Success from Stagehand execute_task
                    execution_id = outcome.get("executionId")
                    task_status = outcome.get("status", "success_unknown_stagehand_status") # Default if Stagehand status missing
                    logger.info(f"Stagehand task execution reported status: {task_status}", extra={**current_log_extra, "stagehand_execution_id": execution_id, "stagehand_status": task_status, "status": "success"})
                    result_entry["stagehandExecutionId"] = execution_id
                    result_entry["status"] = task_status 
                    if session_info: session_info.state = "idle" # Ready for release or next task

                execution_results.append(result_entry)
            logger.info("Finished processing all Stagehand task executions.", extra=log_st_execute)
            return execution_results

        except (self.TaskCreationError, self.SessionCreationError, self.TaskExecutionError, self.OrchestratorError) as e:
            logger.error(f"Orchestration failed: {type(e).__name__}", exc_info=True, extra={**log_extra_base, "error": str(e), "status": "failed_orchestration_error"})
            main_exception = e
            raise 
        except Exception as e:
            logger.exception(f"Unexpected error during workflow execution.", extra={**log_extra_base, "error": str(e), "status": "failed_unexpected_error"})
            main_exception = e
            raise self.OrchestratorError(f"Unexpected orchestration error: {e}") from e

        finally:
            log_cleanup = {**log_extra_base, "sub_action": "release_browserbase_sessions_cleanup"}
            if browserbase_sessions_created_ids:
                logger.info(f"Ensuring release of {len(browserbase_sessions_created_ids)} created Browserbase sessions...", extra=log_cleanup)
                release_tasks = [
                    self._release_browserbase_session(sid, project_id=final_bb_project_id) 
                    for sid in browserbase_sessions_created_ids
                ]
                release_outcomes = await asyncio.gather(*release_tasks, return_exceptions=True)
                
                release_errors_details = []
                for i, res_outcome in enumerate(release_outcomes):
                    session_id_to_release = browserbase_sessions_created_ids[i]
                    current_release_log_extra = {**log_cleanup, "session_id": session_id_to_release}
                    if isinstance(res_outcome, Exception) or not res_outcome: # Checks for Exception or False return
                        error_msg = f"Failed to release Browserbase session {session_id_to_release}: {res_outcome}"
                        logger.error(error_msg, extra={**current_release_log_extra, "error": str(res_outcome), "status": "failed"})
                        release_errors_details.append(error_msg)
                    else:
                         logger.info(f"Successfully released session.", extra={**current_release_log_extra, "status": "success"})
                
                if release_errors_details:
                    final_error_summary = f"Additionally, {len(release_errors_details)} error(s) occurred during session release: {'; '.join(release_errors_details)}"
                    if main_exception:
                        logger.error(final_error_summary, extra=log_cleanup)
                    else: # Main workflow might have succeeded
                        logger.warning(f"Workflow execution may have had successes, but {final_error_summary}", extra=log_cleanup)
            else:
                logger.info("No Browserbase sessions were successfully created, so no specific release needed in cleanup.", extra=log_cleanup)


    def start_api_server(self, host: str = "0.0.0.0", port: int = 8000):
        """Starts the FastAPI server for the Orchestrator's API (e.g., health check)."""
        log_extra = {**DEFAULT_LOG_EXTRA, "action": "start_api_server", "host": host, "port": port}
        logger.info(f"Starting Orchestrator API server.", extra=log_extra)
        uvicorn.run(app, host=host, port=port)

# Example usage (if run directly, for testing)
async def main():
    # Example: Override basicConfig for more detailed local testing if desired
    # logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - Action: %(action)s - %(message)s')
    # logger.setLevel(logging.DEBUG) # Ensure module logger also respects this for testing

    # For testing without .env or actual keys:
    bb_key = "dummy_bb_key_from_main" 
    sh_key = "dummy_sh_key_from_main"
    
    # You'd typically load these from config or environment in a real app
    orchestrator_config = {
        "browserbase_api_key": bb_key,
        "stagehand_api_key": sh_key,
        "browserbase_project_id": "project_dummy_123" # Example project ID
    }

    orchestrator = Orchestrator(config=orchestrator_config)
    logger.info("Orchestrator instance created for main() example.", extra={"action": "main_example_start"})

    try:
        # Example: Create a session (mocked or with dummy keys this will likely fail at API call)
        # This demonstrates how project_id flows from config if not passed directly
        # logger.info("Attempting to create a session via main() example...", extra={"action": "main_example_create_session_attempt"})
        # session_id = await orchestrator._create_browserbase_session(session_params={"test_param": "value"})
        # logger.info(f"Session created via main() example: {session_id}", extra={"action": "main_example_create_session_success", "session_id": session_id})

        # logger.info(f"Active sessions via main(): {orchestrator.list_active_sessions()}", extra={"action": "main_example_list_sessions"})
        # info = orchestrator.get_session_info(session_id)
        # logger.info(f"Session info via main(): {info}", extra={"action": "main_example_get_session_info"})

        # logger.info("Attempting to release the session via main() example...", extra={"action": "main_example_release_session_attempt"})
        # released = await orchestrator._release_browserbase_session(session_id)
        # logger.info(f"Session released via main() example: {released}", extra={"action": "main_example_release_session_success", "released_status": released})
        # logger.info(f"Active sessions after release via main(): {orchestrator.list_active_sessions()}", extra={"action": "main_example_list_sessions_after_release"})
        pass # Keep main simple, focus on init logging for now
    
    except Orchestrator.SessionCreationError as e:
        logger.error(f"SessionCreationError in main example: {e}", exc_info=True, extra={"action": "main_example_session_creation_error"})
    except (BrowserbaseAPIError, StagehandAPIError, StagehandConfigError) as e: # Added StagehandConfigError
        logger.error(f"API or Config Error in main example: {e}", exc_info=True, extra={"action": "main_example_api_config_error"})
    except Exception as e:
        logger.exception(f"An unexpected error occurred in main() example.", extra={"action": "main_example_unexpected_error"})
    finally:
        logger.info("Closing orchestrator from main() example.", extra={"action": "main_example_close_orchestrator"})
        await orchestrator.close()

if __name__ == "__main__":
    logger.info("Orchestrator module loaded directly (__name__ == '__main__').", extra={"action": "main_execution_start"})
    
    # To run the main example async function:
    # asyncio.run(main()) 
    # logger.info("Async main() example finished.", extra={"action": "main_execution_complete_async_main"})

    # To start the API server (as in original code):
    logger.info("Starting Orchestrator API server directly from __main__ block...", extra={"action": "main_start_api_server"})
    # In a real deployment, a process manager (like gunicorn with uvicorn workers) would be used.
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info") 