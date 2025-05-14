from typing import List, Dict, Any, Optional

from .exceptions import WorkflowError, InvalidActionError, WorkflowValidationError
from . import actions # Import action type constants

class WorkflowBuilder:
    """
    Provides a fluent interface to build Stagehand-compatible workflow definitions.
    """
    def __init__(self, workflow_name: str):
        if not workflow_name or not isinstance(workflow_name, str):
            raise WorkflowError("Workflow name must be a non-empty string.")
        self.workflow_name: str = workflow_name
        self._steps: List[Dict[str, Any]] = []

    def _add_step(self, action_type: str, params: Dict[str, Any]) -> 'WorkflowBuilder':
        """Internal helper to add a generic action step."""
        step = {
            "type": "action", # Per PRD, Stagehand output has this. Assume input is similar.
            "actionType": action_type,
            **params
        }
        self._steps.append(step)
        return self

    # --- Chainable Action Methods ---

    def navigate(self, url: str) -> 'WorkflowBuilder':
        """Adds a navigation step."""
        if not url or not isinstance(url, str):
            raise InvalidActionError("URL must be a non-empty string for navigate action.")
        # Basic URL validation could be added here if desired (e.g., starts with http/https)
        return self._add_step(actions.NAVIGATE, {"url": url})

    def click(self, selector: str, text_content_match: Optional[str] = None) -> 'WorkflowBuilder':
        """Adds a click step. Optionally matches text content of the element."""
        if not selector or not isinstance(selector, str):
            raise InvalidActionError("Selector must be a non-empty string for click action.")
        params = {"selector": selector}
        if text_content_match is not None: # Allow empty string if it's a valid match criteria
            if not isinstance(text_content_match, str):
                raise InvalidActionError("text_content_match must be a string if provided.")
            params["textContentMatch"] = text_content_match
        return self._add_step(actions.CLICK, params)

    def type_text(self, selector: str, text_to_type: str, clear_before_type: bool = False) -> 'WorkflowBuilder':
        """Adds a typing step. Optionally clears the field before typing."""
        if not selector or not isinstance(selector, str):
            raise InvalidActionError("Selector must be a non-empty string for type_text action.")
        if not isinstance(text_to_type, str):
            raise InvalidActionError("Text to type must be a string for type_text action.")
        params = {"selector": selector, "text": text_to_type}
        if clear_before_type:
            params["clearBefore"] = True # Assuming Stagehand supports this
        return self._add_step(actions.TYPE, params)

    def wait_for_selector(self, selector: str, timeout: int = 30000, visible: Optional[bool] = None) -> 'WorkflowBuilder':
        """Adds a step to wait for an element to be present/visible."""
        if not selector or not isinstance(selector, str):
            raise InvalidActionError("Selector must be a non-empty string for wait_for_selector.")
        if not isinstance(timeout, int) or timeout < 0:
            raise InvalidActionError("Timeout must be a non-negative integer (milliseconds).")
        params = {"selector": selector, "timeout": timeout}
        if visible is not None:
            params["visible"] = bool(visible) # Ensure boolean
        return self._add_step(actions.WAIT_FOR_SELECTOR, params)

    def wait_for_time(self, duration_ms: int) -> 'WorkflowBuilder':
        """Adds a fixed wait/sleep step."""
        if not isinstance(duration_ms, int) or duration_ms <= 0:
            raise InvalidActionError("Duration must be a positive integer (milliseconds) for wait_for_time.")
        return self._add_step(actions.WAIT_FOR_TIME, {"duration": duration_ms})

    def extract_text(self, selector: str, attribute: Optional[str] = None, variable_name: Optional[str] = None) -> 'WorkflowBuilder':
        """Adds a step to extract text or an attribute from an element, optionally storing it in a variable."""
        if not selector or not isinstance(selector, str):
            raise InvalidActionError("Selector must be a non-empty string for extract_text.")
        params: Dict[str, Any] = {"selector": selector}
        if attribute is not None:
            if not isinstance(attribute, str) or not attribute.strip():
                raise InvalidActionError("Attribute must be a non-empty string if provided.")
            params["attribute"] = attribute.strip()
        if variable_name is not None:
            if not isinstance(variable_name, str) or not variable_name.strip(): # Basic validation for variable name
                raise InvalidActionError("Variable name must be a non-empty string if provided.")
            params["variableName"] = variable_name.strip()
        return self._add_step(actions.EXTRACT_TEXT, params)

    def scroll(self, direction: str, amount_pixels: Optional[int] = None, selector_to_element: Optional[str] = None) -> 'WorkflowBuilder':
        """Adds a scroll step. Direction can be 'up', 'down', 'left', 'right', or 'to_element'."""
        valid_directions = ["up", "down", "left", "right", "to_element", "page_down", "page_up", "home", "end"]
        if direction not in valid_directions:
            raise InvalidActionError(f"Invalid scroll direction '{direction}'. Must be one of {valid_directions}")
        
        params: Dict[str, Any] = {"direction": direction}
        if direction == "to_element":
            if not selector_to_element or not isinstance(selector_to_element, str):
                raise InvalidActionError("selector_to_element is required for 'to_element' scroll direction.")
            params["selector"] = selector_to_element
        elif amount_pixels is not None:
            if not isinstance(amount_pixels, int) or amount_pixels <= 0:
                 raise InvalidActionError("amount_pixels must be a positive integer if provided for scroll.")
            params["amount"] = amount_pixels
        
        # For page_down, page_up, home, end, no other params might be needed beyond direction.
        return self._add_step(actions.SCROLL, params)

    def assert_element(self, selector: str, exists: bool = True, is_visible: Optional[bool] = None) -> 'WorkflowBuilder':
        """Adds an assertion step for an element's existence or visibility."""
        if not selector or not isinstance(selector, str):
            raise InvalidActionError("Selector must be a non-empty string for assert_element.")
        params: Dict[str, Any] = {"selector": selector, "exists": bool(exists)}
        if is_visible is not None:
            params["isVisible"] = bool(is_visible)
        return self._add_step(actions.ASSERT_ELEMENT, params)

    def assert_text(self, text_to_find: str, selector: Optional[str] = None, should_contain: bool = True, is_case_sensitive: bool = False) -> 'WorkflowBuilder':
        """Adds an assertion for text content. If selector is None, checks the whole page (if Stagehand supports)."""
        if not isinstance(text_to_find, str):
            raise InvalidActionError("text_to_find must be a string for assert_text.")
        params: Dict[str, Any] = {"text": text_to_find, "contains": bool(should_contain), "caseSensitive": bool(is_case_sensitive)}
        if selector is not None:
            if not isinstance(selector, str) or not selector.strip():
                raise InvalidActionError("Selector must be a non-empty string if provided for assert_text.")
            params["selector"] = selector.strip()
        return self._add_step(actions.ASSERT_TEXT, params)

    def build(self) -> Dict[str, Any]:
        """
        Constructs the final workflow definition payload for Stagehand.
        Performs basic validation before returning.
        """
        if not self._steps:
            # Depending on Stagehand, an empty steps list might be valid for a named workflow
            # or it might be an error. For now, let's allow it but one might raise WorkflowValidationError here.
            # raise WorkflowValidationError("Cannot build an empty workflow. Add at least one step.")
            pass 

        # This structure MUST match what StagehandClient.create_task expects for its payload.
        return {
            "name": self.workflow_name,
            "steps": self._steps
        }

    def __repr__(self) -> str:
        return f"WorkflowBuilder(workflow_name='{self.workflow_name}', steps={len(self._steps)})" 