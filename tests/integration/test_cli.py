"""Integration test: CLI commands."""

from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from pisti.cli.app import app
from pisti.core.types import AgentResult

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "pisti" in result.output.lower() or "multi-agent" in result.output.lower()


def test_cli_code_help():
    result = runner.invoke(app, ["code", "--help"])
    assert result.exit_code == 0
    assert "instruction" in result.output.lower()


def test_cli_code_with_mock():
    mock_result = AgentResult(
        summary="Created hello.py",
        files_modified=["hello.py"],
        iterations=2,
    )

    with patch("pisti.cli.app._build_coder_agent") as mock_build:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = mock_result
        mock_provider = AsyncMock()
        mock_build.return_value = (mock_agent, mock_provider)

        result = runner.invoke(app, ["code", "Create hello.py"])

    assert result.exit_code == 0


def test_cli_config_init(tmp_path):
    result = runner.invoke(app, ["config", "init", "--dir", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / ".pisti" / "config.yaml").exists()
