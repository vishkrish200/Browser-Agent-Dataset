import typer
import logging
import sys

from . import configure_cli
from . import collect_cli
from .config import settings

def setup_logging():
    """Configures basic logging for the CLI."""
    log_level_str = settings.LOG_LEVEL.upper()
    numeric_level = getattr(logging, log_level_str, logging.INFO)
    
    # Basic configuration affecting the root logger
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stderr)
        ]
    )
    # You can get more specific loggers elsewhere, but this sets the baseline
    # for any logger obtained via logging.getLogger()

app = typer.Typer(
    name="bad-agent",
    help="CLI for managing the Browser Agent Dataset project, including data collection, processing, and model interaction.",
    add_completion=True,
    no_args_is_help=True
)

# Register subcommands
app.add_typer(configure_cli.app, name="configure")
app.add_typer(collect_cli.app, name="collect")

def version_callback(value: bool):
    if value:
        # In a real app, you'd import __version__ from your package
        print(f"Browser-Agent CLI version: 0.1.0 (placeholder)")
        raise typer.Exit()

@app.callback()
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(None, "--version", "-v", callback=version_callback, is_eager=True, help="Show the application's version and exit.")
):
    """
    Browser Agent Dataset CLI
    """
    setup_logging()
    # This callback runs before any command
    # You can use ctx.invoked_subcommand to see if a subcommand is being called
    pass

if __name__ == "__main__":
    app() 