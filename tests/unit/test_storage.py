"""Unit tests for trace_viewer.storage module."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from trace_viewer.storage import TraceWriter


class TestSlugify:
    """Tests for TraceWriter.slugify static method."""

    def test_slugify_simple_text(self):
        """Test slugify with simple text converts to lowercase with underscores."""
        result = TraceWriter.slugify("Login Should Work")
        assert result == "login_should_work"

    def test_slugify_removes_special_characters(self):
        """Test slugify removes special characters like ! @ # etc."""
        result = TraceWriter.slugify("Test! With @Special# Chars$")
        assert result == "test_with_special_chars"

    def test_slugify_preserves_numbers(self):
        """Test slugify preserves numbers in the text."""
        result = TraceWriter.slugify("Test 123 Numbers")
        assert result == "test_123_numbers"

    def test_slugify_handles_hyphens(self):
        """Test slugify converts hyphens to underscores."""
        result = TraceWriter.slugify("test-with-hyphens")
        assert result == "test_with_hyphens"

    def test_slugify_collapses_multiple_spaces(self):
        """Test slugify collapses multiple spaces into single underscore."""
        result = TraceWriter.slugify("test    multiple   spaces")
        assert result == "test_multiple_spaces"

    def test_slugify_respects_max_length(self):
        """Test slugify truncates to max_length."""
        result = TraceWriter.slugify("a" * 100, max_length=10)
        assert result == "a" * 10
        assert len(result) == 10

    def test_slugify_default_max_length_is_50(self):
        """Test slugify default max_length is 50."""
        result = TraceWriter.slugify("a" * 100)
        assert len(result) == 50

    def test_slugify_empty_string_returns_unnamed(self):
        """Test slugify returns 'unnamed' for empty input."""
        result = TraceWriter.slugify("")
        assert result == "unnamed"

    def test_slugify_only_special_chars_returns_unnamed(self):
        """Test slugify returns 'unnamed' when input has only special chars."""
        result = TraceWriter.slugify("!@#$%^&*()")
        assert result == "unnamed"

    def test_slugify_strips_trailing_underscores(self):
        """Test slugify removes trailing underscores."""
        result = TraceWriter.slugify("test ")
        assert result == "test"
        assert not result.endswith("_")


class TestCreateTrace:
    """Tests for TraceWriter.create_trace method."""

    def test_create_trace_creates_directory(self, tmp_path):
        """Test create_trace creates the trace directory."""
        writer = TraceWriter(str(tmp_path))
        trace_dir = writer.create_trace("My Test")

        assert trace_dir.exists()
        assert trace_dir.is_dir()

    def test_create_trace_creates_keywords_subdir(self, tmp_path):
        """Test create_trace creates keywords subdirectory."""
        writer = TraceWriter(str(tmp_path))
        trace_dir = writer.create_trace("My Test")

        keywords_dir = trace_dir / "keywords"
        assert keywords_dir.exists()
        assert keywords_dir.is_dir()

    def test_create_trace_includes_slugified_name(self, tmp_path):
        """Test trace directory name includes slugified test name."""
        writer = TraceWriter(str(tmp_path))
        trace_dir = writer.create_trace("Login Should Work!")

        assert "login_should_work" in trace_dir.name

    def test_create_trace_includes_timestamp(self, tmp_path):
        """Test trace directory name includes timestamp."""
        writer = TraceWriter(str(tmp_path))

        # Patch datetime in the module where it's used
        with patch("trace_viewer.storage.trace_writer.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 19, 14, 30, 22)
            trace_dir = writer.create_trace("Test")

        assert "20250119_143022" in trace_dir.name

    def test_create_trace_resets_keyword_counter(self, tmp_path):
        """Test create_trace resets keyword counter to 0."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test 1")
        writer.create_keyword_dir("Keyword")
        writer.create_keyword_dir("Keyword")
        assert writer.get_keyword_counter() == 2

        writer.create_trace("Test 2")
        assert writer.get_keyword_counter() == 0

    def test_create_trace_sets_current_trace_dir(self, tmp_path):
        """Test create_trace sets current trace directory."""
        writer = TraceWriter(str(tmp_path))
        assert writer.get_current_trace_dir() is None

        trace_dir = writer.create_trace("Test")
        assert writer.get_current_trace_dir() == trace_dir


class TestCreateKeywordDir:
    """Tests for TraceWriter.create_keyword_dir method."""

    def test_create_keyword_dir_increments_counter(self, tmp_path):
        """Test create_keyword_dir increments counter for each call."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")

        assert writer.get_keyword_counter() == 0

        writer.create_keyword_dir("First Keyword")
        assert writer.get_keyword_counter() == 1

        writer.create_keyword_dir("Second Keyword")
        assert writer.get_keyword_counter() == 2

        writer.create_keyword_dir("Third Keyword")
        assert writer.get_keyword_counter() == 3

    def test_create_keyword_dir_uses_padded_number(self, tmp_path):
        """Test keyword dir name uses zero-padded number."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")

        kw_dir = writer.create_keyword_dir("Open Browser")
        assert kw_dir.name.startswith("001_")

    def test_create_keyword_dir_includes_slugified_name(self, tmp_path):
        """Test keyword dir name includes slugified keyword name."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")

        kw_dir = writer.create_keyword_dir("Open Browser")
        assert "open_browser" in kw_dir.name

    def test_create_keyword_dir_creates_directory(self, tmp_path):
        """Test create_keyword_dir actually creates the directory."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")

        kw_dir = writer.create_keyword_dir("Open Browser")
        assert kw_dir.exists()
        assert kw_dir.is_dir()

    def test_create_keyword_dir_without_trace_raises_error(self, tmp_path):
        """Test create_keyword_dir raises RuntimeError without active trace."""
        writer = TraceWriter(str(tmp_path))

        with pytest.raises(RuntimeError, match="No active trace"):
            writer.create_keyword_dir("Open Browser")

    def test_create_keyword_dir_respects_max_length(self, tmp_path):
        """Test keyword name is truncated to 40 chars max."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")

        long_name = "a" * 100
        kw_dir = writer.create_keyword_dir(long_name)

        # 001_ prefix (4 chars) + 40 char slug = 44 chars max
        assert len(kw_dir.name) <= 44


class TestWriteManifest:
    """Tests for TraceWriter.write_manifest method."""

    def test_write_manifest_creates_file(self, tmp_path):
        """Test write_manifest creates manifest.json file."""
        writer = TraceWriter(str(tmp_path))
        trace_dir = writer.create_trace("Test")

        data = {"test_name": "Test", "status": "PASS"}
        manifest_path = writer.write_manifest(data)

        assert manifest_path.exists()
        assert manifest_path.name == "manifest.json"
        assert manifest_path.parent == trace_dir

    def test_write_manifest_content_is_valid_json(self, tmp_path):
        """Test manifest.json contains valid JSON."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")

        data = {"test_name": "Test", "status": "PASS", "duration_ms": 1234}
        manifest_path = writer.write_manifest(data)

        content = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert content == data

    def test_write_manifest_without_trace_raises_error(self, tmp_path):
        """Test write_manifest raises RuntimeError without active trace."""
        writer = TraceWriter(str(tmp_path))

        with pytest.raises(RuntimeError, match="No active trace"):
            writer.write_manifest({"test": "data"})

    def test_write_manifest_handles_unicode(self, tmp_path):
        """Test write_manifest handles unicode characters."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")

        data = {"name": "Test avec accents", "message": "Erreur: element introuvable"}
        manifest_path = writer.write_manifest(data)

        content = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert content["message"] == "Erreur: element introuvable"
        assert content["name"] == "Test avec accents"


class TestWriteKeywordMetadata:
    """Tests for TraceWriter.write_keyword_metadata method."""

    def test_write_keyword_metadata_creates_file(self, tmp_path):
        """Test write_keyword_metadata creates metadata.json file."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")
        kw_dir = writer.create_keyword_dir("Open Browser")

        data = {"name": "Open Browser", "status": "PASS"}
        metadata_path = writer.write_keyword_metadata(kw_dir, data)

        assert metadata_path.exists()
        assert metadata_path.name == "metadata.json"
        assert metadata_path.parent == kw_dir

    def test_write_keyword_metadata_content_is_valid_json(self, tmp_path):
        """Test metadata.json contains valid JSON."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")
        kw_dir = writer.create_keyword_dir("Click Button")

        data = {
            "index": 1,
            "name": "Click Button",
            "library": "SeleniumLibrary",
            "args": ["button#submit"],
            "status": "PASS",
            "duration_ms": 150,
        }
        metadata_path = writer.write_keyword_metadata(kw_dir, data)

        content = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert content == data


class TestWriteKeywordVariables:
    """Tests for TraceWriter.write_keyword_variables method."""

    def test_write_keyword_variables_creates_file(self, tmp_path):
        """Test write_keyword_variables creates variables.json file."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")
        kw_dir = writer.create_keyword_dir("Open Browser")

        data = {"scalar": {"${URL}": "https://example.com"}}
        variables_path = writer.write_keyword_variables(kw_dir, data)

        assert variables_path.exists()
        assert variables_path.name == "variables.json"
        assert variables_path.parent == kw_dir

    def test_write_keyword_variables_content_is_valid_json(self, tmp_path):
        """Test variables.json contains valid JSON."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")
        kw_dir = writer.create_keyword_dir("Set Variable")

        data = {
            "scalar": {"${USERNAME}": "testuser", "${PASSWORD}": "***MASKED***"},
            "list": {"@{ITEMS}": ["a", "b", "c"]},
            "dict": {"&{CONFIG}": {"timeout": "30s"}},
        }
        variables_path = writer.write_keyword_variables(kw_dir, data)

        content = json.loads(variables_path.read_text(encoding="utf-8"))
        assert content == data


class TestWriteScreenshot:
    """Tests for TraceWriter.write_screenshot method."""

    def test_write_screenshot_creates_file(self, tmp_path):
        """Test write_screenshot creates screenshot.png file."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")
        kw_dir = writer.create_keyword_dir("Open Browser")

        # Minimal valid PNG header
        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        screenshot_path = writer.write_screenshot(kw_dir, png_data)

        assert screenshot_path.exists()
        assert screenshot_path.name == "screenshot.png"
        assert screenshot_path.parent == kw_dir

    def test_write_screenshot_preserves_binary_data(self, tmp_path):
        """Test write_screenshot preserves exact binary data."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")
        kw_dir = writer.create_keyword_dir("Capture Page")

        # Create some binary data that looks like PNG
        png_data = bytes(range(256)) * 10

        screenshot_path = writer.write_screenshot(kw_dir, png_data)

        read_data = screenshot_path.read_bytes()
        assert read_data == png_data


class TestWriteJsonAtomic:
    """Tests for TraceWriter._write_json_atomic method."""

    def test_write_json_atomic_is_atomic(self, tmp_path):
        """Test _write_json_atomic uses atomic write pattern (tmp + rename)."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")

        target_path = writer.get_current_trace_dir() / "test.json"
        data = {"key": "value"}

        # The atomic write should:
        # 1. Create .tmp file
        # 2. Rename .tmp to final file
        # After completion, no .tmp file should exist
        writer._write_json_atomic(target_path, data)

        assert target_path.exists()
        assert not target_path.with_suffix(".tmp").exists()

        content = json.loads(target_path.read_text(encoding="utf-8"))
        assert content == data

    def test_write_json_atomic_handles_datetime(self, tmp_path):
        """Test _write_json_atomic serializes datetime objects using default=str."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")

        target_path = writer.get_current_trace_dir() / "test.json"
        now = datetime(2025, 1, 19, 14, 30, 22)
        data = {"timestamp": now}

        writer._write_json_atomic(target_path, data)

        content = json.loads(target_path.read_text(encoding="utf-8"))
        assert content["timestamp"] == "2025-01-19 14:30:22"

    def test_write_json_atomic_uses_indent_2(self, tmp_path):
        """Test _write_json_atomic uses 2-space indentation."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")

        target_path = writer.get_current_trace_dir() / "test.json"
        data = {"key": "value"}

        writer._write_json_atomic(target_path, data)

        raw_content = target_path.read_text(encoding="utf-8")
        # Check that the JSON is formatted with indent
        assert '  "key"' in raw_content

    def test_write_json_atomic_uses_utf8(self, tmp_path):
        """Test _write_json_atomic uses UTF-8 encoding."""
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")

        target_path = writer.get_current_trace_dir() / "test.json"
        data = {"message": "cafe"}

        writer._write_json_atomic(target_path, data)

        # Read as UTF-8 and verify
        raw_content = target_path.read_text(encoding="utf-8")
        assert "cafe" in raw_content


class TestTraceWriterInit:
    """Tests for TraceWriter initialization."""

    def test_init_creates_base_dir(self, tmp_path):
        """Test __init__ creates base directory if it doesn't exist."""
        base_dir = tmp_path / "new_traces_dir"
        assert not base_dir.exists()

        writer = TraceWriter(str(base_dir))

        assert base_dir.exists()
        assert writer.base_dir == base_dir

    def test_init_with_existing_dir(self, tmp_path):
        """Test __init__ works with existing directory."""
        base_dir = tmp_path / "existing"
        base_dir.mkdir()

        writer = TraceWriter(str(base_dir))

        assert writer.base_dir == base_dir

    def test_init_defaults_to_traces_dir(self, tmp_path, monkeypatch):
        """Test __init__ defaults to ./traces directory."""
        monkeypatch.chdir(tmp_path)

        writer = TraceWriter()

        assert writer.base_dir == Path("./traces")
        assert writer.base_dir.exists()

    def test_init_state(self, tmp_path):
        """Test initial state after __init__."""
        writer = TraceWriter(str(tmp_path))

        assert writer.get_current_trace_dir() is None
        assert writer.get_keyword_counter() == 0
