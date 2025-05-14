import typer
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

app = typer.Typer(name="configure", help="Manage CLI and project configuration.", no_args_is_help=True)

ENV_EXAMPLE_CONTENT = """# .env - Fill in your actual values
# API Keys
BROWSERBASE_API_KEY=
STAGEHAND_API_KEY=

# S3 Configuration (Optional - if using S3 for storage)
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_BUCKET_NAME=
S3_ENDPOINT_URL= # e.g., http://localhost:9000 for local MinIO

# CLI Defaults
DEFAULT_OUTPUT_DIR=output
LOG_LEVEL=INFO
"""

@app.command("init")
def configure_init():
    """Initialize project configuration. Checks for a .env file and provides guidance."""
    logger.debug("Starting configure init command.")
    env_path = Path(".env")
    if env_path.exists():
        typer.echo(f"Found existing .env file at: {env_path.resolve()}")
        logger.info(f"Existing .env file found at {env_path.resolve()}")
        typer.echo("Please ensure it contains all necessary keys like BROWSERBASE_API_KEY, STAGEHAND_API_KEY, etc.")
        # Optionally, could offer to merge/update, but for now, just inform.
    else:
        typer.echo("No .env file found.")
        logger.info(".env file not found.")
        create_env = typer.confirm("Would you like to create a sample .env file in the current directory?", default=True)
        if create_env:
            try:
                with open(env_path, "w") as f:
                    f.write(ENV_EXAMPLE_CONTENT)
                typer.echo(f"Successfully created .env file at: {env_path.resolve()}")
                logger.info(f".env file created at {env_path.resolve()}")
                typer.echo("Please open it and fill in your actual API keys and other configurations.")
            except IOError as e:
                logger.error(f"IOError creating .env file: {e}", exc_info=True)
                typer.secho(f"Error creating .env file: {e}", fg=typer.colors.RED, err=True)
        else:
            typer.echo("Skipping .env creation. You can create it manually with the following content:")
            logger.info("User skipped .env creation.")
            typer.echo(ENV_EXAMPLE_CONTENT)
    
    typer.echo("\nConfiguration setup guide:")
    typer.echo("1. Ensure API keys (BROWSERBASE_API_KEY, STAGEHAND_API_KEY) are set either as environment variables or in the .env file.")
    typer.echo("2. Configure S3 settings in .env if you plan to use S3 storage.")
    typer.echo("3. Other settings like DEFAULT_OUTPUT_DIR and LOG_LEVEL can also be set in .env or will use defaults.")


if __name__ == "__main__":
    app() 