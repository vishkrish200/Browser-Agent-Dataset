class WorkflowError(Exception):
    """Base exception for workflow system errors."""
    pass

class InvalidActionError(WorkflowError):
    """Error raised when an action is defined with invalid parameters."""
    pass

class WorkflowValidationError(WorkflowError):
    """Error raised when a workflow fails validation before building."""
    pass 