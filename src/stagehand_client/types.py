from typing import Literal, TypedDict, Optional, List, Dict, Any

WorkflowAction = Literal[
    "navigate", 
    "click", 
    "type_text", 
    "wait_for_selector", 
    "scroll_to_element", 
    "get_text", 
    "get_attribute"
    # Add more actions as Stagehand API supports them
]

class WorkflowStep(TypedDict, total=False):
    action: WorkflowAction
    selector: Optional[str]      # For click, type_text, wait_for_selector, scroll_to_element, get_text, get_attribute
    text: Optional[str]          # For type_text
    url: Optional[str]           # For navigate
    attribute_name: Optional[str] # For get_attribute
    timeout_ms: Optional[int]    # For wait_for_selector or other timed operations
    # Other potential fields based on Stagehand API specifics:
    # x: Optional[int]             # For click at coordinates
    # y: Optional[int]             # For click at coordinates
    # scroll_direction: Optional[Literal["up", "down", "left", "right"]]
    # scroll_amount_pixels: Optional[int]
    # wait_for_text: Optional[str]
    # wait_for_url_pattern: Optional[str]
