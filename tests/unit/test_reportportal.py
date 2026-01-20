"""Unit tests for the ReportPortal integration module."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


class TestReportPortalExporterInit:
    """Tests for ReportPortalExporter initialization."""

    def test_init_with_valid_params(self) -> None:
        """Init succeeds with valid parameters."""
        with patch(
            "trace_viewer.integrations.reportportal.ReportPortalExporter._check_dependencies"
        ):
            from trace_viewer.integrations.reportportal import ReportPortalExporter

            exporter = ReportPortalExporter(
                endpoint="https://rp.example.com",
                project="test_project",
                api_key="test_api_key",
            )

            assert exporter.endpoint == "https://rp.example.com"
            assert exporter.project == "test_project"
            assert exporter.api_key == "test_api_key"
            assert exporter.launch_name == "Robot Framework Traces"

    def test_init_strips_trailing_slash_from_endpoint(self) -> None:
        """Init strips trailing slash from endpoint."""
        with patch(
            "trace_viewer.integrations.reportportal.ReportPortalExporter._check_dependencies"
        ):
            from trace_viewer.integrations.reportportal import ReportPortalExporter

            exporter = ReportPortalExporter(
                endpoint="https://rp.example.com/",
                project="test_project",
                api_key="test_api_key",
            )

            assert exporter.endpoint == "https://rp.example.com"

    def test_init_with_custom_launch_name(self) -> None:
        """Init accepts custom launch name."""
        with patch(
            "trace_viewer.integrations.reportportal.ReportPortalExporter._check_dependencies"
        ):
            from trace_viewer.integrations.reportportal import ReportPortalExporter

            exporter = ReportPortalExporter(
                endpoint="https://rp.example.com",
                project="test_project",
                api_key="test_api_key",
                launch_name="Custom Launch",
            )

            assert exporter.launch_name == "Custom Launch"


class TestStatusMapping:
    """Tests for status mapping between RF and ReportPortal."""

    @pytest.fixture
    def exporter(self) -> Any:
        """Create exporter instance for testing."""
        with patch(
            "trace_viewer.integrations.reportportal.ReportPortalExporter._check_dependencies"
        ):
            from trace_viewer.integrations.reportportal import ReportPortalExporter

            return ReportPortalExporter(
                endpoint="https://rp.example.com",
                project="test_project",
                api_key="test_api_key",
            )

    def test_map_pass_status(self, exporter: Any) -> None:
        """PASS maps to PASSED."""
        assert exporter._map_status("PASS") == "PASSED"

    def test_map_fail_status(self, exporter: Any) -> None:
        """FAIL maps to FAILED."""
        assert exporter._map_status("FAIL") == "FAILED"

    def test_map_skip_status(self, exporter: Any) -> None:
        """SKIP maps to SKIPPED."""
        assert exporter._map_status("SKIP") == "SKIPPED"

    def test_map_not_run_status(self, exporter: Any) -> None:
        """NOT RUN maps to SKIPPED."""
        assert exporter._map_status("NOT RUN") == "SKIPPED"
        assert exporter._map_status("NOT_RUN") == "SKIPPED"

    def test_map_unknown_status(self, exporter: Any) -> None:
        """Unknown status maps to FAILED."""
        assert exporter._map_status("UNKNOWN") == "FAILED"


class TestBuildAttributes:
    """Tests for attribute building."""

    @pytest.fixture
    def exporter(self) -> Any:
        """Create exporter instance for testing."""
        with patch(
            "trace_viewer.integrations.reportportal.ReportPortalExporter._check_dependencies"
        ):
            from trace_viewer.integrations.reportportal import ReportPortalExporter

            return ReportPortalExporter(
                endpoint="https://rp.example.com",
                project="test_project",
                api_key="test_api_key",
            )

    def test_build_attributes_with_suite(self, exporter: Any) -> None:
        """Builds suite attribute."""
        manifest = {"suite_name": "Test Suite"}
        attrs = exporter._build_attributes(manifest)

        assert {"key": "suite", "value": "Test Suite"} in attrs

    def test_build_attributes_with_tags(self, exporter: Any) -> None:
        """Builds tag attributes."""
        manifest = {"tags": ["smoke", "regression"]}
        attrs = exporter._build_attributes(manifest)

        assert {"key": "tag", "value": "smoke"} in attrs
        assert {"key": "tag", "value": "regression"} in attrs

    def test_build_attributes_empty_manifest(self, exporter: Any) -> None:
        """Returns empty list for empty manifest."""
        attrs = exporter._build_attributes({})
        assert attrs == []


class TestTimestampHandling:
    """Tests for timestamp parsing and formatting."""

    @pytest.fixture
    def exporter(self) -> Any:
        """Create exporter instance for testing."""
        with patch(
            "trace_viewer.integrations.reportportal.ReportPortalExporter._check_dependencies"
        ):
            from trace_viewer.integrations.reportportal import ReportPortalExporter

            return ReportPortalExporter(
                endpoint="https://rp.example.com",
                project="test_project",
                api_key="test_api_key",
            )

    def test_parse_iso_timestamp(self, exporter: Any) -> None:
        """Parses ISO 8601 timestamp."""
        result = exporter._parse_timestamp("2025-01-20T10:00:00+00:00")
        assert result.isdigit()
        assert int(result) > 0

    def test_parse_iso_timestamp_with_z(self, exporter: Any) -> None:
        """Parses ISO timestamp with Z suffix."""
        result = exporter._parse_timestamp("2025-01-20T10:00:00Z")
        assert result.isdigit()

    def test_parse_empty_timestamp(self, exporter: Any) -> None:
        """Returns current timestamp for empty input."""
        result = exporter._parse_timestamp("")
        assert result.isdigit()

    def test_parse_invalid_timestamp(self, exporter: Any) -> None:
        """Returns current timestamp for invalid input."""
        result = exporter._parse_timestamp("invalid")
        assert result.isdigit()


class TestExportTrace:
    """Tests for trace export functionality."""

    @pytest.fixture
    def exporter(self) -> Any:
        """Create exporter instance for testing."""
        with patch(
            "trace_viewer.integrations.reportportal.ReportPortalExporter._check_dependencies"
        ):
            from trace_viewer.integrations.reportportal import ReportPortalExporter

            return ReportPortalExporter(
                endpoint="https://rp.example.com",
                project="test_project",
                api_key="test_api_key",
            )

    def test_export_trace_raises_for_nonexistent_directory(
        self, exporter: Any, tmp_path: Path
    ) -> None:
        """Raises FileNotFoundError for nonexistent directory."""
        nonexistent = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError):
            exporter.export_trace(nonexistent)

    def test_export_trace_raises_for_missing_manifest(self, exporter: Any, tmp_path: Path) -> None:
        """Raises FileNotFoundError when manifest is missing."""
        trace_dir = tmp_path / "trace"
        trace_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            exporter.export_trace(trace_dir)

    def test_export_traces_with_no_traces(self, exporter: Any, tmp_path: Path) -> None:
        """Returns empty results when no traces exist."""
        result = exporter.export_traces(tmp_path)

        assert result["total"] == 0
        assert result["exported"] == 0
        assert result["failed"] == 0


class TestBuildStepDescription:
    """Tests for step description building."""

    @pytest.fixture
    def exporter(self) -> Any:
        """Create exporter instance for testing."""
        with patch(
            "trace_viewer.integrations.reportportal.ReportPortalExporter._check_dependencies"
        ):
            from trace_viewer.integrations.reportportal import ReportPortalExporter

            return ReportPortalExporter(
                endpoint="https://rp.example.com",
                project="test_project",
                api_key="test_api_key",
            )

    def test_build_description_with_library(self, exporter: Any) -> None:
        """Includes library in description."""
        metadata = {"library": "SeleniumLibrary"}
        desc = exporter._build_step_description(metadata)

        assert "SeleniumLibrary" in desc

    def test_build_description_with_duration(self, exporter: Any) -> None:
        """Includes duration in description."""
        metadata = {"duration_ms": 500}
        desc = exporter._build_step_description(metadata)

        assert "500ms" in desc

    def test_build_description_empty(self, exporter: Any) -> None:
        """Returns empty string for empty metadata."""
        desc = exporter._build_step_description({})
        assert desc == ""


class TestBuildIssue:
    """Tests for issue info building."""

    @pytest.fixture
    def exporter(self) -> Any:
        """Create exporter instance for testing."""
        with patch(
            "trace_viewer.integrations.reportportal.ReportPortalExporter._check_dependencies"
        ):
            from trace_viewer.integrations.reportportal import ReportPortalExporter

            return ReportPortalExporter(
                endpoint="https://rp.example.com",
                project="test_project",
                api_key="test_api_key",
            )

    def test_build_issue_for_failed_test(self, exporter: Any) -> None:
        """Builds issue info for failed tests."""
        issue = exporter._build_issue("FAIL", "Element not found")

        assert issue is not None
        assert issue["issue_type"] == "TI001"
        assert "Element not found" in issue["comment"]

    def test_build_issue_returns_none_for_pass(self, exporter: Any) -> None:
        """Returns None for passing tests."""
        issue = exporter._build_issue("PASS", "")
        assert issue is None

    def test_build_issue_truncates_long_message(self, exporter: Any) -> None:
        """Truncates long error messages."""
        long_message = "x" * 2000
        issue = exporter._build_issue("FAIL", long_message)

        assert issue is not None
        assert len(issue["comment"]) <= 1000


class TestCLIExportRPCommand:
    """Tests for CLI export-rp command."""

    def test_export_rp_missing_endpoint(self) -> None:
        """Command fails when endpoint is missing."""
        from click.testing import CliRunner

        from trace_viewer.cli import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["export-rp", ".", "-p", "project", "-k", "key"],
        )

        assert result.exit_code != 0
        assert "endpoint" in result.output.lower() or "RP_ENDPOINT" in result.output

    def test_export_rp_missing_project(self) -> None:
        """Command fails when project is missing."""
        from click.testing import CliRunner

        from trace_viewer.cli import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["export-rp", ".", "-e", "https://rp.example.com", "-k", "key"],
        )

        assert result.exit_code != 0
        assert "project" in result.output.lower() or "RP_PROJECT" in result.output

    def test_export_rp_missing_api_key(self) -> None:
        """Command fails when API key is missing."""
        from click.testing import CliRunner

        from trace_viewer.cli import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["export-rp", ".", "-e", "https://rp.example.com", "-p", "project"],
        )

        assert result.exit_code != 0
        assert "api" in result.output.lower() or "RP_API_KEY" in result.output
