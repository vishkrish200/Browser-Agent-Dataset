from typing import List, Dict, Any, Optional

# from .exceptions import WorkflowError, InvalidActionError # To be defined

class WorkflowBuilder:
    """
    Provides a fluent interface to build Stagehand-compatible workflow definitions.
    """
    def __init__(self, workflow_name: str):
        if not workflow_name or not isinstance(workflow_name, str):
            # raise WorkflowError("Workflow name must be a non-empty string.") # Define WorkflowError later
            raise ValueError("Workflow name must be a non-empty string.")
        self.workflow_name: str = workflow_name
        self._steps: List[Dict[str, Any]] = []

    def _add_step(self, action_type: str, params: Dict[str, Any]) -> 'WorkflowBuilder':
        """Internal helper to add a generic action step."""
        # This structure is a guess based on PRD and common patterns.
        # It MUST be aligned with what StagehandClient.create_task expects.
        step = {
            "type": "action", # Assuming all our builder steps are 'actions' for Stagehand
            "actionType": action_type,
            **params
        }
        self._steps.append(step)
        return self

    # --- Chainable Action Methods (to be implemented in Subtask 8.2) ---

    def navigate(self, url: str) -> 'WorkflowBuilder':
        if not url or not isinstance(url, str):
            # raise InvalidActionError("URL must be a non-empty string for navigate action.")
            raise ValueError("URL must be a non-empty string for navigate action.")
        # return self._add_step("navigate", {"url": url}) # Example structure
        # For 8.1, just a placeholder:
        print(f"(Placeholder) Navigate to: {url}") 
        return self

    def click(self, selector: str, text_content_match: Optional[str] = None) -> 'WorkflowBuilder':
        if not selector or not isinstance(selector, str):
            # raise InvalidActionError("Selector must be a non-empty string for click action.")
            raise ValueError("Selector must be a non-empty string for click action.")
        # params = {"selector": selector}
        # if text_content_match:
        #     params["textContentMatch"] = text_content_match
        # return self._add_step("click", params)
        print(f"(Placeholder) Click on selector: {selector}")
        return self

    def type_text(self, selector: str, text_to_type: str) -> 'WorkflowBuilder':
        if not selector or not isinstance(selector, str):
            # raise InvalidActionError("Selector must be a non-empty string for type_text action.")
            raise ValueError("Selector must be a non-empty string for type_text action.")
        if not isinstance(text_to_type, str): # Allow empty string for typing
            # raise InvalidActionError("Text to type must be a string for type_text action.")
            raise ValueError("Text to type must be a string for type_text action.")
        # return self._add_step("type", {"selector": selector, "text": text_to_type})
        print(f"(Placeholder) Type '{text_to_type}' into selector: {selector}")
        return self

    # ... other action methods like wait_for_selector, extract_text will go here ...

    def build(self) -> Dict[str, Any]:
        """
        Constructs the final workflow definition payload for Stagehand.
        """
        if not self._steps:
            # raise WorkflowError("Cannot build an empty workflow. Add at least one step.")
            # For now, allow empty for skeleton, but good to validate later.
            pass 

        # This structure MUST match what StagehandClient.create_task expects for its payload.
        # Based on Orchestrator.run_workflow, StagehandClient.create_task gets workflow.build()
        # and returns a response like {"taskId": "..."}.
        # The orchestrator itself doesn't seem to inspect the contents of workflow.build() beyond calling it.
        return {
            "name": self.workflow_name,
            "steps": self._steps
        }

    def __repr__(self) -> str:
        return f"WorkflowBuilder(workflow_name='{self.workflow_name}', steps={len(self._steps)})" 