import pytest
import os
from typer.testing import CliRunner
from pathlib import Path

from bad_agent_cli.main import app as cli_app # Main Typer app
from bad_agent_cli.config import AppSettings, settings as global_settings

runner = CliRunner()

@pytest.fixture
def temp_env_file(tmp_path: Path):
    """Creates a temporary .env file for testing."""
    env_content = "BROWSERBASE_API_KEY=env_file_key\nLOG_LEVEL=DEBUG\nDEFAULT_OUTPUT_DIR=env_file_output"
    env_file = tmp_path / ".env"
    env_file.write_text(env_content)
    return env_file

@pytest.fixture
def hide_real_dotenv(monkeypatch):
    """Temporarily hides the real .env file if it exists in the current dir."""
    real_env_path = Path(".env")
    moved_env_path = Path(".env.pytest_hidden")
    existed = False
    if real_env_path.exists():
        existed = True
        real_env_path.rename(moved_env_path)
    
    yield # Let the test run
    
    if existed:
        moved_env_path.rename(real_env_path) # Restore it

def test_default_settings_loaded(monkeypatch):
    # Ensure a clean slate for these specific keys by removing them from env vars if they exist
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("DEFAULT_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("BROWSERBASE_API_KEY", raising=False)
    
    s = AppSettings() # Create a new instance for isolation
    assert s.LOG_LEVEL == "INFO" # Default from AppSettings model
    assert s.DEFAULT_OUTPUT_DIR == "output"
    assert s.BROWSERBASE_API_KEY is None

def test_settings_overridden_by_env_vars(monkeypatch):
    monkeypatch.setenv("BROWSERBASE_API_KEY", "env_var_key")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    s = AppSettings() 
    assert s.BROWSERBASE_API_KEY == "env_var_key"
    assert s.LOG_LEVEL == "WARNING"

def test_settings_overridden_by_dotenv_file(tmp_path: Path, monkeypatch, hide_real_dotenv):
    # Ensure no higher-priority env vars are set for these keys
    monkeypatch.delenv("BROWSERBASE_API_KEY", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("DEFAULT_OUTPUT_DIR", raising=False)

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    original_cwd = os.getcwd()
    os.chdir(project_dir) # Change to temp project dir to load .env from there

    env_content = "BROWSERBASE_API_KEY=dotenv_key\nLOG_LEVEL=CRITICAL\nDEFAULT_OUTPUT_DIR=dotenv_output"
    dotenv_file = project_dir / ".env"
    dotenv_file.write_text(env_content)

    s = AppSettings() # This should load from the .env in the current (temp) dir
    
    assert s.BROWSERBASE_API_KEY == "dotenv_key"
    assert s.LOG_LEVEL == "CRITICAL"
    assert s.DEFAULT_OUTPUT_DIR == "dotenv_output"
    
    os.chdir(original_cwd) # Change back

def test_env_vars_priority_over_dotenv(tmp_path: Path, monkeypatch, hide_real_dotenv):
    monkeypatch.setenv("BROWSERBASE_API_KEY", "env_var_is_king")
    monkeypatch.setenv("LOG_LEVEL", "TRACE") # Made up level to ensure it's from env var

    project_dir = tmp_path / "project2"
    project_dir.mkdir()
    original_cwd = os.getcwd()
    os.chdir(project_dir)

    env_content = "BROWSERBASE_API_KEY=dotenv_should_be_ignored\nLOG_LEVEL=ENV_SHOULD_WIN"
    dotenv_file = project_dir / ".env"
    dotenv_file.write_text(env_content)

    s = AppSettings()
    assert s.BROWSERBASE_API_KEY == "env_var_is_king"
    assert s.LOG_LEVEL == "TRACE"
    
    os.chdir(original_cwd)

# --- Tests for `bad-agent configure init` command --- #

def test_configure_init_when_dotenv_exists(tmp_path: Path, hide_real_dotenv):
    original_cwd = os.getcwd()
    # Create a dummy project dir inside tmp_path and cd into it
    project_dir = tmp_path / "project_with_env"
    project_dir.mkdir()
    os.chdir(project_dir)

    # Create a dummy .env file in this temporary project directory
    dummy_env = project_dir / ".env"
    dummy_env.write_text("EXISTING_KEY=TEST_VALUE\n")

    result = runner.invoke(cli_app, ["configure", "init"], input="y\n") 
    
    os.chdir(original_cwd) # Change back

    assert result.exit_code == 0
    assert "Found existing .env file" in result.stdout
    assert "Please ensure it contains all necessary keys" in result.stdout
    # dummy_env.unlink() # Clean up the dummy .env if needed, tmp_path handles overall cleanup

def test_configure_init_create_dotenv(tmp_path: Path, hide_real_dotenv):
    # This test will run in tmp_path, so .env won't exist there initially
    original_cwd = os.getcwd()
    os.chdir(tmp_path) # Run CLI command in tmp_path

    result = runner.invoke(cli_app, ["configure", "init"], input="y\n") # Yes to create
    
    os.chdir(original_cwd) # Change back before assertions on files

    assert result.exit_code == 0
    assert "No .env file found." in result.stdout
    assert "Successfully created .env file" in result.stdout
    env_file_in_tmp = tmp_path / ".env"
    assert env_file_in_tmp.exists()
    content = env_file_in_tmp.read_text()
    assert "BROWSERBASE_API_KEY=" in content
    assert "LOG_LEVEL=INFO" in content
    env_file_in_tmp.unlink() # Clean up

def test_configure_init_skip_create_dotenv(tmp_path: Path, hide_real_dotenv):
    original_cwd = os.getcwd()
    os.chdir(tmp_path)

    result = runner.invoke(cli_app, ["configure", "init"], input="n\n") # No to create
    
    os.chdir(original_cwd)

    assert result.exit_code == 0
    assert "No .env file found." in result.stdout
    assert "Skipping .env creation." in result.stdout
    assert "You can create it manually with the following content:" in result.stdout
    assert "BROWSERBASE_API_KEY=" in result.stdout # Ensure example content is shown
    env_file_in_tmp = tmp_path / ".env"
    assert not env_file_in_tmp.exists() 