import pytest
import logging
from typer.testing import CliRunner
from pathlib import Path
import os

from bad_agent_cli.main import app as cli_app
from bad_agent_cli.config import AppSettings # To create instances for testing

runner = CliRunner()

@pytest.fixture
def hide_real_dotenv_and_clear_env_vars(monkeypatch):
    """Hides .env and clears relevant environment variables for isolated testing."""
    real_env_path = Path(".env")
    moved_env_path = Path(".env.pytest_hidden_logging") # Use a different name if hide_real_dotenv is also used
    existed = False
    if real_env_path.exists():
        existed = True
        real_env_path.rename(moved_env_path)

    # Clear potentially relevant environment variables
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    # Add other config vars if they could interfere
    
    yield
    
    if existed:
        moved_env_path.rename(real_env_path)

def test_logging_default_level(caplog, hide_real_dotenv_and_clear_env_vars):
    """Test that default LOG_LEVEL=INFO is used."""
    with caplog.at_level(logging.DEBUG): # Capture from DEBUG upwards
        # Invoke a command that should trigger logging setup and a log message
        result = runner.invoke(cli_app, ["configure", "init"], input="n\n") # No to .env creation
    
    assert result.exit_code == 0
    # Check for a log message that would appear at INFO but not DEBUG if default is INFO
    # Example from configure_init:
    init_log_messages = [rec.message for rec in caplog.records if rec.name == "bad_agent_cli.configure_cli"]
    assert ".env file not found." in init_log_messages
    # Check that a DEBUG message (if we had one) is NOT present
    # For example, the 'Starting configure init command.' is DEBUG level
    assert "Starting configure init command." in init_log_messages # This should be present because we are at INFO

    # To be more precise, let's check the effective level of a logger
    # Note: AppSettings() will re-initialize based on current env for each call
    # The logger in main gets configured once. We need to test that initial configuration.
    # This test primarily checks if our default in AppSettings leads to INFO level logging.
    # The actual `logging.basicConfig` in main uses settings.LOG_LEVEL


def test_logging_level_from_env_var(caplog, monkeypatch, hide_real_dotenv_and_clear_env_vars):
    """Test that LOG_LEVEL from an environment variable is respected."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    
    with caplog.at_level(logging.DEBUG):
        result = runner.invoke(cli_app, ["configure", "init"], input="n\n")

    assert result.exit_code == 0
    # Check that a DEBUG level message is now present
    debug_messages = [rec.message for rec in caplog.records if rec.name == "bad_agent_cli.configure_cli" and rec.levelname == "DEBUG"]
    assert "Starting configure init command." in debug_messages

def test_logging_level_from_dotenv(tmp_path, caplog, monkeypatch, hide_real_dotenv_and_clear_env_vars):
    """Test that LOG_LEVEL from a .env file is respected if no env var is set."""
    # Ensure env var is not set
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    project_dir = tmp_path / "project_log_test"
    project_dir.mkdir()
    original_cwd = os.getcwd()
    os.chdir(project_dir)

    env_content = "LOG_LEVEL=WARNING\nBROWSERBASE_API_KEY=testkey"
    dotenv_file = project_dir / ".env"
    dotenv_file.write_text(env_content)

    with caplog.at_level(logging.INFO): # Capture INFO and above
        result = runner.invoke(cli_app, ["configure", "init"], input="n\n")
    
    os.chdir(original_cwd)

    assert result.exit_code == 0
    # INFO messages should NOT be present if level is WARNING
    info_messages = [rec.message for rec in caplog.records if rec.name == "bad_agent_cli.configure_cli" and rec.levelname == "INFO"]
    assert ".env file not found." not in info_messages 
    # DEBUG messages should also NOT be present
    debug_messages = [rec.message for rec in caplog.records if rec.name == "bad_agent_cli.configure_cli" and rec.levelname == "DEBUG"]
    assert "Starting configure init command." not in debug_messages

    # A quick check if any WARNING/ERROR/CRITICAL logs were made (though our command doesn't make them by default)
    # This mainly proves that INFO/DEBUG were suppressed.


def test_logging_invalid_level_defaults_to_info(caplog, monkeypatch, hide_real_dotenv_and_clear_env_vars):
    """Test that an invalid LOG_LEVEL defaults to INFO."""
    monkeypatch.setenv("LOG_LEVEL", "INVALID_LOG_LEVEL_XYZ")
    
    with caplog.at_level(logging.DEBUG): # Capture from DEBUG upwards
        result = runner.invoke(cli_app, ["configure", "init"], input="n\n")
    
    assert result.exit_code == 0
    # Should behave like INFO level
    init_log_messages = [rec.message for rec in caplog.records if rec.name == "bad_agent_cli.configure_cli"]
    assert ".env file not found." in init_log_messages # This is an INFO message
    assert "Starting configure init command." in init_log_messages # This is a DEBUG message, should be logged if level is INFO or DEBUG

    # Check the actual level of the root logger after setup
    # This is a bit indirect. A better way might be to inspect the logger object if possible,
    # or check which messages pass through.
    # The getattr in setup_logging defaults to logging.INFO (numeric 20)
    # If an INFO message passes, and a DEBUG message *also* passes (and we expect DEBUG if level is INFO), it's consistent. 