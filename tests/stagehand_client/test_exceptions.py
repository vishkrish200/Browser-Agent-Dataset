"""Tests for stagehand_client.exceptions"""

import pytest
from stagehand_client.exceptions import StagehandAPIError, StagehandError

def test_stagehand_api_error_str_representation():
    """Test the __str__ method of StagehandAPIError."""
    # Test with status code and response content
    error1 = StagehandAPIError(message="Auth failed", status_code=401, response_content="{\"detail\": \"Invalid API key\"}")
    expected_str1 = "API Error 401: Auth failed - {\"detail\": \"Invalid API key\"}"
    assert str(error1) == expected_str1

    # Test with status code but no response content
    error2 = StagehandAPIError(message="Not found", status_code=404)
    expected_str2 = "API Error 404: Not found - No additional content"
    assert str(error2) == expected_str2

    # Test with no status code (should behave like base StagehandError)
    error3 = StagehandAPIError(message="Network issue")
    expected_str3 = "Network issue"
    assert str(error3) == expected_str3

    # Test base StagehandError
    error4 = StagehandError("Generic client error")
    expected_str4 = "Generic client error"
    assert str(error4) == expected_str4 