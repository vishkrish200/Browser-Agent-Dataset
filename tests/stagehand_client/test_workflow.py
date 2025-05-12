"""Tests for stagehand_client.workflow"""

import pytest
from stagehand_client.workflow import WorkflowBuilder
from stagehand_client.types import WorkflowStep # Assuming WorkflowStep is imported for type checking if needed

# Test WorkflowBuilder Instantiation
def test_workflow_builder_instantiation():
    """Test WorkflowBuilder instantiation with a valid name."""
    builder = WorkflowBuilder(workflow_name="TestWorkflow")
    assert builder.workflow_name == "TestWorkflow"
    assert builder._steps == []

@pytest.mark.parametrize(
    "invalid_name, error_message",
    [
        (None, "Workflow name must be a non-empty string."),
        ("", "Workflow name must be a non-empty string."),
        (123, "Workflow name must be a non-empty string."),
    ],
)
def test_workflow_builder_instantiation_invalid_name(invalid_name, error_message):
    """Test WorkflowBuilder instantiation with invalid names."""
    with pytest.raises(ValueError, match=error_message):
        WorkflowBuilder(workflow_name=invalid_name)

# Test Fluent Builder Methods
def test_workflow_builder_navigate():
    builder = WorkflowBuilder(workflow_name="NavFlow")
    builder.navigate(url="https://example.com")
    assert len(builder._steps) == 1
    assert builder._steps[0] == {"action": "navigate", "url": "https://example.com"}

@pytest.mark.parametrize("invalid_url", [None, "", 123])
def test_workflow_builder_navigate_invalid_url(invalid_url):
    builder = WorkflowBuilder(workflow_name="NavFlow")
    with pytest.raises(ValueError, match="URL for navigate action must be a non-empty string."):
        builder.navigate(url=invalid_url)

def test_workflow_builder_click():
    builder = WorkflowBuilder(workflow_name="ClickFlow")
    builder.click(selector="#myButton")
    assert len(builder._steps) == 1
    assert builder._steps[0] == {"action": "click", "selector": "#myButton"}

@pytest.mark.parametrize("invalid_selector", [None, "", 123])
def test_workflow_builder_click_invalid_selector(invalid_selector):
    builder = WorkflowBuilder(workflow_name="ClickFlow")
    with pytest.raises(ValueError, match="Selector for click action must be a non-empty string."):
        builder.click(selector=invalid_selector)

def test_workflow_builder_type_text():
    builder = WorkflowBuilder(workflow_name="TypeFlow")
    builder.type_text(selector="input[name='q']", text="hello world")
    assert len(builder._steps) == 1
    assert builder._steps[0] == {"action": "type_text", "selector": "input[name='q']", "text": "hello world"}
    # Test with empty text, which is allowed
    builder.type_text(selector="#otherInput", text="")
    assert len(builder._steps) == 2
    assert builder._steps[1] == {"action": "type_text", "selector": "#otherInput", "text": ""}

@pytest.mark.parametrize("invalid_selector", [None, "", 123])
def test_workflow_builder_type_text_invalid_selector(invalid_selector):
    builder = WorkflowBuilder(workflow_name="TypeFlow")
    with pytest.raises(ValueError, match="Selector for type_text action must be a non-empty string."):
        builder.type_text(selector=invalid_selector, text="some text")

@pytest.mark.parametrize("invalid_text", [None, 123]) # Empty string is valid for text
def test_workflow_builder_type_text_invalid_text(invalid_text):
    builder = WorkflowBuilder(workflow_name="TypeFlow")
    with pytest.raises(ValueError, match="Text for type_text action must be a string."):
        builder.type_text(selector="#someSelector", text=invalid_text)

def test_workflow_builder_wait_for_selector():
    builder = WorkflowBuilder(workflow_name="WaitFlow")
    builder.wait_for_selector(selector=".ready", timeout_ms=5000)
    assert len(builder._steps) == 1
    assert builder._steps[0] == {"action": "wait_for_selector", "selector": ".ready", "timeout_ms": 5000}
    builder.wait_for_selector(selector="#another") # Test without optional timeout
    assert len(builder._steps) == 2
    assert builder._steps[1] == {"action": "wait_for_selector", "selector": "#another"}

@pytest.mark.parametrize("invalid_selector", [None, "", 123])
def test_workflow_builder_wait_for_selector_invalid_selector(invalid_selector):
    builder = WorkflowBuilder(workflow_name="WaitFlow")
    with pytest.raises(ValueError, match="Selector for wait_for_selector action must be a non-empty string."):
        builder.wait_for_selector(selector=invalid_selector)

@pytest.mark.parametrize("invalid_timeout", [-1, "not_an_int"])
def test_workflow_builder_wait_for_selector_invalid_timeout(invalid_timeout):
    builder = WorkflowBuilder(workflow_name="WaitFlow")
    with pytest.raises(ValueError, match="timeout_ms must be a non-negative integer if provided."):
        builder.wait_for_selector(selector="#valid", timeout_ms=invalid_timeout)

def test_workflow_builder_scroll_to_element():
    builder = WorkflowBuilder(workflow_name="ScrollFlow")
    builder.scroll_to_element(selector="footer")
    assert len(builder._steps) == 1
    assert builder._steps[0] == {"action": "scroll_to_element", "selector": "footer"}

@pytest.mark.parametrize("invalid_selector", [None, "", 123])
def test_workflow_builder_scroll_to_element_invalid_selector(invalid_selector):
    builder = WorkflowBuilder(workflow_name="ScrollFlow")
    with pytest.raises(ValueError, match="Selector for scroll_to_element action must be a non-empty string."):
        builder.scroll_to_element(selector=invalid_selector)

def test_workflow_builder_get_text():
    builder = WorkflowBuilder(workflow_name="GetTextFlow")
    builder.get_text(selector="h1")
    assert len(builder._steps) == 1
    assert builder._steps[0] == {"action": "get_text", "selector": "h1"}

@pytest.mark.parametrize("invalid_selector", [None, "", 123])
def test_workflow_builder_get_text_invalid_selector(invalid_selector):
    builder = WorkflowBuilder(workflow_name="GetTextFlow")
    with pytest.raises(ValueError, match="Selector for get_text action must be a non-empty string."):
        builder.get_text(selector=invalid_selector)

def test_workflow_builder_get_attribute():
    builder = WorkflowBuilder(workflow_name="GetAttrFlow")
    builder.get_attribute(selector="img#logo", attribute_name="src")
    assert len(builder._steps) == 1
    assert builder._steps[0] == {"action": "get_attribute", "selector": "img#logo", "attribute_name": "src"}

@pytest.mark.parametrize("invalid_selector", [None, "", 123])
def test_workflow_builder_get_attribute_invalid_selector(invalid_selector):
    builder = WorkflowBuilder(workflow_name="GetAttrFlow")
    with pytest.raises(ValueError, match="Selector for get_attribute action must be a non-empty string."):
        builder.get_attribute(selector=invalid_selector, attribute_name="href")

@pytest.mark.parametrize("invalid_attr_name", [None, "", 123])
def test_workflow_builder_get_attribute_invalid_attribute_name(invalid_attr_name):
    builder = WorkflowBuilder(workflow_name="GetAttrFlow")
    with pytest.raises(ValueError, match="Attribute name for get_attribute action must be a non-empty string."):
        builder.get_attribute(selector="a.link", attribute_name=invalid_attr_name)

# Test add_custom_step
def test_workflow_builder_add_custom_step():
    builder = WorkflowBuilder(workflow_name="CustomFlow")
    custom_step: WorkflowStep = {"action": "navigate", "url": "https://custom.example.com"}
    builder.add_custom_step(step_data=custom_step)
    assert len(builder._steps) == 1
    assert builder._steps[0] == custom_step

@pytest.mark.parametrize(
    "invalid_step_data, error_message",
    [
        (None, "Custom step_data must be a dictionary."),
        ("not_a_dict", "Custom step_data must be a dictionary."),
        ({}, "Custom step_data must contain a non-empty 'action' key."),
        ({"url": "some_url"}, "Custom step_data must contain a non-empty 'action' key."),
        ({"action": ""}, "Custom step_data must contain a non-empty 'action' key."),
        ({"action": None}, "Custom step_data must contain a non-empty 'action' key."),
    ]
)
def test_workflow_builder_add_custom_step_invalid_data(invalid_step_data, error_message):
    builder = WorkflowBuilder(workflow_name="CustomFlow")
    with pytest.raises(ValueError, match=error_message):
        builder.add_custom_step(step_data=invalid_step_data) # type: ignore

# Test build method
def test_workflow_builder_build():
    builder = WorkflowBuilder(workflow_name="FullWorkflow")
    builder.navigate(url="https://start.com") \
           .click(selector="#go") \
           .type_text(selector="input", text="search")
    
    expected_workflow = {
        "name": "FullWorkflow",
        "steps": [
            {"action": "navigate", "url": "https://start.com"},
            {"action": "click", "selector": "#go"},
            {"action": "type_text", "selector": "input", "text": "search"}
        ]
    }
    assert builder.build() == expected_workflow

def test_workflow_builder_build_empty():
    builder = WorkflowBuilder(workflow_name="EmptyWorkflow")
    expected_workflow = {
        "name": "EmptyWorkflow",
        "steps": []
    }
    assert builder.build() == expected_workflow

# Test chaining
def test_workflow_builder_chaining():
    builder = WorkflowBuilder(workflow_name="ChainFlow")
    result = builder.navigate("https://a.com").click("#b").type_text("#c", "d")
    assert result is builder # Ensure methods return self for chaining
    assert len(builder._steps) == 3 