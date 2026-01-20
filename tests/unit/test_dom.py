"""Unit tests for the DOMCapture module.

These tests use mocks to simulate Robot Framework and Selenium environments
without requiring an actual browser.
"""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchWindowException,
    WebDriverException,
)

from trace_viewer.capture.dom import DOMCapture


class TestDOMCapture:
    """Test suite for DOMCapture class."""

    @pytest.fixture
    def capture(self) -> DOMCapture:
        """Create a fresh DOMCapture instance for each test."""
        return DOMCapture()

    @pytest.fixture
    def mock_builtin(self) -> MagicMock:
        """Create a mock BuiltIn library."""
        return MagicMock()

    @pytest.fixture
    def mock_selenium_library(self) -> MagicMock:
        """Create a mock SeleniumLibrary with a mock driver."""
        selenium_lib = MagicMock()
        mock_driver = MagicMock()
        mock_driver.execute_script.return_value = (
            "<html><head></head><body><h1>Test Page</h1></body></html>"
        )
        type(selenium_lib).driver = PropertyMock(return_value=mock_driver)
        return selenium_lib

    @pytest.fixture
    def mock_selenium_library_with_scripts(self) -> MagicMock:
        """Create a mock SeleniumLibrary returning HTML with script tags."""
        selenium_lib = MagicMock()
        mock_driver = MagicMock()
        mock_driver.execute_script.return_value = """<html>
<head>
<script>alert('xss')</script>
<script type="text/javascript">
    console.log('dangerous');
</script>
</head>
<body>
<h1>Test Page</h1>
<script src="https://evil.com/script.js"></script>
</body>
</html>"""
        type(selenium_lib).driver = PropertyMock(return_value=mock_driver)
        return selenium_lib

    # =========================================================================
    # Basic functionality tests
    # =========================================================================

    def test_capture_returns_none_when_no_selenium_library(
        self, capture: DOMCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that capture returns None when SeleniumLibrary is not loaded."""
        mock_builtin.get_library_instance.side_effect = RuntimeError(
            "No library 'SeleniumLibrary' found."
        )

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert result is None
        mock_builtin.get_library_instance.assert_called()

    def test_capture_returns_none_when_no_browser_open(
        self, capture: DOMCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that capture returns None when no browser window is open."""
        mock_selenium_library = MagicMock()
        type(mock_selenium_library).driver = PropertyMock(side_effect=Exception("No browser open"))
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert result is None

    def test_capture_returns_html_when_browser_available(
        self,
        capture: DOMCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that capture returns HTML when browser is available."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert result is not None
        assert "<html>" in result
        assert "<h1>Test Page</h1>" in result
        mock_selenium_library.driver.execute_script.assert_called_once_with(
            "return document.documentElement.outerHTML;"
        )

    # =========================================================================
    # HTML sanitization tests
    # =========================================================================

    def test_sanitize_html_removes_script_tags(self, capture: DOMCapture) -> None:
        """Test that sanitize_html removes all script tags."""
        html = '<html><script>alert("xss")</script><body>Hello</body></html>'
        result = capture.sanitize_html(html)

        assert "<script>" not in result
        assert "</script>" not in result
        assert "alert" not in result
        assert "<body>Hello</body>" in result

    def test_sanitize_html_removes_script_tags_with_attributes(self, capture: DOMCapture) -> None:
        """Test that sanitize_html removes script tags with attributes."""
        html = '<html><script type="text/javascript">code()</script><body></body></html>'
        result = capture.sanitize_html(html)

        assert "<script" not in result
        assert "code()" not in result

    def test_sanitize_html_removes_script_tags_with_src(self, capture: DOMCapture) -> None:
        """Test that sanitize_html removes script tags with src attribute."""
        html = '<html><script src="https://evil.com/script.js"></script><body></body></html>'
        result = capture.sanitize_html(html)

        assert "<script" not in result
        assert "evil.com" not in result

    def test_sanitize_html_removes_self_closing_script_tags(self, capture: DOMCapture) -> None:
        """Test that sanitize_html removes self-closing script tags."""
        html = '<html><script src="script.js" /><body></body></html>'
        result = capture.sanitize_html(html)

        assert "<script" not in result

    def test_sanitize_html_removes_multiple_script_tags(self, capture: DOMCapture) -> None:
        """Test that sanitize_html removes multiple script tags."""
        html = """<html>
<script>first()</script>
<script>second()</script>
<body>Content</body>
<script>third()</script>
</html>"""
        result = capture.sanitize_html(html)

        assert "<script" not in result
        assert "first()" not in result
        assert "second()" not in result
        assert "third()" not in result
        assert "<body>Content</body>" in result

    def test_sanitize_html_handles_multiline_scripts(self, capture: DOMCapture) -> None:
        """Test that sanitize_html handles multiline script content."""
        html = """<html>
<script>
    function doSomething() {
        console.log('test');
    }
    doSomething();
</script>
<body></body>
</html>"""
        result = capture.sanitize_html(html)

        assert "<script" not in result
        assert "doSomething" not in result

    def test_sanitize_html_case_insensitive(self, capture: DOMCapture) -> None:
        """Test that sanitize_html is case insensitive."""
        html = "<html><SCRIPT>code()</SCRIPT><Script>more()</Script><body></body></html>"
        result = capture.sanitize_html(html)

        assert "script" not in result.lower()
        assert "code()" not in result
        assert "more()" not in result

    def test_sanitize_html_handles_empty_string(self, capture: DOMCapture) -> None:
        """Test that sanitize_html handles empty string."""
        result = capture.sanitize_html("")
        assert result == ""

    def test_sanitize_html_handles_none_like_empty(self, capture: DOMCapture) -> None:
        """Test that sanitize_html returns empty string for None-like input."""
        result = capture.sanitize_html("")
        assert result == ""

    def test_capture_sanitizes_html_automatically(
        self,
        capture: DOMCapture,
        mock_builtin: MagicMock,
        mock_selenium_library_with_scripts: MagicMock,
    ) -> None:
        """Test that capture automatically sanitizes HTML."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library_with_scripts

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert result is not None
        assert "<script" not in result
        assert "<h1>Test Page</h1>" in result

    # =========================================================================
    # WebDriver exception handling tests
    # =========================================================================

    @pytest.mark.parametrize(
        "exception_class",
        [
            WebDriverException,
            NoSuchWindowException,
            InvalidSessionIdException,
        ],
    )
    def test_capture_handles_webdriver_exception(
        self,
        capture: DOMCapture,
        mock_builtin: MagicMock,
        exception_class: type,
    ) -> None:
        """Test that capture handles WebDriver exceptions gracefully."""
        mock_selenium_library = MagicMock()
        mock_driver = MagicMock()
        mock_driver.execute_script.side_effect = exception_class("Browser closed")
        type(mock_selenium_library).driver = PropertyMock(return_value=mock_driver)
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert result is None

    def test_capture_handles_generic_exception(
        self,
        capture: DOMCapture,
        mock_builtin: MagicMock,
    ) -> None:
        """Test that capture handles generic exceptions gracefully."""
        mock_selenium_library = MagicMock()
        mock_driver = MagicMock()
        mock_driver.execute_script.side_effect = Exception("Unexpected error")
        type(mock_selenium_library).driver = PropertyMock(return_value=mock_driver)
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert result is None

    # =========================================================================
    # Browser availability tests
    # =========================================================================

    def test_is_browser_available_returns_true_when_driver_exists(
        self,
        capture: DOMCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that is_browser_available returns True when a driver is available."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.is_browser_available()

        assert result is True

    def test_is_browser_available_returns_false_when_no_driver(
        self, capture: DOMCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that is_browser_available returns False when no driver is available."""
        mock_builtin.get_library_instance.side_effect = RuntimeError(
            "No library 'SeleniumLibrary' found."
        )

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.is_browser_available()

        assert result is False

    # =========================================================================
    # Library access tests
    # =========================================================================

    def test_get_selenium_library_returns_library_instance(
        self,
        capture: DOMCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that get_selenium_library returns the library instance."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.get_selenium_library()

        assert result is mock_selenium_library

    def test_get_selenium_library_returns_none_when_not_loaded(
        self, capture: DOMCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that get_selenium_library returns None when library not loaded."""
        mock_builtin.get_library_instance.side_effect = RuntimeError(
            "No library 'SeleniumLibrary' found."
        )

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.get_selenium_library()

        assert result is None

    def test_get_driver_returns_driver_instance(
        self,
        capture: DOMCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that get_driver returns the WebDriver instance."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.get_driver()

        assert result is mock_selenium_library.driver

    def test_get_selenium_driver_returns_driver_instance(
        self,
        capture: DOMCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that get_selenium_driver returns the WebDriver instance."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.get_selenium_driver()

        assert result is mock_selenium_library.driver

    # =========================================================================
    # Builtin property tests
    # =========================================================================

    def test_builtin_property_lazy_loads(self, capture: DOMCapture) -> None:
        """Test that the builtin property lazy-loads the BuiltIn instance."""
        assert capture._builtin is None

        with patch("trace_viewer.capture.dom.BuiltIn") as mock_builtin_class:
            mock_instance = MagicMock()
            mock_builtin_class.return_value = mock_instance

            # First access should create the instance
            result1 = capture.builtin
            assert result1 is mock_instance
            mock_builtin_class.assert_called_once()

            # Second access should return the same instance
            result2 = capture.builtin
            assert result2 is mock_instance
            # Should still be called only once (lazy loading)
            mock_builtin_class.assert_called_once()

    # =========================================================================
    # File writing tests
    # =========================================================================

    def test_capture_to_file_writes_html(
        self,
        capture: DOMCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
        tmp_path,
    ) -> None:
        """Test that capture_to_file writes HTML to file."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        filepath = tmp_path / "dom.html"

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_to_file(str(filepath))

        assert result is True
        assert filepath.exists()
        content = filepath.read_text(encoding="utf-8")
        assert "<html>" in content

    def test_capture_to_file_returns_false_when_no_browser(
        self,
        capture: DOMCapture,
        mock_builtin: MagicMock,
        tmp_path,
    ) -> None:
        """Test that capture_to_file returns False when no browser available."""
        mock_builtin.get_library_instance.side_effect = RuntimeError(
            "No library 'SeleniumLibrary' found."
        )

        filepath = tmp_path / "dom.html"

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_to_file(str(filepath))

        assert result is False
        assert not filepath.exists()

    def test_capture_to_file_returns_false_on_write_error(
        self,
        capture: DOMCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that capture_to_file returns False on file write error."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        # Use an invalid path that will fail to write
        filepath = "/nonexistent/directory/dom.html"

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_to_file(filepath)

        assert result is False

    # =========================================================================
    # Browser Library (Playwright) tests
    # =========================================================================

    def test_get_browser_library_returns_library_instance(
        self, capture: DOMCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that get_browser_library returns the library instance."""
        mock_browser_lib = MagicMock()
        mock_builtin.get_library_instance.return_value = mock_browser_lib

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.get_browser_library()

        assert result is mock_browser_lib
        mock_builtin.get_library_instance.assert_called_with("Browser")

    def test_get_browser_library_returns_none_when_not_loaded(
        self, capture: DOMCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that get_browser_library returns None when library not loaded."""
        mock_builtin.get_library_instance.side_effect = RuntimeError("No library 'Browser' found.")

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.get_browser_library()

        assert result is None

    def test_is_browser_library_available_returns_false_when_no_library(
        self, capture: DOMCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that is_browser_library_available returns False when not loaded."""
        mock_builtin.get_library_instance.side_effect = RuntimeError("No library 'Browser' found.")

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.is_browser_library_available()

        assert result is False

    def test_is_browser_library_available_returns_false_when_no_page(
        self, capture: DOMCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that is_browser_library_available returns False when no page."""
        mock_browser_lib = MagicMock()
        mock_browser_lib._playwright_state = None
        mock_browser_lib.playwright = None
        mock_builtin.get_library_instance.return_value = mock_browser_lib

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.is_browser_library_available()

        assert result is False

    def test_capture_from_browser_library_returns_none_when_no_library(
        self, capture: DOMCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that capture_from_browser_library returns None when not loaded."""
        mock_builtin.get_library_instance.side_effect = RuntimeError("No library 'Browser' found.")

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_from_browser_library()

        assert result is None

    def test_capture_from_browser_library_returns_sanitized_html(
        self, capture: DOMCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that capture_from_browser_library returns sanitized HTML."""
        mock_browser_lib = MagicMock()
        mock_page = MagicMock()
        mock_page.content.return_value = "<html><script>bad()</script><body>Good</body></html>"
        mock_catalog = MagicMock()
        mock_catalog.get_current_page.return_value = mock_page
        mock_browser_lib._playwright_state = mock_catalog
        mock_builtin.get_library_instance.return_value = mock_browser_lib

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_from_browser_library()

        assert result is not None
        assert "<script" not in result
        assert "<body>Good</body>" in result

    def test_capture_prefers_browser_library_over_selenium(
        self, capture: DOMCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that capture prefers Browser Library over SeleniumLibrary."""
        # Set up Browser Library mock
        mock_browser_lib = MagicMock()
        mock_page = MagicMock()
        mock_page.content.return_value = "<html><body>From Playwright</body></html>"
        mock_catalog = MagicMock()
        mock_catalog.get_current_page.return_value = mock_page
        mock_browser_lib._playwright_state = mock_catalog

        # Set up Selenium mock
        mock_selenium_lib = MagicMock()
        mock_driver = MagicMock()
        mock_driver.execute_script.return_value = "<html><body>From Selenium</body></html>"
        type(mock_selenium_lib).driver = PropertyMock(return_value=mock_driver)

        def get_library(name):
            if name == "Browser":
                return mock_browser_lib
            elif name == "SeleniumLibrary":
                return mock_selenium_lib
            raise RuntimeError(f"No library '{name}' found.")

        mock_builtin.get_library_instance.side_effect = get_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        # Should use Browser Library (Playwright)
        assert result is not None
        assert "From Playwright" in result


class TestDOMCaptureIntegration:
    """Integration tests for DOMCapture with TraceWriter."""

    def test_dom_snapshot_workflow(self, tmp_path) -> None:
        """Test the complete DOM capture and storage workflow."""
        from trace_viewer.storage.trace_writer import TraceWriter

        # Create a trace writer
        writer = TraceWriter(str(tmp_path))
        writer.create_trace("Test")
        keyword_dir = writer.create_keyword_dir("Click Button")

        # Simulate DOM capture
        html_content = "<html><body><h1>Test Page</h1></body></html>"
        writer.write_dom_snapshot(keyword_dir, html_content)

        # Verify the file was created
        dom_path = keyword_dir / "dom.html"
        assert dom_path.exists()
        assert dom_path.read_text(encoding="utf-8") == html_content
