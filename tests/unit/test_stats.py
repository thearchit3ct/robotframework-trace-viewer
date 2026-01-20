"""Unit tests for the Statistics Dashboard module."""

import json
from pathlib import Path

import pytest


class TestStatsDashboardInit:
    """Tests for StatsDashboard initialization."""

    def test_init_with_valid_directory(self, tmp_path: Path) -> None:
        """Init succeeds with a valid directory."""
        from trace_viewer.stats.dashboard import StatsDashboard

        dashboard = StatsDashboard(tmp_path)
        assert dashboard.traces_dir == tmp_path
        assert dashboard.traces == []

    def test_init_with_nonexistent_directory(self, tmp_path: Path) -> None:
        """Init raises FileNotFoundError for nonexistent directory."""
        from trace_viewer.stats.dashboard import StatsDashboard

        nonexistent = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError):
            StatsDashboard(nonexistent)

    def test_init_loads_traces(self, tmp_path: Path) -> None:
        """Init loads trace manifests from subdirectories."""
        from trace_viewer.stats.dashboard import StatsDashboard

        # Create a trace
        trace_dir = tmp_path / "test_trace_20250120"
        trace_dir.mkdir()
        manifest = {
            "test_name": "Test Example",
            "status": "PASS",
            "duration_ms": 1000,
            "start_time": "2025-01-20T10:00:00Z",
        }
        (trace_dir / "manifest.json").write_text(json.dumps(manifest))

        dashboard = StatsDashboard(tmp_path)
        assert len(dashboard.traces) == 1
        assert dashboard.traces[0]["test_name"] == "Test Example"


class TestCalculateStatistics:
    """Tests for calculate_statistics method."""

    def test_empty_statistics_when_no_traces(self, tmp_path: Path) -> None:
        """Returns empty statistics when no traces exist."""
        from trace_viewer.stats.dashboard import StatsDashboard

        dashboard = StatsDashboard(tmp_path)
        stats = dashboard.calculate_statistics()

        assert stats["summary"]["total"] == 0
        assert stats["summary"]["passed"] == 0
        assert stats["summary"]["failed"] == 0
        assert stats["summary"]["pass_rate"] == 0

    def test_statistics_with_one_passing_test(self, tmp_path: Path) -> None:
        """Calculates correct statistics with one passing test."""
        from trace_viewer.stats.dashboard import StatsDashboard

        trace_dir = tmp_path / "test1"
        trace_dir.mkdir()
        (trace_dir / "manifest.json").write_text(
            json.dumps({"test_name": "Test", "status": "PASS", "duration_ms": 500})
        )

        dashboard = StatsDashboard(tmp_path)
        stats = dashboard.calculate_statistics()

        assert stats["summary"]["total"] == 1
        assert stats["summary"]["passed"] == 1
        assert stats["summary"]["pass_rate"] == 100.0

    def test_statistics_with_mixed_statuses(self, tmp_path: Path) -> None:
        """Calculates correct statistics with mixed test statuses."""
        from trace_viewer.stats.dashboard import StatsDashboard

        # Create 4 traces: 2 PASS, 1 FAIL, 1 SKIP
        for i, status in enumerate(["PASS", "PASS", "FAIL", "SKIP"]):
            trace_dir = tmp_path / f"test{i}"
            trace_dir.mkdir()
            (trace_dir / "manifest.json").write_text(
                json.dumps(
                    {"test_name": f"Test {i}", "status": status, "duration_ms": 100 * (i + 1)}
                )
            )

        dashboard = StatsDashboard(tmp_path)
        stats = dashboard.calculate_statistics()

        assert stats["summary"]["total"] == 4
        assert stats["summary"]["passed"] == 2
        assert stats["summary"]["failed"] == 1
        assert stats["summary"]["skipped"] == 1
        assert stats["summary"]["pass_rate"] == 50.0
        assert stats["summary"]["fail_rate"] == 25.0

    def test_duration_statistics(self, tmp_path: Path) -> None:
        """Calculates correct duration statistics."""
        from trace_viewer.stats.dashboard import StatsDashboard

        durations = [100, 200, 300, 400, 500]
        for i, duration in enumerate(durations):
            trace_dir = tmp_path / f"test{i}"
            trace_dir.mkdir()
            (trace_dir / "manifest.json").write_text(
                json.dumps({"test_name": f"Test {i}", "status": "PASS", "duration_ms": duration})
            )

        dashboard = StatsDashboard(tmp_path)
        stats = dashboard.calculate_statistics()

        assert stats["duration_stats"]["total_ms"] == 1500
        assert stats["duration_stats"]["average_ms"] == 300
        assert stats["duration_stats"]["min_ms"] == 100
        assert stats["duration_stats"]["max_ms"] == 500


class TestSlowestTests:
    """Tests for slowest tests calculation."""

    def test_slowest_tests_ordered_correctly(self, tmp_path: Path) -> None:
        """Slowest tests are ordered by duration descending."""
        from trace_viewer.stats.dashboard import StatsDashboard

        durations = [100, 500, 300, 200, 400]
        for i, duration in enumerate(durations):
            trace_dir = tmp_path / f"test{i}"
            trace_dir.mkdir()
            (trace_dir / "manifest.json").write_text(
                json.dumps({"test_name": f"Test {i}", "status": "PASS", "duration_ms": duration})
            )

        dashboard = StatsDashboard(tmp_path)
        stats = dashboard.calculate_statistics()

        slowest = stats["slowest_tests"]
        assert len(slowest) == 5
        assert slowest[0]["duration_ms"] == 500
        assert slowest[1]["duration_ms"] == 400
        assert slowest[4]["duration_ms"] == 100

    def test_slowest_tests_limited_to_10(self, tmp_path: Path) -> None:
        """Slowest tests list is limited to 10."""
        from trace_viewer.stats.dashboard import StatsDashboard

        for i in range(15):
            trace_dir = tmp_path / f"test{i}"
            trace_dir.mkdir()
            (trace_dir / "manifest.json").write_text(
                json.dumps({"test_name": f"Test {i}", "status": "PASS", "duration_ms": i * 100})
            )

        dashboard = StatsDashboard(tmp_path)
        stats = dashboard.calculate_statistics()

        assert len(stats["slowest_tests"]) == 10


class TestFlakyTests:
    """Tests for flaky test detection."""

    def test_identifies_flaky_test(self, tmp_path: Path) -> None:
        """Identifies tests that have both passed and failed."""
        from trace_viewer.stats.dashboard import StatsDashboard

        # Same test name with different statuses
        for i, status in enumerate(["PASS", "FAIL", "PASS"]):
            trace_dir = tmp_path / f"flaky_test_{i}"
            trace_dir.mkdir()
            (trace_dir / "manifest.json").write_text(
                json.dumps({"test_name": "Flaky Test", "status": status, "duration_ms": 100})
            )

        dashboard = StatsDashboard(tmp_path)
        stats = dashboard.calculate_statistics()

        flaky_tests = [t for t in stats["test_name_stats"] if t["is_flaky"]]
        assert len(flaky_tests) == 1
        assert flaky_tests[0]["name"] == "Flaky Test"
        assert flaky_tests[0]["total_runs"] == 3
        assert flaky_tests[0]["passed"] == 2
        assert flaky_tests[0]["failed"] == 1

    def test_non_flaky_all_pass(self, tmp_path: Path) -> None:
        """Tests that always pass are not marked as flaky."""
        from trace_viewer.stats.dashboard import StatsDashboard

        for i in range(3):
            trace_dir = tmp_path / f"stable_test_{i}"
            trace_dir.mkdir()
            (trace_dir / "manifest.json").write_text(
                json.dumps({"test_name": "Stable Test", "status": "PASS", "duration_ms": 100})
            )

        dashboard = StatsDashboard(tmp_path)
        stats = dashboard.calculate_statistics()

        flaky_tests = [t for t in stats["test_name_stats"] if t["is_flaky"]]
        assert len(flaky_tests) == 0


class TestKeywordStats:
    """Tests for keyword statistics calculation."""

    def test_keyword_stats_with_keywords(self, tmp_path: Path) -> None:
        """Calculates keyword statistics from keyword directories."""
        from trace_viewer.stats.dashboard import StatsDashboard

        trace_dir = tmp_path / "test1"
        trace_dir.mkdir()
        (trace_dir / "manifest.json").write_text(
            json.dumps({"test_name": "Test", "status": "PASS", "duration_ms": 1000})
        )

        # Create keywords directory
        keywords_dir = trace_dir / "keywords"
        keywords_dir.mkdir()

        for i in range(3):
            kw_dir = keywords_dir / f"00{i+1}_keyword"
            kw_dir.mkdir()
            (kw_dir / "metadata.json").write_text(
                json.dumps({"name": "Click Button", "status": "PASS", "duration_ms": 100})
            )

        dashboard = StatsDashboard(tmp_path)
        stats = dashboard.calculate_statistics()

        assert stats["keyword_stats"]["total"] == 3
        assert stats["keyword_stats"]["unique"] == 1
        assert "Click Button" in stats["keyword_stats"]["by_name"]
        assert stats["keyword_stats"]["by_name"]["Click Button"]["count"] == 3


class TestGenerateHtml:
    """Tests for HTML generation."""

    def test_generate_html_creates_file(self, tmp_path: Path) -> None:
        """generate_html creates an HTML file."""
        from trace_viewer.stats.dashboard import StatsDashboard

        dashboard = StatsDashboard(tmp_path)
        output_path = dashboard.generate_html()

        assert output_path.exists()
        assert output_path.name == "dashboard.html"

    def test_generate_html_custom_output(self, tmp_path: Path) -> None:
        """generate_html respects custom output path."""
        from trace_viewer.stats.dashboard import StatsDashboard

        dashboard = StatsDashboard(tmp_path)
        custom_path = tmp_path / "custom" / "stats.html"
        output_path = dashboard.generate_html(custom_path)

        assert output_path == custom_path
        assert output_path.exists()

    def test_generate_html_content(self, tmp_path: Path) -> None:
        """Generated HTML contains expected content."""
        from trace_viewer.stats.dashboard import StatsDashboard

        # Create a trace
        trace_dir = tmp_path / "test1"
        trace_dir.mkdir()
        (trace_dir / "manifest.json").write_text(
            json.dumps({"test_name": "Example Test", "status": "PASS", "duration_ms": 500})
        )

        dashboard = StatsDashboard(tmp_path)
        output_path = dashboard.generate_html()

        content = output_path.read_text()
        assert "Test Statistics Dashboard" in content
        assert "Example Test" in content or "STATS" in content
        assert "<!DOCTYPE html>" in content


class TestTimeline:
    """Tests for timeline generation."""

    def test_timeline_sorted_by_date_descending(self, tmp_path: Path) -> None:
        """Timeline is sorted by start_time descending."""
        from trace_viewer.stats.dashboard import StatsDashboard

        dates = [
            "2025-01-20T10:00:00Z",
            "2025-01-20T12:00:00Z",
            "2025-01-20T11:00:00Z",
        ]
        for i, date in enumerate(dates):
            trace_dir = tmp_path / f"test{i}"
            trace_dir.mkdir()
            (trace_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "test_name": f"Test {i}",
                        "status": "PASS",
                        "duration_ms": 100,
                        "start_time": date,
                    }
                )
            )

        dashboard = StatsDashboard(tmp_path)
        stats = dashboard.calculate_statistics()

        timeline = stats["timeline"]
        assert len(timeline) == 3
        assert timeline[0]["start_time"] == "2025-01-20T12:00:00Z"
        assert timeline[1]["start_time"] == "2025-01-20T11:00:00Z"
        assert timeline[2]["start_time"] == "2025-01-20T10:00:00Z"

    def test_timeline_limited_to_50(self, tmp_path: Path) -> None:
        """Timeline is limited to 50 most recent entries."""
        from trace_viewer.stats.dashboard import StatsDashboard

        for i in range(60):
            trace_dir = tmp_path / f"test{i}"
            trace_dir.mkdir()
            (trace_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "test_name": f"Test {i}",
                        "status": "PASS",
                        "duration_ms": 100,
                        "start_time": f"2025-01-{20 + (i // 24):02d}T{i % 24:02d}:00:00Z",
                    }
                )
            )

        dashboard = StatsDashboard(tmp_path)
        stats = dashboard.calculate_statistics()

        assert len(stats["timeline"]) == 50


class TestCLIStatsCommand:
    """Tests for CLI stats command."""

    def test_stats_command_generates_dashboard(self, tmp_path: Path) -> None:
        """Stats command generates dashboard file."""
        from click.testing import CliRunner

        from trace_viewer.cli import main

        # Create a trace
        trace_dir = tmp_path / "test1"
        trace_dir.mkdir()
        (trace_dir / "manifest.json").write_text(
            json.dumps({"test_name": "Test", "status": "PASS", "duration_ms": 500})
        )

        runner = CliRunner()
        result = runner.invoke(main, ["stats", str(tmp_path)])

        assert result.exit_code == 0
        assert "Dashboard generated" in result.output
        assert (tmp_path / "dashboard.html").exists()

    def test_stats_command_shows_summary(self, tmp_path: Path) -> None:
        """Stats command shows summary statistics."""
        from click.testing import CliRunner

        from trace_viewer.cli import main

        # Create traces
        for i, status in enumerate(["PASS", "PASS", "FAIL"]):
            trace_dir = tmp_path / f"test{i}"
            trace_dir.mkdir()
            (trace_dir / "manifest.json").write_text(
                json.dumps({"test_name": f"Test {i}", "status": status, "duration_ms": 100})
            )

        runner = CliRunner()
        result = runner.invoke(main, ["stats", str(tmp_path)])

        assert result.exit_code == 0
        assert "Found 3 trace(s)" in result.output
        assert "2 passed" in result.output
        assert "1 failed" in result.output

    def test_stats_command_custom_output(self, tmp_path: Path) -> None:
        """Stats command respects custom output path."""
        from click.testing import CliRunner

        from trace_viewer.cli import main

        # Create a trace
        trace_dir = tmp_path / "traces" / "test1"
        trace_dir.mkdir(parents=True)
        (trace_dir / "manifest.json").write_text(
            json.dumps({"test_name": "Test", "status": "PASS", "duration_ms": 500})
        )

        output_path = tmp_path / "custom_dashboard.html"
        runner = CliRunner()
        result = runner.invoke(main, ["stats", str(tmp_path / "traces"), "-o", str(output_path)])

        assert result.exit_code == 0
        assert output_path.exists()

    def test_stats_command_nonexistent_directory(self) -> None:
        """Stats command fails for nonexistent directory."""
        from click.testing import CliRunner

        from trace_viewer.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["stats", "/nonexistent/path"])

        assert result.exit_code != 0
