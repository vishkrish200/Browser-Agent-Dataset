"""Core Orchestration Service"""

import asyncio
import logging
import os
from typing import Optional, Dict, List, Any, Type # Added Type
from threading import Lock # For potential thread-safe state management
from fastapi import FastAPI
import uvicorn
from dotenv import load_dotenv
import pathlib
from pyobjtojson import obj_to_json # For serializing complex history objects
import base64

# === Logging Configuration (MOVED UP) ===
# Basic config is set here, can be overridden by applications importing this module
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S%z' 
)
logger = logging.getLogger(__name__)
DEFAULT_LOG_EXTRA = {"action": "unknown"}
# === END Logging Configuration ===

# Import clients (adjust based on final install structure)
from browserbase import Browserbase, BrowserbaseError as OfficialBrowserbaseError # MODIFIED

# === Playwright Imports (already existing and confirmed functional) ===
PlaywrightAsyncContextManager = None
PlaywrightBrowser = None # This will be Playwright's Browser type
PlaywrightPage = None    # This will be Playwright's Page type
PlaywrightContext = None # This will be Playwright's BrowserContext type
PlaywrightError = None # For catching specific Playwright errors

try:
    from playwright.async_api import async_playwright, Browser as PWBrowser, Page as PWPage, BrowserContext as PWContext, Error as PWError
    PlaywrightAsyncContextManager = async_playwright
    PlaywrightBrowser = PWBrowser
    PlaywrightPage = PWPage
    PlaywrightContext = PWContext
    PlaywrightError = PWError # Assign PlaywrightError
    logger.info("Successfully imported playwright.async_api components (Browser, Page, Context, Error).")
    # ... (rest of existing Playwright setup) ...
except ImportError as e_playwright_import:
    logger.error(f"Failed to import playwright.async_api. Direct Playwright connection will not be possible. Error: {e_playwright_import}")

# === NEW: browser-use and Langchain Imports ===
BrowserUseAgent = None
BrowserUseBrowser = None
BrowserUseBrowserConfig = None
BrowserUseContext = None
BrowserUseContextConfig = None
BrowserUseSession = None
ChatOpenAI = None # For the LLM
AgentHistoryList = None # For agent results

try:
    from browser_use import Agent as BUAgent, Browser as BUBrowser, BrowserConfig as BUBrowserConfig
    from browser_use.browser.context import BrowserContext as BUBrowserContext, BrowserContextConfig as BUBrowserContextConfig
    from browser_use.browser.session import BrowserSession as BUBrowserSession
    from browser_use.agent.views import AgentHistoryList as BUAgentHistoryList
    BrowserUseAgent = BUAgent
    BrowserUseBrowser = BUBrowser
    BrowserUseBrowserConfig = BUBrowserConfig
    BrowserUseContext = BUBrowserContext
    BrowserUseContextConfig = BUBrowserContextConfig
    BrowserUseSession = BUBrowserSession
    AgentHistoryList = BUAgentHistoryList
    logger.info("Successfully imported browser-use components (including BrowserContext).")
except ImportError as e_browser_use_import:
    logger.error(f"Failed to import browser-use components. AI actions via browser-use will not be available. Error: {e_browser_use_import}")

try:
    from langchain_openai import ChatOpenAI as LangchainChatOpenAI
    ChatOpenAI = LangchainChatOpenAI
    logger.info("Successfully imported ChatOpenAI from langchain_openai.")
except ImportError as e_langchain_import:
    logger.error(f"Failed to import ChatOpenAI. LLM integration for browser-use will be affected. Error: {e_langchain_import}")

# === NEW: browser-use Helper Classes (adapted from Browserbase docs) ===
class ExtendedBrowserUseSession(BrowserUseSession):
    """Extended version of BrowserSession that includes current_page."""
    def __init__(
        self,
        context: PlaywrightContext, # This should be Playwright's BrowserContext
        cached_state: Optional[dict] = None,
        current_page: Optional[PlaywrightPage] = None # This is Playwright's Page type
    ):
        super().__init__(context=context, cached_state=cached_state)
        self.current_page = current_page

class OrchestratorBrowserUseContext(BrowserUseContext):
    """Custom BrowserContext for Orchestrator to integrate with Browserbase-provided Playwright page."""
    def __init__(self, browser: BUBrowser, config: BUBrowserContextConfig, existing_playwright_page: PlaywrightPage):
        # Call Pydantic model __init__ with keyword arguments
        super().__init__(browser=browser, config=config)
        self.playwright_page = existing_playwright_page
        self.browser = browser # Store browser instance if needed by this subclass
        self.config = config   # Store config instance if needed by this subclass
        self.logger = logging.getLogger(f"{BASE_LOGGER_NAME}.OrchestratorBrowserUseContext")
        self.telemetry_handler = Telemetry()
        self._page_event_handler = None # Initialize to None
        # We won't call _add_new_page_listener here as we are using an existing page

    async def _initialize_session(self) -> ExtendedBrowserUseSession:
        """Initialize a browser session using an existing Playwright page from Browserbase."""
        # Get the Playwright Browser object that browser-use's Browser instance is connected to.
        # This assumes self.browser (BrowserUseBrowser) has an underlying Playwright Browser object.
        # The BrowserUseBrowser is initialized with a CDP URL, so it should manage this.
        playwright_browser_from_bu = await self.browser.get_playwright_browser()

        # We need a Playwright BrowserContext. The incoming self._existing_playwright_page already belongs to a context.
        # We should use that existing context directly if possible, or ensure browser-use uses it.
        # For simplicity and alignment with the example, let's assume browser-use's context creation
        # with an existing playwright_browser handle will correctly pick up the existing page's context.
        
        # The example creates a new context then gets a page. We have an existing page.
        # Let's get the context OF the existing page.
        playwright_context_of_existing_page = self._existing_playwright_page.context

        # The original example adds a new page listener to the context. 
        # Since we are attaching to an *existing* page from Browserbase, 
        # we might not need/want to manage new pages created by browser-use in the same way.
        # self._add_new_page_listener(playwright_context_of_existing_page) # Let's omit this for now

        self.session = ExtendedBrowserUseSession(
            context=playwright_context_of_existing_page, # Use the context of the page we were given
            cached_state=None, # Will be updated by _update_state
            current_page=self._existing_playwright_page # Crucially, set the page we got from Browserbase
        )

        # Initialize session state using browser-use's method
        # This method likely interacts with the self.session.current_page
        self.session.cached_state = await self._update_state()
        logger.info(f"OrchestratorBrowserUseContext: Initialized session with existing page: {self.session.current_page.url if self.session.current_page else 'No URL'}", extra=DEFAULT_LOG_EXTRA)
        return self.session

    # ADD ALIAS METHOD HERE
    async def go_to_url(self, url: str):
        """Alias for navigate_to to match expected agent action call."""
        # The parent BrowserContext has navigate_to
        if hasattr(super(), 'navigate_to') and callable(getattr(super(), 'navigate_to')):
            return await super().navigate_to(url)
        # Fallback if super() doesn't have it directly (e.g. if navigate_to is on self but not go_to_url)
        elif hasattr(self, 'navigate_to') and callable(getattr(self, 'navigate_to')):
             return await self.navigate_to(url)
        else:
            logger.error("OrchestratorBrowserUseContext: Neither self nor super has a callable 'navigate_to' method.")
            raise AttributeError("OrchestratorBrowserUseContext does not have a 'navigate_to' method to alias.")

app = FastAPI()

@app.get("/health")
async def health_check():
    logger.info("Health check endpoint called.", extra={"action": "health_check_invoked"})
    return {"status": "healthy"}

class ActiveSessionInfo:
    def __init__(self, browserbase_id: str, state: str = "idle", task_id: Optional[str] = None, websocket_url: Optional[str] = None):
        self.browserbase_id: str = browserbase_id
        self.state: str = state
        self.task_id: Optional[str] = task_id
        self.websocket_url: Optional[str] = websocket_url

    def __repr__(self):
        return f"ActiveSessionInfo(id={self.browserbase_id}, state={self.state}, task_id={self.task_id}, websocket_url={self.websocket_url})"

class Orchestrator:
    class OrchestratorError(Exception): pass
    class SessionCreationError(OrchestratorError): pass
    class TaskExecutionError(OrchestratorError): pass

    def __init__(self, config: Optional[Dict] = None):
        self.logger = logging.getLogger(__name__)
        self.config = config if config is not None else {}
        
        # Load sensitive keys and project ID from env if not in config
        self.config.setdefault("browserbase_api_key", os.environ.get("BROWSERBASE_API_KEY"))
        self.config.setdefault("browserbase_project_id", os.environ.get("BROWSERBASE_PROJECT_ID"))
        self.config.setdefault("openai_api_key", os.environ.get("OPENAI_API_KEY"))
        self.config.setdefault("llm_model_name", os.environ.get("MODEL_NAME", "gpt-4o"))
        self.config.setdefault("llm_temperature", float(os.environ.get("LLM_TEMPERATURE", 0.0)))
        self.config.setdefault("playwright_cdp_connect_timeout_ms", int(os.environ.get("PLAYWRIGHT_CDP_CONNECT_TIMEOUT_MS", 60000)))
        self.config.setdefault("browser_use_network_idle_time", float(os.environ.get("BROWSER_USE_NETWORK_IDLE_TIME", 10.0)))
        self.config.setdefault("browser_use_highlight_elements", os.environ.get("BROWSER_USE_HIGHLIGHT_ELEMENTS", "True").lower() == "true")
        self.config.setdefault("browser_use_ai_action_timeout_ms", int(os.environ.get("BROWSER_USE_AI_ACTION_TIMEOUT_MS", 90000)))

        self.browserbase_project_id = self.config.get("browserbase_project_id")
        bb_api_key = self.config.get("browserbase_api_key")

        if not bb_api_key:
            self.logger.warning("Browserbase API key not found. Official Browserbase SDK may not function.")
        self.browserbase_sdk = Browserbase(api_key=bb_api_key, base_url="https://api.browserbase.com")
        
        self.active_sessions: Dict[str, ActiveSessionInfo] = {}
        self._session_lock = asyncio.Lock()

        if not PlaywrightAsyncContextManager or not BrowserUseAgent or not ChatOpenAI or not AgentHistoryList:
            err_msg = "Orchestrator disabled: Playwright, BrowserUseAgent, ChatOpenAI, or AgentHistoryList not available."
            self.logger.error(err_msg)
            # In a real app, might raise an error or set a disabled state

        self.logger.info("Orchestrator initialized with hook capabilities.", extra=DEFAULT_LOG_EXTRA)

        self.session_step_data: Dict[str, List[Dict[str, Any]]] = {}

    async def close(self):
        log_extra = {**DEFAULT_LOG_EXTRA, "action": "orchestrator_close"}
        self.logger.info("Closing Orchestrator...", extra=log_extra)
        # Note: The official browserbase SDK does not have an explicit async close().
        # HTTP clients are typically managed internally by libraries like 'requests'.
        self.logger.info("No explicit close needed for synchronous Browserbase SDK.", extra=log_extra)
        self.logger.info("Orchestrator close procedure completed.", extra=log_extra)

    async def _create_browserbase_session(self, project_id: Optional[str] = None, session_params: Optional[Dict] = None) -> ActiveSessionInfo:
        session_params_to_use = session_params or {}
        final_project_id = project_id or self.browserbase_project_id
        log_extra = {**DEFAULT_LOG_EXTRA, "action": "create_browserbase_session", "project_id": final_project_id}
        self.logger.info("Attempting to create Browserbase session.", extra=log_extra)
        if not final_project_id:
            self.logger.error("Cannot create session: project_id missing.", extra=log_extra)
            raise self.SessionCreationError("Browserbase project_id required.")
        try:
            response_data = await asyncio.to_thread(
                self.browserbase_sdk.sessions.create, 
                project_id=final_project_id,
                **session_params_to_use
            )
            session_id = response_data.id
            websocket_url = getattr(getattr(response_data, 'connect_params', None), 'wss_url', None) or response_data.connect_url
            
            if not session_id:
                raise self.SessionCreationError(f"No 'id' in Browserbase response: {response_data}")
            if not websocket_url:
                self.logger.warning(f"Browserbase response missing WebSocket URL. Session: {session_id}", extra=log_extra)

            new_session_info = ActiveSessionInfo(browserbase_id=session_id, websocket_url=websocket_url)
            async with self._session_lock:
                self.active_sessions[session_id] = new_session_info
            self.logger.info(f"Browserbase session created: {session_id}", extra={**log_extra, "session_id": session_id, "websocket_url": websocket_url})
            return new_session_info
        except OfficialBrowserbaseError as e:
            self.logger.error(f"Browserbase API error: {e}", exc_info=True, extra=log_extra)
            raise self.SessionCreationError(f"API error creating session: {e}") from e
        except Exception as e:
            self.logger.exception("Unexpected error creating session.", extra=log_extra)
            raise self.SessionCreationError(f"Unexpected error: {e}") from e

    async def _release_browserbase_session(self, session_id: str, project_id: Optional[str] = None) -> bool:
        final_project_id = project_id or self.browserbase_project_id
        log_extra = {**DEFAULT_LOG_EXTRA, "action": "release_browserbase_session", "session_id": session_id}
        if not final_project_id:
            self.logger.error("Cannot release session: project_id missing.", extra=log_extra)
            return False
        self.logger.info("Attempting to release Browserbase session.", extra=log_extra)
        try:
            await asyncio.to_thread(
                self.browserbase_sdk.sessions.update,
                id=session_id,
                project_id=final_project_id, 
                status="REQUEST_RELEASE"
            )
            async with self._session_lock:
                if session_id in self.active_sessions: del self.active_sessions[session_id]
            self.logger.info(f"Browserbase session {session_id} released.", extra=log_extra)
            return True
        except Exception as e:
            self.logger.exception(f"Error releasing session {session_id}.", extra=log_extra)
            return False

    def _agent_step_hook_wrapper(self, session_id: str):
        self.logger.info(f"_agent_step_hook_wrapper called with session_id: {session_id}") # DEBUG
        # This wrapper returns the actual hook function with the session_id partially applied (via closure)
        async def actual_hook(
            # Argument 1: Passed by browser-use as browser_state_summary (which is the BrowserSession)
            bu_session_obj: Any, 
            # Argument 2: Passed by browser-use as model_output
            agent_action_output: Any, 
            # Argument 3: Passed by browser-use as self.state.n_steps
            current_step_number: int
        ):
            self.logger.info(f"actual_hook called. WILL CALL _agent_step_hook with session_id: {session_id}") # DEBUG
            # Now call the real hook, passing ONLY session_id for this test
            await self._agent_step_hook(session_id=session_id)
            # Original call commented out for debugging:
            # await self._agent_step_hook(
            #     bu_session_or_context=bu_session_obj,
            #     browser_state=bu_session_obj,
            #     agent_output=agent_action_output,
            #     step_number=current_step_number,
            #     session_id=session_id 
            # )
        return actual_hook

    async def _agent_step_hook(
        self,
        bu_session_or_context: Any, # This will be BrowserSession
        browser_state: Any,         # This will also be BrowserSession (as it contains state)
        agent_output: Any,          # This is browser_use.agent.views.AgentOutput
        step_number: int,
        session_id: str
    ):
        self.logger.info(f"_agent_step_hook ENTERED. Received session_id: {session_id}, step_number: {step_number}") # DEBUG
        log_extra_hook = {**DEFAULT_LOG_EXTRA, "action": "agent_step_hook", "session_id": session_id, "step": step_number}
        self.logger.debug(f"Agent step hook triggered for session {session_id}, step {step_number}. Output type: {type(agent_output)}", extra=log_extra_hook)
        
        step_data: Dict[str, Any] = {}
        try:
            step_data["step_number_capture"] = step_number # Use the passed step_number

            # Capture raw model actions for debugging and dataset
            raw_action_data = None
            if hasattr(agent_output, 'action'):
                # Log the type and content of agent_output.action for clarity
                self.logger.info(f"Hook: agent_output.action type: {type(agent_output.action)}, content: {obj_to_json(agent_output.action)}", extra=log_extra_hook)
                raw_action_data = obj_to_json(agent_output.action) # Capture as JSON string
            step_data["model_actions_raw"] = raw_action_data

            # Capture raw LLM response if available
            raw_llm_response_data = None
            if hasattr(agent_output, 'raw_output') and agent_output.raw_output:
                 raw_llm_response_data = agent_output.raw_output
            step_data["raw_llm_response"] = raw_llm_response_data

            # Capture extracted content if available (might be specific to certain action types)
            extracted_content_data = None
            if hasattr(agent_output, 'action') and hasattr(agent_output.action, 'extracted_content'):
                 extracted_content_data = agent_output.action.extracted_content
            step_data["extracted_content"] = extracted_content_data
            
            # Get URL and Screenshot from browser_state (which should be the BrowserSession)
            current_url = None
            if hasattr(browser_state, 'get_current_page_url'): # BrowserSession has this
                current_url = browser_state.get_current_page_url()
            step_data["url"] = current_url
            
            # HTML snapshot and screenshot
            html_snapshot = None
            png_snapshot_b64 = None
            if current_url and hasattr(browser_state, 'active_page'): # BrowserSession has active_page
                active_page = browser_state.active_page
                if active_page:
                    html_snapshot = await active_page.content()
                    try:
                        screenshot_bytes = await active_page.screenshot()
                        png_snapshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                    except Exception as e_screenshot:
                        self.logger.warning(f"Failed to capture screenshot: {e_screenshot}", extra=log_extra_hook)
            step_data["html_snapshot_b64"] = base64.b64encode(html_snapshot.encode('utf-8')).decode('utf-8') if html_snapshot else None
            step_data["png_snapshot_b64"] = png_snapshot_b64

        except Exception as e:
            self.logger.error(f"Error in agent step hook: {e}", extra=log_extra_hook)
            step_data["hook_error"] = str(e)
        
        if session_id in self.session_step_data:
            self.session_step_data[session_id].append(step_data)
            self.logger.debug(f"Appended step data for session {session_id}. Total steps captured: {len(self.session_step_data[session_id])}", extra=log_extra_hook)
        else:
            self.logger.warning(f"Session ID {session_id} not found in session_step_data. Hook data lost for this step.", extra=log_extra_hook)

    async def _execute_ai_task_on_single_session(self, session_info: ActiveSessionInfo, task_prompt: str, start_url: Optional[str] = None) -> Dict[str, Any]:
        log_extra_exec = {**DEFAULT_LOG_EXTRA, "action": "execute_ai_task", "session_id": session_info.browserbase_id, "task_prompt": task_prompt[:100]}
        self.logger.info(f"Executing AI task with detailed step capture on session {session_info.browserbase_id}", extra=log_extra_exec)

        # Dependency checks
        if not all([PlaywrightAsyncContextManager, BUAgent, ChatOpenAI, BUBrowser, BUAgentHistoryList]):
            msg = "Playwright or browser-use components not available."
            self.logger.error(msg, extra=log_extra_exec)
            return {"status": "failed_dependencies_missing", "error": msg, "dataset_trace": []}
        
        if not session_info.websocket_url:
            msg = f"Session {session_info.browserbase_id} missing WebSocket URL."
            self.logger.error(msg, extra=log_extra_exec)
            return {"status": "failed_missing_websocket_url", "error": msg, "dataset_trace": []}

        playwright_browser_conn: Optional[PlaywrightBrowser] = None
        bu_session_obj: Optional[BUBrowser] = None # BUBrowser is browser_use.Browser, acting as BrowserSession
        dataset_trace: List[Dict[str, Any]] = []
        agent_summary_obj: Optional[BUAgentHistoryList] = None
        result_status = "unknown_task_status" # Default status
        task_result_summary = "Task execution did not complete or summary unavailable."

        # Initialize LLM for the agent
        if not self.config.get("openai_api_key"):
            self.logger.error("OpenAI API key not configured. Cannot initialize LLM for browser-use agent.", extra=log_extra_exec)
            return {"status": "failed_config_missing_openai_key", "error": "OpenAI API key missing", "dataset_trace": dataset_trace}
        
        try:
            llm_instance = ChatOpenAI(
                openai_api_key=self.config["openai_api_key"], 
                model_name=self.config.get("llm_model_name", "gpt-4o"), 
                temperature=self.config.get("llm_temperature", 0.0)
            )
            self.logger.info(f"ChatOpenAI LLM instance created for agent. Model: {llm_instance.model_name}", extra=log_extra_exec)
        except Exception as e_llm:
            self.logger.error(f"Failed to initialize ChatOpenAI LLM: {e_llm}", exc_info=True, extra=log_extra_exec)
            return {"status": "failed_llm_initialization", "error": str(e_llm), "dataset_trace": dataset_trace}

        try: # Outer try for the whole method's core logic
            async with PlaywrightAsyncContextManager() as p:
                try:
                    self.logger.info(f"Connecting Playwright to: {session_info.websocket_url}", extra=log_extra_exec)
                    playwright_browser_conn = await p.chromium.connect_over_cdp(
                        session_info.websocket_url, 
                        timeout=self.config.get("playwright_cdp_connect_timeout_ms", 60000)
                    )
                    self.logger.info(f"Playwright connected. Browser: {playwright_browser_conn.version}", extra=log_extra_exec)
                    
                    if not playwright_browser_conn.contexts:
                        self.logger.error("No browser contexts found in Playwright connection.", extra=log_extra_exec)
                        return {"status": "failed_playwright_no_context", "error": "Playwright connection has no contexts", "dataset_trace": dataset_trace}
                    
                    pw_context_instance = playwright_browser_conn.contexts[0]
                    if not pw_context_instance.pages:
                        self.logger.info("Playwright context has no pages, creating one.", extra=log_extra_exec)
                        external_page = await pw_context_instance.new_page() # type: ignore
                    else:
                        external_page = pw_context_instance.pages[0] # type: ignore
                    self.logger.info(f"Acquired Playwright page: {external_page.url}", extra=log_extra_exec)

                    if start_url and external_page.url != start_url:
                        self.logger.info(f"Navigating to start_url: {start_url}", extra=log_extra_exec)
                        await external_page.goto(start_url, timeout=60000)
                        dataset_trace.append({"step_type": "manual_navigation", "url": start_url, "action_summary": f"Manually navigated to {start_url}"})
                        self.logger.info(f"Navigation to {start_url} complete.", extra=log_extra_exec)

                    self.logger.info("Setting up browser-use BrowserSession...", extra=log_extra_exec)
                    
                    bu_session_obj = BUBrowser(
                        cdp_url=session_info.websocket_url, 
                        page=external_page,
                        highlight_elements=self.config.get("browser_use_highlight_elements", True),
                        wait_for_network_idle_page_load_time=self.config.get("browser_use_network_idle_time", 0.5), 
                        minimum_wait_page_load_time=self.config.get("browser_use_min_wait_page_load", 0.25),
                    )
                    self.logger.info(f"browser-use BrowserSession object created. Type: {type(bu_session_obj)}", extra=log_extra_exec)
                    
                    if hasattr(bu_session_obj, 'start') and asyncio.iscoroutinefunction(bu_session_obj.start):
                         if not getattr(bu_session_obj, 'initialized', True):
                            self.logger.info("Explicitly starting browser-use session.", extra=log_extra_exec)
                            await bu_session_obj.start()

                    current_task = task_prompt

                    self.logger.info("Instantiating BrowserUseAgent...", extra=log_extra_exec)
                    bu_agent = BUAgent(
                        task=current_task,
                        llm=llm_instance,
                        browser_session=bu_session_obj,
                        register_new_step_callback=self._agent_step_hook_wrapper(session_info.browserbase_id)
                    )
                    self.logger.info("BrowserUseAgent instantiated.", extra=log_extra_exec)

                    self.logger.info("Running BrowserUseAgent...", extra=log_extra_exec)
                    self.session_step_data[session_info.browserbase_id] = []
                    
                    agent_summary_obj = await bu_agent.run(max_steps=self.config.get("browser_use_max_steps", 15)) 
                    self.logger.info(f"BrowserUseAgent run completed. Summary type: {type(agent_summary_obj)}", extra=log_extra_exec)

                    if agent_summary_obj and hasattr(agent_summary_obj, 'final_answer') and agent_summary_obj.final_answer:
                        task_result_summary = agent_summary_obj.final_answer
                    elif agent_summary_obj and hasattr(agent_summary_obj, 'status_message') and agent_summary_obj.status_message:
                         task_result_summary = agent_summary_obj.status_message
                    
                    dataset_trace.extend(self.session_step_data.get(session_info.browserbase_id, []))
                    
                    if agent_summary_obj and hasattr(agent_summary_obj, 'status') and agent_summary_obj.status:
                        raw_agent_status = str(agent_summary_obj.status).lower().replace(' ', '_')
                        if "complete" in raw_agent_status:
                            result_status = "completed_by_agent"
                        elif "fail" in raw_agent_status:
                            result_status = "failed_by_agent_error"
                        elif "max_step" in raw_agent_status:
                            result_status = "failed_agent_max_steps"
                        else:
                            result_status = f"agent_status_{raw_agent_status}"
                    else:
                        result_status = "completed_agent_run_no_status"

                except PlaywrightError as e_pw_run:
                    self.logger.error(f"Playwright error during AI task execution: {e_pw_run}", exc_info=True, extra=log_extra_exec)
                    result_status = "failed_task_execution_playwright_error"
                    task_result_summary = str(e_pw_run)
                except Exception as e_inner_exec: 
                    error_msg = f"Error during AI task execution (inside async with): {type(e_inner_exec).__name__} - {e_inner_exec}"
                    self.logger.exception(error_msg, extra=log_extra_exec)
                    result_status = "failed_task_execution_inner_error"
                    task_result_summary = error_msg
                finally:
                    log_final_inner = {**log_extra_exec, "sub_action": "inner_cleanup"}
                    self.logger.debug("Starting cleanup for 'async with PlaywrightAsyncContextManager' block.", extra=log_final_inner)
                    
                    if bu_session_obj and hasattr(bu_session_obj, 'close') and asyncio.iscoroutinefunction(bu_session_obj.close):
                        self.logger.debug("Attempting to close browser-use Session (bu_session_obj)", extra=log_final_inner)
                        try: 
                            await bu_session_obj.close()
                            self.logger.info("browser-use Session closed.", extra=log_final_inner)
                        except Exception as e_bu_s_close: 
                            self.logger.error(f"Error closing bu_session_obj: {e_bu_s_close}", exc_info=True, extra=log_final_inner)

                    if playwright_browser_conn and hasattr(playwright_browser_conn, 'close') and asyncio.iscoroutinefunction(playwright_browser_conn.close):
                        self.logger.debug("Attempting to close Playwright browser connection (playwright_browser_conn)", extra=log_final_inner)
                        try: 
                            await playwright_browser_conn.close()
                            self.logger.info("Playwright browser connection closed.", extra=log_final_inner)
                        except Exception as e_pw_close: 
                            self.logger.error(f"Error closing playwright_conn: {e_pw_close}", exc_info=True, extra=log_final_inner)
                    
                    self.logger.info("Finished cleanup for 'async with PlaywrightAsyncContextManager' block.", extra=log_final_inner)

                # Prepare final result for this session
                final_state_url = external_page.url if external_page and hasattr(external_page, 'url') else "Unknown"
                final_page_title = "Unknown"
                if external_page and hasattr(external_page, 'title') and callable(external_page.title):
                    try:
                        final_page_title = await external_page.title()
                    except Exception as e_title:
                        self.logger.warning(f"Could not get final page title: {e_title}", extra=log_extra_exec)

                return {
                    "status": result_status, 
                    "summary": task_result_summary,
                    "final_url": final_state_url,
                    "final_page_title": final_page_title,
                    "dataset_trace": dataset_trace, 
                    "agent_full_summary_obj": obj_to_json(agent_summary_obj) if agent_summary_obj else None
                }

        except Exception as e_outer_task:
            error_msg_outer = f"Major error in _execute_ai_task_on_single_session (outside async with): {type(e_outer_task).__name__} - {e_outer_task}"
            self.logger.exception(error_msg_outer, extra=log_extra_exec)
            return {
                "status": "failed_task_execution_outer_error", 
                "error": error_msg_outer, 
                "dataset_trace": dataset_trace # May contain manual nav step if error was after that
            }

    async def execute_dynamic_task(
        self, 
        task_prompt: str,
        start_url: Optional[str] = None,
        num_sessions: int = 1, 
        browserbase_project_id: Optional[str] = None,
        browserbase_session_params: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        log_extra_base = {**DEFAULT_LOG_EXTRA, "action": "execute_dynamic_task", "task_prompt": task_prompt[:100], "num_requested": num_sessions}
        self.logger.info(f"Attempting to execute dynamic task for prompt: {task_prompt[:100]}...", extra=log_extra_base)

        final_bb_project_id = browserbase_project_id or self.browserbase_project_id
        if not final_bb_project_id:
            self.logger.critical("Task failed: Browserbase Project ID missing.", extra=log_extra_base)
            raise self.OrchestratorError("Browserbase Project ID required.")

        created_session_infos: List[ActiveSessionInfo] = []
        all_results: List[Dict[str, Any]] = []

        try:
            self.logger.info(f"Provisioning {num_sessions} Browserbase sessions.", extra=log_extra_base)
            session_creation_tasks = [
                self._create_browserbase_session(project_id=final_bb_project_id, session_params=browserbase_session_params) 
                for _ in range(num_sessions)
            ]
            session_creation_outcomes = await asyncio.gather(*session_creation_tasks, return_exceptions=True)

            for i, outcome in enumerate(session_creation_outcomes):
                if isinstance(outcome, Exception):
                    self.logger.error(f"Failed to create Browserbase session {i+1}. Error: {outcome}", exc_info=outcome, extra=log_extra_base)
                    all_results.append({"sessionId": None, "status": "failed_session_creation", "error": str(outcome), "dataset_trace": []})
                else:
                    created_session_infos.append(outcome) # outcome is ActiveSessionInfo instance
                    self.logger.info(f"Browserbase session {outcome.browserbase_id} provisioned.", extra={**log_extra_base, "session_id": outcome.browserbase_id})
            
            if not created_session_infos:
                 self.logger.warning("No Browserbase sessions were created. Aborting task execution.", extra=log_extra_base)
                 return all_results

            self.logger.info(f"Executing AI task on {len(created_session_infos)} sessions.", extra=log_extra_base)
            execution_tasks = [
                self._execute_ai_task_on_single_session(session_info, task_prompt, start_url)
                for session_info in created_session_infos
            ]
            individual_session_results = await asyncio.gather(*execution_tasks, return_exceptions=True)

            for i, exec_outcome in enumerate(individual_session_results):
                session_info = created_session_infos[i]
                result_entry = {"sessionId": session_info.browserbase_id, "status": "unknown", "error": None, "dataset_trace": []}
                
                if isinstance(exec_outcome, Exception):
                    self.logger.error(f"Error during AI task execution on session {session_info.browserbase_id}. Error: {exec_outcome}", exc_info=exec_outcome, extra=log_extra_base)
                    result_entry["status"] = "failed_task_execution_wrapper"
                    result_entry["error"] = str(exec_outcome)
                else:
                    result_entry.update(exec_outcome) # Merge status, error, dataset_trace, agent_summary
                all_results.append(result_entry)
            
            self.logger.info("Finished all AI task executions.", extra=log_extra_base)
            return all_results

        except Exception as e:
            self.logger.exception(f"Unexpected error during execute_dynamic_task: {e}", extra=log_extra_base)
            # Ensure any created sessions are attempted to be released if an overarching error occurs
            # before individual execution or during session creation loop.
            # Add partial results if any task started but overall process failed.
            if not all_results and created_session_infos: # if some sessions were made but no results yet
                for s_info in created_session_infos:
                    all_results.append({"sessionId": s_info.browserbase_id, "status": "failed_orchestration_error", "error": str(e), "dataset_trace": []})
            elif not all_results:
                 all_results.append({"sessionId": None, "status": "failed_orchestration_error_early", "error": str(e), "dataset_trace": []})
            raise self.TaskExecutionError(f"Core error in execute_dynamic_task: {e}") from e
        finally:
            sessions_to_release_ids = [s.browserbase_id for s in created_session_infos if s]
            if sessions_to_release_ids:
                self.logger.info(f"Ensuring release of {len(sessions_to_release_ids)} Browserbase sessions...", extra=log_extra_base)
                release_tasks = [
                    self._release_browserbase_session(sid, project_id=final_bb_project_id) 
                    for sid in sessions_to_release_ids
                ]
                await asyncio.gather(*release_tasks, return_exceptions=True)
                self.logger.info(f"Cleanup: Attempted release for {len(sessions_to_release_ids)} sessions.", extra=log_extra_base)

    def start_api_server(self, host: str = "0.0.0.0", port: int = 8000):
        log_extra = {**DEFAULT_LOG_EXTRA, "action": "start_api_server", "host": host, "port": port}
        self.logger.info("Starting Orchestrator API server.", extra=log_extra)
        uvicorn.run(app, host=host, port=port)

# Main block for example or direct server start (remains for testing)
async def example_main():
    # Load .env from project root for example_main
    from dotenv import load_dotenv
    import pathlib
    project_root_env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
    if project_root_env_path.exists():
        load_dotenv(dotenv_path=project_root_env_path, override=True)
        logger.info(f"Example main loaded .env from: {project_root_env_path}")
    else:
        logger.warning(f"Example main: .env not found at {project_root_env_path}. Using shell vars.")

    orchestrator = Orchestrator() # Config will be loaded from env vars
    logger.info("Orchestrator instance created for example_main.")
    
    test_prompt = "Go to wikipedia.org and search for 'Artificial Intelligence'. What is the first sentence of the main content?"
    test_start_url = "https://www.wikipedia.org"

    try:
        logger.info(f"Running example dynamic task: {test_prompt}", extra=DEFAULT_LOG_EXTRA)
        results = await orchestrator.execute_dynamic_task(task_prompt=test_prompt, start_url=test_start_url, num_sessions=1)
        logger.info(f"Example dynamic task results: {results}", extra=DEFAULT_LOG_EXTRA)
    except Exception as e:
        logger.exception("Error in example_main execution.", extra=DEFAULT_LOG_EXTRA)
    finally:
        await orchestrator.close()

if __name__ == "__main__":
    run_mode = os.environ.get("ORCHESTRATOR_RUN_MODE", "API_SERVER")
    if run_mode == "EXAMPLE_WORKFLOW":
        asyncio.run(example_main())
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info") 