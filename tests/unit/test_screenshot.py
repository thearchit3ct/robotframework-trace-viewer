"""Unit tests for the ScreenshotCapture module.

These tests use mocks to simulate Robot Framework and Selenium environments
without requiring an actual browser. Tests cover both SeleniumLibrary and
Browser Library (Playwright) support.
"""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchWindowException,
    WebDriverException,
)

from trace_viewer.capture.screenshot import ScreenshotCapture


class TestScreenshotCapture:
    """Test suite for ScreenshotCapture class."""

    @pytest.fixture
    def capture(self) -> ScreenshotCapture:
        """Create a fresh ScreenshotCapture instance for each test."""
        return ScreenshotCapture()

    @pytest.fixture
    def mock_builtin(self) -> MagicMock:
        """Create a mock BuiltIn library."""
        return MagicMock()

    @pytest.fixture
    def mock_selenium_library(self) -> MagicMock:
        """Create a mock SeleniumLibrary with a mock driver."""
        selenium_lib = MagicMock()
        mock_driver = MagicMock()
        mock_driver.get_screenshot_as_png.return_value = b"\x89PNG\r\n\x1a\n"
        type(selenium_lib).driver = PropertyMock(return_value=mock_driver)
        return selenium_lib

    @pytest.fixture
    def mock_browser_library(self) -> MagicMock:
        """Create a mock Browser Library with a mock Playwright page."""
        browser_lib = MagicMock()
        mock_page = MagicMock()
        mock_page.screenshot.return_value = b"\x89PNG\r\n\x1a\nPlaywright"
        mock_catalog = MagicMock()
        mock_catalog.get_current_page.return_value = mock_page
        browser_lib._playwright_state = mock_catalog
        return browser_lib

    def test_capture_returns_none_when_no_libraries_available(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that capture returns None when no browser libraries are loaded."""
        mock_builtin.get_library_instance.side_effect = RuntimeError("No library found.")

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert result is None

    def test_capture_returns_none_when_no_browser_open(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that capture returns None when no browser window is open."""
        mock_selenium_library = MagicMock()
        type(mock_selenium_library).driver = PropertyMock(side_effect=Exception("No browser open"))

        def get_library_side_effect(name: str) -> MagicMock:
            if name == "Browser":
                raise RuntimeError("No library 'Browser' found.")
            return mock_selenium_library

        mock_builtin.get_library_instance.side_effect = get_library_side_effect

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert result is None

    def test_capture_returns_png_data_from_selenium_when_available(
        self,
        capture: ScreenshotCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that capture returns PNG data from SeleniumLibrary when available."""

        def get_library_side_effect(name: str) -> MagicMock:
            if name == "Browser":
                raise RuntimeError("No library 'Browser' found.")
            return mock_selenium_library

        mock_builtin.get_library_instance.side_effect = get_library_side_effect

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert result is not None
        assert isinstance(result, bytes)
        assert result.startswith(b"\x89PNG")
        mock_selenium_library.driver.get_screenshot_as_png.assert_called_once()

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
        capture: ScreenshotCapture,
        mock_builtin: MagicMock,
        exception_class: type,
    ) -> None:
        """Test that capture handles WebDriver exceptions gracefully."""
        mock_selenium_library = MagicMock()
        mock_driver = MagicMock()
        mock_driver.get_screenshot_as_png.side_effect = exception_class("Browser closed")
        type(mock_selenium_library).driver = PropertyMock(return_value=mock_driver)

        def get_library_side_effect(name: str) -> MagicMock:
            if name == "Browser":
                raise RuntimeError("No library 'Browser' found.")
            return mock_selenium_library

        mock_builtin.get_library_instance.side_effect = get_library_side_effect

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert result is None

    def test_capture_to_file_saves_png(
        self,
        capture: ScreenshotCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Test that capture_to_file saves PNG data to the specified file."""

        def get_library_side_effect(name: str) -> MagicMock:
            if name == "Browser":
                raise RuntimeError("No library 'Browser' found.")
            return mock_selenium_library

        mock_builtin.get_library_instance.side_effect = get_library_side_effect
        filepath = str(tmp_path / "screenshot.png")

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_to_file(filepath)

        assert result is True
        with open(filepath, "rb") as f:
            content = f.read()
        assert content.startswith(b"\x89PNG")

    def test_capture_to_file_returns_false_when_capture_fails(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Test that capture_to_file returns False when capture fails."""
        mock_builtin.get_library_instance.side_effect = RuntimeError("No library found.")
        filepath = str(tmp_path / "screenshot.png")

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_to_file(filepath)

        assert result is False

    def test_capture_to_file_returns_false_on_io_error(
        self,
        capture: ScreenshotCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that capture_to_file returns False on IOError."""

        def get_library_side_effect(name: str) -> MagicMock:
            if name == "Browser":
                raise RuntimeError("No library 'Browser' found.")
            return mock_selenium_library

        mock_builtin.get_library_instance.side_effect = get_library_side_effect
        invalid_path = "/nonexistent/directory/screenshot.png"

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_to_file(invalid_path)

        assert result is False

    def test_is_browser_available_returns_true_when_selenium_driver_exists(
        self,
        capture: ScreenshotCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that is_browser_available returns True when Selenium driver is available."""

        def get_library_side_effect(name: str) -> MagicMock:
            if name == "Browser":
                raise RuntimeError("No library 'Browser' found.")
            return mock_selenium_library

        mock_builtin.get_library_instance.side_effect = get_library_side_effect

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.is_browser_available()

        assert result is True

    def test_is_browser_available_returns_true_when_browser_library_active(
        self,
        capture: ScreenshotCapture,
        mock_builtin: MagicMock,
        mock_browser_library: MagicMock,
    ) -> None:
        """Test that is_browser_available returns True when Browser Library has active page."""

        def get_library_side_effect(name: str) -> MagicMock:
            if name == "Browser":
                return mock_browser_library
            raise RuntimeError("No library 'SeleniumLibrary' found.")

        mock_builtin.get_library_instance.side_effect = get_library_side_effect

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.is_browser_available()

        assert result is True

    def test_is_browser_available_returns_false_when_no_libraries(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that is_browser_available returns False when no libraries are available."""
        mock_builtin.get_library_instance.side_effect = RuntimeError("No library found.")

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.is_browser_available()

        assert result is False

    def test_get_selenium_library_returns_library_instance(
        self,
        capture: ScreenshotCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that get_selenium_library returns the library instance."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.get_selenium_library()

        assert result is mock_selenium_library

    def test_get_driver_returns_driver_instance(
        self,
        capture: ScreenshotCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that get_driver returns the WebDriver instance."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.get_driver()

        assert result is mock_selenium_library.driver

    def test_builtin_property_lazy_loads(self, capture: ScreenshotCapture) -> None:
        """Test that the builtin property lazy-loads the BuiltIn instance."""
        assert capture._builtin is None

        with patch("trace_viewer.capture.screenshot.BuiltIn") as mock_builtin_class:
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


class TestBrowserLibrarySupport:
    """Test suite for Browser Library (Playwright) support."""

    @pytest.fixture
    def capture(self) -> ScreenshotCapture:
        """Create a fresh ScreenshotCapture instance for each test."""
        return ScreenshotCapture()

    @pytest.fixture
    def mock_builtin(self) -> MagicMock:
        """Create a mock BuiltIn library."""
        return MagicMock()

    @pytest.fixture
    def mock_browser_library(self) -> MagicMock:
        """Create a mock Browser Library with a mock Playwright page."""
        browser_lib = MagicMock()
        mock_page = MagicMock()
        mock_page.screenshot.return_value = b"\x89PNG\r\n\x1a\nPlaywright"
        mock_catalog = MagicMock()
        mock_catalog.get_current_page.return_value = mock_page
        browser_lib._playwright_state = mock_catalog
        return browser_lib

    @pytest.fixture
    def mock_browser_library_with_playwright_attr(self) -> MagicMock:
        """Create a mock Browser Library using 'playwright' attribute."""
        browser_lib = MagicMock()
        mock_page = MagicMock()
        mock_page.screenshot.return_value = b"\x89PNG\r\n\x1a\nPlaywrightAlt"
        mock_catalog = MagicMock()
        mock_catalog.get_current_page.return_value = mock_page
        browser_lib._playwright_state = None
        browser_lib.playwright = mock_catalog
        return browser_lib

    def test_get_browser_library_returns_library_instance(
        self,
        capture: ScreenshotCapture,
        mock_builtin: MagicMock,
        mock_browser_library: MagicMock,
    ) -> None:
        """Test that get_browser_library returns the Browser Library instance."""
        mock_builtin.get_library_instance.return_value = mock_browser_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.get_browser_library()

        assert result is mock_browser_library
        mock_builtin.get_library_instance.assert_called_once_with("Browser")

    def test_get_browser_library_returns_none_when_not_loaded(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that get_browser_library returns None when not loaded."""
        mock_builtin.get_library_instance.side_effect = RuntimeError("No library 'Browser' found.")

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.get_browser_library()

        assert result is None

    def test_is_browser_library_available_returns_true_with_active_page(
        self,
        capture: ScreenshotCapture,
        mock_builtin: MagicMock,
        mock_browser_library: MagicMock,
    ) -> None:
        """Test is_browser_library_available returns True with active page."""
        mock_builtin.get_library_instance.return_value = mock_browser_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.is_browser_library_available()

        assert result is True

    def test_is_browser_library_available_returns_false_without_library(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test is_browser_library_available returns False without library."""
        mock_builtin.get_library_instance.side_effect = RuntimeError("No library 'Browser' found.")

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.is_browser_library_available()

        assert result is False

    def test_is_browser_library_available_returns_false_without_page(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test is_browser_library_available returns False when no page is active."""
        browser_lib = MagicMock()
        mock_catalog = MagicMock()
        mock_catalog.get_current_page.return_value = None
        browser_lib._playwright_state = mock_catalog
        mock_builtin.get_library_instance.return_value = browser_lib

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.is_browser_library_available()

        assert result is False

    def test_capture_from_browser_library_returns_png_data(
        self,
        capture: ScreenshotCapture,
        mock_builtin: MagicMock,
        mock_browser_library: MagicMock,
    ) -> None:
        """Test capture_from_browser_library returns PNG data."""
        mock_builtin.get_library_instance.return_value = mock_browser_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_from_browser_library()

        assert result is not None
        assert isinstance(result, bytes)
        assert result.startswith(b"\x89PNG")
        # Verify screenshot was called with correct params
        mock_browser_library._playwright_state.get_current_page().screenshot.assert_called_once_with(
            type="png"
        )

    def test_capture_from_browser_library_uses_playwright_attr_fallback(
        self,
        capture: ScreenshotCapture,
        mock_builtin: MagicMock,
        mock_browser_library_with_playwright_attr: MagicMock,
    ) -> None:
        """Test capture_from_browser_library uses 'playwright' attribute as fallback."""
        mock_builtin.get_library_instance.return_value = mock_browser_library_with_playwright_attr

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_from_browser_library()

        assert result is not None
        assert isinstance(result, bytes)
        assert result.startswith(b"\x89PNG")

    def test_capture_from_browser_library_returns_none_when_library_unavailable(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test capture_from_browser_library returns None when library is unavailable."""
        mock_builtin.get_library_instance.side_effect = RuntimeError("No library 'Browser' found.")

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_from_browser_library()

        assert result is None

    def test_capture_from_browser_library_returns_none_when_no_page(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test capture_from_browser_library returns None when no page exists."""
        browser_lib = MagicMock()
        mock_catalog = MagicMock()
        mock_catalog.get_current_page.return_value = None
        browser_lib._playwright_state = mock_catalog
        mock_builtin.get_library_instance.return_value = browser_lib

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_from_browser_library()

        assert result is None

    def test_capture_from_browser_library_handles_exception(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test capture_from_browser_library handles exceptions gracefully."""
        browser_lib = MagicMock()
        mock_page = MagicMock()
        mock_page.screenshot.side_effect = Exception("Playwright error")
        mock_catalog = MagicMock()
        mock_catalog.get_current_page.return_value = mock_page
        browser_lib._playwright_state = mock_catalog
        mock_builtin.get_library_instance.return_value = browser_lib

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_from_browser_library()

        assert result is None

    def test_capture_prefers_browser_library_over_selenium(
        self,
        capture: ScreenshotCapture,
        mock_builtin: MagicMock,
        mock_browser_library: MagicMock,
    ) -> None:
        """Test that capture() prefers Browser Library when both are available."""
        mock_selenium_library = MagicMock()
        mock_driver = MagicMock()
        mock_driver.get_screenshot_as_png.return_value = b"\x89PNG\r\n\x1a\nSelenium"
        type(mock_selenium_library).driver = PropertyMock(return_value=mock_driver)

        def get_library_side_effect(name: str) -> MagicMock:
            if name == "Browser":
                return mock_browser_library
            return mock_selenium_library

        mock_builtin.get_library_instance.side_effect = get_library_side_effect

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        # Should get Playwright screenshot, not Selenium
        assert result is not None
        assert b"Playwright" in result
        assert b"Selenium" not in result

    def test_capture_falls_back_to_selenium_when_browser_library_fails(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that capture() falls back to SeleniumLibrary when Browser Library fails."""
        # Browser Library without active page
        browser_lib = MagicMock()
        browser_lib._playwright_state = None
        browser_lib.playwright = None

        mock_selenium_library = MagicMock()
        mock_driver = MagicMock()
        mock_driver.get_screenshot_as_png.return_value = b"\x89PNG\r\n\x1a\nSeleniumFallback"
        type(mock_selenium_library).driver = PropertyMock(return_value=mock_driver)

        def get_library_side_effect(name: str) -> MagicMock:
            if name == "Browser":
                return browser_lib
            return mock_selenium_library

        mock_builtin.get_library_instance.side_effect = get_library_side_effect

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        # Should fall back to Selenium
        assert result is not None
        assert b"SeleniumFallback" in result

    def test_capture_from_selenium_returns_png_data(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test capture_from_selenium returns PNG data."""
        mock_selenium_library = MagicMock()
        mock_driver = MagicMock()
        mock_driver.get_screenshot_as_png.return_value = b"\x89PNG\r\n\x1a\nSelenium"
        type(mock_selenium_library).driver = PropertyMock(return_value=mock_driver)
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_from_selenium()

        assert result is not None
        assert result.startswith(b"\x89PNG")
        mock_driver.get_screenshot_as_png.assert_called_once()

    def test_capture_from_selenium_returns_none_when_no_library(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test capture_from_selenium returns None when SeleniumLibrary not loaded."""
        mock_builtin.get_library_instance.side_effect = RuntimeError(
            "No library 'SeleniumLibrary' found."
        )

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_from_selenium()

        assert result is None

    def test_get_selenium_driver_returns_driver(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test get_selenium_driver returns the Selenium driver."""
        mock_selenium_library = MagicMock()
        mock_driver = MagicMock()
        type(mock_selenium_library).driver = PropertyMock(return_value=mock_driver)
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.get_selenium_driver()

        assert result is mock_driver

    def test_get_selenium_driver_returns_none_when_no_library(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test get_selenium_driver returns None when no SeleniumLibrary."""
        mock_builtin.get_library_instance.side_effect = RuntimeError(
            "No library 'SeleniumLibrary' found."
        )

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.get_selenium_driver()

        assert result is None
