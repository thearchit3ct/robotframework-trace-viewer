"""Unit tests for the ScreenshotCapture module.

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

    def test_capture_returns_none_when_no_selenium_library(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that capture returns None when SeleniumLibrary is not loaded."""
        mock_builtin.get_library_instance.side_effect = RuntimeError(
            "No library 'SeleniumLibrary' found."
        )

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert result is None
        mock_builtin.get_library_instance.assert_called_once_with("SeleniumLibrary")

    def test_capture_returns_none_when_no_browser_open(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that capture returns None when no browser window is open."""
        mock_selenium_library = MagicMock()
        type(mock_selenium_library).driver = PropertyMock(side_effect=Exception("No browser open"))
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert result is None

    def test_capture_returns_png_data_when_browser_available(
        self,
        capture: ScreenshotCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that capture returns PNG data when browser is available."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library

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
        mock_builtin.get_library_instance.return_value = mock_selenium_library

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
        mock_builtin.get_library_instance.return_value = mock_selenium_library
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
        mock_builtin.get_library_instance.side_effect = RuntimeError(
            "No library 'SeleniumLibrary' found."
        )
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
        mock_builtin.get_library_instance.return_value = mock_selenium_library
        invalid_path = "/nonexistent/directory/screenshot.png"

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_to_file(invalid_path)

        assert result is False

    def test_is_browser_available_returns_true_when_driver_exists(
        self,
        capture: ScreenshotCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that is_browser_available returns True when a driver is available."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.is_browser_available()

        assert result is True

    def test_is_browser_available_returns_false_when_no_driver(
        self, capture: ScreenshotCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that is_browser_available returns False when no driver is available."""
        mock_builtin.get_library_instance.side_effect = RuntimeError(
            "No library 'SeleniumLibrary' found."
        )

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
