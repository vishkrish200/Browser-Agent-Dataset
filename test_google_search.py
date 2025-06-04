import asyncio
import os
from dotenv import load_dotenv
import pathlib
from src.orchestrator import Orchestrator

async def main():
    # Load environment variables
    project_root_env_path = pathlib.Path('.').resolve() / '.env'
    if project_root_env_path.exists():
        load_dotenv(dotenv_path=project_root_env_path, override=True)
        print(f'Loaded .env from: {project_root_env_path}')
    else:
        print(f'.env not found at {project_root_env_path}. Using shell vars.')

    orchestrator = Orchestrator()
    print('Orchestrator instance created.')
    
    # Task to navigate to Google, search for LLMs, and click first link
    test_prompt = 'Go to google.com, search for "llms", and click on the first search result link'
    test_start_url = 'https://www.google.com'

    try:
        print(f'Running task: {test_prompt}')
        results = await orchestrator.execute_dynamic_task(
            task_prompt=test_prompt, 
            start_url=test_start_url, 
            num_sessions=1
        )
        print(f'Task completed. Results summary:')
        for i, result in enumerate(results):
            print(f'Session {i+1}: Status = {result.get("status")}, Dataset trace entries = {len(result.get("dataset_trace", []))}')
            if result.get('error'):
                print(f'  Error: {result["error"]}')
            if result.get('agent_summary'):
                print(f'  Agent Summary: {result["agent_summary"][:200]}...')
    except Exception as e:
        print(f'Error during execution: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await orchestrator.close()
        print('Orchestrator closed.')

if __name__ == "__main__":
    asyncio.run(main()) 