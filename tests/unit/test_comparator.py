"""Unit tests for the TraceComparator module."""

import json
from pathlib import Path
from typing import Any, Optional

import pytest

from trace_viewer.viewer.comparator import TraceComparator


@pytest.fixture
def temp_traces_dir(tmp_path: Path) -> Path:
    """Create a temporary traces directory."""
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    return traces_dir


def create_trace(
    base_dir: Path,
    name: str,
    test_name: str = "Test Name",
    status: str = "PASS",
    duration_ms: int = 1000,
    keywords: Optional[list[dict[str, Any]]] = None,
) -> Path:
    """Helper function to create a trace directory with manifest and keywords.

    Args:
        base_dir: Base directory for traces.
        name: Name of the trace directory.
        test_name: Name of the test.
        status: Test status (PASS, FAIL, etc.).
        duration_ms: Duration in milliseconds.
        keywords: List of keyword data dictionaries.

    Returns:
        Path to the created trace directory.
    """
    trace_dir = base_dir / name
    trace_dir.mkdir(parents=True, exist_ok=True)

    # Create manifest
    manifest = {
        "version": "1.0.0",
        "tool_version": "0.1.0",
        "test_name": test_name,
        "suite_name": "Test Suite",
        "suite_source": "/tests/suite.robot",
        "start_time": "2025-01-20T10:00:00.000Z",
        "end_time": "2025-01-20T10:00:01.000Z",
        "duration_ms": duration_ms,
        "status": status,
        "message": "" if status == "PASS" else "Test failed",
        "keywords_count": len(keywords) if keywords else 0,
        "rf_version": "7.0",
        "browser": "chrome",
        "capture_mode": "full",
    }
    with open(trace_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    # Create keywords directory and keyword data
    keywords_dir = trace_dir / "keywords"
    keywords_dir.mkdir(exist_ok=True)

    if keywords:
        for kw in keywords:
            kw_index = kw.get("index", 1)
            kw_name = kw.get("name", "Keyword").lower().replace(" ", "_")
            kw_dir = keywords_dir / f"{kw_index:03d}_{kw_name}"
            kw_dir.mkdir(exist_ok=True)

            # Write metadata
            metadata = {
                "index": kw_index,
                "name": kw.get("name", "Keyword"),
                "library": kw.get("library", "BuiltIn"),
                "args": kw.get("args", []),
                "status": kw.get("status", "PASS"),
                "duration_ms": kw.get("duration_ms", 100),
                "message": kw.get("message", ""),
                "level": kw.get("level", 0),
            }
            with open(kw_dir / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f)

            # Write variables if provided
            if "variables" in kw:
                with open(kw_dir / "variables.json", "w", encoding="utf-8") as f:
                    json.dump(kw["variables"], f)

            # Create a dummy screenshot if requested
            if kw.get("has_screenshot", False):
                # Minimal valid PNG (1x1 transparent pixel)
                png_data = (
                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
                    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
                )
                (kw_dir / "screenshot.png").write_bytes(png_data)

    return trace_dir


class TestTraceComparatorInit:
    """Tests for TraceComparator initialization."""

    def test_init_with_valid_traces(self, temp_traces_dir: Path) -> None:
        """Test initialization with two valid trace directories."""
        trace1 = create_trace(temp_traces_dir, "trace1", test_name="Test 1")
        trace2 = create_trace(temp_traces_dir, "trace2", test_name="Test 2")

        comparator = TraceComparator(trace1, trace2)

        assert comparator.trace1_dir == trace1
        assert comparator.trace2_dir == trace2
        assert comparator.trace1_data["test_name"] == "Test 1"
        assert comparator.trace2_data["test_name"] == "Test 2"

    def test_init_with_nonexistent_trace1(self, temp_traces_dir: Path) -> None:
        """Test initialization fails when trace1 doesn't exist."""
        trace2 = create_trace(temp_traces_dir, "trace2")
        nonexistent = temp_traces_dir / "nonexistent"

        with pytest.raises(FileNotFoundError, match="Trace directory not found"):
            TraceComparator(nonexistent, trace2)

    def test_init_with_nonexistent_trace2(self, temp_traces_dir: Path) -> None:
        """Test initialization fails when trace2 doesn't exist."""
        trace1 = create_trace(temp_traces_dir, "trace1")
        nonexistent = temp_traces_dir / "nonexistent"

        with pytest.raises(FileNotFoundError, match="Trace directory not found"):
            TraceComparator(trace1, nonexistent)

    def test_init_without_manifest(self, temp_traces_dir: Path) -> None:
        """Test initialization fails when manifest.json is missing."""
        trace1 = create_trace(temp_traces_dir, "trace1")
        trace2_dir = temp_traces_dir / "trace2"
        trace2_dir.mkdir()  # No manifest.json

        with pytest.raises(FileNotFoundError, match="Manifest not found"):
            TraceComparator(trace1, trace2_dir)


class TestMetadataComparison:
    """Tests for metadata comparison functionality."""

    def test_compare_identical_metadata(self, temp_traces_dir: Path) -> None:
        """Test comparing traces with identical metadata."""
        trace1 = create_trace(
            temp_traces_dir, "trace1", test_name="Same Test", status="PASS", duration_ms=1000
        )
        trace2 = create_trace(
            temp_traces_dir, "trace2", test_name="Same Test", status="PASS", duration_ms=1000
        )

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        metadata_diff = result["metadata_diff"]
        assert metadata_diff["test_name"]["changed"] is False
        assert metadata_diff["status"]["changed"] is False

    def test_compare_different_test_names(self, temp_traces_dir: Path) -> None:
        """Test comparing traces with different test names."""
        trace1 = create_trace(temp_traces_dir, "trace1", test_name="Test A")
        trace2 = create_trace(temp_traces_dir, "trace2", test_name="Test B")

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        diff = result["metadata_diff"]["test_name"]
        assert diff["changed"] is True
        assert diff["trace1"] == "Test A"
        assert diff["trace2"] == "Test B"

    def test_compare_different_status(self, temp_traces_dir: Path) -> None:
        """Test comparing traces with different statuses."""
        trace1 = create_trace(temp_traces_dir, "trace1", status="PASS")
        trace2 = create_trace(temp_traces_dir, "trace2", status="FAIL")

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        diff = result["metadata_diff"]["status"]
        assert diff["changed"] is True
        assert diff["trace1"] == "PASS"
        assert diff["trace2"] == "FAIL"

    def test_compare_different_duration(self, temp_traces_dir: Path) -> None:
        """Test comparing traces with different durations."""
        trace1 = create_trace(temp_traces_dir, "trace1", duration_ms=1000)
        trace2 = create_trace(temp_traces_dir, "trace2", duration_ms=5000)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        diff = result["metadata_diff"]["duration_ms"]
        assert diff["changed"] is True
        assert diff["trace1"] == 1000
        assert diff["trace2"] == 5000


class TestKeywordComparison:
    """Tests for keyword comparison functionality."""

    def test_compare_identical_keywords(self, temp_traces_dir: Path) -> None:
        """Test comparing traces with identical keywords."""
        keywords = [
            {"index": 1, "name": "Open Browser", "status": "PASS", "duration_ms": 100},
            {"index": 2, "name": "Click Button", "status": "PASS", "duration_ms": 50},
        ]
        trace1 = create_trace(temp_traces_dir, "trace1", keywords=keywords)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=keywords)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        kw_comp = result["keywords_comparison"]
        assert len(kw_comp) == 2
        assert kw_comp[0]["match_type"] == "matched"
        assert kw_comp[1]["match_type"] == "matched"

    def test_compare_modified_keyword_status(self, temp_traces_dir: Path) -> None:
        """Test comparing keywords with different statuses."""
        kw1 = [{"index": 1, "name": "Click Button", "status": "PASS"}]
        kw2 = [{"index": 1, "name": "Click Button", "status": "FAIL"}]

        trace1 = create_trace(temp_traces_dir, "trace1", keywords=kw1)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=kw2)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        kw_comp = result["keywords_comparison"]
        assert len(kw_comp) == 1
        assert kw_comp[0]["match_type"] == "modified"
        assert kw_comp[0]["status_match"] is False

    def test_compare_added_keyword(self, temp_traces_dir: Path) -> None:
        """Test comparing when trace2 has an additional keyword."""
        kw1 = [{"index": 1, "name": "Open Browser", "status": "PASS"}]
        kw2 = [
            {"index": 1, "name": "Open Browser", "status": "PASS"},
            {"index": 2, "name": "Click Button", "status": "PASS"},
        ]

        trace1 = create_trace(temp_traces_dir, "trace1", keywords=kw1)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=kw2)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        kw_comp = result["keywords_comparison"]
        assert len(kw_comp) == 2
        assert kw_comp[0]["match_type"] == "matched"
        assert kw_comp[1]["match_type"] == "added"
        assert kw_comp[1]["trace1_kw"] is None
        assert kw_comp[1]["trace2_kw"] is not None

    def test_compare_removed_keyword(self, temp_traces_dir: Path) -> None:
        """Test comparing when trace1 has a keyword that trace2 doesn't."""
        kw1 = [
            {"index": 1, "name": "Open Browser", "status": "PASS"},
            {"index": 2, "name": "Click Button", "status": "PASS"},
        ]
        kw2 = [{"index": 1, "name": "Open Browser", "status": "PASS"}]

        trace1 = create_trace(temp_traces_dir, "trace1", keywords=kw1)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=kw2)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        kw_comp = result["keywords_comparison"]
        assert len(kw_comp) == 2
        assert kw_comp[0]["match_type"] == "matched"
        assert kw_comp[1]["match_type"] == "removed"
        assert kw_comp[1]["trace1_kw"] is not None
        assert kw_comp[1]["trace2_kw"] is None

    def test_compare_different_keyword_names_same_index(self, temp_traces_dir: Path) -> None:
        """Test comparing keywords with same index but different names."""
        kw1 = [{"index": 1, "name": "Open Browser", "status": "PASS"}]
        kw2 = [{"index": 1, "name": "Go To URL", "status": "PASS"}]

        trace1 = create_trace(temp_traces_dir, "trace1", keywords=kw1)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=kw2)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        kw_comp = result["keywords_comparison"]
        assert len(kw_comp) == 1
        assert kw_comp[0]["match_type"] == "modified"
        assert kw_comp[0]["name_match"] is False

    def test_compare_duration_difference(self, temp_traces_dir: Path) -> None:
        """Test duration difference calculation."""
        kw1 = [{"index": 1, "name": "Sleep", "status": "PASS", "duration_ms": 100}]
        kw2 = [{"index": 1, "name": "Sleep", "status": "PASS", "duration_ms": 500}]

        trace1 = create_trace(temp_traces_dir, "trace1", keywords=kw1)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=kw2)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        kw_comp = result["keywords_comparison"]
        assert kw_comp[0]["duration_diff"] == 400  # 500 - 100


class TestVariableComparison:
    """Tests for variable comparison functionality."""

    def test_compare_identical_variables(self, temp_traces_dir: Path) -> None:
        """Test comparing keywords with identical variables."""
        variables = {"${URL}": "https://example.com", "${USERNAME}": "testuser"}
        kw1 = [{"index": 1, "name": "Setup", "status": "PASS", "variables": variables}]
        kw2 = [{"index": 1, "name": "Setup", "status": "PASS", "variables": variables}]

        trace1 = create_trace(temp_traces_dir, "trace1", keywords=kw1)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=kw2)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        kw_comp = result["keywords_comparison"]
        assert kw_comp[0]["variable_diff"] == {}
        assert kw_comp[0]["match_type"] == "matched"

    def test_compare_added_variable(self, temp_traces_dir: Path) -> None:
        """Test comparing when trace2 has an additional variable."""
        kw1 = [{"index": 1, "name": "Setup", "status": "PASS", "variables": {"${URL}": "url"}}]
        kw2 = [
            {
                "index": 1,
                "name": "Setup",
                "status": "PASS",
                "variables": {"${URL}": "url", "${NEW_VAR}": "value"},
            }
        ]

        trace1 = create_trace(temp_traces_dir, "trace1", keywords=kw1)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=kw2)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        var_diff = result["keywords_comparison"][0]["variable_diff"]
        assert "${NEW_VAR}" in var_diff
        assert var_diff["${NEW_VAR}"]["type"] == "added"
        assert var_diff["${NEW_VAR}"]["trace1"] is None
        assert var_diff["${NEW_VAR}"]["trace2"] == "value"

    def test_compare_removed_variable(self, temp_traces_dir: Path) -> None:
        """Test comparing when trace1 has a variable that trace2 doesn't."""
        kw1 = [
            {
                "index": 1,
                "name": "Setup",
                "status": "PASS",
                "variables": {"${URL}": "url", "${OLD_VAR}": "value"},
            }
        ]
        kw2 = [{"index": 1, "name": "Setup", "status": "PASS", "variables": {"${URL}": "url"}}]

        trace1 = create_trace(temp_traces_dir, "trace1", keywords=kw1)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=kw2)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        var_diff = result["keywords_comparison"][0]["variable_diff"]
        assert "${OLD_VAR}" in var_diff
        assert var_diff["${OLD_VAR}"]["type"] == "removed"
        assert var_diff["${OLD_VAR}"]["trace1"] == "value"
        assert var_diff["${OLD_VAR}"]["trace2"] is None

    def test_compare_changed_variable(self, temp_traces_dir: Path) -> None:
        """Test comparing when a variable has a different value."""
        kw1 = [{"index": 1, "name": "Setup", "status": "PASS", "variables": {"${COUNT}": 5}}]
        kw2 = [{"index": 1, "name": "Setup", "status": "PASS", "variables": {"${COUNT}": 10}}]

        trace1 = create_trace(temp_traces_dir, "trace1", keywords=kw1)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=kw2)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        var_diff = result["keywords_comparison"][0]["variable_diff"]
        assert "${COUNT}" in var_diff
        assert var_diff["${COUNT}"]["type"] == "changed"
        assert var_diff["${COUNT}"]["trace1"] == 5
        assert var_diff["${COUNT}"]["trace2"] == 10


class TestSummaryCalculation:
    """Tests for summary statistics calculation."""

    def test_summary_all_matched(self, temp_traces_dir: Path) -> None:
        """Test summary when all keywords match."""
        keywords = [
            {"index": 1, "name": "Keyword 1", "status": "PASS"},
            {"index": 2, "name": "Keyword 2", "status": "PASS"},
        ]
        trace1 = create_trace(temp_traces_dir, "trace1", keywords=keywords)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=keywords)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        summary = result["summary"]
        assert summary["total_keywords"] == 2
        assert summary["matched"] == 2
        assert summary["modified"] == 0
        assert summary["added"] == 0
        assert summary["removed"] == 0

    def test_summary_with_all_types(self, temp_traces_dir: Path) -> None:
        """Test summary with matched, modified, added, and removed keywords."""
        kw1 = [
            {"index": 1, "name": "Matched", "status": "PASS"},
            {"index": 2, "name": "Modified", "status": "PASS"},
            {"index": 3, "name": "Removed", "status": "PASS"},
        ]
        kw2 = [
            {"index": 1, "name": "Matched", "status": "PASS"},
            {"index": 2, "name": "Modified", "status": "FAIL"},  # Status change
            {"index": 4, "name": "Added", "status": "PASS"},
        ]

        trace1 = create_trace(temp_traces_dir, "trace1", keywords=kw1)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=kw2)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        summary = result["summary"]
        assert summary["total_keywords"] == 4  # 1, 2, 3, 4
        assert summary["matched"] == 1
        assert summary["modified"] == 1
        assert summary["added"] == 1
        assert summary["removed"] == 1
        assert summary["status_changes"] == 1

    def test_summary_variable_changes_count(self, temp_traces_dir: Path) -> None:
        """Test summary counts keywords with variable changes."""
        kw1 = [
            {"index": 1, "name": "KW1", "status": "PASS", "variables": {"${A}": 1}},
            {"index": 2, "name": "KW2", "status": "PASS", "variables": {"${B}": 2}},
        ]
        kw2 = [
            {"index": 1, "name": "KW1", "status": "PASS", "variables": {"${A}": 100}},
            {"index": 2, "name": "KW2", "status": "PASS", "variables": {"${B}": 2}},
        ]

        trace1 = create_trace(temp_traces_dir, "trace1", keywords=kw1)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=kw2)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        summary = result["summary"]
        assert summary["variable_changes"] == 1


class TestHtmlGeneration:
    """Tests for HTML comparison generation."""

    def test_generate_html_creates_file(self, temp_traces_dir: Path, tmp_path: Path) -> None:
        """Test that generate_html creates the output file."""
        trace1 = create_trace(temp_traces_dir, "trace1")
        trace2 = create_trace(temp_traces_dir, "trace2")
        output_path = tmp_path / "comparison.html"

        comparator = TraceComparator(trace1, trace2)
        result_path = comparator.generate_html(output_path)

        assert result_path == output_path
        assert output_path.exists()

    def test_generate_html_content(self, temp_traces_dir: Path, tmp_path: Path) -> None:
        """Test that generated HTML contains expected content."""
        trace1 = create_trace(temp_traces_dir, "trace1", test_name="Test Alpha")
        trace2 = create_trace(temp_traces_dir, "trace2", test_name="Test Beta")
        output_path = tmp_path / "comparison.html"

        comparator = TraceComparator(trace1, trace2)
        comparator.generate_html(output_path)

        html = output_path.read_text(encoding="utf-8")

        # Check for expected elements
        assert "<!DOCTYPE html>" in html
        assert "Trace Comparison" in html
        assert "Test Alpha" in html
        assert "Test Beta" in html
        assert "COMPARISON_DATA" in html

    def test_generate_html_creates_parent_directories(
        self, temp_traces_dir: Path, tmp_path: Path
    ) -> None:
        """Test that generate_html creates parent directories if needed."""
        trace1 = create_trace(temp_traces_dir, "trace1")
        trace2 = create_trace(temp_traces_dir, "trace2")
        output_path = tmp_path / "nested" / "deep" / "comparison.html"

        comparator = TraceComparator(trace1, trace2)
        comparator.generate_html(output_path)

        assert output_path.exists()
        assert output_path.parent.exists()

    def test_generate_html_with_keywords(self, temp_traces_dir: Path, tmp_path: Path) -> None:
        """Test HTML generation with keyword comparison data."""
        keywords1 = [{"index": 1, "name": "Open Browser", "status": "PASS"}]
        keywords2 = [{"index": 1, "name": "Open Browser", "status": "FAIL"}]

        trace1 = create_trace(temp_traces_dir, "trace1", keywords=keywords1)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=keywords2)
        output_path = tmp_path / "comparison.html"

        comparator = TraceComparator(trace1, trace2)
        comparator.generate_html(output_path)

        html = output_path.read_text(encoding="utf-8")

        # The HTML should contain the comparison data JSON
        assert "Open Browser" in html
        assert '"match_type"' in html
        assert '"modified"' in html

    def test_generate_html_with_variable_diff(self, temp_traces_dir: Path, tmp_path: Path) -> None:
        """Test HTML generation includes variable differences."""
        kw1 = [{"index": 1, "name": "Setup", "status": "PASS", "variables": {"${URL}": "old.com"}}]
        kw2 = [{"index": 1, "name": "Setup", "status": "PASS", "variables": {"${URL}": "new.com"}}]

        trace1 = create_trace(temp_traces_dir, "trace1", keywords=kw1)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=kw2)
        output_path = tmp_path / "comparison.html"

        comparator = TraceComparator(trace1, trace2)
        comparator.generate_html(output_path)

        html = output_path.read_text(encoding="utf-8")

        # Variable diff should be in the data
        assert '"variable_diff"' in html
        assert "old.com" in html
        assert "new.com" in html


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_compare_empty_traces(self, temp_traces_dir: Path) -> None:
        """Test comparing traces with no keywords."""
        trace1 = create_trace(temp_traces_dir, "trace1", keywords=[])
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=[])

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        assert result["keywords_comparison"] == []
        assert result["summary"]["total_keywords"] == 0

    def test_compare_trace1_empty_trace2_has_keywords(self, temp_traces_dir: Path) -> None:
        """Test comparing when trace1 is empty but trace2 has keywords."""
        kw2 = [{"index": 1, "name": "New Keyword", "status": "PASS"}]
        trace1 = create_trace(temp_traces_dir, "trace1", keywords=[])
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=kw2)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        kw_comp = result["keywords_comparison"]
        assert len(kw_comp) == 1
        assert kw_comp[0]["match_type"] == "added"

    def test_compare_trace1_has_keywords_trace2_empty(self, temp_traces_dir: Path) -> None:
        """Test comparing when trace1 has keywords but trace2 is empty."""
        kw1 = [{"index": 1, "name": "Old Keyword", "status": "PASS"}]
        trace1 = create_trace(temp_traces_dir, "trace1", keywords=kw1)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=[])

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        kw_comp = result["keywords_comparison"]
        assert len(kw_comp) == 1
        assert kw_comp[0]["match_type"] == "removed"

    def test_compare_with_screenshot_paths(self, temp_traces_dir: Path) -> None:
        """Test that screenshot paths are preserved in comparison."""
        kw1 = [{"index": 1, "name": "Screenshot KW", "status": "PASS", "has_screenshot": True}]
        kw2 = [{"index": 1, "name": "Screenshot KW", "status": "PASS", "has_screenshot": True}]

        trace1 = create_trace(temp_traces_dir, "trace1", keywords=kw1)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=kw2)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        # Screenshots should be loaded from keyword directories
        kw_comp = result["keywords_comparison"]
        assert kw_comp[0]["trace1_kw"].get("screenshot") is not None
        assert kw_comp[0]["trace2_kw"].get("screenshot") is not None

    def test_compare_preserves_trace_info(self, temp_traces_dir: Path) -> None:
        """Test that trace directory info is preserved in comparison."""
        trace1 = create_trace(temp_traces_dir, "trace1", test_name="Test 1")
        trace2 = create_trace(temp_traces_dir, "trace2", test_name="Test 2")

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        assert result["trace1"]["trace_dir"] == str(trace1)
        assert result["trace2"]["trace_dir"] == str(trace2)
        assert result["trace1"]["name"] == "trace1"
        assert result["trace2"]["name"] == "trace2"

    def test_compare_complex_variables(self, temp_traces_dir: Path) -> None:
        """Test comparing complex variable types (lists, dicts)."""
        kw1 = [
            {
                "index": 1,
                "name": "Complex",
                "status": "PASS",
                "variables": {
                    "${LIST}": ["a", "b", "c"],
                    "${DICT}": {"key": "value"},
                },
            }
        ]
        kw2 = [
            {
                "index": 1,
                "name": "Complex",
                "status": "PASS",
                "variables": {
                    "${LIST}": ["a", "b", "d"],  # Changed
                    "${DICT}": {"key": "value"},  # Same
                },
            }
        ]

        trace1 = create_trace(temp_traces_dir, "trace1", keywords=kw1)
        trace2 = create_trace(temp_traces_dir, "trace2", keywords=kw2)

        comparator = TraceComparator(trace1, trace2)
        result = comparator.compare()

        var_diff = result["keywords_comparison"][0]["variable_diff"]
        assert "${LIST}" in var_diff
        assert var_diff["${LIST}"]["type"] == "changed"
        assert "${DICT}" not in var_diff  # Same value, no diff
