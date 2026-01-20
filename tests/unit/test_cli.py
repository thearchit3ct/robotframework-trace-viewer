"""Unit tests for the CLI module."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from trace_viewer.cli import main


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_traces_dir(tmp_path: Path) -> Path:
    """Create a temporary traces directory with sample traces."""
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    return traces_dir


@pytest.fixture
def sample_trace(temp_traces_dir: Path) -> Path:
    """Create a sample trace with manifest and keywords."""
    trace_dir = temp_traces_dir / "my_test_20250119_143022"
    trace_dir.mkdir()

    # Create manifest.json
    manifest = {
        "version": "1.0.0",
        "tool_version": "0.1.0",
        "test_name": "Login Should Work",
        "suite_name": "Authentication",
        "suite_source": "/tests/auth.robot",
        "start_time": "2025-01-19T14:30:22.123Z",
        "end_time": "2025-01-19T14:30:45.456Z",
        "duration_ms": 23333,
        "status": "PASS",
        "message": "",
        "keywords_count": 3,
        "rf_version": "7.0",
        "browser": "chrome",
        "capture_mode": "full",
    }
    with open(trace_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    # Create keywords directory with sample keywords
    keywords_dir = trace_dir / "keywords"
    keywords_dir.mkdir()

    for i, (name, status) in enumerate(
        [("Open Browser", "PASS"), ("Click Button", "PASS"), ("Verify Text", "PASS")], start=1
    ):
        kw_dir = keywords_dir / f"{i:03d}_{name.lower().replace(' ', '_')}"
        kw_dir.mkdir()
        kw_metadata = {
            "index": i,
            "name": name,
            "library": "SeleniumLibrary",
            "args": [],
            "status": status,
            "duration_ms": 100,
        }
        with open(kw_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(kw_metadata, f)

    # Create viewer.html
    (trace_dir / "viewer.html").write_text("<html><body>Viewer</body></html>", encoding="utf-8")

    return trace_dir


@pytest.fixture
def failed_trace(temp_traces_dir: Path) -> Path:
    """Create a sample failed trace."""
    trace_dir = temp_traces_dir / "failed_test_20250119_150000"
    trace_dir.mkdir()

    manifest = {
        "version": "1.0.0",
        "tool_version": "0.1.0",
        "test_name": "Login Should Fail Gracefully",
        "suite_name": "Authentication",
        "suite_source": "/tests/auth.robot",
        "start_time": "2025-01-19T15:00:00.000Z",
        "end_time": "2025-01-19T15:00:10.000Z",
        "duration_ms": 10000,
        "status": "FAIL",
        "message": "Element 'button#submit' not found",
        "keywords_count": 2,
        "rf_version": "7.0",
        "browser": "chrome",
        "capture_mode": "full",
    }
    with open(trace_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    return trace_dir


class TestCliVersion:
    """Tests for the --version option."""

    def test_cli_version(self, runner: CliRunner) -> None:
        """Test that --version displays the version."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output or "version" in result.output.lower()


class TestListCommand:
    """Tests for the list command."""

    def test_list_command_no_traces(self, runner: CliRunner, temp_traces_dir: Path) -> None:
        """Test list command with an empty traces directory."""
        result = runner.invoke(main, ["list", str(temp_traces_dir)])
        assert result.exit_code == 0
        assert "No traces found." in result.output

    def test_list_command_with_traces(
        self, runner: CliRunner, sample_trace: Path, temp_traces_dir: Path
    ) -> None:
        """Test list command with available traces."""
        result = runner.invoke(main, ["list", str(temp_traces_dir)])
        assert result.exit_code == 0
        assert "Found 1 trace(s)" in result.output
        assert "Login Should Work" in result.output
        assert "PASS" in result.output
        assert "23333ms" in result.output

    def test_list_command_with_multiple_traces(
        self, runner: CliRunner, sample_trace: Path, failed_trace: Path, temp_traces_dir: Path
    ) -> None:
        """Test list command with multiple traces."""
        result = runner.invoke(main, ["list", str(temp_traces_dir)])
        assert result.exit_code == 0
        assert "Found 2 trace(s)" in result.output
        assert "Login Should Work" in result.output
        assert "Login Should Fail Gracefully" in result.output

    def test_list_command_nonexistent_dir(self, runner: CliRunner) -> None:
        """Test list command with nonexistent directory."""
        result = runner.invoke(main, ["list", "/nonexistent/path"])
        assert result.exit_code != 0


class TestInfoCommand:
    """Tests for the info command."""

    def test_info_command(self, runner: CliRunner, sample_trace: Path) -> None:
        """Test info command displays trace details."""
        result = runner.invoke(main, ["info", str(sample_trace)])
        assert result.exit_code == 0
        assert "Login Should Work" in result.output
        assert "Authentication" in result.output
        assert "PASS" in result.output
        assert "23333ms" in result.output
        assert "Keywords (3)" in result.output
        assert "Open Browser" in result.output
        assert "Click Button" in result.output
        assert "Verify Text" in result.output

    def test_info_command_failed_trace(self, runner: CliRunner, failed_trace: Path) -> None:
        """Test info command displays failure message."""
        result = runner.invoke(main, ["info", str(failed_trace)])
        assert result.exit_code == 0
        assert "FAIL" in result.output
        assert "Element 'button#submit' not found" in result.output

    def test_info_command_no_manifest(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test info command with missing manifest.json."""
        empty_dir = tmp_path / "empty_trace"
        empty_dir.mkdir()
        result = runner.invoke(main, ["info", str(empty_dir)])
        assert result.exit_code == 1
        assert "No manifest.json found" in result.output

    def test_info_command_many_keywords(self, runner: CliRunner, sample_trace: Path) -> None:
        """Test info command truncates keyword list when more than 10."""
        keywords_dir = sample_trace / "keywords"

        # Add more keywords to exceed 10
        for i in range(4, 15):
            kw_dir = keywords_dir / f"{i:03d}_keyword_{i}"
            kw_dir.mkdir()
            kw_metadata = {
                "index": i,
                "name": f"Keyword {i}",
                "library": "BuiltIn",
                "args": [],
                "status": "PASS",
                "duration_ms": 50,
            }
            with open(kw_dir / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(kw_metadata, f)

        result = runner.invoke(main, ["info", str(sample_trace)])
        assert result.exit_code == 0
        assert "... and" in result.output
        assert "more" in result.output


class TestOpenCommand:
    """Tests for the open command."""

    def test_open_command_no_viewer(self, runner: CliRunner, failed_trace: Path) -> None:
        """Test open command when no viewer.html exists."""
        result = runner.invoke(main, ["open", str(failed_trace)])
        assert result.exit_code == 1
        assert "No viewer.html found" in result.output

    @patch("trace_viewer.cli.webbrowser.open")
    def test_open_command_with_viewer(
        self, mock_webbrowser: patch, runner: CliRunner, sample_trace: Path
    ) -> None:
        """Test open command opens browser with viewer.html."""
        result = runner.invoke(main, ["open", str(sample_trace)])
        assert result.exit_code == 0
        assert "Opening" in result.output
        mock_webbrowser.assert_called_once()
        call_arg = mock_webbrowser.call_args[0][0]
        assert "viewer.html" in call_arg
        assert call_arg.startswith("file://")

    @patch("trace_viewer.cli.webbrowser.open")
    def test_open_command_with_index_html(
        self, mock_webbrowser: patch, runner: CliRunner, temp_traces_dir: Path
    ) -> None:
        """Test open command falls back to index.html."""
        trace_dir = temp_traces_dir / "trace_with_index"
        trace_dir.mkdir()
        (trace_dir / "index.html").write_text("<html>Index</html>", encoding="utf-8")

        result = runner.invoke(main, ["open", str(trace_dir)])
        assert result.exit_code == 0
        mock_webbrowser.assert_called_once()
        call_arg = mock_webbrowser.call_args[0][0]
        assert "index.html" in call_arg

    def test_open_command_nonexistent_path(self, runner: CliRunner) -> None:
        """Test open command with nonexistent path."""
        result = runner.invoke(main, ["open", "/nonexistent/trace"])
        assert result.exit_code != 0
