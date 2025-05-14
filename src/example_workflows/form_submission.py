from src.workflow_system import WorkflowBuilder
from typing import List, Dict, Optional

def create_form_submission_workflow(
    workflow_name: str,
    form_url: str,
    fields: List[Dict[str, str]],  # List of dicts, each with "selector" and "value"
    submit_selector: str,
    success_indicator_selector: Optional[str] = None, # Selector to wait for after submission
    pre_form_cookie_banner_selector: Optional[str] = None, 
    pre_form_cookie_accept_selector: Optional[str] = None,
):
    """
    Creates a generalized form submission workflow.
    Fills specified fields and clicks a submit button.
    Optionally handles a cookie banner before interacting with the form.
    Optionally waits for a success indicator after submission.
    """
    builder = WorkflowBuilder(workflow_name)
    builder.navigate(form_url)

    if pre_form_cookie_banner_selector and pre_form_cookie_accept_selector:
        builder.wait_for_selector(pre_form_cookie_banner_selector, timeout=5000)
        builder.click(pre_form_cookie_accept_selector)
        builder.wait_for_time(500) # Give banner time to disappear

    for field_info in fields:
        if not isinstance(field_info, dict) or "selector" not in field_info or "value" not in field_info:
            raise ValueError("Each field in fields list must be a dict with 'selector' and 'value' keys.")
        
        selector = field_info["selector"]
        value_to_type = field_info["value"]
        
        builder.wait_for_selector(selector, timeout=10000) # Wait for field to be present
        # Consider adding clear_before_type=True as a default or option here
        builder.type_text(selector, value_to_type, clear_before_type=True) 

    builder.click(submit_selector)

    if success_indicator_selector:
        builder.wait_for_selector(success_indicator_selector, timeout=15000) # Wait longer for post-submission page load
    
    return builder # Returns the builder instance

if __name__ == '__main__':
    # Example Usage

    # Simple Login Form Example (illustrative selectors)
    login_fields = [
        {"selector": "#username", "value": "testuser"},
        {"selector": "#password", "value": "securepassword123"}
    ]
    login_workflow_payload = create_form_submission_workflow(
        workflow_name="example_login_form",
        form_url="https://example.com/login",
        fields=login_fields,
        submit_selector="button[type=submit]",
        success_indicator_selector=".user-dashboard-greeting" # e.g., a welcome message on the next page
    ).build()
    print("--- Login Form Workflow Example ---")
    print(login_workflow_payload)

    # Contact Form Example (illustrative selectors)
    contact_fields = [
        {"selector": "input[name=fullname]", "value": "Jane Doe"},
        {"selector": "input[name=email]", "value": "jane.doe@example.com"},
        {"selector": "textarea[name=message]", "value": "Hello, I have a question about your services."}
    ]
    contact_workflow_payload = create_form_submission_workflow(
        workflow_name="example_contact_form",
        form_url="https://example.com/contact-us",
        fields=contact_fields,
        submit_selector="#submit-contact-form",
        success_indicator_selector=".thank-you-message",
        pre_form_cookie_banner_selector="#cookie-notice",
        pre_form_cookie_accept_selector="#cookie-accept-button"
    ).build()
    print("\n--- Contact Form Workflow Example (with cookie handling) ---")
    print(contact_workflow_payload) 