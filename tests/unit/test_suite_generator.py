"""Tests for trace_viewer.viewer.suite_generator module."""

import contextlib
import json
from pathlib import Path

from trace_viewer.viewer.suite_generator import SuiteViewerGenerator


def _create_trace(
    traces_dir: Path, name: str, status: str = "PASS", duration_ms: int = 1000
) -> Path:
    """Create a fake trace directory."""
    trace_dir = traces_dir / name
    trace_dir.mkdir(parents=True)
    manifest = {
        "test_name": name.replace("_", " ").title(),
        "status": status,
        "duration_ms": duration_ms,
        "start_time": "2025-01-20T10:00:00+00:00",
        "keywords_count": 5,
        "suite_name": "Test Suite",
    }
    (trace_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return trace_dir


class TestSuiteViewerGenerator:
    """Test suite viewer generation."""

    def test_generate_basic(self, tmp_path):
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        _create_trace(traces_dir, "test_login", "PASS")
        _create_trace(traces_dir, "test_logout", "FAIL")

        generator = SuiteViewerGenerator()
        output = generator.generate(traces_dir)
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content or "<!doctype html>" in content.lower()

    def test_generate_custom_output(self, tmp_path):
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        _create_trace(traces_dir, "test_one", "PASS")

        output_path = tmp_path / "custom_suite.html"
        generator = SuiteViewerGenerator()
        result = generator.generate(traces_dir, output_path)
        assert result.exists()

    def test_empty_traces_dir(self, tmp_path):
        traces_dir = tmp_path / "empty"
        traces_dir.mkdir()
        generator = SuiteViewerGenerator()
        # Should handle gracefully - either generate empty report or raise
        with contextlib.suppress(FileNotFoundError, ValueError):
            generator.generate(traces_dir)

    def test_stats_calculation(self, tmp_path):
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        _create_trace(traces_dir, "pass1", "PASS")
        _create_trace(traces_dir, "pass2", "PASS")
        _create_trace(traces_dir, "fail1", "FAIL")

        generator = SuiteViewerGenerator()
        traces = generator._load_traces(traces_dir)
        stats = generator._calculate_stats(traces)
        assert stats["total"] == 3
        assert stats["passed"] == 2
        assert stats["failed"] == 1


class TestSuiteViewerTemplate:
    """Test the suite viewer HTML template exists and is valid."""

    def test_template_exists(self):
        template = (
            Path(__file__).parent.parent.parent
            / "src"
            / "trace_viewer"
            / "viewer"
            / "templates"
            / "suite_viewer.html"
        )
        assert template.exists()

    def test_template_has_placeholders(self):
        template = (
            Path(__file__).parent.parent.parent
            / "src"
            / "trace_viewer"
            / "viewer"
            / "templates"
            / "suite_viewer.html"
        )
        content = template.read_text(encoding="utf-8")
        assert "{{SUITE_DATA}}" in content
        assert "{{SUITE_NAME}}" in content
