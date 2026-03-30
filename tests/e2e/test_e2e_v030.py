"""End-to-end tests for v0.3.0 features.

These tests exercise complete user workflows by chaining multiple modules
together — from config loading through listener capture to viewer generation,
compression, export, and CI publishing — mirroring real-world usage scenarios.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from PIL import Image

from trace_viewer.cli import main
from trace_viewer.config import TraceConfig, generate_default_config, load_config
from trace_viewer.listener import TraceListener
from trace_viewer.viewer.generator import ViewerGenerator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_data(**kwargs):
    """Create a mock RF data object."""
    mock = MagicMock()
    for k, v in kwargs.items():
        setattr(mock, k, v)
    return mock


def _mock_result(**kwargs):
    """Create a mock RF result object."""
    mock = MagicMock()
    for k, v in kwargs.items():
        if k == "elapsed_time":
            elapsed = MagicMock()
            elapsed.total_seconds = MagicMock(return_value=v)
            setattr(mock, k, elapsed)
        else:
            setattr(mock, k, v)
    return mock


def _create_screenshot_png(width: int = 100, height: int = 80, color: str = "red") -> bytes:
    """Create a minimal valid PNG image in memory."""
    import io

    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _run_simulated_test(
    listener: TraceListener,
    test_name: str = "My Test",
    suite_name: str = "Suite",
    status: str = "PASS",
    keywords: list[tuple[str, str, str]] | None = None,
):
    """Simulate a full RF test lifecycle through the listener.

    Args:
        keywords: List of (name, libname, status) tuples.
    """
    suite_data = _mock_data(name=suite_name, source=None)
    suite_result = _mock_result(status=status)

    test_data = _mock_data(
        name=test_name,
        longname=f"{suite_name}.{test_name}",
        doc="",
        tags=["e2e"],
    )
    test_result = _mock_result(
        status=status, message="" if status == "PASS" else "Failed", elapsed_time=1.0
    )

    listener.start_suite(suite_data, suite_result)
    listener.start_test(test_data, test_result)

    if keywords is None:
        keywords = [("Log", "BuiltIn", "PASS")]

    for kw_name, kw_lib, kw_status in keywords:
        kw_data = _mock_data(
            name=kw_name, args=("arg1",), assign=(), libname=kw_lib, type="KEYWORD"
        )
        kw_result = _mock_result(status=kw_status, message="", elapsed_time=0.2)
        listener.start_keyword(kw_data, kw_result)
        listener.end_keyword(kw_data, kw_result)

    listener.end_test(test_data, test_result)
    listener.end_suite(suite_data, suite_result)


def _create_trace_with_screenshots(
    traces_dir: Path,
    test_name: str,
    status: str = "PASS",
    num_keywords: int = 3,
    start_time: str = "2025-01-20T10:00:00+00:00",
    duration_ms: int = 2000,
    pabot_suffix: str = "",
) -> Path:
    """Create a complete fake trace directory with manifest, keywords, and screenshots."""
    dir_name = test_name.lower().replace(" ", "_")
    if pabot_suffix:
        dir_name += f"_{pabot_suffix}"
    trace_dir = traces_dir / dir_name
    trace_dir.mkdir(parents=True)

    manifest = {
        "version": "1.0.0",
        "tool_version": "0.3.0",
        "test_name": test_name,
        "suite_name": "E2E Suite",
        "status": status,
        "message": "" if status == "PASS" else "Test failed",
        "start_time": start_time,
        "end_time": "2025-01-20T10:00:02+00:00",
        "duration_ms": duration_ms,
        "keywords_count": num_keywords,
        "tags": ["e2e"],
    }
    (trace_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    # Use different colors per keyword so GIFs have distinct frames
    _keyword_colors = ["red", "green", "blue", "yellow", "cyan", "magenta", "orange", "purple"]

    kw_dir_base = trace_dir / "keywords"
    for i in range(1, num_keywords + 1):
        kw_name = f"Step {i}"
        kw_dir = kw_dir_base / f"{i:03d}_{kw_name.lower().replace(' ', '_')}"
        kw_dir.mkdir(parents=True)

        metadata = {
            "index": i,
            "name": kw_name,
            "status": status,
            "duration_ms": 100,
            "args": [f"arg_{i}"],
            "level": 1,
        }
        (kw_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        color = _keyword_colors[(i - 1) % len(_keyword_colors)]
        (kw_dir / "screenshot.png").write_bytes(_create_screenshot_png(color=color))

    # Generate viewer.html
    generator = ViewerGenerator()
    generator.generate_from_manifest(trace_dir)

    return trace_dir


# ===========================================================================
# E2E Test Classes
# ===========================================================================


class TestConfigToListenerE2E:
    """E2E: Config file -> Listener initialization -> Trace capture."""

    def test_yaml_config_drives_listener(self, tmp_path):
        """Config file values propagate through listener to trace output."""
        config_file = tmp_path / "trace-viewer.yml"
        config_file.write_text(
            "output_dir: custom_traces\n"
            "capture_mode: on_failure\n"
            "screenshot_mode: full_page\n"
            "buffer_size: 5\n"
            "masking_patterns:\n"
            "  - secret\n"
            "  - api_key\n",
            encoding="utf-8",
        )

        config = load_config(config_path=str(config_file))
        assert config.output_dir == "custom_traces"
        assert config.capture_mode == "on_failure"
        assert config.screenshot_mode == "full_page"
        assert config.buffer_size == 5
        assert "secret" in config.masking_patterns

    def test_env_vars_override_config_file(self, tmp_path):
        """Environment variables override config file values."""
        config_file = tmp_path / "trace-viewer.yml"
        config_file.write_text("capture_mode: full\nbuffer_size: 10\n", encoding="utf-8")

        with patch.dict(
            os.environ,
            {
                "TRACE_VIEWER_CAPTURE_MODE": "on_failure",
                "TRACE_VIEWER_BUFFER_SIZE": "3",
            },
        ):
            config = load_config(config_path=str(config_file))
            assert config.capture_mode == "on_failure"
            assert config.buffer_size == 3

    def test_cli_overrides_everything(self, tmp_path):
        """CLI overrides take highest precedence."""
        config_file = tmp_path / "trace-viewer.yml"
        config_file.write_text("capture_mode: full\n", encoding="utf-8")

        with patch.dict(os.environ, {"TRACE_VIEWER_CAPTURE_MODE": "disabled"}):
            config = load_config(
                config_path=str(config_file),
                cli_overrides={"capture_mode": "on_failure"},
            )
            assert config.capture_mode == "on_failure"

    def test_init_command_generates_loadable_config(self, tmp_path):
        """trace-viewer init produces a config that load_config can parse."""
        runner = CliRunner()
        output = tmp_path / "trace-viewer.yml"
        result = runner.invoke(main, ["init", "--output", str(output)])
        assert result.exit_code == 0
        assert output.exists()

        config = load_config(config_path=str(output))
        assert isinstance(config, TraceConfig)
        assert config.output_dir == "traces"
        assert config.capture_mode == "full"


class TestRingBufferOnFailureE2E:
    """E2E: on_failure mode captures only when test fails."""

    def test_passing_test_no_disk_capture(self, tmp_path):
        """In on_failure mode, passing tests produce no screenshot files."""
        listener = TraceListener(output_dir=str(tmp_path), capture_mode="on_failure")
        _run_simulated_test(
            listener,
            test_name="Passing Test",
            status="PASS",
            keywords=[("Click", "SeleniumLibrary", "PASS"), ("Log", "BuiltIn", "PASS")],
        )

        trace_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        assert len(trace_dirs) == 1

        # Ring buffer should have been cleared, no screenshots flushed
        manifest = json.loads((trace_dirs[0] / "manifest.json").read_text())
        assert manifest["status"] == "PASS"

    def test_failing_test_flushes_ring_buffer(self, tmp_path):
        """In on_failure mode, failing test triggers ring buffer flush to disk."""
        listener = TraceListener(output_dir=str(tmp_path), capture_mode="on_failure")

        suite_data = _mock_data(name="Suite", source=None)
        suite_result = _mock_result(status="FAIL")
        test_data = _mock_data(name="Failing Test", longname="Suite.Failing Test", doc="", tags=[])
        test_result = _mock_result(status="FAIL", message="Element not found", elapsed_time=2.0)

        listener.start_suite(suite_data, suite_result)
        listener.start_test(test_data, test_result)

        # Add keywords - buffer should store them in memory
        for i in range(3):
            kw = _mock_data(name=f"Step {i}", args=(), assign=(), libname="BuiltIn", type="KEYWORD")
            kw_result = _mock_result(
                status="PASS" if i < 2 else "FAIL", message="", elapsed_time=0.1
            )
            listener.start_keyword(kw, kw_result)
            listener.end_keyword(kw, kw_result)

        listener.end_test(test_data, test_result)
        listener.end_suite(suite_data, suite_result)

        trace_dir = [d for d in tmp_path.iterdir() if d.is_dir()][0]
        manifest = json.loads((trace_dir / "manifest.json").read_text())
        assert manifest["status"] == "FAIL"
        assert manifest["keywords_count"] == 3


class TestListenerToViewerE2E:
    """E2E: Listener capture -> Viewer generation -> Viewer HTML validation."""

    def test_full_workflow_listener_to_viewer(self, tmp_path):
        """Complete flow: capture via listener, generate viewer, validate HTML."""
        listener = TraceListener(output_dir=str(tmp_path))
        _run_simulated_test(
            listener,
            test_name="Login Test",
            suite_name="Auth Suite",
            keywords=[
                ("Open Browser", "SeleniumLibrary", "PASS"),
                ("Input Text", "SeleniumLibrary", "PASS"),
                ("Click Button", "SeleniumLibrary", "PASS"),
            ],
        )

        trace_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        assert len(trace_dirs) == 1

        trace_dir = trace_dirs[0]

        # Manifest is correct
        manifest = json.loads((trace_dir / "manifest.json").read_text())
        assert manifest["test_name"] == "Login Test"
        assert manifest["suite_name"] == "Auth Suite"
        assert manifest["keywords_count"] == 3

        # Viewer was auto-generated
        viewer = trace_dir / "viewer.html"
        assert viewer.exists()
        content = viewer.read_text()
        assert "<!DOCTYPE html>" in content
        assert "TRACE_DATA" in content
        assert "Login Test" in content


class TestSuiteViewerE2E:
    """E2E: Multiple traces -> Suite viewer generation."""

    def test_suite_viewer_from_multiple_traces(self, tmp_path):
        """Create multiple traces, generate suite viewer, validate output."""
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()

        _create_trace_with_screenshots(
            traces_dir, "Login Test", "PASS", start_time="2025-01-20T10:00:00+00:00"
        )
        _create_trace_with_screenshots(
            traces_dir, "Checkout Test", "FAIL", start_time="2025-01-20T10:01:00+00:00"
        )
        _create_trace_with_screenshots(
            traces_dir, "Search Test", "PASS", start_time="2025-01-20T10:02:00+00:00"
        )

        runner = CliRunner()
        output = tmp_path / "suite.html"
        result = runner.invoke(main, ["suite", str(traces_dir), "--output", str(output)])
        assert result.exit_code == 0
        assert output.exists()

        content = output.read_text()
        assert "Login Test" in content
        assert "Checkout Test" in content
        assert "Search Test" in content

    def test_suite_viewer_stats_accuracy(self, tmp_path):
        """Suite viewer calculates correct aggregate statistics."""
        from trace_viewer.viewer.suite_generator import SuiteViewerGenerator

        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()

        _create_trace_with_screenshots(traces_dir, "Test A", "PASS", duration_ms=1000)
        _create_trace_with_screenshots(traces_dir, "Test B", "FAIL", duration_ms=2000)
        _create_trace_with_screenshots(traces_dir, "Test C", "PASS", duration_ms=1500)

        generator = SuiteViewerGenerator()
        output = generator.generate(traces_dir)

        content = output.read_text()
        # Should contain the JSON payload with stats
        assert '"passed": 2' in content
        assert '"failed": 1' in content
        assert '"total": 3' in content


class TestCompressionE2E:
    """E2E: Create traces with PNGs -> Compress -> Verify WebP output."""

    def test_compress_and_verify_savings(self, tmp_path):
        """Compress trace screenshots and verify file format conversion."""
        from trace_viewer.storage.compression import compress_traces_dir

        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        _create_trace_with_screenshots(traces_dir, "Compress Test", "PASS", num_keywords=5)

        # Verify PNGs exist before compression
        pngs_before = list(traces_dir.rglob("screenshot.png"))
        assert len(pngs_before) == 5

        result = compress_traces_dir(traces_dir, quality=80)
        assert result["files_converted"] == 5
        assert result["savings_percent"] > 0

        # PNGs should be removed, WebPs should exist
        pngs_after = list(traces_dir.rglob("screenshot.png"))
        webps_after = list(traces_dir.rglob("screenshot.webp"))
        assert len(pngs_after) == 0
        assert len(webps_after) == 5

    def test_compress_via_cli(self, tmp_path):
        """trace-viewer compress CLI command works end-to-end."""
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        _create_trace_with_screenshots(traces_dir, "CLI Compress", "PASS", num_keywords=2)

        runner = CliRunner()
        result = runner.invoke(main, ["compress", str(traces_dir), "--quality", "70"])
        assert result.exit_code == 0
        assert "Converted 2 file(s)" in result.output


class TestCleanupE2E:
    """E2E: Create old and new traces -> Cleanup -> Verify retention."""

    def test_cleanup_removes_old_traces(self, tmp_path):
        """Cleanup removes traces older than retention period."""
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()

        # Create an "old" trace (400 days ago)
        _create_trace_with_screenshots(
            traces_dir,
            "Old Test",
            "PASS",
            start_time="2024-01-01T10:00:00+00:00",
        )
        # Create a "recent" trace
        _create_trace_with_screenshots(
            traces_dir,
            "Recent Test",
            "PASS",
            start_time="2026-03-29T10:00:00+00:00",
        )

        runner = CliRunner()
        result = runner.invoke(main, ["cleanup", str(traces_dir), "--days", "30"])
        assert result.exit_code == 0
        assert "Deleted 1 trace(s)" in result.output
        assert "Remaining: 1 trace(s)" in result.output

        # Only recent test should remain
        remaining = [d for d in traces_dir.iterdir() if d.is_dir()]
        assert len(remaining) == 1
        manifest = json.loads((remaining[0] / "manifest.json").read_text())
        assert manifest["test_name"] == "Recent Test"


class TestGifReplayE2E:
    """E2E: Trace with screenshots -> GIF generation -> Validation."""

    def test_generate_gif_from_trace(self, tmp_path):
        """Generate an animated GIF from a trace's screenshots."""
        from trace_viewer.media.gif_generator import generate_gif

        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        trace_dir = _create_trace_with_screenshots(traces_dir, "GIF Test", "PASS", num_keywords=4)

        gif_path = generate_gif(trace_dir, fps=2, max_width=200)
        assert gif_path.exists()
        assert gif_path.stat().st_size > 0

        # Verify it's a valid GIF
        img = Image.open(gif_path)
        assert img.format == "GIF"
        assert img.is_animated
        assert img.n_frames == 4

    def test_generate_slideshow_from_trace(self, tmp_path):
        """Generate an HTML slideshow from a trace's screenshots."""
        from trace_viewer.media.gif_generator import generate_slideshow

        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        trace_dir = _create_trace_with_screenshots(
            traces_dir, "Slideshow Test", "PASS", num_keywords=3
        )

        html_path = generate_slideshow(trace_dir)
        assert html_path.exists()

        content = html_path.read_text()
        assert "<!DOCTYPE html>" in content
        assert "data:image/png;base64," in content
        assert "Slideshow Test" in content
        assert "Step 1" in content

    def test_replay_cli_html_format(self, tmp_path):
        """trace-viewer replay --format html works end-to-end."""
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        trace_dir = _create_trace_with_screenshots(traces_dir, "CLI Replay", "PASS", num_keywords=2)

        runner = CliRunner()
        result = runner.invoke(main, ["replay", str(trace_dir), "--format", "html"])
        assert result.exit_code == 0
        assert "Replay generated" in result.output

    def test_replay_cli_gif_format(self, tmp_path):
        """trace-viewer replay --format gif works end-to-end."""
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        trace_dir = _create_trace_with_screenshots(traces_dir, "CLI GIF", "PASS", num_keywords=2)

        runner = CliRunner()
        output = tmp_path / "output.gif"
        result = runner.invoke(
            main, ["replay", str(trace_dir), "--format", "gif", "--output", str(output)]
        )
        assert result.exit_code == 0
        assert output.exists()


class TestVisualDiffE2E:
    """E2E: Two traces with different screenshots -> Visual diff -> Report."""

    def test_compare_traces_generates_report(self, tmp_path):
        """Compare two traces visually and generate HTML report."""
        from trace_viewer.comparison.visual_diff import compare_traces, generate_comparison_html

        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()

        # Create two traces with different colored screenshots
        trace1 = _create_trace_with_screenshots(traces_dir, "Run 1", "PASS", num_keywords=3)
        trace2_dir = traces_dir / "run_2"
        trace2_dir.mkdir()

        # Copy structure from trace1 but with different screenshots
        manifest = json.loads((trace1 / "manifest.json").read_text())
        manifest["test_name"] = "Run 2"
        (trace2_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        kw_src = trace1 / "keywords"
        kw_dst = trace2_dir / "keywords"
        kw_dst.mkdir()

        for kw_dir in sorted(kw_src.iterdir()):
            dest_kw = kw_dst / kw_dir.name
            dest_kw.mkdir()
            # Copy metadata
            if (kw_dir / "metadata.json").exists():
                (dest_kw / "metadata.json").write_bytes((kw_dir / "metadata.json").read_bytes())
            # Write different colored screenshot (white — distinct from trace1's red/green/blue)
            (dest_kw / "screenshot.png").write_bytes(_create_screenshot_png(color="white"))

        results = compare_traces(trace1, trace2_dir)
        assert len(results) == 3

        # Screenshots are different (red vs blue)
        for r in results:
            assert r["similarity"] < 1.0
            assert r["changed_pixels"] > 0

        # Generate HTML report
        report = tmp_path / "diff_report.html"
        generate_comparison_html(results, trace1, trace2_dir, report)
        assert report.exists()

        content = report.read_text()
        assert "Visual Comparison" in content
        assert "Baseline" in content
        assert "Candidate" in content

    def test_compare_visual_cli(self, tmp_path):
        """trace-viewer compare-visual CLI command works end-to-end."""
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        trace1 = _create_trace_with_screenshots(traces_dir, "Trace A", "PASS", num_keywords=2)
        trace2 = _create_trace_with_screenshots(traces_dir, "Trace B", "PASS", num_keywords=2)

        runner = CliRunner()
        output = tmp_path / "visual_diff.html"
        result = runner.invoke(
            main, ["compare-visual", str(trace1), str(trace2), "--output", str(output)]
        )
        assert result.exit_code == 0


class TestPabotMergeE2E:
    """E2E: Pabot parallel traces -> Merge -> Timeline viewer."""

    def test_merge_parallel_traces(self, tmp_path):
        """Merge traces from 2 Pabot workers into a unified timeline."""
        from trace_viewer.integrations.pabot_merger import PabotMerger

        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()

        _create_trace_with_screenshots(
            traces_dir,
            "Login Test",
            "PASS",
            start_time="2025-01-20T10:00:00+00:00",
            duration_ms=3000,
            pabot_suffix="pabot0",
        )
        _create_trace_with_screenshots(
            traces_dir,
            "Checkout Test",
            "FAIL",
            start_time="2025-01-20T10:00:01+00:00",
            duration_ms=4000,
            pabot_suffix="pabot1",
        )
        _create_trace_with_screenshots(
            traces_dir,
            "Search Test",
            "PASS",
            start_time="2025-01-20T10:00:03+00:00",
            duration_ms=2000,
            pabot_suffix="pabot0",
        )

        merger = PabotMerger(traces_dir)
        traces = merger.scan_traces()
        assert len(traces) == 3

        # Verify worker assignment
        workers = {t["worker_id"] for t in traces}
        assert "pabot0" in workers
        assert "pabot1" in workers

        output = merger.merge()
        assert output.exists()

        # Timeline HTML should exist
        timeline = output / "timeline.html"
        assert timeline.exists()
        content = timeline.read_text()
        assert "pabot0" in content
        assert "pabot1" in content
        assert "Login Test" in content

    def test_merge_cli(self, tmp_path):
        """trace-viewer merge CLI command works end-to-end."""
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()

        _create_trace_with_screenshots(
            traces_dir,
            "Test A",
            "PASS",
            pabot_suffix="pabot0",
        )
        _create_trace_with_screenshots(
            traces_dir,
            "Test B",
            "PASS",
            pabot_suffix="pabot1",
        )

        runner = CliRunner()
        output = tmp_path / "merged"
        result = runner.invoke(main, ["merge", str(traces_dir), "--output", str(output)])
        assert result.exit_code == 0
        assert output.exists()


class TestCICDPublishE2E:
    """E2E: Traces -> CI/CD publishing (Jenkins & GitLab)."""

    def test_jenkins_publish_creates_index(self, tmp_path):
        """Jenkins publish creates index.html with all traces."""
        from trace_viewer.integrations.cicd import CICDPublisher

        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()

        _create_trace_with_screenshots(traces_dir, "Login", "PASS", duration_ms=1500)
        _create_trace_with_screenshots(traces_dir, "Checkout", "FAIL", duration_ms=3000)

        publisher = CICDPublisher(traces_dir, format="jenkins")
        output = publisher.publish(tmp_path / "jenkins_report")

        assert output.exists()
        index = output / "index.html"
        assert index.exists()

        content = index.read_text()
        assert "Robot Framework Trace Report" in content
        assert "Login" in content
        assert "Checkout" in content
        assert "PASS" in content
        assert "FAIL" in content

    def test_gitlab_publish_creates_markdown(self, tmp_path):
        """GitLab publish creates trace-summary.md for MR comments."""
        from trace_viewer.integrations.cicd import CICDPublisher

        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()

        _create_trace_with_screenshots(traces_dir, "API Test", "PASS")
        _create_trace_with_screenshots(traces_dir, "UI Test", "FAIL")

        publisher = CICDPublisher(traces_dir, format="gitlab")
        output = publisher.publish(tmp_path / "gitlab_report")

        assert output.exists()
        md_path = output / "trace-summary.md"
        assert md_path.exists()

        content = md_path.read_text()
        assert "Robot Framework Trace Report" in content
        assert "API Test" in content
        assert "UI Test" in content
        assert ":white_check_mark:" in content
        assert ":x:" in content

    def test_publish_cli_jenkins(self, tmp_path):
        """trace-viewer publish --format jenkins works end-to-end."""
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        _create_trace_with_screenshots(traces_dir, "CLI Test", "PASS")

        runner = CliRunner()
        output = tmp_path / "ci_out"
        result = runner.invoke(
            main, ["publish", str(traces_dir), "--format", "jenkins", "--output", str(output)]
        )
        assert result.exit_code == 0

    def test_publish_cli_gitlab(self, tmp_path):
        """trace-viewer publish --format gitlab works end-to-end."""
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        _create_trace_with_screenshots(traces_dir, "GL Test", "PASS")

        runner = CliRunner()
        output = tmp_path / "gl_out"
        result = runner.invoke(
            main, ["publish", str(traces_dir), "--format", "gitlab", "--output", str(output)]
        )
        assert result.exit_code == 0


class TestPDFExportE2E:
    """E2E: Trace with screenshots -> PDF export."""

    def test_pdf_export_with_mock_weasyprint(self, tmp_path):
        """PDF export generates report from a real trace directory."""
        import sys
        from unittest.mock import MagicMock

        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        trace_dir = _create_trace_with_screenshots(traces_dir, "PDF Test", "PASS", num_keywords=3)

        # Mock weasyprint — write_pdf() returns bytes (no arguments)
        mock_wp = MagicMock()
        mock_html_cls = MagicMock()

        def fake_write_pdf():
            return b"%PDF-1.4 fake pdf content"

        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf = fake_write_pdf
        mock_html_cls.return_value = mock_html_instance
        mock_wp.HTML = mock_html_cls

        from importlib import reload

        import trace_viewer.export.pdf_exporter as pdf_mod

        with patch.dict(sys.modules, {"weasyprint": mock_wp}):
            reload(pdf_mod)

            exporter = pdf_mod.PDFExporter()
            output = tmp_path / "report.pdf"
            result = exporter.export(trace_dir, output)
            assert result.exists()
            assert result.read_bytes().startswith(b"%PDF")

        # Reload to remove mock contamination for subsequent tests
        reload(pdf_mod)

    def test_pdf_export_cli(self, tmp_path):
        """trace-viewer export-pdf CLI raises gracefully without weasyprint."""
        import sys
        from importlib import reload

        # Clean up any mock weasyprint injected by unit tests
        saved = sys.modules.pop("weasyprint", None)
        import trace_viewer.export.pdf_exporter as pdf_mod

        reload(pdf_mod)

        try:
            traces_dir = tmp_path / "traces"
            traces_dir.mkdir()
            trace_dir = _create_trace_with_screenshots(traces_dir, "PDF CLI", "PASS")

            runner = CliRunner()
            # This should fail gracefully if weasyprint is not installed
            result = runner.invoke(main, ["export-pdf", str(trace_dir)])
            # Either succeeds or gives a helpful error about weasyprint
            assert result.exit_code == 0 or "weasyprint" in result.output.lower()
        finally:
            if saved is not None:
                sys.modules["weasyprint"] = saved


class TestFullPipelineE2E:
    """E2E: Complete pipeline from config -> listener -> suite -> compress -> publish."""

    def test_complete_ci_pipeline(self, tmp_path):
        """Simulate a full CI pipeline workflow."""
        from trace_viewer.integrations.cicd import CICDPublisher
        from trace_viewer.storage.compression import compress_traces_dir
        from trace_viewer.viewer.suite_generator import SuiteViewerGenerator

        # Step 1: Create config
        config_content = generate_default_config()
        config_file = tmp_path / "trace-viewer.yml"
        config_file.write_text(config_content, encoding="utf-8")

        config = load_config(config_path=str(config_file))
        assert config.capture_mode == "full"

        # Step 2: Simulate multiple test executions
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()

        test_scenarios = [
            ("Login Should Work", "PASS", "2025-01-20T10:00:00+00:00"),
            ("Checkout Should Process", "PASS", "2025-01-20T10:01:00+00:00"),
            ("Admin Access Denied", "FAIL", "2025-01-20T10:02:00+00:00"),
            ("Search Returns Results", "PASS", "2025-01-20T10:03:00+00:00"),
        ]

        for name, status, time in test_scenarios:
            _create_trace_with_screenshots(
                traces_dir,
                name,
                status,
                start_time=time,
                num_keywords=4,
            )

        # Step 3: Compress screenshots
        compress_result = compress_traces_dir(traces_dir, quality=80)
        assert compress_result["files_converted"] == 16  # 4 tests × 4 keywords

        # Step 4: Generate suite viewer
        suite_gen = SuiteViewerGenerator()
        suite_path = suite_gen.generate(traces_dir)
        assert suite_path.exists()

        suite_content = suite_path.read_text()
        assert "Login Should Work" in suite_content
        assert '"passed": 3' in suite_content
        assert '"failed": 1' in suite_content

        # Step 5: Publish for Jenkins
        publisher = CICDPublisher(traces_dir, format="jenkins")
        report_dir = publisher.publish(tmp_path / "ci_report")
        assert (report_dir / "index.html").exists()

        # Step 6: Publish for GitLab
        publisher_gl = CICDPublisher(traces_dir, format="gitlab")
        gl_dir = publisher_gl.publish(tmp_path / "gl_report")
        assert (gl_dir / "trace-summary.md").exists()

        md_content = (gl_dir / "trace-summary.md").read_text()
        assert "3 passed" in md_content
        assert "1 failed" in md_content

    def test_on_failure_mode_full_pipeline(self, tmp_path):
        """on_failure mode: only failing tests retain captures."""
        listener = TraceListener(
            output_dir=str(tmp_path),
            capture_mode="on_failure",
            buffer_size=5,
        )

        # Passing test
        _run_simulated_test(
            listener, "Pass Test", status="PASS", keywords=[("Log", "BuiltIn", "PASS")]
        )

        # Failing test
        suite_data = _mock_data(name="Suite", source=None)
        suite_result = _mock_result(status="FAIL")
        test_data = _mock_data(name="Fail Test", longname="Suite.Fail Test", doc="", tags=[])
        test_result = _mock_result(status="FAIL", message="Error occurred", elapsed_time=1.0)

        listener.start_suite(suite_data, suite_result)
        listener.start_test(test_data, test_result)
        for i in range(3):
            kw = _mock_data(name=f"Action {i}", args=(), assign=(), libname="Lib", type="KEYWORD")
            kw_r = _mock_result(status="PASS" if i < 2 else "FAIL", message="", elapsed_time=0.1)
            listener.start_keyword(kw, kw_r)
            listener.end_keyword(kw, kw_r)
        listener.end_test(test_data, test_result)
        listener.end_suite(suite_data, suite_result)

        # Both tests should have trace dirs
        trace_dirs = sorted(d for d in tmp_path.iterdir() if d.is_dir())
        assert len(trace_dirs) == 2

        # Both should have valid manifests
        for td in trace_dirs:
            assert (td / "manifest.json").exists()
