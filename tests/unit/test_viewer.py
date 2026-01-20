"""Unit tests for the ViewerGenerator class.

Tests cover HTML generation, data preparation, and file handling
for the trace viewer.
"""

import json

import pytest

from trace_viewer.viewer import ViewerGenerator


class TestViewerGenerator:
    """Tests for ViewerGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create a ViewerGenerator instance."""
        return ViewerGenerator()

    @pytest.fixture
    def sample_trace_data(self):
        """Sample trace data for testing."""
        return {
            "test_name": "Login Should Work",
            "suite_name": "Authentication",
            "status": "FAIL",
            "message": "Element not found",
            "start_time": "2025-01-20T14:30:22Z",
            "duration_ms": 23333,
            "keywords": [
                {
                    "index": 1,
                    "name": "Open Browser",
                    "status": "PASS",
                    "duration_ms": 1500,
                    "args": ["https://example.com", "chrome"],
                    "screenshot": "keywords/001_open_browser/screenshot.png",
                    "variables": {"URL": "https://example.com"},
                    "level": 0,
                    "parent": None,
                },
                {
                    "index": 2,
                    "name": "Input Text",
                    "status": "PASS",
                    "duration_ms": 200,
                    "args": ["id=username", "testuser"],
                    "screenshot": "keywords/002_input_text/screenshot.png",
                    "variables": {"USERNAME": "testuser"},
                    "level": 0,
                    "parent": None,
                },
                {
                    "index": 3,
                    "name": "Click Button",
                    "status": "FAIL",
                    "duration_ms": 500,
                    "args": ["id=submit"],
                    "screenshot": None,
                    "variables": {},
                    "level": 0,
                    "parent": None,
                    "message": "Element 'id=submit' not found",
                },
            ],
        }

    def test_init_sets_template_path(self, generator):
        """Test that generator initializes with correct template path."""
        assert generator.template_path.name == "viewer.html"
        assert generator.template_path.parent.name == "templates"

    def test_template_exists(self, generator):
        """Test that the template file exists."""
        assert generator.template_path.exists()

    def test_generate_creates_viewer_file(self, generator, sample_trace_data, tmp_path):
        """Test that generate creates a viewer.html file."""
        output_path = generator.generate(tmp_path, sample_trace_data)

        assert output_path.exists()
        assert output_path.name == "viewer.html"
        assert output_path.parent == tmp_path

    def test_generate_returns_correct_path(self, generator, sample_trace_data, tmp_path):
        """Test that generate returns the correct output path."""
        output_path = generator.generate(tmp_path, sample_trace_data)

        assert output_path == tmp_path / "viewer.html"

    def test_generated_file_contains_trace_data(self, generator, sample_trace_data, tmp_path):
        """Test that generated HTML contains the trace data."""
        output_path = generator.generate(tmp_path, sample_trace_data)
        content = output_path.read_text(encoding="utf-8")

        # Check that test name appears in data
        assert "Login Should Work" in content
        # Check that suite name appears
        assert "Authentication" in content
        # Check that keyword names appear
        assert "Open Browser" in content
        assert "Input Text" in content
        assert "Click Button" in content

    def test_generated_file_is_valid_html(self, generator, sample_trace_data, tmp_path):
        """Test that generated file is valid HTML structure."""
        output_path = generator.generate(tmp_path, sample_trace_data)
        content = output_path.read_text(encoding="utf-8")

        assert content.startswith("<!DOCTYPE html>")
        assert "<html" in content
        assert "</html>" in content
        assert "<head>" in content
        assert "</head>" in content
        assert "<body>" in content
        assert "</body>" in content

    def test_generated_file_contains_trace_data_json(self, generator, sample_trace_data, tmp_path):
        """Test that TRACE_DATA is properly embedded as JSON."""
        output_path = generator.generate(tmp_path, sample_trace_data)
        content = output_path.read_text(encoding="utf-8")

        # Extract the TRACE_DATA JSON from the HTML
        # Look for the pattern: const TRACE_DATA = {...};
        import re

        match = re.search(r"const TRACE_DATA = ({.*?});", content, re.DOTALL)
        assert match is not None, "TRACE_DATA not found in generated HTML"

        # Verify it's valid JSON
        json_str = match.group(1)
        data = json.loads(json_str)

        assert data["test_name"] == "Login Should Work"
        assert data["status"] == "FAIL"
        assert len(data["keywords"]) == 3

    def test_generate_with_invalid_data_raises_error(self, generator, tmp_path):
        """Test that generate raises error with invalid trace_data."""
        with pytest.raises(ValueError):
            generator.generate(tmp_path, "not a dict")

    def test_generate_with_missing_template_raises_error(self, tmp_path, sample_trace_data):
        """Test that generate raises error if template doesn't exist."""
        generator = ViewerGenerator()
        generator.template_path = tmp_path / "nonexistent.html"

        with pytest.raises(FileNotFoundError):
            generator.generate(tmp_path, sample_trace_data)


class TestPrepareViewerData:
    """Tests for _prepare_viewer_data method."""

    @pytest.fixture
    def generator(self):
        """Create a ViewerGenerator instance."""
        return ViewerGenerator()

    def test_prepare_with_minimal_data(self, generator, tmp_path):
        """Test preparing viewer data with minimal input."""
        trace_data = {"test_name": "Simple Test"}

        result = generator._prepare_viewer_data(tmp_path, trace_data)

        assert result["test_name"] == "Simple Test"
        assert result["suite_name"] == ""
        assert result["status"] == "NOT RUN"
        assert result["keywords"] == []

    def test_prepare_preserves_all_fields(self, generator, tmp_path):
        """Test that all trace data fields are preserved."""
        trace_data = {
            "test_name": "Test Name",
            "suite_name": "Suite Name",
            "status": "PASS",
            "message": "Test passed",
            "start_time": "2025-01-20T10:00:00Z",
            "duration_ms": 1000,
            "keywords": [],
        }

        result = generator._prepare_viewer_data(tmp_path, trace_data)

        assert result["test_name"] == "Test Name"
        assert result["suite_name"] == "Suite Name"
        assert result["status"] == "PASS"
        assert result["message"] == "Test passed"
        assert result["start_time"] == "2025-01-20T10:00:00Z"
        assert result["duration_ms"] == 1000


class TestProcessKeyword:
    """Tests for _process_keyword method."""

    @pytest.fixture
    def generator(self):
        """Create a ViewerGenerator instance."""
        return ViewerGenerator()

    def test_process_keyword_with_all_fields(self, generator, tmp_path):
        """Test processing a complete keyword."""
        keyword = {
            "index": 1,
            "name": "Click Button",
            "status": "PASS",
            "duration_ms": 500,
            "args": ["locator", "value"],
            "variables": {"VAR1": "value1"},
            "level": 1,
            "parent": "Parent Keyword",
            "message": "",
            "screenshot": "keywords/001_click_button/screenshot.png",
        }

        result = generator._process_keyword(tmp_path, keyword)

        assert result["index"] == 1
        assert result["name"] == "Click Button"
        assert result["status"] == "PASS"
        assert result["duration_ms"] == 500
        assert result["args"] == ["locator", "value"]
        assert result["variables"] == {"VAR1": "value1"}
        assert result["level"] == 1
        assert result["parent"] == "Parent Keyword"
        assert result["screenshot"] == "keywords/001_click_button/screenshot.png"

    def test_process_keyword_with_minimal_data(self, generator, tmp_path):
        """Test processing a keyword with minimal data."""
        keyword = {"name": "Simple Keyword"}

        result = generator._process_keyword(tmp_path, keyword)

        assert result["name"] == "Simple Keyword"
        assert result["index"] == 0
        assert result["status"] == "NOT RUN"
        assert result["duration_ms"] == 0
        assert result["args"] == []
        assert result["variables"] == {}
        assert result["level"] == 0
        assert result["parent"] is None
        assert result["screenshot"] is None

    def test_process_keyword_with_absolute_screenshot_path(self, generator, tmp_path):
        """Test that absolute screenshot paths are converted to relative."""
        keyword = {
            "name": "Test Keyword",
            "screenshot": str(tmp_path / "keywords" / "001_test" / "screenshot.png"),
        }

        result = generator._process_keyword(tmp_path, keyword)

        # Should be relative to tmp_path
        assert result["screenshot"] == "keywords/001_test/screenshot.png"

    def test_process_keyword_with_null_screenshot(self, generator, tmp_path):
        """Test processing keyword with no screenshot."""
        keyword = {"name": "Test Keyword", "screenshot": None}

        result = generator._process_keyword(tmp_path, keyword)

        assert result["screenshot"] is None


class TestGenerateFromManifest:
    """Tests for generate_from_manifest method."""

    @pytest.fixture
    def generator(self):
        """Create a ViewerGenerator instance."""
        return ViewerGenerator()

    @pytest.fixture
    def trace_dir_with_manifest(self, tmp_path):
        """Create a trace directory with manifest and keywords."""
        # Create manifest
        manifest = {
            "test_name": "Manifest Test",
            "suite_name": "Test Suite",
            "status": "PASS",
            "duration_ms": 2000,
        }
        manifest_path = tmp_path / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)

        # Create keywords directory
        keywords_dir = tmp_path / "keywords"
        keywords_dir.mkdir()

        # Create keyword 1
        kw1_dir = keywords_dir / "001_open_browser"
        kw1_dir.mkdir()
        with open(kw1_dir / "metadata.json", "w") as f:
            json.dump(
                {"index": 1, "name": "Open Browser", "status": "PASS", "duration_ms": 1000}, f
            )
        with open(kw1_dir / "variables.json", "w") as f:
            json.dump({"URL": "https://example.com"}, f)
        # Create a dummy screenshot
        (kw1_dir / "screenshot.png").write_bytes(b"fake png data")

        # Create keyword 2 without screenshot
        kw2_dir = keywords_dir / "002_click_element"
        kw2_dir.mkdir()
        with open(kw2_dir / "metadata.json", "w") as f:
            json.dump(
                {"index": 2, "name": "Click Element", "status": "PASS", "duration_ms": 500}, f
            )

        return tmp_path

    def test_generate_from_manifest_creates_viewer(self, generator, trace_dir_with_manifest):
        """Test generating viewer from existing trace directory."""
        output_path = generator.generate_from_manifest(trace_dir_with_manifest)

        assert output_path.exists()
        assert output_path.name == "viewer.html"

    def test_generate_from_manifest_includes_keywords(self, generator, trace_dir_with_manifest):
        """Test that keywords from directory are included in viewer."""
        output_path = generator.generate_from_manifest(trace_dir_with_manifest)
        content = output_path.read_text(encoding="utf-8")

        assert "Open Browser" in content
        assert "Click Element" in content

    def test_generate_from_manifest_missing_manifest_raises_error(self, generator, tmp_path):
        """Test that missing manifest raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            generator.generate_from_manifest(tmp_path)


class TestLoadKeywordsFromDir:
    """Tests for _load_keywords_from_dir method."""

    @pytest.fixture
    def generator(self):
        """Create a ViewerGenerator instance."""
        return ViewerGenerator()

    def test_load_empty_keywords_dir(self, generator, tmp_path):
        """Test loading from empty keywords directory."""
        keywords_dir = tmp_path / "keywords"
        keywords_dir.mkdir()

        result = generator._load_keywords_from_dir(tmp_path)

        assert result == []

    def test_load_nonexistent_keywords_dir(self, generator, tmp_path):
        """Test loading when keywords directory doesn't exist."""
        result = generator._load_keywords_from_dir(tmp_path)

        assert result == []

    def test_load_keywords_sorted_by_index(self, generator, tmp_path):
        """Test that keywords are loaded in correct order."""
        keywords_dir = tmp_path / "keywords"
        keywords_dir.mkdir()

        # Create keywords out of order
        for name in ["003_third", "001_first", "002_second"]:
            kw_dir = keywords_dir / name
            kw_dir.mkdir()
            with open(kw_dir / "metadata.json", "w") as f:
                json.dump({"name": name.split("_")[1]}, f)

        result = generator._load_keywords_from_dir(tmp_path)

        assert len(result) == 3
        assert result[0]["name"] == "first"
        assert result[1]["name"] == "second"
        assert result[2]["name"] == "third"

    def test_load_keyword_with_screenshot(self, generator, tmp_path):
        """Test loading keyword with screenshot sets correct path."""
        keywords_dir = tmp_path / "keywords"
        kw_dir = keywords_dir / "001_test"
        kw_dir.mkdir(parents=True)

        with open(kw_dir / "metadata.json", "w") as f:
            json.dump({"name": "Test"}, f)
        (kw_dir / "screenshot.png").write_bytes(b"fake png")

        result = generator._load_keywords_from_dir(tmp_path)

        assert len(result) == 1
        assert result[0]["screenshot"] == "keywords/001_test/screenshot.png"

    def test_load_keyword_without_screenshot(self, generator, tmp_path):
        """Test loading keyword without screenshot sets None."""
        keywords_dir = tmp_path / "keywords"
        kw_dir = keywords_dir / "001_test"
        kw_dir.mkdir(parents=True)

        with open(kw_dir / "metadata.json", "w") as f:
            json.dump({"name": "Test"}, f)

        result = generator._load_keywords_from_dir(tmp_path)

        assert len(result) == 1
        assert result[0]["screenshot"] is None

    def test_load_keyword_with_variables(self, generator, tmp_path):
        """Test loading keyword includes variables."""
        keywords_dir = tmp_path / "keywords"
        kw_dir = keywords_dir / "001_test"
        kw_dir.mkdir(parents=True)

        with open(kw_dir / "metadata.json", "w") as f:
            json.dump({"name": "Test"}, f)
        with open(kw_dir / "variables.json", "w") as f:
            json.dump({"VAR1": "value1", "VAR2": "value2"}, f)

        result = generator._load_keywords_from_dir(tmp_path)

        assert len(result) == 1
        assert result[0]["variables"] == {"VAR1": "value1", "VAR2": "value2"}
