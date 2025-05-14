import pytest
from typer.testing import CliRunner
from bad_agent_cli.main import app # Assuming 'app' is your Typer instance in main.py

runner = CliRunner()

def test_main_app_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage: bad-agent [OPTIONS] COMMAND [ARGS]..." in result.stdout
    assert "configure" in result.stdout
    assert "collect" in result.stdout

def test_main_app_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Browser-Agent CLI version: 0.1.0 (placeholder)" in result.stdout

def test_configure_help():
    result = runner.invoke(app, ["configure", "--help"])
    assert result.exit_code == 0
    assert "Usage: bad-agent configure [OPTIONS] COMMAND [ARGS]..." in result.stdout
    assert "init" in result.stdout

def test_configure_init_command():
    result = runner.invoke(app, ["configure", "init"])
    assert result.exit_code == 0
    assert "Placeholder: Initializing/updating project configuration..." in result.stdout

def test_collect_help():
    result = runner.invoke(app, ["collect", "--help"])
    assert result.exit_code == 0
    assert "Usage: bad-agent collect [OPTIONS] COMMAND [ARGS]..." in result.stdout
    assert "list-workflows" in result.stdout
    assert "run" in result.stdout

def test_collect_list_workflows_command():
    result = runner.invoke(app, ["collect", "list-workflows"])
    assert result.exit_code == 0
    assert "Placeholder: Listing available workflows..." in result.stdout

def test_collect_run_command():
    result = runner.invoke(app, ["collect", "run", "test-workflow"])
    assert result.exit_code == 0
    assert "Placeholder: Running workflow 'test-workflow'..." in result.stdout 