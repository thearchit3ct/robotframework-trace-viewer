"""Integration tests for the full trace capture flow."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from trace_viewer.listener import TraceListener
from trace_viewer.storage.trace_writer import TraceWriter
from trace_viewer.viewer.generator import ViewerGenerator


def create_mock_data(**kwargs):
    """Create a mock data object with specified attributes."""
    mock = MagicMock()
    for key, value in kwargs.items():
        setattr(mock, key, value)
    return mock


def create_mock_result(**kwargs):
    """Create a mock result object with specified attributes."""
    mock = MagicMock()
    for key, value in kwargs.items():
        if key == "elapsed_time":
            # Create a mock timedelta-like object
            elapsed_mock = MagicMock()
            elapsed_mock.total_seconds = MagicMock(return_value=value)
            setattr(mock, key, elapsed_mock)
        else:
            setattr(mock, key, value)
    return mock


class TestFullTraceFlow:
    """Test the complete flow from listener to viewer generation."""

    def test_listener_creates_trace_structure(self, tmp_path):
        """Test that running a simulated test creates proper trace structure."""
        listener = TraceListener(output_dir=str(tmp_path))

        # Simulate RF events
        suite_data = create_mock_data(name="Test Suite", source=Path("/tests/test.robot"))
        suite_result = create_mock_result(status="PASS")

        test_data = create_mock_data(
            name="My Test",
            longname="Test Suite.My Test",
            doc="Test doc",
            tags=["tag1"],
        )
        test_result = create_mock_result(status="PASS", message="", elapsed_time=0.5)

        kw_data = create_mock_data(
            name="Log",
            args=("Hello",),
            assign=(),
            libname="BuiltIn",
            type="KEYWORD",
        )
        kw_result = create_mock_result(status="PASS", message="", elapsed_time=0.1)

        # Run the listener hooks
        listener.start_suite(suite_data, suite_result)
        listener.start_test(test_data, test_result)
        listener.start_keyword(kw_data, kw_result)
        listener.end_keyword(kw_data, kw_result)
        listener.end_test(test_data, test_result)
        listener.end_suite(suite_data, suite_result)

        # Verify trace structure
        trace_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        assert len(trace_dirs) == 1

        trace_dir = trace_dirs[0]
        assert (trace_dir / "manifest.json").exists()
        assert (trace_dir / "keywords").is_dir()

        # Verify manifest content
        manifest = json.loads((trace_dir / "manifest.json").read_text())
        assert manifest["test_name"] == "My Test"
        assert manifest["status"] == "PASS"

    def test_trace_contains_keyword_metadata(self, tmp_path):
        """Test that keyword directories contain proper metadata."""
        listener = TraceListener(output_dir=str(tmp_path))

        # Run minimal test
        suite_data = create_mock_data(name="Suite", source=None)
        suite_result = create_mock_result(status="PASS")
        test_data = create_mock_data(
            name="Test",
            longname="Suite.Test",
            doc="",
            tags=[],
        )
        test_result = create_mock_result(status="PASS", message="", elapsed_time=1.0)
        kw_data = create_mock_data(
            name="Click Button",
            args=("button#submit",),
            assign=(),
            libname="SeleniumLibrary",
            type="KEYWORD",
        )
        kw_result = create_mock_result(status="PASS", message="", elapsed_time=0.5)

        listener.start_suite(suite_data, suite_result)
        listener.start_test(test_data, test_result)
        listener.start_keyword(kw_data, kw_result)
        listener.end_keyword(kw_data, kw_result)
        listener.end_test(test_data, test_result)
        listener.end_suite(suite_data, suite_result)

        # Find keyword directory
        trace_dir = [d for d in tmp_path.iterdir() if d.is_dir()][0]
        kw_dirs = list((trace_dir / "keywords").iterdir())
        assert len(kw_dirs) == 1

        # Verify metadata
        metadata = json.loads((kw_dirs[0] / "metadata.json").read_text())
        assert metadata["name"] == "Click Button"
        assert metadata["status"] == "PASS"
        assert "args" in metadata
        assert metadata["args"] == ["button#submit"]

    def test_viewer_can_be_generated_from_trace(self, tmp_path):
        """Test that viewer.html can be generated from trace directory."""
        listener = TraceListener(output_dir=str(tmp_path))

        suite_data = create_mock_data(name="Suite", source=None)
        suite_result = create_mock_result(status="PASS")
        test_data = create_mock_data(
            name="Test",
            longname="Suite.Test",
            doc="",
            tags=[],
        )
        test_result = create_mock_result(status="PASS", message="", elapsed_time=0.5)

        listener.start_suite(suite_data, suite_result)
        listener.start_test(test_data, test_result)
        listener.end_test(test_data, test_result)
        listener.end_suite(suite_data, suite_result)

        # Generate viewer using ViewerGenerator
        trace_dir = [d for d in tmp_path.iterdir() if d.is_dir()][0]
        generator = ViewerGenerator()
        viewer_file = generator.generate_from_manifest(trace_dir)

        assert viewer_file.exists()
        assert viewer_file.name == "viewer.html"

    def test_failed_keyword_is_marked_correctly(self, tmp_path):
        """Test that failed keywords have correct status in trace."""
        listener = TraceListener(output_dir=str(tmp_path))

        suite_data = create_mock_data(name="Suite", source=None)
        suite_result = create_mock_result(status="FAIL")
        test_data = create_mock_data(
            name="Test",
            longname="Suite.Test",
            doc="",
            tags=[],
        )
        test_result = create_mock_result(
            status="FAIL", message="Element not found", elapsed_time=1.0
        )
        kw_data = create_mock_data(
            name="Click",
            args=(),
            assign=(),
            libname="SeleniumLibrary",
            type="KEYWORD",
        )
        kw_result = create_mock_result(status="FAIL", message="Element not found", elapsed_time=0.1)

        listener.start_suite(suite_data, suite_result)
        listener.start_test(test_data, test_result)
        listener.start_keyword(kw_data, kw_result)
        listener.end_keyword(kw_data, kw_result)
        listener.end_test(test_data, test_result)
        listener.end_suite(suite_data, suite_result)

        trace_dir = [d for d in tmp_path.iterdir() if d.is_dir()][0]
        manifest = json.loads((trace_dir / "manifest.json").read_text())
        assert manifest["status"] == "FAIL"
        assert "Element not found" in manifest["message"]

    def test_multiple_tests_create_separate_traces(self, tmp_path):
        """Test that multiple tests create separate trace directories."""
        listener = TraceListener(output_dir=str(tmp_path))

        suite_data = create_mock_data(name="Suite", source=None)
        suite_result = create_mock_result(status="PASS")

        listener.start_suite(suite_data, suite_result)

        # First test
        test_data1 = create_mock_data(
            name="Test One",
            longname="Suite.Test One",
            doc="",
            tags=[],
        )
        test_result1 = create_mock_result(status="PASS", message="", elapsed_time=0.5)
        listener.start_test(test_data1, test_result1)
        listener.end_test(test_data1, test_result1)

        # Second test
        test_data2 = create_mock_data(
            name="Test Two",
            longname="Suite.Test Two",
            doc="",
            tags=[],
        )
        test_result2 = create_mock_result(status="PASS", message="", elapsed_time=0.5)
        listener.start_test(test_data2, test_result2)
        listener.end_test(test_data2, test_result2)

        listener.end_suite(suite_data, suite_result)

        # Verify two trace directories were created
        trace_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        assert len(trace_dirs) == 2

        # Verify trace_data contains both tests
        assert len(listener.trace_data["tests"]) == 2


class TestCaptureMode:
    """Test different capture modes."""

    def test_full_mode_captures_all_keywords(self, tmp_path):
        """Test that full mode attempts capture for every keyword."""
        listener = TraceListener(output_dir=str(tmp_path), capture_mode="full")

        suite_data = create_mock_data(name="Suite", source=None)
        suite_result = create_mock_result(status="PASS")
        test_data = create_mock_data(
            name="Test",
            longname="Suite.Test",
            doc="",
            tags=[],
        )
        test_result = create_mock_result(status="PASS", message="", elapsed_time=1.0)

        # Create passing keyword
        kw_data = create_mock_data(
            name="Log",
            args=("test",),
            assign=(),
            libname="BuiltIn",
            type="KEYWORD",
        )
        kw_result = create_mock_result(status="PASS", message="", elapsed_time=0.1)

        listener.start_suite(suite_data, suite_result)
        listener.start_test(test_data, test_result)
        listener.start_keyword(kw_data, kw_result)
        listener.end_keyword(kw_data, kw_result)
        listener.end_test(test_data, test_result)
        listener.end_suite(suite_data, suite_result)

        # In full mode, has_screenshot and has_variables flags should be set
        # (even if False because no browser/RF context)
        assert len(listener.trace_data["tests"]) == 1

    def test_on_failure_mode_only_captures_failures(self, tmp_path):
        """Test that on_failure mode only captures for failed keywords."""
        listener = TraceListener(output_dir=str(tmp_path), capture_mode="on_failure")

        # Verify internal _should_capture method
        assert listener._should_capture("PASS") is False
        assert listener._should_capture("FAIL") is True

    def test_disabled_mode_skips_capture(self, tmp_path):
        """Test that disabled mode doesn't attempt capture."""
        listener = TraceListener(output_dir=str(tmp_path), capture_mode="disabled")

        # Verify internal _should_capture method
        assert listener._should_capture("PASS") is False
        assert listener._should_capture("FAIL") is False


class TestNestedKeywords:
    """Test handling of nested keywords."""

    def test_nested_keywords_have_correct_level(self, tmp_path):
        """Test that nested keywords track their level correctly."""
        listener = TraceListener(output_dir=str(tmp_path))

        suite_data = create_mock_data(name="Suite", source=None)
        suite_result = create_mock_result(status="PASS")
        test_data = create_mock_data(
            name="Test",
            longname="Suite.Test",
            doc="",
            tags=[],
        )
        test_result = create_mock_result(status="PASS", message="", elapsed_time=2.0)

        parent_kw = create_mock_data(
            name="Login",
            args=(),
            assign=(),
            libname="",
            type="KEYWORD",
        )
        parent_result = create_mock_result(status="PASS", message="", elapsed_time=1.0)
        child_kw = create_mock_data(
            name="Input Text",
            args=("id=user", "admin"),
            assign=(),
            libname="SeleniumLibrary",
            type="KEYWORD",
        )
        child_result = create_mock_result(status="PASS", message="", elapsed_time=0.1)

        listener.start_suite(suite_data, suite_result)
        listener.start_test(test_data, test_result)
        listener.start_keyword(parent_kw, parent_result)  # Level 1
        listener.start_keyword(child_kw, child_result)  # Level 2
        listener.end_keyword(child_kw, child_result)
        listener.end_keyword(parent_kw, parent_result)
        listener.end_test(test_data, test_result)
        listener.end_suite(suite_data, suite_result)

        trace_dir = [d for d in tmp_path.iterdir() if d.is_dir()][0]
        kw_dirs = sorted((trace_dir / "keywords").iterdir())

        # Verify both keywords are tracked
        assert len(kw_dirs) == 2

        # Load and verify levels
        # Keywords are stored in execution order (by index), but end in reverse
        # So child (index 2) ends first, then parent (index 1)
        metadata_files = [kw_dir / "metadata.json" for kw_dir in kw_dirs]

        # First directory should be 001_login (parent started first)
        parent_metadata = json.loads(metadata_files[0].read_text())
        assert parent_metadata["name"] == "Login"
        assert parent_metadata["level"] == 1
        assert parent_metadata["parent_keyword"] is None

        # Second directory should be 002_input_text (child started second)
        child_metadata = json.loads(metadata_files[1].read_text())
        assert child_metadata["name"] == "Input Text"
        assert child_metadata["level"] == 2
        assert child_metadata["parent_keyword"] == "Login"

    def test_deeply_nested_keywords(self, tmp_path):
        """Test keywords nested 3 levels deep."""
        listener = TraceListener(output_dir=str(tmp_path))

        suite_data = create_mock_data(name="Suite", source=None)
        suite_result = create_mock_result(status="PASS")
        test_data = create_mock_data(
            name="Test",
            longname="Suite.Test",
            doc="",
            tags=[],
        )
        test_result = create_mock_result(status="PASS", message="", elapsed_time=3.0)

        # Level 1: User keyword
        kw1 = create_mock_data(
            name="Login As Admin", args=(), assign=(), libname="", type="KEYWORD"
        )
        kw1_result = create_mock_result(status="PASS", message="", elapsed_time=2.0)

        # Level 2: Another user keyword
        kw2 = create_mock_data(
            name="Fill Login Form", args=(), assign=(), libname="", type="KEYWORD"
        )
        kw2_result = create_mock_result(status="PASS", message="", elapsed_time=1.0)

        # Level 3: Library keyword
        kw3 = create_mock_data(
            name="Input Text",
            args=("id=user", "admin"),
            assign=(),
            libname="SeleniumLibrary",
            type="KEYWORD",
        )
        kw3_result = create_mock_result(status="PASS", message="", elapsed_time=0.1)

        listener.start_suite(suite_data, suite_result)
        listener.start_test(test_data, test_result)

        listener.start_keyword(kw1, kw1_result)  # Level 1
        assert len(listener.keyword_stack) == 1

        listener.start_keyword(kw2, kw2_result)  # Level 2
        assert len(listener.keyword_stack) == 2

        listener.start_keyword(kw3, kw3_result)  # Level 3
        assert len(listener.keyword_stack) == 3
        assert listener.keyword_stack[-1]["level"] == 3
        assert listener.keyword_stack[-1]["parent_keyword"] == "Fill Login Form"

        listener.end_keyword(kw3, kw3_result)
        listener.end_keyword(kw2, kw2_result)
        listener.end_keyword(kw1, kw1_result)

        listener.end_test(test_data, test_result)
        listener.end_suite(suite_data, suite_result)

        # Verify all 3 keywords were tracked
        trace_dir = [d for d in tmp_path.iterdir() if d.is_dir()][0]
        kw_dirs = list((trace_dir / "keywords").iterdir())
        assert len(kw_dirs) == 3


class TestViewerContent:
    """Test that viewer HTML contains correct content."""

    def test_viewer_contains_trace_data(self, tmp_path):
        """Test that viewer.html contains embedded TRACE_DATA."""
        listener = TraceListener(output_dir=str(tmp_path))

        suite_data = create_mock_data(name="Suite", source=None)
        suite_result = create_mock_result(status="PASS")
        test_data = create_mock_data(
            name="Test ABC",
            longname="Suite.Test ABC",
            doc="",
            tags=[],
        )
        test_result = create_mock_result(status="PASS", message="", elapsed_time=0.5)

        listener.start_suite(suite_data, suite_result)
        listener.start_test(test_data, test_result)
        listener.end_test(test_data, test_result)
        listener.end_suite(suite_data, suite_result)

        # Generate viewer using ViewerGenerator
        trace_dir = [d for d in tmp_path.iterdir() if d.is_dir()][0]
        generator = ViewerGenerator()
        generator.generate_from_manifest(trace_dir)

        viewer_html = (trace_dir / "viewer.html").read_text()

        # Check that TRACE_DATA is embedded
        assert "TRACE_DATA" in viewer_html
        assert "Test ABC" in viewer_html  # Test name should be in data

    def test_viewer_is_valid_html(self, tmp_path):
        """Test that generated viewer is valid HTML structure."""
        listener = TraceListener(output_dir=str(tmp_path))

        suite_data = create_mock_data(name="Suite", source=None)
        suite_result = create_mock_result(status="PASS")
        test_data = create_mock_data(
            name="Test",
            longname="Suite.Test",
            doc="",
            tags=[],
        )
        test_result = create_mock_result(status="PASS", message="", elapsed_time=0.5)

        # Add a keyword to have more content
        kw_data = create_mock_data(
            name="Log",
            args=("Hello",),
            assign=(),
            libname="BuiltIn",
            type="KEYWORD",
        )
        kw_result = create_mock_result(status="PASS", message="", elapsed_time=0.1)

        listener.start_suite(suite_data, suite_result)
        listener.start_test(test_data, test_result)
        listener.start_keyword(kw_data, kw_result)
        listener.end_keyword(kw_data, kw_result)
        listener.end_test(test_data, test_result)
        listener.end_suite(suite_data, suite_result)

        # Generate viewer using ViewerGenerator
        trace_dir = [d for d in tmp_path.iterdir() if d.is_dir()][0]
        generator = ViewerGenerator()
        generator.generate_from_manifest(trace_dir)

        viewer_html = (trace_dir / "viewer.html").read_text()

        # Basic HTML structure checks
        assert "<!DOCTYPE html>" in viewer_html
        assert "<html" in viewer_html
        assert "</html>" in viewer_html
        assert "<head>" in viewer_html
        assert "</head>" in viewer_html
        assert "<body>" in viewer_html
        assert "</body>" in viewer_html
        assert "<script>" in viewer_html


class TestViewerGeneratorDirect:
    """Test ViewerGenerator directly."""

    def test_generate_from_manifest(self, tmp_path):
        """Test generating viewer from existing manifest."""
        # Create a trace directory with manifest and keywords
        trace_dir = tmp_path / "test_trace_20250120_120000"
        trace_dir.mkdir()
        keywords_dir = trace_dir / "keywords"
        keywords_dir.mkdir()

        # Create manifest
        manifest = {
            "version": "1.0.0",
            "test_name": "Generated Test",
            "suite_name": "Generated Suite",
            "status": "PASS",
            "message": "",
            "duration_ms": 1000,
        }
        (trace_dir / "manifest.json").write_text(json.dumps(manifest))

        # Create a keyword directory with metadata
        kw_dir = keywords_dir / "001_log"
        kw_dir.mkdir()
        kw_metadata = {
            "index": 1,
            "name": "Log",
            "status": "PASS",
            "duration_ms": 50,
            "args": ["Hello World"],
            "level": 1,
        }
        (kw_dir / "metadata.json").write_text(json.dumps(kw_metadata))

        # Generate viewer
        generator = ViewerGenerator()
        output_path = generator.generate_from_manifest(trace_dir)

        assert output_path.exists()
        assert output_path.name == "viewer.html"

        content = output_path.read_text()
        assert "Generated Test" in content
        assert "TRACE_DATA" in content

    def test_generator_handles_missing_manifest(self, tmp_path):
        """Test that generator raises error for missing manifest."""
        trace_dir = tmp_path / "empty_trace"
        trace_dir.mkdir()

        generator = ViewerGenerator()

        with pytest.raises(FileNotFoundError):
            generator.generate_from_manifest(trace_dir)


class TestTraceWriter:
    """Test TraceWriter functionality in integration context."""

    def test_writer_creates_complete_structure(self, tmp_path):
        """Test that TraceWriter creates complete directory structure."""
        writer = TraceWriter(str(tmp_path))

        # Create trace
        trace_dir = writer.create_trace("Complete Test")
        assert trace_dir.exists()
        assert (trace_dir / "keywords").exists()

        # Create keyword
        kw_dir = writer.create_keyword_dir("First Keyword")
        assert kw_dir.exists()

        # Write manifest
        manifest = {"test_name": "Complete Test", "status": "PASS"}
        manifest_path = writer.write_manifest(manifest)
        assert manifest_path.exists()

        # Write keyword metadata
        metadata = {"name": "First Keyword", "status": "PASS"}
        metadata_path = writer.write_keyword_metadata(kw_dir, metadata)
        assert metadata_path.exists()

        # Write variables
        variables = {"${VAR}": "value"}
        variables_path = writer.write_keyword_variables(kw_dir, variables)
        assert variables_path.exists()

        # Write screenshot
        png_data = b"\x89PNG\r\n\x1a\n"  # PNG magic bytes
        screenshot_path = writer.write_screenshot(kw_dir, png_data)
        assert screenshot_path.exists()
        assert screenshot_path.read_bytes() == png_data

    def test_keyword_directories_are_numbered(self, tmp_path):
        """Test that keyword directories are numbered sequentially."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")

        kw1 = writer.create_keyword_dir("First")
        kw2 = writer.create_keyword_dir("Second")
        kw3 = writer.create_keyword_dir("Third")

        assert kw1.name.startswith("001_")
        assert kw2.name.startswith("002_")
        assert kw3.name.startswith("003_")


class TestEndToEndScenarios:
    """End-to-end test scenarios simulating real usage."""

    def test_login_test_scenario(self, tmp_path):
        """Simulate a complete login test scenario."""
        listener = TraceListener(output_dir=str(tmp_path))

        # Suite setup
        suite_data = create_mock_data(
            name="Login Tests",
            source=Path("/tests/login.robot"),
        )
        suite_result = create_mock_result(status="PASS")

        listener.start_suite(suite_data, suite_result)

        # Test: Valid Login
        test_data = create_mock_data(
            name="Valid Login Should Succeed",
            longname="Login Tests.Valid Login Should Succeed",
            doc="Test that valid credentials allow login",
            tags=["smoke", "login", "critical"],
        )
        test_result = create_mock_result(status="PASS", message="", elapsed_time=5.0)

        listener.start_test(test_data, test_result)

        # Keywords
        keywords = [
            ("Open Browser", "SeleniumLibrary", ["https://example.com/login", "chrome"]),
            ("Input Text", "SeleniumLibrary", ["id:username", "admin"]),
            ("Input Password", "SeleniumLibrary", ["id:password", "secret123"]),
            ("Click Button", "SeleniumLibrary", ["id:submit"]),
            ("Wait Until Page Contains", "SeleniumLibrary", ["Welcome, admin"]),
            ("Close Browser", "SeleniumLibrary", []),
        ]

        for name, lib, args in keywords:
            kw_data = create_mock_data(
                name=name,
                args=tuple(args),
                assign=(),
                libname=lib,
                type="KEYWORD",
            )
            kw_result = create_mock_result(status="PASS", message="", elapsed_time=0.5)
            listener.start_keyword(kw_data, kw_result)
            listener.end_keyword(kw_data, kw_result)

        listener.end_test(test_data, test_result)
        listener.end_suite(suite_data, suite_result)

        # Verify complete trace
        trace_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        assert len(trace_dirs) == 1

        trace_dir = trace_dirs[0]

        # Verify manifest
        manifest = json.loads((trace_dir / "manifest.json").read_text())
        assert manifest["test_name"] == "Valid Login Should Succeed"
        assert manifest["suite_name"] == "Login Tests"
        assert manifest["status"] == "PASS"
        assert manifest["keywords_count"] == 6
        assert "smoke" in manifest["tags"]

        # Verify keyword directories
        kw_dirs = list((trace_dir / "keywords").iterdir())
        assert len(kw_dirs) == 6

        # Generate and verify viewer
        generator = ViewerGenerator()
        viewer_path = generator.generate_from_manifest(trace_dir)
        assert viewer_path.exists()
        assert "Valid Login Should Succeed" in viewer_path.read_text()

    def test_failed_test_scenario(self, tmp_path):
        """Simulate a test that fails."""
        listener = TraceListener(output_dir=str(tmp_path))

        suite_data = create_mock_data(name="Failed Tests", source=None)
        suite_result = create_mock_result(status="FAIL")

        listener.start_suite(suite_data, suite_result)

        test_data = create_mock_data(
            name="Test That Fails",
            longname="Failed Tests.Test That Fails",
            doc="This test is expected to fail",
            tags=["negative"],
        )
        test_result = create_mock_result(
            status="FAIL",
            message="AssertionError: Expected 'success' but got 'error'",
            elapsed_time=2.0,
        )

        listener.start_test(test_data, test_result)

        # Passing keyword
        kw1_data = create_mock_data(
            name="Setup",
            args=(),
            assign=(),
            libname="",
            type="KEYWORD",
        )
        kw1_result = create_mock_result(status="PASS", message="", elapsed_time=0.1)
        listener.start_keyword(kw1_data, kw1_result)
        listener.end_keyword(kw1_data, kw1_result)

        # Failing keyword
        kw2_data = create_mock_data(
            name="Should Be Equal",
            args=("error", "success"),
            assign=(),
            libname="BuiltIn",
            type="KEYWORD",
        )
        kw2_result = create_mock_result(
            status="FAIL",
            message="AssertionError: Expected 'success' but got 'error'",
            elapsed_time=0.05,
        )
        listener.start_keyword(kw2_data, kw2_result)
        listener.end_keyword(kw2_data, kw2_result)

        listener.end_test(test_data, test_result)
        listener.end_suite(suite_data, suite_result)

        # Verify trace
        trace_dir = [d for d in tmp_path.iterdir() if d.is_dir()][0]
        manifest = json.loads((trace_dir / "manifest.json").read_text())

        assert manifest["status"] == "FAIL"
        assert "AssertionError" in manifest["message"]

        # Verify failed keyword metadata
        kw_dirs = sorted((trace_dir / "keywords").iterdir())
        failed_kw_metadata = json.loads((kw_dirs[1] / "metadata.json").read_text())
        assert failed_kw_metadata["status"] == "FAIL"
        assert "AssertionError" in failed_kw_metadata["message"]
