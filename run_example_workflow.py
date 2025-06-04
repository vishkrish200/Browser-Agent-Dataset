import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

from src.orchestrator import Orchestrator
# REMOVED: from src.example_workflows.general_search import create_general_search_workflow

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S%z'
)

# Set src.orchestrator to DEBUG level
logging.getLogger("src.orchestrator").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
DEFAULT_LOG_EXTRA_SCRIPT = {"script_name": "run_example_workflow.py"}

# Load environment variables from the src/.env file
# Adjusted path to be relative to this script's location, assuming it's in the project root
# and .env is in src/
script_dir = os.path.dirname(__file__)
env_path = os.path.join(script_dir, "src", ".env")

if not os.path.exists(env_path):
    logger.warning(f".env file not found at {env_path}. Trying project root .env")
    env_path = os.path.join(script_dir, ".env") # Try .env in the same dir as script (project root)

if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)
    logger.info(f"Loaded .env file from: {env_path}")
else:
    logger.warning(f".env file not found at {env_path} or src/.env. Relying on shell-exported variables.")

def safe_key_display(key_name: str) -> str:
    value = os.environ.get(key_name)
    if not value:
        return "[not set]"
    if len(value) <= 8:
        return "[key too short or already partial]"
    return f"{value[:5]}...{value[-4:]}"

logger.info(
    "Initial Environment Check:",
    extra={
        "BROWSERBASE_PROJECT_ID": os.environ.get("BROWSERBASE_PROJECT_ID", "[not set]"),
        "BROWSERBASE_API_KEY": safe_key_display("BROWSERBASE_API_KEY"),
        "OPENAI_API_KEY": safe_key_display("OPENAI_API_KEY"),
        "MODEL_NAME": os.environ.get("MODEL_NAME", "[not set, will default in Orchestrator]")
    }
)

if not os.environ.get("OPENAI_API_KEY"):
    logger.error("CRITICAL: OPENAI_API_KEY environment variable is not set. Required for browser-use AI actions.")
    sys.exit(1)
if not os.environ.get("BROWSERBASE_API_KEY") or not os.environ.get("BROWSERBASE_PROJECT_ID"):
    logger.error("CRITICAL: BROWSERBASE_API_KEY or BROWSERBASE_PROJECT_ID not set. Required for Browserbase.")
    sys.exit(1)

async def run_test(orchestrator: Orchestrator, prompt_text: str):
    """
    Runs a test by executing a dynamic task through the orchestrator.
    """
    try:
        logger.info("Starting dynamic task execution test...", extra=DEFAULT_LOG_EXTRA_SCRIPT)
        
        # Ensure API keys and Project ID are loaded
        # These are now primarily used by the Orchestrator and its components
        # but good to have them available if direct client use is needed.
        browserbase_api_key = orchestrator.config.get("browserbase_api_key")
        browserbase_project_id = orchestrator.config.get("browserbase_project_id")
        stagehand_api_key = orchestrator.config.get("stagehand_api_key") # Though Stagehand is local now
        openai_api_key = orchestrator.config.get("openai_api_key")

        if not all([browserbase_api_key, browserbase_project_id, openai_api_key]):
            logger.error(
                "One or more critical environment variables (Browserbase API Key/Project ID, OpenAI API Key) are missing.",
                extra=DEFAULT_LOG_EXTRA_SCRIPT
            )
            logger.info(f"Loaded Browserbase API Key: {safe_key_display(browserbase_api_key)}")
            logger.info(f"Loaded Browserbase Project ID: {browserbase_project_id}")
            logger.info(f"Loaded Stagehand API Key: {safe_key_display(stagehand_api_key)}")
            logger.info(f"Loaded OpenAI API Key: {safe_key_display(openai_api_key)}")
            return

        logger.info("All necessary API keys and Project ID seem to be loaded into orchestrator config.")
        
        # Define the dynamic task prompt
        # This is now passed as an argument

        if not prompt_text:
            logger.error("Dynamic task prompt is empty. Cannot proceed.", extra=DEFAULT_LOG_EXTRA_SCRIPT)
            return

        logger.info(f"Executing dynamic task with prompt: '{prompt_text}'", extra=DEFAULT_LOG_EXTRA_SCRIPT)
        
        # Run the dynamic task
        final_dataset_trace = await orchestrator.execute_dynamic_task(
            task_prompt=prompt_text, # MODIFIED: Changed 'prompt' to 'task_prompt'
            num_sessions=1 # For now, just one session
        )

        logger.info(f"Dynamic task execution completed. Dataset trace has {len(final_dataset_trace)} entries.")
        
        # Print the final dataset trace for inspection
        logger.info("Final Dataset Trace:")
        import json
        for i, entry in enumerate(final_dataset_trace):
            logger.info(f"Trace Entry {i+1}:")
            # Attempt to pretty-print. If it's a list of dicts (from multi-session), handle that.
            if isinstance(entry, list):
                for sub_i, sub_entry in enumerate(entry):
                    logger.info(f"  Sub-Trace {sub_i+1}:")
                    try:
                        logger.info(json.dumps(sub_entry, indent=2, default=str)) # Use default=str for non-serializable
                    except TypeError:
                        logger.info(str(sub_entry)) # Fallback to plain string representation
            elif isinstance(entry, dict):
                try:
                    logger.info(json.dumps(entry, indent=2, default=str))
                except TypeError:
                    logger.info(str(entry))
            else:
                logger.info(str(entry))

    except Exception as e:
        logger.error(f"An error occurred during the test run: {e}", exc_info=True, extra=DEFAULT_LOG_EXTRA_SCRIPT)

async def main():
    # Orchestrator config can be loaded from environment variables or passed directly
    # For this example, we'll rely on environment variables for Browserbase/OpenAI keys
    # and Orchestrator's defaults for other settings.
    config_values = { 
        # "browserbase_api_key": os.environ.get("BROWSERBASE_API_KEY"),
        # "browserbase_project_id": os.environ.get("BROWSERBASE_PROJECT_ID"),
        # "openai_api_key": os.environ.get("OPENAI_API_KEY"),
        # "llm_model_name": "gpt-4-turbo-preview", # Example override
    }
    orchestrator = Orchestrator(config=config_values)
    logger.info("Orchestrator initialized.", extra=DEFAULT_LOG_EXTRA_SCRIPT)

    # SIMPLIFIED PROMPT
    dynamic_task_prompt = "Go to google.com, search for 'llms', and click on the first search result link" 

    try:
        await run_test(orchestrator, dynamic_task_prompt)
    finally:
        logger.info("Closing orchestrator...", extra=DEFAULT_LOG_EXTRA_SCRIPT)
        await orchestrator.close()

if __name__ == "__main__":
    asyncio.run(main()) # Call the async main function 