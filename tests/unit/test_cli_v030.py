"""Tests for v0.3.0 CLI commands."""

import json

import pytest
from click.testing import CliRunner

from trace_viewer.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def traces_dir(tmp_path):
    """Create a traces directory with sample traces."""
    traces = tmp_path / "traces"
    traces.mkdir()
    for name, status in [("test_login", "PASS"), ("test_checkout", "FAIL")]:
        trace_dir = traces / name
        trace_dir.mkdir()
        manifest = {
            "test_name": name,
            "status": status,
            "duration_ms": 1000,
            "start_time": "2025-01-20T10:00:00+00:00",
            "keywords_count": 3,
            "suite_name": "Test Suite",
        }
        (trace_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (trace_dir / "viewer.html").write_text("<html><body>viewer</body></html>", encoding="utf-8")
        kw_dir = trace_dir / "keywords" / "001_step"
        kw_dir.mkdir(parents=True)
        (kw_dir / "metadata.json").write_text(
            json.dumps({"index": 1, "name": "Step", "status": status}),
            encoding="utf-8",
        )
    return traces


class TestInitCommand:
    """Test trace-viewer init command."""

    def test_init_creates_config(self, runner, tmp_path):
        output = tmp_path / "trace-viewer.yml"
        result = runner.invoke(main, ["init", "--output", str(output)])
        assert result.exit_code == 0
        assert output.exists()
        content = output.read_text()
        assert "output_dir" in content

    def test_init_existing_file(self, runner, tmp_path):
        output = tmp_path / "trace-viewer.yml"
        output.write_text("existing")
        result = runner.invoke(main, ["init", "--output", str(output)])
        assert result.exit_code != 0


class TestSuiteCommand:
    """Test trace-viewer suite command."""

    def test_suite_basic(self, runner, traces_dir, tmp_path):
        output = tmp_path / "suite.html"
        result = runner.invoke(main, ["suite", str(traces_dir), "--output", str(output)])
        assert result.exit_code == 0
        assert output.exists()


class TestCleanupCommand:
    """Test trace-viewer cleanup command."""

    def test_cleanup_basic(self, runner, traces_dir):
        result = runner.invoke(main, ["cleanup", str(traces_dir), "--days", "365"])
        assert result.exit_code == 0
        assert "Deleted" in result.output or "deleted" in result.output.lower()


class TestPublishCommand:
    """Test trace-viewer publish command."""

    def test_publish_jenkins(self, runner, traces_dir, tmp_path):
        output = tmp_path / "ci_output"
        result = runner.invoke(
            main,
            ["publish", str(traces_dir), "--format", "jenkins", "--output", str(output)],
        )
        assert result.exit_code == 0

    def test_publish_gitlab(self, runner, traces_dir, tmp_path):
        output = tmp_path / "ci_output"
        result = runner.invoke(
            main,
            ["publish", str(traces_dir), "--format", "gitlab", "--output", str(output)],
        )
        assert result.exit_code == 0


class TestMergeCommand:
    """Test trace-viewer merge command."""

    def test_merge_basic(self, runner, traces_dir, tmp_path):
        output = tmp_path / "merged"
        result = runner.invoke(main, ["merge", str(traces_dir), "--output", str(output)])
        assert result.exit_code == 0
