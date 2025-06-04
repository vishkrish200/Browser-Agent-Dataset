from src.stagehand_client import WorkflowBuilder
from typing import Optional

def create_general_search_workflow(search_query: str, workflow_name: str = "dynamic_google_search") -> WorkflowBuilder:
    builder = WorkflowBuilder(workflow_name=workflow_name)

    # Remove explicit navigation: builder.navigate("https://www.google.com")
    # The AI agent should handle navigation as part of the broader task.

    # Use browser-use AI to perform the entire search task dynamically
    builder.add_custom_step({
        "action": "ai_action",
        "prompt": f"Go to google.com and search for '{search_query}'. Confirm that the search results page has loaded.",
        "timeout_ms": 90000  # AI actions for multi-step tasks might need longer timeouts
    })

    return builder

if __name__ == '__main__':
    # Example Usage
    
    # Google Search Example
    google_search_flow = create_general_search_workflow(
        search_query="large language models"
    ).build()
    print("--- Google Search Workflow (Dynamic AI) ---")
    print(google_search_flow)

    # DuckDuckGo Search Example (Illustrative - prompt would need to change for DDG)
    # For a different search engine, the prompt would change accordingly.
    # ddg_search_flow = create_general_search_workflow(
    #     search_query="AI programming assistants",
    #     # workflow_name="dynamic_ddg_search" # Optional: if you want a different name
    # ).build()
    # print("\\n--- DuckDuckGo Search Workflow (Dynamic AI) ---")
    # print(ddg_search_flow) 