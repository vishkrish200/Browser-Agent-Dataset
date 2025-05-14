import pytest
from src.workflow_system import WorkflowBuilder, WorkflowError, InvalidActionError # Corrected import
from src.workflow_system import actions # Import action constants

# Basic tests will be added in a subsequent subtask (e.g., 8.2 or 8.8)

# Example placeholder test (can be removed later)
# def test_workflow_builder_initialization():
#     builder = WorkflowBuilder(workflow_name="Test Flow")
#     assert builder.workflow_name == "Test Flow"
#     assert builder.build() == {"name": "Test Flow", "steps": []}

# def test_workflow_builder_empty_name_fail():
#     with pytest.raises(ValueError): # Or WorkflowError when defined 

def test_workflow_builder_initialization():
    """Test basic initialization and build of an empty workflow."""
    builder = WorkflowBuilder(workflow_name="TestFlow_Init")
    assert builder.workflow_name == "TestFlow_Init"
    assert builder.build() == {"name": "TestFlow_Init", "steps": []}

def test_workflow_builder_empty_name_fail():
    """Test that initializing with an empty name raises WorkflowError."""
    with pytest.raises(WorkflowError, match="Workflow name must be a non-empty string."):
        WorkflowBuilder(workflow_name="")

def test_workflow_builder_invalid_name_type_fail():
    """Test that initializing with a non-string name raises WorkflowError."""
    with pytest.raises(WorkflowError, match="Workflow name must be a non-empty string."):
        WorkflowBuilder(workflow_name=123) # type: ignore

# --- Test individual action methods ---

def test_navigate_action():
    builder = WorkflowBuilder(workflow_name="NavFlow")
    builder.navigate(url="https://example.com")
    expected_step = {"type": "action", "actionType": actions.NAVIGATE, "url": "https://example.com"}
    assert builder._steps == [expected_step]
    assert builder.build()["steps"] == [expected_step]

def test_navigate_invalid_url():
    builder = WorkflowBuilder(workflow_name="NavFail")
    with pytest.raises(InvalidActionError, match="URL must be a non-empty string for navigate action."):
        builder.navigate(url="")
    with pytest.raises(InvalidActionError, match="URL must be a non-empty string for navigate action."):
        builder.navigate(url=None) # type: ignore

def test_click_action():
    builder = WorkflowBuilder(workflow_name="ClickFlow")
    builder.click(selector="#button1")
    expected_step1 = {"type": "action", "actionType": actions.CLICK, "selector": "#button1"}
    assert builder._steps == [expected_step1]

    builder.click(selector=".item", text_content_match="Submit")
    expected_step2 = {"type": "action", "actionType": actions.CLICK, "selector": ".item", "textContentMatch": "Submit"}
    assert builder._steps == [expected_step1, expected_step2]
    assert builder.build()["steps"] == [expected_step1, expected_step2]

def test_click_invalid_selector():
    builder = WorkflowBuilder(workflow_name="ClickFail")
    with pytest.raises(InvalidActionError, match="Selector must be a non-empty string for click action."):
        builder.click(selector="")
    with pytest.raises(InvalidActionError, match="text_content_match must be a string if provided."):
        builder.click(selector="#id", text_content_match=123) # type: ignore

def test_type_text_action():
    builder = WorkflowBuilder(workflow_name="TypeFlow")
    builder.type_text(selector="input[name=q]", text_to_type="hello world")
    expected_step1 = {"type": "action", "actionType": actions.TYPE, "selector": "input[name=q]", "text": "hello world"}
    assert builder._steps == [expected_step1]

    builder.type_text(selector="textarea", text_to_type="multi\nline", clear_before_type=True)
    expected_step2 = {"type": "action", "actionType": actions.TYPE, "selector": "textarea", "text": "multi\nline", "clearBefore": True}
    assert builder._steps == [expected_step1, expected_step2]

def test_type_text_invalid_params():
    builder = WorkflowBuilder(workflow_name="TypeFail")
    with pytest.raises(InvalidActionError, match="Selector must be a non-empty string for type_text action."):
        builder.type_text(selector="", text_to_type="abc")
    with pytest.raises(InvalidActionError, match="Text to type must be a string for type_text action."):
        builder.type_text(selector="#id", text_to_type=123) # type: ignore

def test_wait_for_selector_action():
    builder = WorkflowBuilder(workflow_name="WaitFlow")
    builder.wait_for_selector(selector="#dynamic-content", timeout=5000, visible=True)
    expected_step = {"type": "action", "actionType": actions.WAIT_FOR_SELECTOR, "selector": "#dynamic-content", "timeout": 5000, "visible": True}
    assert builder._steps == [expected_step]

    builder.wait_for_selector(selector=".loaded") # Default timeout and visible
    expected_step2 = {"type": "action", "actionType": actions.WAIT_FOR_SELECTOR, "selector": ".loaded", "timeout": 30000}
    assert builder._steps[1] == expected_step2

def test_wait_for_time_action():
    builder = WorkflowBuilder(workflow_name="WaitTimeFlow")
    builder.wait_for_time(duration_ms=1500)
    expected_step = {"type": "action", "actionType": actions.WAIT_FOR_TIME, "duration": 1500}
    assert builder._steps == [expected_step]

def test_extract_text_action():
    builder = WorkflowBuilder(workflow_name="ExtractFlow")
    builder.extract_text(selector="h1.title", variable_name="pageTitle")
    expected_step1 = {"type": "action", "actionType": actions.EXTRACT_TEXT, "selector": "h1.title", "variableName": "pageTitle"}
    assert builder._steps == [expected_step1]

    builder.extract_text(selector="img.logo", attribute="src", variable_name="logoUrl")
    expected_step2 = {"type": "action", "actionType": actions.EXTRACT_TEXT, "selector": "img.logo", "attribute": "src", "variableName": "logoUrl"}
    assert builder._steps == [expected_step1, expected_step2]

def test_scroll_action():
    builder = WorkflowBuilder(workflow_name="ScrollFlow")
    builder.scroll(direction="down", amount_pixels=500)
    expected_step1 = {"type": "action", "actionType": actions.SCROLL, "direction": "down", "amount": 500}
    assert builder._steps == [expected_step1]

    builder.scroll(direction="to_element", selector_to_element="#footer")
    expected_step2 = {"type": "action", "actionType": actions.SCROLL, "direction": "to_element", "selector": "#footer"}
    assert builder._steps == [expected_step1, expected_step2]

    builder.scroll(direction="page_up")
    expected_step3 = {"type": "action", "actionType": actions.SCROLL, "direction": "page_up"}
    assert builder._steps == [expected_step1, expected_step2, expected_step3]

def test_scroll_invalid_direction():
    builder = WorkflowBuilder(workflow_name="ScrollFail")
    with pytest.raises(InvalidActionError, match="Invalid scroll direction 'diagonal'"):
        builder.scroll(direction="diagonal")

def test_assert_element_action():
    builder = WorkflowBuilder(workflow_name="AssertElemFlow")
    builder.assert_element(selector="#my-id", exists=True, is_visible=True)
    expected_step1 = {"type": "action", "actionType": actions.ASSERT_ELEMENT, "selector": "#my-id", "exists": True, "isVisible": True}
    assert builder._steps == [expected_step1]

    builder.assert_element(selector=".optional", exists=False)
    expected_step2 = {"type": "action", "actionType": actions.ASSERT_ELEMENT, "selector": ".optional", "exists": False}
    assert builder._steps[1] == expected_step2 

def test_assert_text_action():
    builder = WorkflowBuilder(workflow_name="AssertTextFlow")
    builder.assert_text(text_to_find="Welcome User!", selector="h1", should_contain=True, is_case_sensitive=False)
    expected_step1 = {"type": "action", "actionType": actions.ASSERT_TEXT, "text": "Welcome User!", "selector": "h1", "contains": True, "caseSensitive": False}
    assert builder._steps == [expected_step1]

    builder.assert_text(text_to_find="Error 404", should_contain=False) # Page-level check
    expected_step2 = {"type": "action", "actionType": actions.ASSERT_TEXT, "text": "Error 404", "contains": False, "caseSensitive": False}
    assert builder._steps[1] == expected_step2


def test_build_method():
    builder = WorkflowBuilder(workflow_name="FullBuildTest")
    builder.navigate("https://a.com")
    builder.click("#b")
    workflow_payload = builder.build()
    assert workflow_payload["name"] == "FullBuildTest"
    assert len(workflow_payload["steps"]) == 2
    assert workflow_payload["steps"][0]["actionType"] == actions.NAVIGATE
    assert workflow_payload["steps"][1]["actionType"] == actions.CLICK

# Test for building an empty workflow (currently allowed, might change)
# def test_build_empty_workflow():
#     builder = WorkflowBuilder(workflow_name="EmptyTest")
#     payload = builder.build()
#     assert payload["name"] == "EmptyTest"
#     assert payload["steps"] == []
#     # If we later decide to raise WorkflowValidationError for empty steps:
#     # with pytest.raises(WorkflowValidationError, match="Cannot build an empty workflow"):
#     #     builder.build() 