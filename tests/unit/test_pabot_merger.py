"""Tests for trace_viewer.integrations.pabot_merger module."""

import json
from pathlib import Path

from trace_viewer.integrations.pabot_merger import PabotMerger, extract_worker_id


def _create_trace(
    traces_dir: Path,
    name: str,
    status: str = "PASS",
    start_time: str = "2025-01-20T10:00:00+00:00",
    duration_ms: int = 1000,
) -> Path:
    """Create a fake trace directory."""
    trace_dir = traces_dir / name
    trace_dir.mkdir(parents=True)
    manifest = {
        "test_name": name.replace("_", " ").title(),
        "status": status,
        "duration_ms": duration_ms,
        "start_time": start_time,
        "keywords_count": 3,
    }
    (trace_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    # Create viewer.html
    (trace_dir / "viewer.html").write_text("<html><body>viewer</body></html>", encoding="utf-8")
    return trace_dir


class TestExtractWorkerId:
    """Test worker ID extraction from directory names."""

    def test_pabot_suffix(self):
        assert extract_worker_id("login_test_20250119_143022_pabot1") == "pabot1"

    def test_pabot_suffix_multi_digit(self):
        assert extract_worker_id("test_20250119_pabot12") == "pabot12"

    def test_no_pabot(self):
        assert extract_worker_id("login_test_20250119_143022") == "sequential"

    def test_pabot0(self):
        assert extract_worker_id("test_pabot0") == "pabot0"


class TestPabotMerger:
    """Test Pabot trace merging."""

    def test_scan_traces(self, tmp_path):
        _create_trace(tmp_path, "test_login_20250119_pabot0", "PASS")
        _create_trace(tmp_path, "test_checkout_20250119_pabot1", "FAIL")
        _create_trace(tmp_path, "test_search_20250119", "PASS")

        merger = PabotMerger(tmp_path)
        traces = merger.scan_traces()
        assert len(traces) == 3

    def test_merge_creates_output(self, tmp_path):
        _create_trace(
            tmp_path,
            "test_a_20250119_pabot0",
            "PASS",
            "2025-01-19T10:00:00+00:00",
            2000,
        )
        _create_trace(
            tmp_path,
            "test_b_20250119_pabot1",
            "FAIL",
            "2025-01-19T10:00:01+00:00",
            3000,
        )

        merger = PabotMerger(tmp_path)
        output = merger.merge()
        assert output.exists()

    def test_empty_dir(self, tmp_path):
        merger = PabotMerger(tmp_path)
        traces = merger.scan_traces()
        assert len(traces) == 0

    def test_timeline_html_generated(self, tmp_path):
        _create_trace(
            tmp_path,
            "test_pabot0",
            "PASS",
            "2025-01-19T10:00:00+00:00",
        )
        merger = PabotMerger(tmp_path)
        output = merger.merge()
        # Should have an HTML file in the output
        html_files = list(output.glob("*.html"))
        assert len(html_files) >= 1
