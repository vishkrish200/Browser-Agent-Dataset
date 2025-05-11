import json
from typing import Dict, Any, List, TYPE_CHECKING

# Use TYPE_CHECKING to avoid circular import issues if WorkflowBuilder imports from utils
if TYPE_CHECKING:
    from .workflow import WorkflowBuilder  # Import for type hinting only
    from .types import WorkflowStep       # Import for type hinting only

def load_workflow_from_dict(definition: Dict[str, Any]) -> 'WorkflowBuilder':
    """
    Reconstructs a WorkflowBuilder instance from a dictionary definition.

    Args:
        definition: A dictionary expected to have 'name' (str) and 'steps' (List[WorkflowStep]) keys.

    Returns:
        A WorkflowBuilder instance populated with the definition.

    Raises:
        ValueError: If the definition is missing required keys or has invalid structure.
    """
    from .workflow import WorkflowBuilder # Local import for runtime
    from .types import WorkflowStep       # Local import for runtime

    if not isinstance(definition, dict):
        raise ValueError("Workflow definition must be a dictionary.")
    
    workflow_name = definition.get("name")
    if not workflow_name or not isinstance(workflow_name, str):
        raise ValueError("Workflow definition must contain a non-empty string 'name'.")

    steps_data = definition.get("steps")
    if not isinstance(steps_data, list):
        raise ValueError("Workflow definition must contain a list of 'steps'.")

    builder = WorkflowBuilder(workflow_name)
    for i, step_data in enumerate(steps_data):
        if not isinstance(step_data, dict) or "action" not in step_data:
            raise ValueError(f"Step at index {i} is invalid: must be a dict with an 'action' key.")
        # Here, step_data is assumed to be compatible with WorkflowStep TypedDict.
        # More thorough validation against WorkflowStep fields could be added if needed.
        builder.add_custom_step(step_data) # type: ignore 
        # Using type: ignore as step_data is Dict[str, Any] but add_custom_step expects WorkflowStep.
        # A more robust solution would involve validating/casting step_data to WorkflowStep.
        
    return builder

def load_workflow_from_json(file_path: str) -> 'WorkflowBuilder':
    """
    Loads a workflow definition from a JSON file and reconstructs a WorkflowBuilder.

    Args:
        file_path: The path to the JSON file.

    Returns:
        A WorkflowBuilder instance populated from the JSON file.

    Raises:
        FileNotFoundError: If the file_path does not exist.
        json.JSONDecodeError: If the file content is not valid JSON.
        ValueError: If the parsed JSON structure is invalid for a workflow definition.
    """
    try:
        with open(file_path, 'r') as f:
            definition = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Workflow JSON file not found at: {file_path}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Error decoding JSON from {file_path}: {e.msg}", e.doc, e.pos)
    
    return load_workflow_from_dict(definition)
