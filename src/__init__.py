"""Top-level package for the Browser Agent Dataset project utilities."""

# Import and re-export key components from submodules

# browserbase_client exports
from .browserbase_client import (
    BrowserbaseClient,
    BrowserbaseAPIError,
    # BrowserbaseConfigError, # This was removed as it was not defined
    # Session (if it were defined in bb_client and intended for public API)
)

# stagehand_client exports
from .stagehand_client import (
    StagehandClient,
    StagehandAPIError,
    StagehandConfigError,
    WorkflowBuilder as StagehandWorkflowBuilder, # Renaming to avoid conflict if needed
    # Action (if defined and public)
)

# orchestrator exports
from .orchestrator import (
    Orchestrator,
    # OrchestratorError, # Base error, could be exported
    # SessionCreationError, 
    # TaskCreationError,
    # TaskExecutionError
    # Session (class defined within Orchestrator, might not be for public API)
)

# NEW: workflow_system exports
from .workflow_system.builder import WorkflowBuilder # Default name for this one
from .workflow_system.exceptions import WorkflowError, InvalidActionError, WorkflowValidationError


__all__ = [
    # Browserbase
    "BrowserbaseClient",
    "BrowserbaseAPIError",
    # "BrowserbaseConfigError", 

    # Stagehand
    "StagehandClient",
    "StagehandAPIError",
    "StagehandConfigError",
    "StagehandWorkflowBuilder", # Exported with its new name

    # Orchestrator
    "Orchestrator",
    # "OrchestratorError",
    # "SessionCreationError", 
    # "TaskCreationError",
    # "TaskExecutionError",

    # Workflow System
    "WorkflowBuilder",
    "WorkflowError",
    "InvalidActionError",
    "WorkflowValidationError",
] 