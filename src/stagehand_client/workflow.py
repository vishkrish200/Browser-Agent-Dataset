from typing import List, Dict, Any, Optional

from .types import WorkflowAction, WorkflowStep

class WorkflowBuilder:
    """A fluent builder for creating Stagehand workflow definitions."""

    def __init__(self, workflow_name: str):
        """
        Initialize the WorkflowBuilder.

        Args:
            workflow_name: The name of the workflow.
        """
        if not workflow_name or not isinstance(workflow_name, str):
            raise ValueError("Workflow name must be a non-empty string.")
        self.workflow_name = workflow_name
        self._steps: List[WorkflowStep] = []

    def _add_step(self, step: WorkflowStep) -> 'WorkflowBuilder':
        self._steps.append(step)
        return self

    def navigate(self, url: str) -> 'WorkflowBuilder':
        """Adds a 'navigate' step to the workflow."""
        if not url or not isinstance(url, str):
            raise ValueError("URL for navigate action must be a non-empty string.")
        return self._add_step(WorkflowStep(action="navigate", url=url))

    def click(self, selector: str) -> 'WorkflowBuilder':
        """Adds a 'click' step to the workflow."""
        if not selector or not isinstance(selector, str):
            raise ValueError("Selector for click action must be a non-empty string.")
        return self._add_step(WorkflowStep(action="click", selector=selector))

    def type_text(self, selector: str, text: str) -> 'WorkflowBuilder':
        """Adds a 'type_text' step to the workflow."""
        if not selector or not isinstance(selector, str):
            raise ValueError("Selector for type_text action must be a non-empty string.")
        # Text can be an empty string, so no check for emptiness, only type.
        if not isinstance(text, str):
            raise ValueError("Text for type_text action must be a string.")
        return self._add_step(WorkflowStep(action="type_text", selector=selector, text=text))

    def wait_for_selector(self, selector: str, timeout_ms: Optional[int] = None) -> 'WorkflowBuilder':
        """Adds a 'wait_for_selector' step to the workflow."""
        if not selector or not isinstance(selector, str):
            raise ValueError("Selector for wait_for_selector action must be a non-empty string.")
        step = WorkflowStep(action="wait_for_selector", selector=selector)
        if timeout_ms is not None:
            if not isinstance(timeout_ms, int) or timeout_ms < 0:
                raise ValueError("timeout_ms must be a non-negative integer if provided.")
            step["timeout_ms"] = timeout_ms
        return self._add_step(step)

    def scroll_to_element(self, selector: str) -> 'WorkflowBuilder':
        """Adds a 'scroll_to_element' step to the workflow."""
        if not selector or not isinstance(selector, str):
            raise ValueError("Selector for scroll_to_element action must be a non-empty string.")
        return self._add_step(WorkflowStep(action="scroll_to_element", selector=selector))

    def get_text(self, selector: str) -> 'WorkflowBuilder':
        """Adds a 'get_text' step to the workflow. The result of this step would typically be captured by Stagehand."""
        if not selector or not isinstance(selector, str):
            raise ValueError("Selector for get_text action must be a non-empty string.")
        return self._add_step(WorkflowStep(action="get_text", selector=selector))

    def get_attribute(self, selector: str, attribute_name: str) -> 'WorkflowBuilder':
        """Adds a 'get_attribute' step to the workflow. The result would be captured by Stagehand."""
        if not selector or not isinstance(selector, str):
            raise ValueError("Selector for get_attribute action must be a non-empty string.")
        if not attribute_name or not isinstance(attribute_name, str):
            raise ValueError("Attribute name for get_attribute action must be a non-empty string.")
        return self._add_step(WorkflowStep(action="get_attribute", selector=selector, attribute_name=attribute_name))

    def build(self) -> Dict[str, Any]:
        """
        Builds the workflow definition dictionary.
        This structure is a common representation but might need adjustment
        based on the actual Stagehand API specification.
        """
        return {
            "name": self.workflow_name,
            "steps": self._steps
        }
