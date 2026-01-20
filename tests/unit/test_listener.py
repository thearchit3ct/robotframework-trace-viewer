"""Unit tests for TraceListener and related functions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from trace_viewer.listener import (
    TraceListener,
    get_iso_timestamp,
    slugify,
    write_json_atomic,
)


class TestSlugify:
    """Tests for the slugify function."""

    def test_slugify_basic(self) -> None:
        """Test basic text conversion."""
        assert slugify("Hello World") == "hello_world"

    def test_slugify_special_characters(self) -> None:
        """Test that special characters are removed."""
        assert slugify("Test with special chars: @#$%!") == "test_with_special_chars"

    def test_slugify_multiple_spaces(self) -> None:
        """Test that multiple spaces become single underscore."""
        assert slugify("  Multiple   Spaces  ") == "multiple_spaces"

    def test_slugify_max_length(self) -> None:
        """Test that output is truncated to max_length."""
        result = slugify("A" * 100, max_length=10)
        assert len(result) <= 10
        assert result == "a" * 10

    def test_slugify_preserves_hyphens(self) -> None:
        """Test that hyphens are preserved."""
        assert slugify("test-case-name") == "test-case-name"

    def test_slugify_empty_string(self) -> None:
        """Test empty string input."""
        assert slugify("") == ""

    def test_slugify_only_special_chars(self) -> None:
        """Test string with only special characters."""
        assert slugify("@#$%!") == ""

    def test_slugify_underscores(self) -> None:
        """Test that existing underscores are handled."""
        assert slugify("test__name___here") == "test_name_here"

    def test_slugify_robot_framework_test_name(self) -> None:
        """Test with realistic RF test name."""
        assert (
            slugify("Login Should Work With Valid Credentials")
            == "login_should_work_with_valid_credentials"
        )

    def test_slugify_truncation_does_not_end_with_underscore(self) -> None:
        """Test that truncation removes trailing underscores."""
        result = slugify("hello_world_test_case", max_length=12)
        assert not result.endswith("_")


class TestGetIsoTimestamp:
    """Tests for the get_iso_timestamp function."""

    def test_timestamp_format(self) -> None:
        """Test that timestamp is in ISO 8601 format."""
        ts = get_iso_timestamp()
        # Should contain date, time, and timezone
        assert "T" in ts
        assert "+" in ts or "Z" in ts

    def test_timestamp_is_string(self) -> None:
        """Test that timestamp is a string."""
        ts = get_iso_timestamp()
        assert isinstance(ts, str)


class TestWriteJsonAtomic:
    """Tests for the write_json_atomic function."""

    def test_writes_valid_json(self, tmp_path: Path) -> None:
        """Test that valid JSON is written."""
        file_path = tmp_path / "test.json"
        data = {"key": "value", "number": 42}
        write_json_atomic(file_path, data)

        assert file_path.exists()
        with open(file_path, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that parent directories are created."""
        file_path = tmp_path / "nested" / "dirs" / "test.json"
        data = {"test": True}
        write_json_atomic(file_path, data)

        assert file_path.exists()

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Test that existing file is overwritten."""
        file_path = tmp_path / "test.json"
        write_json_atomic(file_path, {"old": "data"})
        write_json_atomic(file_path, {"new": "data"})

        with open(file_path, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == {"new": "data"}


class TestTraceListenerInit:
    """Tests for TraceListener initialization."""

    def test_listener_init_creates_output_dir(self, tmp_path: Path) -> None:
        """Test that initializing the listener creates the output directory."""
        output_dir = tmp_path / "traces"
        assert not output_dir.exists()

        listener = TraceListener(output_dir=str(output_dir))

        assert output_dir.exists()
        assert output_dir.is_dir()
        assert listener.output_dir == output_dir

    def test_listener_init_default_capture_mode(self, tmp_path: Path) -> None:
        """Test that default capture mode is 'full'."""
        output_dir = tmp_path / "traces"
        listener = TraceListener(output_dir=str(output_dir))

        assert listener.capture_mode == "full"

    def test_listener_init_custom_capture_mode(self, tmp_path: Path) -> None:
        """Test that custom capture mode is set."""
        output_dir = tmp_path / "traces"
        listener = TraceListener(output_dir=str(output_dir), capture_mode="on_failure")

        assert listener.capture_mode == "on_failure"

    def test_listener_init_invalid_capture_mode_defaults_to_full(self, tmp_path: Path) -> None:
        """Test that invalid capture mode defaults to 'full'."""
        output_dir = tmp_path / "traces"
        listener = TraceListener(output_dir=str(output_dir), capture_mode="invalid")

        assert listener.capture_mode == "full"

    def test_listener_init_state(self, tmp_path: Path) -> None:
        """Test initial state of listener."""
        output_dir = tmp_path / "traces"
        listener = TraceListener(output_dir=str(output_dir))

        assert listener.trace_data == {}
        assert listener.suite_name == ""
        assert listener.suite_source == ""
        assert listener.current_test == {}
        assert listener.current_test_dir is None
        assert listener.keyword_index == 0
        assert listener.keyword_stack == []


def create_mock_data(**kwargs: Any) -> MagicMock:
    """Create a mock data object with specified attributes."""
    mock = MagicMock()
    for key, value in kwargs.items():
        setattr(mock, key, value)
    return mock


def create_mock_result(**kwargs: Any) -> MagicMock:
    """Create a mock result object with specified attributes."""
    mock = MagicMock()
    for key, value in kwargs.items():
        setattr(mock, key, value)
    return mock


class TestTraceListenerStartSuite:
    """Tests for TraceListener.start_suite method."""

    def test_listener_start_suite_initializes_trace_data(self, tmp_path: Path) -> None:
        """Test that start_suite initializes trace_data correctly."""
        output_dir = tmp_path / "traces"
        listener = TraceListener(output_dir=str(output_dir))

        suite_data = create_mock_data(
            name="Authentication Suite",
            source=Path("/tests/auth.robot"),
        )
        suite_result = create_mock_result()

        listener.start_suite(suite_data, suite_result)

        assert listener.suite_name == "Authentication Suite"
        assert listener.suite_source == str(Path("/tests/auth.robot"))
        assert listener.trace_data["suite_name"] == "Authentication Suite"
        assert listener.trace_data["version"] == "1.0.0"
        assert listener.trace_data["capture_mode"] == "full"
        assert listener.trace_data["tests"] == []

    def test_listener_start_suite_handles_none_source(self, tmp_path: Path) -> None:
        """Test that start_suite handles None source."""
        output_dir = tmp_path / "traces"
        listener = TraceListener(output_dir=str(output_dir))

        suite_data = create_mock_data(name="Test Suite", source=None)
        suite_result = create_mock_result()

        listener.start_suite(suite_data, suite_result)

        assert listener.suite_source == ""


class TestTraceListenerStartTest:
    """Tests for TraceListener.start_test method."""

    def test_listener_start_test_creates_test_folder(self, tmp_path: Path) -> None:
        """Test that start_test creates the test folder structure."""
        output_dir = tmp_path / "traces"
        listener = TraceListener(output_dir=str(output_dir))

        # Initialize suite first
        suite_data = create_mock_data(name="Test Suite", source=None)
        listener.start_suite(suite_data, create_mock_result())

        # Start test
        test_data = create_mock_data(
            name="Login Should Work",
            longname="Test Suite.Login Should Work",
            doc="Test documentation",
            tags=["smoke", "login"],
        )
        listener.start_test(test_data, create_mock_result())

        # Verify test folder was created
        assert listener.current_test_dir is not None
        assert listener.current_test_dir.exists()
        assert listener.current_test_dir.name.startswith("login_should_work_")

        # Verify keywords subfolder exists
        keywords_dir = listener.current_test_dir / "keywords"
        assert keywords_dir.exists()

    def test_listener_start_test_initializes_current_test(self, tmp_path: Path) -> None:
        """Test that start_test initializes current_test data."""
        output_dir = tmp_path / "traces"
        listener = TraceListener(output_dir=str(output_dir))

        suite_data = create_mock_data(name="Test Suite", source=None)
        listener.start_suite(suite_data, create_mock_result())

        test_data = create_mock_data(
            name="Login Should Work",
            longname="Test Suite.Login Should Work",
            doc="Test doc",
            tags=["smoke"],
        )
        listener.start_test(test_data, create_mock_result())

        assert listener.current_test["name"] == "Login Should Work"
        assert listener.current_test["longname"] == "Test Suite.Login Should Work"
        assert listener.current_test["doc"] == "Test doc"
        assert listener.current_test["tags"] == ["smoke"]
        assert listener.current_test["start_time"] is not None
        assert listener.keyword_index == 0

    def test_listener_start_test_handles_empty_tags(self, tmp_path: Path) -> None:
        """Test that start_test handles empty tags."""
        output_dir = tmp_path / "traces"
        listener = TraceListener(output_dir=str(output_dir))

        suite_data = create_mock_data(name="Suite", source=None)
        listener.start_suite(suite_data, create_mock_result())

        test_data = create_mock_data(
            name="Test",
            longname="Suite.Test",
            doc="",
            tags=None,
        )
        listener.start_test(test_data, create_mock_result())

        assert listener.current_test["tags"] == []


class TestTraceListenerKeywordTracking:
    """Tests for TraceListener keyword tracking."""

    def test_listener_keyword_tracking_order(self, tmp_path: Path) -> None:
        """Test that keywords are tracked in correct order."""
        output_dir = tmp_path / "traces"
        listener = TraceListener(output_dir=str(output_dir))

        # Setup suite and test
        suite_data = create_mock_data(name="Suite", source=None)
        listener.start_suite(suite_data, create_mock_result())

        test_data = create_mock_data(
            name="Test",
            longname="Suite.Test",
            doc="",
            tags=[],
        )
        listener.start_test(test_data, create_mock_result())

        # Create and track keywords
        keywords = [
            ("Open Browser", ["http://example.com", "chrome"]),
            ("Click Button", ["button#submit"]),
            ("Wait Until Element Is Visible", ["div#result"]),
        ]

        for name, args in keywords:
            kw_data = create_mock_data(
                name=name,
                args=args,
                assign=[],
                libname="SeleniumLibrary",
                type="KEYWORD",
            )
            kw_result = create_mock_result(status="PASS", message="", elapsed_time=0.5)

            listener.start_keyword(kw_data, kw_result)
            listener.end_keyword(kw_data, kw_result)

        # Verify keyword order
        assert len(listener.current_test["keywords"]) == 3
        assert listener.current_test["keywords"][0]["name"] == "Open Browser"
        assert listener.current_test["keywords"][0]["index"] == 1
        assert listener.current_test["keywords"][1]["name"] == "Click Button"
        assert listener.current_test["keywords"][1]["index"] == 2
        assert listener.current_test["keywords"][2]["name"] == "Wait Until Element Is Visible"
        assert listener.current_test["keywords"][2]["index"] == 3

    def test_listener_keyword_nesting(self, tmp_path: Path) -> None:
        """Test that nested keywords have correct parent and level."""
        output_dir = tmp_path / "traces"
        listener = TraceListener(output_dir=str(output_dir))

        # Setup
        suite_data = create_mock_data(name="Suite", source=None)
        listener.start_suite(suite_data, create_mock_result())
        test_data = create_mock_data(name="Test", longname="Test", doc="", tags=[])
        listener.start_test(test_data, create_mock_result())

        # Create parent keyword
        parent_data = create_mock_data(
            name="Login With Valid Credentials",
            args=[],
            assign=[],
            libname="",
            type="KEYWORD",
        )
        parent_result = create_mock_result(status="PASS", message="", elapsed_time=1.0)
        listener.start_keyword(parent_data, parent_result)

        # Create nested keyword
        child_data = create_mock_data(
            name="Input Text",
            args=["id=username", "testuser"],
            assign=[],
            libname="SeleniumLibrary",
            type="KEYWORD",
        )
        child_result = create_mock_result(status="PASS", message="", elapsed_time=0.2)
        listener.start_keyword(child_data, child_result)

        # Verify nesting while child is active
        assert len(listener.keyword_stack) == 2
        assert listener.keyword_stack[1]["level"] == 2
        assert listener.keyword_stack[1]["parent_keyword"] == "Login With Valid Credentials"

        # End child
        listener.end_keyword(child_data, child_result)
        assert len(listener.keyword_stack) == 1

        # End parent
        listener.end_keyword(parent_data, parent_result)
        assert len(listener.keyword_stack) == 0

        # Verify saved keyword data
        # Note: Keywords are added when they END, so child ends first
        assert len(listener.current_test["keywords"]) == 2
        # First in list is the child (ended first)
        assert listener.current_test["keywords"][0]["level"] == 2
        assert (
            listener.current_test["keywords"][0]["parent_keyword"] == "Login With Valid Credentials"
        )
        assert listener.current_test["keywords"][0]["name"] == "Input Text"
        # Second in list is the parent (ended last)
        assert listener.current_test["keywords"][1]["level"] == 1
        assert listener.current_test["keywords"][1]["parent_keyword"] is None
        assert listener.current_test["keywords"][1]["name"] == "Login With Valid Credentials"

    def test_listener_keyword_creates_folder(self, tmp_path: Path) -> None:
        """Test that each keyword gets its own folder."""
        output_dir = tmp_path / "traces"
        listener = TraceListener(output_dir=str(output_dir))

        suite_data = create_mock_data(name="Suite", source=None)
        listener.start_suite(suite_data, create_mock_result())
        test_data = create_mock_data(name="Test", longname="Test", doc="", tags=[])
        listener.start_test(test_data, create_mock_result())

        kw_data = create_mock_data(
            name="Click Button",
            args=["submit"],
            assign=[],
            libname="SeleniumLibrary",
            type="KEYWORD",
        )
        kw_result = create_mock_result(status="PASS", message="", elapsed_time=0.1)

        listener.start_keyword(kw_data, kw_result)
        listener.end_keyword(kw_data, kw_result)

        # Check folder exists with metadata
        keyword_folder = listener.current_test_dir / "keywords" / "001_click_button"
        assert keyword_folder.exists()
        assert (keyword_folder / "metadata.json").exists()

    def test_listener_keyword_metadata_content(self, tmp_path: Path) -> None:
        """Test that keyword metadata.json contains correct data."""
        output_dir = tmp_path / "traces"
        listener = TraceListener(output_dir=str(output_dir))

        suite_data = create_mock_data(name="Suite", source=None)
        listener.start_suite(suite_data, create_mock_result())
        test_data = create_mock_data(name="Test", longname="Test", doc="", tags=[])
        listener.start_test(test_data, create_mock_result())

        kw_data = create_mock_data(
            name="Input Text",
            args=["id=username", "testuser"],
            assign=["${result}"],
            libname="SeleniumLibrary",
            type="KEYWORD",
        )
        kw_result = create_mock_result(status="FAIL", message="Element not found", elapsed_time=0.5)

        listener.start_keyword(kw_data, kw_result)
        listener.end_keyword(kw_data, kw_result)

        # Read and verify metadata
        metadata_path = listener.current_test_dir / "keywords" / "001_input_text" / "metadata.json"
        with open(metadata_path, encoding="utf-8") as f:
            metadata = json.load(f)

        assert metadata["name"] == "Input Text"
        assert metadata["args"] == ["id=username", "testuser"]
        assert metadata["assign"] == ["${result}"]
        assert metadata["library"] == "SeleniumLibrary"
        assert metadata["status"] == "FAIL"
        assert metadata["message"] == "Element not found"
        assert metadata["level"] == 1
        assert metadata["parent_keyword"] is None


class TestTraceListenerEndTest:
    """Tests for TraceListener.end_test method."""

    def test_listener_end_test_saves_manifest(self, tmp_path: Path) -> None:
        """Test that end_test saves manifest.json."""
        output_dir = tmp_path / "traces"
        listener = TraceListener(output_dir=str(output_dir))

        # Setup and run test
        suite_data = create_mock_data(name="Suite", source=Path("/test.robot"))
        listener.start_suite(suite_data, create_mock_result())

        test_data = create_mock_data(
            name="My Test",
            longname="Suite.My Test",
            doc="Test doc",
            tags=["smoke"],
        )
        listener.start_test(test_data, create_mock_result())

        test_dir = listener.current_test_dir

        test_result = create_mock_result(status="PASS", message="", elapsed_time=2.5)
        listener.end_test(test_data, test_result)

        # Verify manifest exists and has correct content
        manifest_path = test_dir / "manifest.json"
        assert manifest_path.exists()

        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest["test_name"] == "My Test"
        assert manifest["suite_name"] == "Suite"
        assert manifest["status"] == "PASS"
        assert manifest["tags"] == ["smoke"]
        assert manifest["doc"] == "Test doc"

    def test_listener_end_test_resets_state(self, tmp_path: Path) -> None:
        """Test that end_test resets test-level state."""
        output_dir = tmp_path / "traces"
        listener = TraceListener(output_dir=str(output_dir))

        suite_data = create_mock_data(name="Suite", source=None)
        listener.start_suite(suite_data, create_mock_result())

        test_data = create_mock_data(name="Test", longname="Test", doc="", tags=[])
        listener.start_test(test_data, create_mock_result())

        test_result = create_mock_result(status="PASS", message="", elapsed_time=1.0)
        listener.end_test(test_data, test_result)

        assert listener.current_test == {}
        assert listener.current_test_dir is None
        assert listener.keyword_index == 0
        assert listener.keyword_stack == []


class TestTraceListenerFullFlow:
    """Integration-style tests for complete listener flow."""

    def test_listener_full_test_execution(self, tmp_path: Path) -> None:
        """Test a complete test execution flow."""
        output_dir = tmp_path / "traces"
        listener = TraceListener(output_dir=str(output_dir))

        # Start suite
        suite_data = create_mock_data(
            name="Authentication",
            source=Path("/tests/auth.robot"),
        )
        listener.start_suite(suite_data, create_mock_result())

        # Start test
        test_data = create_mock_data(
            name="Login Should Work",
            longname="Authentication.Login Should Work",
            doc="Verify login functionality",
            tags=["smoke", "login"],
        )
        listener.start_test(test_data, create_mock_result())
        test_dir = listener.current_test_dir

        # Execute keywords
        keywords = [
            ("Open Browser", "SeleniumLibrary", ["http://example.com", "chrome"], "PASS"),
            ("Input Text", "SeleniumLibrary", ["id=username", "admin"], "PASS"),
            ("Input Password", "SeleniumLibrary", ["id=password", "secret"], "PASS"),
            ("Click Button", "SeleniumLibrary", ["id=login"], "PASS"),
            ("Wait Until Element Is Visible", "SeleniumLibrary", ["id=welcome"], "PASS"),
        ]

        for name, lib, args, status in keywords:
            kw_data = create_mock_data(name=name, args=args, assign=[], libname=lib, type="KEYWORD")
            kw_result = create_mock_result(status=status, message="", elapsed_time=0.3)
            listener.start_keyword(kw_data, kw_result)
            listener.end_keyword(kw_data, kw_result)

        # End test
        test_result = create_mock_result(status="PASS", message="", elapsed_time=1.5)
        listener.end_test(test_data, test_result)

        # End suite
        listener.end_suite(suite_data, create_mock_result())

        # Verify trace structure
        assert test_dir.exists()
        assert (test_dir / "manifest.json").exists()
        assert (test_dir / "keywords").exists()

        # Verify all keyword folders exist
        for _i in range(1, 6):
            keyword_folders = list((test_dir / "keywords").iterdir())
            assert len(keyword_folders) == 5

        # Verify manifest content
        with open(test_dir / "manifest.json", encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest["test_name"] == "Login Should Work"
        assert manifest["suite_name"] == "Authentication"
        assert manifest["status"] == "PASS"
        assert manifest["keywords_count"] == 5

        # Verify trace_data was updated
        assert len(listener.trace_data["tests"]) == 1
        assert listener.trace_data["tests"][0]["status"] == "PASS"
