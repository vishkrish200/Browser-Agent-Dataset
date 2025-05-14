from src.workflow_system import WorkflowBuilder
from typing import Optional

def create_general_search_workflow(
    workflow_name: str,
    search_engine_url: str,
    search_input_selector: str,
    search_query: str,
    search_button_selector: str,
    results_selector: str, # Selector to confirm search results page has loaded
    # Optional parameters for more complex searches
    pre_search_cookie_banner_selector: Optional[str] = None, 
    pre_search_cookie_accept_selector: Optional[str] = None,
    # Add other params like pagination handling selectors if needed later
):
    """
    Creates a generalized search workflow for a given search engine.
    Handles optional cookie banner dismissal.
    """
    builder = WorkflowBuilder(workflow_name)
    builder.navigate(search_engine_url)

    if pre_search_cookie_banner_selector and pre_search_cookie_accept_selector:
        # Optional: wait for cookie banner and click accept
        # This assumes a simple click, might need more complex logic for some sites
        builder.wait_for_selector(pre_search_cookie_banner_selector, timeout=5000) # Short timeout for banner
        builder.click(pre_search_cookie_accept_selector)
        # Add a small fixed wait after click if needed for banner to disappear
        builder.wait_for_time(500) 

    builder.wait_for_selector(search_input_selector, timeout=10000)
    builder.type_text(search_input_selector, search_query, clear_before_type=True)
    builder.click(search_button_selector)
    builder.wait_for_selector(results_selector, timeout=15000) # Wait a bit longer for results
    
    # Placeholder for extracting results or further interaction
    # builder.extract_text(f"{results_selector} .result-title", variable_name="first_result_title")

    return builder # Returns the builder instance, .build() is called by orchestrator

if __name__ == '__main__':
    # Example Usage
    
    # Google Search Example (selectors are illustrative and may change)
    google_search_flow = create_general_search_workflow(
        workflow_name="google_search_example",
        search_engine_url="https://www.google.com",
        search_input_selector="textarea[name=q]",
        search_query="large language models",
        search_button_selector="input[name=btnK]", # This might be complex due to multiple buttons
        results_selector="#search", # Main container for search results
        pre_search_cookie_banner_selector="#CXQnmb", # Example cookie banner ID
        pre_search_cookie_accept_selector="#L2AGLb"  # Example cookie accept button ID
    ).build()
    print("--- Google Search Workflow ---")
    print(google_search_flow)

    # DuckDuckGo Search Example (selectors are illustrative)
    ddg_search_flow = create_general_search_workflow(
        workflow_name="duckduckgo_search_example",
        search_engine_url="https://duckduckgo.com",
        search_input_selector="#search_form_input_homepage",
        search_query="AI programming assistants",
        search_button_selector="#search_button_homepage",
        results_selector=".results--main #links"
    ).build()
    print("\n--- DuckDuckGo Search Workflow ---")
    print(ddg_search_flow) 