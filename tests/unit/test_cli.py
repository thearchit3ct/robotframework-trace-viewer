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


class TestExportCommand:
    """Tests for the export command."""

    def test_export_command_creates_zip(
        self, runner: CliRunner, sample_trace: Path, tmp_path: Path
    ) -> None:
        """Test export command creates a valid ZIP archive."""
        output_zip = tmp_path / "exported.zip"
        result = runner.invoke(main, ["export", str(sample_trace), "--output", str(output_zip)])

        assert result.exit_code == 0
        assert output_zip.exists()
        assert "Trace exported to:" in result.output
        assert "Archive size:" in result.output

    def test_export_command_default_output(
        self, runner: CliRunner, sample_trace: Path, tmp_path: Path
    ) -> None:
        """Test export command uses trace name for default output."""
        # Change to tmp_path for the default output location
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(main, ["export", str(sample_trace)])
            assert result.exit_code == 0

            # Default output should be <trace_name>.zip in current directory
            expected_zip = tmp_path / f"{sample_trace.name}.zip"
            assert expected_zip.exists()
        finally:
            os.chdir(original_cwd)

    def test_export_command_zip_contents(
        self, runner: CliRunner, sample_trace: Path, tmp_path: Path
    ) -> None:
        """Test exported ZIP contains all expected files."""
        import zipfile

        output_zip = tmp_path / "exported.zip"
        result = runner.invoke(main, ["export", str(sample_trace), "--output", str(output_zip)])
        assert result.exit_code == 0

        with zipfile.ZipFile(output_zip, "r") as zf:
            names = zf.namelist()

            # Check for expected files
            assert "manifest.json" in names
            assert "viewer.html" in names

            # Check for keywords directory structure
            keyword_files = [n for n in names if n.startswith("keywords/")]
            assert len(keyword_files) > 0

            # Check for metadata.json in keyword directories
            metadata_files = [n for n in names if n.endswith("metadata.json")]
            assert len(metadata_files) >= 1  # At least the manifest and keyword metadata

    def test_export_command_no_manifest(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test export command fails when no manifest.json exists."""
        empty_dir = tmp_path / "empty_trace"
        empty_dir.mkdir()

        result = runner.invoke(main, ["export", str(empty_dir)])
        assert result.exit_code == 1
        assert "No manifest.json found" in result.output
        assert "not appear to be a valid trace directory" in result.output

    def test_export_command_nonexistent_path(self, runner: CliRunner) -> None:
        """Test export command with nonexistent path."""
        result = runner.invoke(main, ["export", "/nonexistent/trace"])
        assert result.exit_code != 0

    def test_export_command_adds_zip_extension(
        self, runner: CliRunner, sample_trace: Path, tmp_path: Path
    ) -> None:
        """Test export command adds .zip extension if not provided."""
        output_path = tmp_path / "my_export"  # No .zip extension
        result = runner.invoke(main, ["export", str(sample_trace), "--output", str(output_path)])

        assert result.exit_code == 0
        expected_zip = tmp_path / "my_export.zip"
        assert expected_zip.exists()
        assert not (tmp_path / "my_export").exists()

    def test_export_command_creates_parent_directories(
        self, runner: CliRunner, sample_trace: Path, tmp_path: Path
    ) -> None:
        """Test export command creates parent directories if needed."""
        output_zip = tmp_path / "nested" / "dir" / "exported.zip"
        result = runner.invoke(main, ["export", str(sample_trace), "--output", str(output_zip)])

        assert result.exit_code == 0
        assert output_zip.exists()

    def test_export_command_short_option(
        self, runner: CliRunner, sample_trace: Path, tmp_path: Path
    ) -> None:
        """Test export command with -o short option."""
        output_zip = tmp_path / "short_option.zip"
        result = runner.invoke(main, ["export", str(sample_trace), "-o", str(output_zip)])

        assert result.exit_code == 0
        assert output_zip.exists()

    def test_export_command_zip_is_valid(
        self, runner: CliRunner, sample_trace: Path, tmp_path: Path
    ) -> None:
        """Test that exported ZIP is a valid, extractable archive."""
        import zipfile

        output_zip = tmp_path / "valid_test.zip"
        result = runner.invoke(main, ["export", str(sample_trace), "--output", str(output_zip)])
        assert result.exit_code == 0

        # Verify it's a valid ZIP file
        assert zipfile.is_zipfile(output_zip)

        # Try extracting it
        extract_dir = tmp_path / "extracted"
        with zipfile.ZipFile(output_zip, "r") as zf:
            zf.extractall(extract_dir)

        # Verify extracted content
        assert (extract_dir / "manifest.json").exists()
        assert (extract_dir / "viewer.html").exists()
        assert (extract_dir / "keywords").is_dir()

    def test_export_command_with_screenshots(
        self, runner: CliRunner, sample_trace: Path, tmp_path: Path
    ) -> None:
        """Test export includes screenshot files if present."""
        import zipfile

        # Add a screenshot to one of the keywords
        keywords_dir = sample_trace / "keywords"
        first_keyword = next(keywords_dir.iterdir())
        screenshot_path = first_keyword / "screenshot.png"
        # Create a minimal valid PNG (1x1 transparent pixel)
        png_data = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        screenshot_path.write_bytes(png_data)

        output_zip = tmp_path / "with_screenshot.zip"
        result = runner.invoke(main, ["export", str(sample_trace), "--output", str(output_zip)])
        assert result.exit_code == 0

        with zipfile.ZipFile(output_zip, "r") as zf:
            names = zf.namelist()
            screenshot_files = [n for n in names if n.endswith("screenshot.png")]
            assert len(screenshot_files) == 1


class TestCompareCommand:
    """Tests for the compare command."""

    @pytest.fixture
    def second_trace(self, temp_traces_dir: Path) -> Path:
        """Create a second sample trace for comparison."""
        trace_dir = temp_traces_dir / "second_test_20250119_150000"
        trace_dir.mkdir()

        manifest = {
            "version": "1.0.0",
            "tool_version": "0.1.0",
            "test_name": "Login Should Also Work",
            "suite_name": "Authentication",
            "suite_source": "/tests/auth.robot",
            "start_time": "2025-01-19T15:00:00.000Z",
            "end_time": "2025-01-19T15:00:30.000Z",
            "duration_ms": 30000,
            "status": "FAIL",
            "message": "Button not found",
            "keywords_count": 3,
            "rf_version": "7.0",
            "browser": "chrome",
            "capture_mode": "full",
        }
        with open(trace_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        # Create keywords directory with sample keywords (different from sample_trace)
        keywords_dir = trace_dir / "keywords"
        keywords_dir.mkdir()

        for i, (name, status) in enumerate(
            [("Open Browser", "PASS"), ("Click Button", "FAIL"), ("Verify Text", "NOT RUN")],
            start=1,
        ):
            kw_dir = keywords_dir / f"{i:03d}_{name.lower().replace(' ', '_')}"
            kw_dir.mkdir()
            kw_metadata = {
                "index": i,
                "name": name,
                "library": "SeleniumLibrary",
                "args": [],
                "status": status,
                "duration_ms": 200,
            }
            with open(kw_dir / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(kw_metadata, f)

        return trace_dir

    def test_compare_command_basic(
        self, runner: CliRunner, sample_trace: Path, second_trace: Path, tmp_path: Path
    ) -> None:
        """Test basic compare command execution."""
        output_html = tmp_path / "comparison.html"
        result = runner.invoke(
            main,
            ["compare", str(sample_trace), str(second_trace), "--output", str(output_html)],
        )

        assert result.exit_code == 0
        assert output_html.exists()
        assert "Comparing traces:" in result.output
        assert "Comparison Summary:" in result.output
        assert "Comparison report generated:" in result.output

    def test_compare_command_default_output(
        self, runner: CliRunner, sample_trace: Path, second_trace: Path, tmp_path: Path
    ) -> None:
        """Test compare command uses default output path."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(main, ["compare", str(sample_trace), str(second_trace)])

            assert result.exit_code == 0
            expected_output = tmp_path / "comparison.html"
            assert expected_output.exists()
        finally:
            os.chdir(original_cwd)

    def test_compare_command_shows_summary(
        self, runner: CliRunner, sample_trace: Path, second_trace: Path, tmp_path: Path
    ) -> None:
        """Test compare command displays summary statistics."""
        output_html = tmp_path / "comparison.html"
        result = runner.invoke(
            main,
            ["compare", str(sample_trace), str(second_trace), "--output", str(output_html)],
        )

        assert result.exit_code == 0
        assert "Total keywords:" in result.output
        assert "Matched:" in result.output
        assert "Modified:" in result.output

    def test_compare_command_no_manifest_trace1(
        self, runner: CliRunner, temp_traces_dir: Path, second_trace: Path
    ) -> None:
        """Test compare command fails when trace1 has no manifest."""
        empty_dir = temp_traces_dir / "empty_trace"
        empty_dir.mkdir()

        result = runner.invoke(main, ["compare", str(empty_dir), str(second_trace)])

        assert result.exit_code == 1
        assert "No manifest.json found" in result.output

    def test_compare_command_no_manifest_trace2(
        self, runner: CliRunner, sample_trace: Path, temp_traces_dir: Path
    ) -> None:
        """Test compare command fails when trace2 has no manifest."""
        empty_dir = temp_traces_dir / "empty_trace2"
        empty_dir.mkdir()

        result = runner.invoke(main, ["compare", str(sample_trace), str(empty_dir)])

        assert result.exit_code == 1
        assert "No manifest.json found" in result.output

    def test_compare_command_nonexistent_trace1(
        self, runner: CliRunner, second_trace: Path
    ) -> None:
        """Test compare command with nonexistent trace1 path."""
        result = runner.invoke(main, ["compare", "/nonexistent/trace1", str(second_trace)])
        assert result.exit_code != 0

    def test_compare_command_nonexistent_trace2(
        self, runner: CliRunner, sample_trace: Path
    ) -> None:
        """Test compare command with nonexistent trace2 path."""
        result = runner.invoke(main, ["compare", str(sample_trace), "/nonexistent/trace2"])
        assert result.exit_code != 0

    @patch("trace_viewer.cli.webbrowser.open")
    def test_compare_command_with_open_flag(
        self,
        mock_webbrowser: patch,
        runner: CliRunner,
        sample_trace: Path,
        second_trace: Path,
        tmp_path: Path,
    ) -> None:
        """Test compare command with --open flag opens browser."""
        output_html = tmp_path / "comparison.html"
        result = runner.invoke(
            main,
            [
                "compare",
                str(sample_trace),
                str(second_trace),
                "--output",
                str(output_html),
                "--open",
            ],
        )

        assert result.exit_code == 0
        assert "Opening in browser..." in result.output
        mock_webbrowser.assert_called_once()
        call_arg = mock_webbrowser.call_args[0][0]
        assert "comparison.html" in call_arg
        assert call_arg.startswith("file://")

    @patch("trace_viewer.cli.webbrowser.open")
    def test_compare_command_with_short_open_flag(
        self,
        mock_webbrowser: patch,
        runner: CliRunner,
        sample_trace: Path,
        second_trace: Path,
        tmp_path: Path,
    ) -> None:
        """Test compare command with -O short flag."""
        output_html = tmp_path / "comparison.html"
        result = runner.invoke(
            main,
            ["compare", str(sample_trace), str(second_trace), "-o", str(output_html), "-O"],
        )

        assert result.exit_code == 0
        mock_webbrowser.assert_called_once()

    def test_compare_command_adds_html_extension(
        self, runner: CliRunner, sample_trace: Path, second_trace: Path, tmp_path: Path
    ) -> None:
        """Test compare command adds .html extension if not provided."""
        output_path = tmp_path / "my_comparison"  # No .html extension
        result = runner.invoke(
            main,
            ["compare", str(sample_trace), str(second_trace), "--output", str(output_path)],
        )

        assert result.exit_code == 0
        expected_html = tmp_path / "my_comparison.html"
        assert expected_html.exists()

    def test_compare_command_creates_parent_directories(
        self, runner: CliRunner, sample_trace: Path, second_trace: Path, tmp_path: Path
    ) -> None:
        """Test compare command creates parent directories if needed."""
        output_html = tmp_path / "nested" / "dir" / "comparison.html"
        result = runner.invoke(
            main,
            ["compare", str(sample_trace), str(second_trace), "--output", str(output_html)],
        )

        assert result.exit_code == 0
        assert output_html.exists()

    def test_compare_command_output_content(
        self, runner: CliRunner, sample_trace: Path, second_trace: Path, tmp_path: Path
    ) -> None:
        """Test compare command generates valid HTML content."""
        output_html = tmp_path / "comparison.html"
        result = runner.invoke(
            main,
            ["compare", str(sample_trace), str(second_trace), "--output", str(output_html)],
        )

        assert result.exit_code == 0
        html_content = output_html.read_text(encoding="utf-8")

        # Check for expected HTML elements
        assert "<!DOCTYPE html>" in html_content
        assert "Trace Comparison" in html_content
        assert "COMPARISON_DATA" in html_content
        assert "Login Should Work" in html_content  # From sample_trace
        assert "Login Should Also Work" in html_content  # From second_trace

    def test_compare_command_shows_status_changes(
        self, runner: CliRunner, sample_trace: Path, second_trace: Path, tmp_path: Path
    ) -> None:
        """Test compare command shows status change count when present."""
        output_html = tmp_path / "comparison.html"
        result = runner.invoke(
            main,
            ["compare", str(sample_trace), str(second_trace), "--output", str(output_html)],
        )

        assert result.exit_code == 0
        # The second trace has different statuses, so status changes should be reported
        assert "Status changes:" in result.output
