"""Tests for stagehand_client.utils"""

import pytest
import json
import os
from unittest import mock

from stagehand_client.utils import load_workflow_from_dict, load_workflow_from_json
from stagehand_client.workflow import WorkflowBuilder # Needed for type assertion and creating expected objects

# Tests for load_workflow_from_dict
def test_load_workflow_from_dict_valid():
    valid_definition = {
        "name": "MyDictWorkflow",
        "steps": [
            {"action": "navigate", "url": "https://dict.example.com"},
            {"action": "click", "selector": "#submit"}
        ]
    }
    builder = load_workflow_from_dict(valid_definition)
    assert isinstance(builder, WorkflowBuilder)
    assert builder.workflow_name == "MyDictWorkflow"
    assert len(builder._steps) == 2
    assert builder._steps[0] == {"action": "navigate", "url": "https://dict.example.com"}
    assert builder._steps[1] == {"action": "click", "selector": "#submit"}

@pytest.mark.parametrize(
    "invalid_definition, error_message_match",
    [
        (None, "Workflow definition must be a dictionary."),
        ("not_a_dict", "Workflow definition must be a dictionary."),
        ({}, "Workflow definition must contain a non-empty string 'name'."),
        ({"name": ""}, "Workflow definition must contain a non-empty string 'name'."),
        ({"name": 123}, "Workflow definition must contain a non-empty string 'name'."),
        ({"name": "ValidName"}, "Workflow definition must contain a list of 'steps'."),
        ({"name": "ValidName", "steps": "not_a_list"}, "Workflow definition must contain a list of 'steps'."),
        ({"name": "ValidName", "steps": [{}]}, "Step at index 0 is invalid: must be a dict with an 'action' key."),
        ({"name": "ValidName", "steps": [{"action": "navigate"}, {"selector": "#id"}]}, "Step at index 1 is invalid: must be a dict with an 'action' key."),
    ]
)
def test_load_workflow_from_dict_invalid(invalid_definition, error_message_match):
    with pytest.raises(ValueError, match=error_message_match):
        load_workflow_from_dict(invalid_definition)

# Tests for load_workflow_from_json
@pytest.fixture
def temp_workflow_file(tmp_path):
    def _create_file(content):
        file_path = tmp_path / "workflow.json"
        with open(file_path, 'w') as f:
            if isinstance(content, dict) or content is None: # Handle None by dumping 'null'
                json.dump(content, f)
            elif isinstance(content, str): # For writing intentionally malformed JSON strings
                f.write(content)
            else:
                # Safety net, though test cases should provide dict, None, or str
                raise TypeError(f"Unsupported content type for temp_workflow_file: {type(content)}")
        return file_path
    return _create_file

def test_load_workflow_from_json_valid(temp_workflow_file):
    valid_definition = {
        "name": "MyJsonWorkflow",
        "steps": [
            {"action": "navigate", "url": "https://json.example.com"},
            {"action": "click", "selector": "#confirm"}
        ]
    }
    file_path = temp_workflow_file(valid_definition)
    builder = load_workflow_from_json(str(file_path))
    assert isinstance(builder, WorkflowBuilder)
    assert builder.workflow_name == "MyJsonWorkflow"
    assert len(builder._steps) == 2
    assert builder._steps[0] == {"action": "navigate", "url": "https://json.example.com"}
    assert builder._steps[1] == {"action": "click", "selector": "#confirm"}

def test_load_workflow_from_json_file_not_found():
    with pytest.raises(FileNotFoundError, match="Workflow JSON file not found at: non_existent_workflow.json"):
        load_workflow_from_json("non_existent_workflow.json")

def test_load_workflow_from_json_invalid_json(temp_workflow_file):
    file_path = temp_workflow_file("this is not valid json{")
    with pytest.raises(json.JSONDecodeError):
        load_workflow_from_json(str(file_path))

@pytest.mark.parametrize(
    "invalid_definition, error_message_match", # Reusing invalid definitions from dict tests
    [
        (None, "Workflow definition must be a dictionary."),
        # Skipping "not_a_dict" as json.load will fail before our validation for that specific string
        ({}, "Workflow definition must contain a non-empty string 'name'."),
        ({"name": ""}, "Workflow definition must contain a non-empty string 'name'."),
        ({"name": 123}, "Workflow definition must contain a non-empty string 'name'."),
        ({"name": "ValidName"}, "Workflow definition must contain a list of 'steps'."),
        ({"name": "ValidName", "steps": "not_a_list"}, "Workflow definition must contain a list of 'steps'."),
        ({"name": "ValidName", "steps": [{}]}, "Step at index 0 is invalid: must be a dict with an 'action' key."),
    ]
)
def test_load_workflow_from_json_invalid_structure(temp_workflow_file, invalid_definition, error_message_match):
    file_path = temp_workflow_file(invalid_definition)
    # For None, json.dump will write 'null', json.load will return None, 
    # then load_workflow_from_dict(None) will raise ValueError.
    if invalid_definition is None:
         with pytest.raises(ValueError, match="Workflow definition must be a dictionary."):
            load_workflow_from_json(str(file_path))
    else:
        with pytest.raises(ValueError, match=error_message_match):
            load_workflow_from_json(str(file_path)) 