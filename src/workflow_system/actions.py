"""Constants for Stagehand action types."""

NAVIGATE = "navigate"
CLICK = "click"
TYPE = "type"  # Assumed, could be "type_text" or similar based on Stagehand client
WAIT_FOR_SELECTOR = "wait_for_selector"
WAIT_FOR_TIME = "wait_for_time" # Assuming a specific actionType for fixed waits
EXTRACT_TEXT = "extract_text"
SCROLL = "scroll"
ASSERT_ELEMENT = "assert_element" # For existence checks
ASSERT_TEXT = "assert_text"       # For text containment checks

# Potentially other action types Stagehand supports:
# GET_COOKIE, SET_COOKIE, GET_URL, SWITCH_FRAME, EXECUTE_SCRIPT, SCREENSHOT etc. 