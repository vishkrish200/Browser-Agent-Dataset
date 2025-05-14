# Browser-Agent Dataset MVP

This project aims to build an open, production-ready orchestration layer to record real browser interactions and package them as a clean, portable dataset for fine-tuning large language models (LLMs) into web-capable agents.

*Further details will be added here.*

## CLI Usage

The Browser-Agent Dataset project includes a Command Line Interface (CLI) to help manage various aspects of the project, from configuration to data collection.

### Installation

Currently, for development, the CLI can be run from the project root after setting up the environment:

```bash
# Ensure you have Python 3.10+ and pip
# 1. Create and activate a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate # On Windows use `.venv\Scripts\activate`

# 2. Install dependencies and the project in editable mode
pip install -r requirements.txt
pip install -e .
```

In the future, the CLI might be packaged for installation via `pip install bad-agent-dataset`.

### Configuration

The CLI uses a `.env` file in the project root to manage sensitive configurations like API keys.

To get started, you can initialize the configuration:

```bash
bad-agent configure init
```

This command will guide you. If you don't have a `.env` file, it will offer to create one based on an example. You will then need to fill in your actual API keys (e.g., `BROWSERBASE_API_KEY`, `STAGEHAND_API_KEY`) and any S3 details if you plan to use S3 storage.

The configuration system loads settings with the following priority:
1.  Environment Variables
2.  Values in the `.env` file
3.  Default values defined in the application.

Key configuration variables include:
*   `BROWSERBASE_API_KEY`: Your API key for Browserbase.
*   `STAGEHAND_API_KEY`: Your API key for Stagehand.
*   `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET_NAME`, `S3_ENDPOINT_URL`: For S3 storage (optional).
*   `DEFAULT_OUTPUT_DIR`: Default directory for outputs (defaults to `output`).
*   `LOG_LEVEL`: Logging verbosity (e.g., `INFO`, `DEBUG`, defaults to `INFO`).

### Command Reference

Below is a reference for the available commands. You can always get help for any command or subcommand by appending `--help`.

**Main Application (`bad-agent`)**

```
Usage: bad-agent [OPTIONS] COMMAND [ARGS]...

  CLI for managing the Browser Agent Dataset project, including data
  collection, processing, and model interaction.

Options:
  --install-completion [bash|zsh|fish|powershell|pwsh]
                                  Install completion for the specified shell.
  --show-completion [bash|zsh|fish|powershell|pwsh]
                                  Show completion for the specified shell, to
                                  copy it or customize the installation.
  -v, --version                   Show the application's version and exit.
  --help                          Show this message and exit.

Commands:
  collect    Run data collection workflows.
  configure  Manage CLI and project configuration.
```

**Configure Commands (`bad-agent configure`)**

```
Usage: bad-agent configure [OPTIONS] COMMAND [ARGS]...

  Manage CLI and project configuration.

Options:
  --help  Show this message and exit.

Commands:
  init  Initialize project configuration. Checks for a .env file and...
```

*   `bad-agent configure init`: 
    ```
    Usage: bad-agent configure init [OPTIONS]

      Initialize project configuration. Checks for a .env file and provides
      guidance.

    Options:
      --help  Show this message and exit.
    ```

**Collect Commands (`bad-agent collect`)**

(Note: The `collect` commands are currently placeholders and will be implemented as the data collection module is developed.)

```
Usage: bad-agent collect [OPTIONS] COMMAND [ARGS]...

  Run data collection workflows.

Options:
  --help  Show this message and exit.

Commands:
  list-workflows  List available data collection workflows.
  run             Run a specific data collection workflow.
```

*   `bad-agent collect list-workflows`:
    ```
    Usage: bad-agent collect list-workflows [OPTIONS]

      List available data collection workflows.

    Options:
      --help  Show this message and exit.
    ```
*   `bad-agent collect run WORKFLOW_NAME`:
    ```
    Usage: bad-agent collect run [OPTIONS] WORKFLOW_NAME

      Run a specific data collection workflow.

    Arguments:
      WORKFLOW_NAME  Name of the workflow to run. [required]

    Options:
      --help  Show this message and exit.
    ```

### Development Notes

(Placeholder for notes on how to contribute to the CLI, e.g., adding new commands.) 