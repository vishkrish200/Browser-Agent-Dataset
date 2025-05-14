import pytest
from typer.testing import CliRunner
from bad_agent_cli.main import app # Assuming 'app' is your Typer instance in main.py

runner = CliRunner()

def test_main_app_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage: bad-agent [OPTIONS] COMMAND [ARGS]..." in result.stdout
    assert "CLI for managing the Browser Agent Dataset project" in result.stdout
    assert "configure" in result.stdout
    assert "collect" in result.stdout
    assert "--version" in result.stdout
    assert "--install-completion" in result.stdout

def test_main_app_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Browser-Agent CLI version: 0.1.0 (placeholder)" in result.stdout

def test_configure_help():
    result = runner.invoke(app, ["configure", "--help"])
    assert result.exit_code == 0
    assert "Usage: bad-agent configure [OPTIONS] COMMAND [ARGS]..." in result.stdout
    assert "Manage CLI and project configuration." in result.stdout
    assert "init" in result.stdout

def test_configure_init_command():
    result = runner.invoke(app, ["configure", "init"])
    assert result.exit_code == 0

def test_configure_init_command_help():
    result = runner.invoke(app, ["configure", "init", "--help"])
    assert result.exit_code == 0
    assert "Usage: bad-agent configure init [OPTIONS]" in result.stdout
    assert "Initialize project configuration." in result.stdout

def test_collect_help():
    result = runner.invoke(app, ["collect", "--help"])
    assert result.exit_code == 0
    assert "Usage: bad-agent collect [OPTIONS] COMMAND [ARGS]..." in result.stdout
    assert "Run data collection workflows." in result.stdout
    assert "list-workflows" in result.stdout
    assert "run" in result.stdout

def test_collect_list_workflows_command():
    result = runner.invoke(app, ["collect", "list-workflows"])
    assert result.exit_code == 0

def test_collect_list_workflows_command_help():
    result = runner.invoke(app, ["collect", "list-workflows", "--help"])
    assert result.exit_code == 0
    assert "Usage: bad-agent collect list-workflows [OPTIONS]" in result.stdout
    assert "List available data collection workflows." in result.stdout

def test_collect_run_command():
    result = runner.invoke(app, ["collect", "run", "test-workflow"])
    assert result.exit_code == 0

def test_collect_run_command_help():
    result = runner.invoke(app, ["collect", "run", "--help"])
    assert result.exit_code == 0
    assert "Usage: bad-agent collect run [OPTIONS] WORKFLOW_NAME" in result.stdout
    assert "Run a specific data collection workflow." in result.stdout
    assert "WORKFLOW_NAME" in result.stdout 