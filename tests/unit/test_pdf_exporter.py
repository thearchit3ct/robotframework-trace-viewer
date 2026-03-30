"""Unit tests for the PDFExporter class.

All tests run without weasyprint installed by patching the module at import
time with a lightweight fake.  The tests focus on HTML generation correctness,
edge-case handling, and helper function contracts.
"""

from __future__ import annotations

import base64
import json
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Inject a fake weasyprint so PDFExporter.__init__ succeeds even when the
# real library is not installed.
# ---------------------------------------------------------------------------

_FAKE_WEASYPRINT = types.ModuleType("weasyprint")
_FAKE_WEASYPRINT.HTML = MagicMock()  # type: ignore[attr-defined]

sys.modules.setdefault("weasyprint", _FAKE_WEASYPRINT)

from trace_viewer.export.pdf_exporter import (  # noqa: E402
    PDFExporter,
    _escape,
    _format_duration,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "version": "1.0.0",
        "tool_version": "0.2.0",
        "test_name": "Login Should Work",
        "suite_name": "Authentication",
        "start_time": "2026-01-20T06:16:46Z",
        "end_time": "2026-01-20T06:16:50Z",
        "duration_ms": 4000,
        "status": "PASS",
        "message": "",
        "keywords_count": 2,
        "capture_mode": "full",
    }
    base.update(overrides)
    return base


def _make_keyword(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "index": 1,
        "name": "Go To",
        "library": "SeleniumLibrary",
        "type": "KEYWORD",
        "args": ["https://example.com"],
        "assign": [],
        "start_time": "2026-01-20T06:16:46Z",
        "end_time": "2026-01-20T06:16:47Z",
        "duration_ms": 500,
        "status": "PASS",
        "message": "",
        "parent_keyword": None,
        "level": 1,
        "folder": "001_go_to",
        "has_screenshot": False,
        "has_variables": False,
        "screenshot": None,
        "variables": {},
    }
    base.update(overrides)
    return base


def _minimal_png() -> bytes:
    """Return a 1-pixel PNG for screenshot embedding tests."""
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
    )


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def exporter() -> PDFExporter:
    """PDFExporter instance with weasyprint stubbed out."""
    instance = PDFExporter.__new__(PDFExporter)
    instance._weasyprint = _FAKE_WEASYPRINT  # type: ignore[attr-defined]
    return instance


# ---------------------------------------------------------------------------
# Tests: _escape
# ---------------------------------------------------------------------------


class TestEscape:
    """Tests for the _escape() HTML-escaping helper."""

    def test_ampersand(self) -> None:
        assert _escape("a & b") == "a &amp; b"

    def test_less_than(self) -> None:
        assert _escape("<tag>") == "&lt;tag&gt;"

    def test_greater_than(self) -> None:
        assert _escape("a > b") == "a &gt; b"

    def test_double_quote(self) -> None:
        assert _escape('say "hello"') == "say &quot;hello&quot;"

    def test_single_quote(self) -> None:
        assert _escape("it's") == "it&#x27;s"

    def test_script_injection(self) -> None:
        assert _escape("<script>alert('xss')</script>") == (
            "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
        )

    def test_plain_text_unchanged(self) -> None:
        assert _escape("hello world 123") == "hello world 123"

    def test_empty_string(self) -> None:
        assert _escape("") == ""


# ---------------------------------------------------------------------------
# Tests: _format_duration
# ---------------------------------------------------------------------------


class TestFormatDuration:
    """Tests for the _format_duration() duration formatting helper."""

    def test_zero(self) -> None:
        assert _format_duration(0) == "0 ms"

    def test_sub_second(self) -> None:
        assert _format_duration(850) == "850 ms"

    def test_exactly_one_second(self) -> None:
        assert _format_duration(1000) == "1.0 s"

    def test_under_one_minute(self) -> None:
        assert _format_duration(12345) == "12.3 s"

    def test_exactly_one_minute(self) -> None:
        assert _format_duration(60000) == "1m 0s"

    def test_over_one_minute(self) -> None:
        assert _format_duration(125000) == "2m 5s"

    def test_float_input_truncated(self) -> None:
        assert _format_duration(500.7) == "500 ms"


# ---------------------------------------------------------------------------
# Tests: PDFExporter.__init__
# ---------------------------------------------------------------------------


class TestPDFExporterInit:
    """Tests for the ImportError guard in PDFExporter.__init__."""

    def test_raises_import_error_when_weasyprint_missing(self) -> None:
        with patch.dict(sys.modules, {"weasyprint": None}), pytest.raises(ImportError) as exc_info:  # type: ignore[dict-item]
            PDFExporter()
        message = str(exc_info.value)
        assert "weasyprint>=60.0" in message
        assert "pip install" in message

    def test_init_succeeds_with_weasyprint_available(self, exporter: PDFExporter) -> None:
        assert exporter._weasyprint is _FAKE_WEASYPRINT  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Tests: _generate_report_html
# ---------------------------------------------------------------------------


class TestGenerateReportHtml:
    """Tests for _generate_report_html()."""

    def test_returns_valid_html_skeleton(self, exporter: PDFExporter, tmp_path: Path) -> None:
        html = exporter._generate_report_html(_make_manifest(), [], tmp_path, False)
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "<head>" in html
        assert "<body>" in html

    def test_cover_contains_test_name(self, exporter: PDFExporter, tmp_path: Path) -> None:
        html = exporter._generate_report_html(
            _make_manifest(test_name="My Awesome Test"), [], tmp_path, False
        )
        assert "My Awesome Test" in html

    def test_cover_contains_suite_name(self, exporter: PDFExporter, tmp_path: Path) -> None:
        html = exporter._generate_report_html(
            _make_manifest(suite_name="Core Suite"), [], tmp_path, False
        )
        assert "Core Suite" in html

    def test_cover_pass_colour(self, exporter: PDFExporter, tmp_path: Path) -> None:
        html = exporter._generate_report_html(_make_manifest(status="PASS"), [], tmp_path, False)
        assert "#2e7d32" in html

    def test_cover_fail_colour(self, exporter: PDFExporter, tmp_path: Path) -> None:
        html = exporter._generate_report_html(_make_manifest(status="FAIL"), [], tmp_path, False)
        assert "#c62828" in html

    def test_empty_keywords_shows_placeholder(self, exporter: PDFExporter, tmp_path: Path) -> None:
        html = exporter._generate_report_html(_make_manifest(), [], tmp_path, False)
        assert "No keywords were captured" in html

    def test_keyword_section_present(self, exporter: PDFExporter, tmp_path: Path) -> None:
        html = exporter._generate_report_html(
            _make_manifest(), [_make_keyword(name="Open Browser")], tmp_path, False
        )
        assert "Open Browser" in html
        assert "kw-section" in html

    def test_html_escaping_in_test_name(self, exporter: PDFExporter, tmp_path: Path) -> None:
        html = exporter._generate_report_html(
            _make_manifest(test_name="<Test> & 'Suite'"), [], tmp_path, False
        )
        assert "<Test>" not in html
        assert "&lt;Test&gt;" in html


# ---------------------------------------------------------------------------
# Tests: _build_cover_html
# ---------------------------------------------------------------------------


class TestBuildCoverHtml:
    """Tests for the cover-page HTML fragment builder."""

    def _cover(self, exporter: PDFExporter, **kwargs: Any) -> str:
        defaults = {
            "test_name": "T",
            "suite_name": "S",
            "status": "PASS",
            "status_colour": "#2e7d32",
            "start_time": "2026-01-01",
            "duration_text": "1.0 s",
            "keywords_count": 3,
            "tool_version": "0.2.0",
        }
        defaults.update(kwargs)
        return exporter._build_cover_html(**defaults)  # type: ignore[arg-type]

    def test_tool_version_included(self, exporter: PDFExporter) -> None:
        assert "0.2.0" in self._cover(exporter)

    def test_suite_present_when_non_empty(self, exporter: PDFExporter) -> None:
        html = self._cover(exporter, suite_name="My Suite")
        assert "My Suite" in html

    def test_suite_absent_when_empty(self, exporter: PDFExporter) -> None:
        html = self._cover(exporter, suite_name="")
        assert "cover__suite" not in html

    def test_keywords_count_present(self, exporter: PDFExporter) -> None:
        assert "42" in self._cover(exporter, keywords_count=42)


# ---------------------------------------------------------------------------
# Tests: _build_keyword_html
# ---------------------------------------------------------------------------


class TestBuildKeywordHtml:
    """Tests for keyword section HTML fragment builder."""

    def test_keyword_name_in_output(self, exporter: PDFExporter, tmp_path: Path) -> None:
        html = exporter._build_keyword_html(
            _make_keyword(name="Verify Title"), tmp_path, screenshots_only=False
        )
        assert "Verify Title" in html

    def test_args_displayed(self, exporter: PDFExporter, tmp_path: Path) -> None:
        html = exporter._build_keyword_html(
            _make_keyword(args=["https://example.com"]), tmp_path, screenshots_only=False
        )
        assert "https://example.com" in html

    def test_no_args_fragment_absent(self, exporter: PDFExporter, tmp_path: Path) -> None:
        html = exporter._build_keyword_html(
            _make_keyword(args=[]), tmp_path, screenshots_only=False
        )
        assert "Args:" not in html

    def test_fail_message_shown(self, exporter: PDFExporter, tmp_path: Path) -> None:
        html = exporter._build_keyword_html(
            _make_keyword(status="FAIL", message="Element not found"),
            tmp_path,
            screenshots_only=False,
        )
        assert "Element not found" in html

    def test_pass_message_not_shown_as_error(self, exporter: PDFExporter, tmp_path: Path) -> None:
        html = exporter._build_keyword_html(
            _make_keyword(status="PASS", message="some text"),
            tmp_path,
            screenshots_only=False,
        )
        assert "Error:" not in html

    def test_variables_present_in_full_mode(self, exporter: PDFExporter, tmp_path: Path) -> None:
        kw = _make_keyword(variables={"URL": "https://example.com"})
        html = exporter._build_keyword_html(kw, tmp_path, screenshots_only=False)
        assert "vars-table" in html

    def test_variables_absent_in_screenshots_only(
        self, exporter: PDFExporter, tmp_path: Path
    ) -> None:
        kw = _make_keyword(variables={"URL": "https://example.com"})
        html = exporter._build_keyword_html(kw, tmp_path, screenshots_only=True)
        assert "vars-table" not in html

    def test_index_zero_padded(self, exporter: PDFExporter, tmp_path: Path) -> None:
        html = exporter._build_keyword_html(
            _make_keyword(index=7), tmp_path, screenshots_only=False
        )
        assert "#007" in html


# ---------------------------------------------------------------------------
# Tests: _build_screenshot_html
# ---------------------------------------------------------------------------


class TestBuildScreenshotHtml:
    """Tests for screenshot base64 embedding."""

    def test_no_screenshot_shows_placeholder(self, exporter: PDFExporter, tmp_path: Path) -> None:
        kw = _make_keyword(screenshot=None, has_screenshot=False)
        html = exporter._build_screenshot_html(kw, tmp_path)
        assert "No screenshot available" in html
        assert "<img" not in html

    def test_screenshot_embedded_as_base64(self, exporter: PDFExporter, tmp_path: Path) -> None:
        ss_dir = tmp_path / "keywords" / "001_go_to"
        ss_dir.mkdir(parents=True)
        (ss_dir / "screenshot.png").write_bytes(_minimal_png())

        kw = _make_keyword(
            screenshot="keywords/001_go_to/screenshot.png",
            folder="001_go_to",
            has_screenshot=True,
        )
        html = exporter._build_screenshot_html(kw, tmp_path)
        assert "data:image/png;base64," in html
        assert "<img" in html

    def test_screenshot_resolved_via_has_screenshot_flag(
        self, exporter: PDFExporter, tmp_path: Path
    ) -> None:
        ss_dir = tmp_path / "keywords" / "002_input_text"
        ss_dir.mkdir(parents=True)
        (ss_dir / "screenshot.png").write_bytes(_minimal_png())

        kw = _make_keyword(
            index=2,
            screenshot=None,
            folder="002_input_text",
            has_screenshot=True,
        )
        html = exporter._build_screenshot_html(kw, tmp_path)
        assert "data:image/png;base64," in html

    def test_unreadable_screenshot_returns_placeholder(
        self, exporter: PDFExporter, tmp_path: Path
    ) -> None:
        ss_dir = tmp_path / "keywords" / "001_go_to"
        ss_dir.mkdir(parents=True)
        (ss_dir / "screenshot.png").write_bytes(b"valid bytes")

        kw = _make_keyword(
            screenshot="keywords/001_go_to/screenshot.png",
            folder="001_go_to",
            has_screenshot=True,
        )
        with patch.object(Path, "read_bytes", side_effect=OSError("permission denied")):
            html = exporter._build_screenshot_html(kw, tmp_path)
        assert "could not be loaded" in html


# ---------------------------------------------------------------------------
# Tests: _build_variables_html
# ---------------------------------------------------------------------------


class TestBuildVariablesHtml:
    """Tests for the variables table static builder."""

    def test_empty_dict_returns_empty_string(self) -> None:
        assert PDFExporter._build_variables_html({}) == ""

    def test_flat_variables_rendered_as_table(self) -> None:
        html = PDFExporter._build_variables_html({"URL": "https://example.com"})
        assert "URL" in html
        assert "https://example.com" in html
        assert "vars-table" in html

    def test_namespaced_variables_render_namespace_headers(self) -> None:
        variables = {
            "scalar": {"URL": "https://example.com", "ENV": "prod"},
            "list": {"BROWSERS": "['chrome']"},
        }
        html = PDFExporter._build_variables_html(variables)
        assert "scalar" in html
        assert "list" in html
        assert "URL" in html
        assert "BROWSERS" in html

    def test_values_html_escaped(self) -> None:
        html = PDFExporter._build_variables_html({"key": "<value> & 'test'"})
        assert "<value>" not in html
        assert "&lt;value&gt;" in html

    def test_empty_namespace_dict_skipped(self) -> None:
        variables: dict[str, Any] = {"scalar": {}, "list": {"ITEM": "value"}}
        html = PDFExporter._build_variables_html(variables)
        assert "ITEM" in html


# ---------------------------------------------------------------------------
# Tests: _load_keywords
# ---------------------------------------------------------------------------


class TestLoadKeywords:
    """Tests for keyword directory loading."""

    def test_no_keywords_dir_returns_empty(self, exporter: PDFExporter, tmp_path: Path) -> None:
        assert exporter._load_keywords(tmp_path) == []

    def test_empty_keywords_dir_returns_empty(self, exporter: PDFExporter, tmp_path: Path) -> None:
        (tmp_path / "keywords").mkdir()
        assert exporter._load_keywords(tmp_path) == []

    def test_loads_keyword_metadata(self, exporter: PDFExporter, tmp_path: Path) -> None:
        kw_dir = tmp_path / "keywords" / "001_go_to"
        kw_dir.mkdir(parents=True)
        (kw_dir / "metadata.json").write_text(
            json.dumps(_make_keyword(name="Go To", index=1)), encoding="utf-8"
        )
        result = exporter._load_keywords(tmp_path)
        assert len(result) == 1
        assert result[0]["name"] == "Go To"

    def test_loads_variables_alongside_metadata(
        self, exporter: PDFExporter, tmp_path: Path
    ) -> None:
        kw_dir = tmp_path / "keywords" / "001_go_to"
        kw_dir.mkdir(parents=True)
        (kw_dir / "metadata.json").write_text(json.dumps(_make_keyword()), encoding="utf-8")
        variables = {"scalar": {"URL": "https://example.com"}}
        (kw_dir / "variables.json").write_text(json.dumps(variables), encoding="utf-8")
        result = exporter._load_keywords(tmp_path)
        assert result[0]["variables"] == variables

    def test_invalid_metadata_json_skipped(self, exporter: PDFExporter, tmp_path: Path) -> None:
        kw_dir = tmp_path / "keywords" / "001_bad"
        kw_dir.mkdir(parents=True)
        (kw_dir / "metadata.json").write_text("not-valid-json", encoding="utf-8")
        assert exporter._load_keywords(tmp_path) == []

    def test_invalid_variables_json_defaults_to_empty(
        self, exporter: PDFExporter, tmp_path: Path
    ) -> None:
        kw_dir = tmp_path / "keywords" / "001_go_to"
        kw_dir.mkdir(parents=True)
        (kw_dir / "metadata.json").write_text(json.dumps(_make_keyword()), encoding="utf-8")
        (kw_dir / "variables.json").write_text("{{bad json}}", encoding="utf-8")
        result = exporter._load_keywords(tmp_path)
        assert result[0]["variables"] == {}

    def test_keywords_sorted_by_directory_name(self, exporter: PDFExporter, tmp_path: Path) -> None:
        for i, name in [(3, "003_log"), (1, "001_go_to"), (2, "002_title")]:
            kw_dir = tmp_path / "keywords" / name
            kw_dir.mkdir(parents=True)
            (kw_dir / "metadata.json").write_text(
                json.dumps(_make_keyword(index=i, name=name)), encoding="utf-8"
            )
        result = exporter._load_keywords(tmp_path)
        assert [kw["index"] for kw in result] == [1, 2, 3]

    def test_screenshot_path_set_when_file_exists(
        self, exporter: PDFExporter, tmp_path: Path
    ) -> None:
        kw_dir = tmp_path / "keywords" / "001_go_to"
        kw_dir.mkdir(parents=True)
        (kw_dir / "metadata.json").write_text(json.dumps(_make_keyword()), encoding="utf-8")
        (kw_dir / "screenshot.png").write_bytes(_minimal_png())
        result = exporter._load_keywords(tmp_path)
        assert result[0]["screenshot"] == "keywords/001_go_to/screenshot.png"

    def test_screenshot_none_when_file_absent(self, exporter: PDFExporter, tmp_path: Path) -> None:
        kw_dir = tmp_path / "keywords" / "001_go_to"
        kw_dir.mkdir(parents=True)
        (kw_dir / "metadata.json").write_text(json.dumps(_make_keyword()), encoding="utf-8")
        result = exporter._load_keywords(tmp_path)
        assert result[0]["screenshot"] is None


# ---------------------------------------------------------------------------
# Tests: export() – weasyprint.HTML write_pdf mocked
# ---------------------------------------------------------------------------


class TestExport:
    """Tests for the public export() method."""

    def _setup_trace(self, tmp_path: Path) -> None:
        (tmp_path / "manifest.json").write_text(json.dumps(_make_manifest()), encoding="utf-8")
        kw_dir = tmp_path / "keywords" / "001_go_to"
        kw_dir.mkdir(parents=True)
        (kw_dir / "metadata.json").write_text(
            json.dumps(_make_keyword(name="Go To", index=1)), encoding="utf-8"
        )

    def _stub_weasyprint(self, exporter: PDFExporter, pdf_bytes: bytes = b"%PDF") -> None:
        fake_html_class = MagicMock()
        fake_html_class.return_value.write_pdf.return_value = pdf_bytes
        exporter._weasyprint = MagicMock()  # type: ignore[attr-defined]
        exporter._weasyprint.HTML = fake_html_class  # type: ignore[attr-defined]

    def test_default_output_is_report_pdf(self, exporter: PDFExporter, tmp_path: Path) -> None:
        self._setup_trace(tmp_path)
        self._stub_weasyprint(exporter)
        result = exporter.export(tmp_path)
        assert result == tmp_path / "report.pdf"
        assert result.exists()

    def test_custom_output_path_honoured(self, exporter: PDFExporter, tmp_path: Path) -> None:
        self._setup_trace(tmp_path)
        self._stub_weasyprint(exporter)
        custom = tmp_path / "custom.pdf"
        result = exporter.export(tmp_path, output=custom)
        assert result == custom
        assert result.exists()

    def test_raises_for_nonexistent_trace_dir(self, exporter: PDFExporter, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Trace directory does not exist"):
            exporter.export(tmp_path / "ghost")

    def test_raises_for_missing_manifest(self, exporter: PDFExporter, tmp_path: Path) -> None:
        (tmp_path / "keywords").mkdir()
        with pytest.raises(FileNotFoundError, match="manifest.json not found"):
            exporter.export(tmp_path)

    def test_written_bytes_match_weasyprint_output(
        self, exporter: PDFExporter, tmp_path: Path
    ) -> None:
        self._setup_trace(tmp_path)
        expected = b"%PDF-1.4 content"
        self._stub_weasyprint(exporter, pdf_bytes=expected)
        output = exporter.export(tmp_path)
        assert output.read_bytes() == expected

    def test_empty_trace_no_crash(self, exporter: PDFExporter, tmp_path: Path) -> None:
        (tmp_path / "manifest.json").write_text(
            json.dumps(_make_manifest(keywords_count=0)), encoding="utf-8"
        )
        self._stub_weasyprint(exporter)
        result = exporter.export(tmp_path)
        assert result.exists()
