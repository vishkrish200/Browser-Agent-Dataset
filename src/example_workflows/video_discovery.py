from src.workflow_system import WorkflowBuilder

# For PRD consistency, let's make it a directly usable payload as a constant
# but also provide the function if users want to build it with slight variations.

EXAMPLE_WORKFLOW_NAME = "youtube_video_discovery_v1"

def get_youtube_video_discovery_workflow(workflow_name: str = EXAMPLE_WORKFLOW_NAME):
    """
    Builds a workflow to navigate YouTube, search for a video, click it,
    and extract its title.
    """
    return WorkflowBuilder(workflow_name) \
        .navigate("https://youtube.com") \
        .wait_for_selector("input#search", timeout=10000) \
        .type_text("input#search", "lofi hip hop radio - beats to relax/study to") \
        .click("button#search-icon-legacy") \
        .wait_for_selector("ytd-video-renderer a#video-title", timeout=20000) \
        .click("ytd-video-renderer a#video-title") \
        .wait_for_selector("h1.title yt-formatted-string", timeout=10000) \
        .extract_text("h1.title yt-formatted-string", variable_name="videoTitle") \
        .wait_for_time(5000) # Wait 5 seconds as if watching a bit
        # .build() # Build is called by the orchestrator typically, or user if they want the dict

# Example of how it might be stored if pre-built:
# VIDEO_DISCOVERY_WORKFLOW_PAYLOAD = get_youtube_video_discovery_workflow().build()

if __name__ == '__main__':
    # Example of building and printing the workflow definition
    # Note: To run this directly, ensure PYTHONPATH includes the project root or install the package.
    # Adjust import if running from project root: from src.workflow_system import WorkflowBuilder
    
    # Test building the workflow
    youtube_workflow_builder = get_youtube_video_discovery_workflow()
    youtube_workflow_payload = youtube_workflow_builder.build()
    
    print(f"Workflow Name: {youtube_workflow_payload['name']}")
    print("Steps:")
    for i, step in enumerate(youtube_workflow_payload['steps']):
        print(f"  {i+1}. Type: {step['actionType']}")
        params_str = ", ".join([f"{k}='{v}'" for k, v in step.items() if k not in ['type', 'actionType']])
        print(f"     Params: {params_str}")

    # Example of using the builder directly (as in PRD Task 8 example)
    # Note the PRD example calls .build() at the end.
    YOUTUBE_EXAMPLE_FROM_PRD = WorkflowBuilder("video_discovery_v1_prd_style") \
        .navigate("https://youtube.com") \
        .wait_for_selector("#search", timeout=10000) \
        .type_text("#search", "lofi music") \
        .click("#search-icon-legacy") \
        .wait_for_selector("#video-title", timeout=10000) \
        .click("#video-title") \
        .wait_for_selector(".ytp-play-button", timeout=10000) \
        .build()
    
    print("\nPRD Style Example Output:")
    print(YOUTUBE_EXAMPLE_FROM_PRD) 