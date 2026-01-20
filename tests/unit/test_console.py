"""Unit tests for the ConsoleCapture module.

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

from trace_viewer.capture.console import ConsoleCapture


class TestConsoleCapture:
    """Test suite for ConsoleCapture class."""

    @pytest.fixture
    def capture(self) -> ConsoleCapture:
        """Create a fresh ConsoleCapture instance for each test."""
        return ConsoleCapture()

    @pytest.fixture
    def mock_builtin(self) -> MagicMock:
        """Create a mock BuiltIn library."""
        return MagicMock()

    @pytest.fixture
    def mock_selenium_library(self) -> MagicMock:
        """Create a mock SeleniumLibrary with a mock driver supporting console logs."""
        selenium_lib = MagicMock()
        mock_driver = MagicMock()
        mock_driver.log_types = ["browser", "driver"]
        mock_driver.get_log.return_value = [
            {
                "level": "SEVERE",
                "message": "https://example.com/script.js 42:13 Uncaught TypeError",
                "timestamp": 1705678902345,
                "source": "javascript",
            },
            {
                "level": "WARNING",
                "message": "Deprecated API called",
                "timestamp": 1705678902350,
            },
        ]
        type(selenium_lib).driver = PropertyMock(return_value=mock_driver)
        return selenium_lib

    @pytest.fixture
    def mock_selenium_library_no_browser_logs(self) -> MagicMock:
        """Create a mock SeleniumLibrary with a driver that doesn't support browser logs."""
        selenium_lib = MagicMock()
        mock_driver = MagicMock()
        mock_driver.log_types = ["driver"]  # No 'browser' log type (e.g., Firefox)
        type(selenium_lib).driver = PropertyMock(return_value=mock_driver)
        return selenium_lib

    def test_capture_returns_empty_list_when_no_selenium_library(
        self, capture: ConsoleCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that capture returns empty list when SeleniumLibrary is not loaded."""
        mock_builtin.get_library_instance.side_effect = RuntimeError(
            "No library 'SeleniumLibrary' found."
        )

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert result == []
        mock_builtin.get_library_instance.assert_called_once_with("SeleniumLibrary")

    def test_capture_returns_empty_list_when_no_browser_open(
        self, capture: ConsoleCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that capture returns empty list when no browser window is open."""
        mock_selenium_library = MagicMock()
        type(mock_selenium_library).driver = PropertyMock(side_effect=Exception("No browser open"))
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert result == []

    def test_capture_returns_logs_when_browser_available(
        self,
        capture: ConsoleCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that capture returns console logs when browser is available."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert len(result) == 2
        assert result[0]["level"] == "SEVERE"
        assert "TypeError" in result[0]["message"]
        assert result[0]["timestamp"] == 1705678902345
        assert result[1]["level"] == "WARNING"
        mock_selenium_library.driver.get_log.assert_called_once_with("browser")

    def test_capture_returns_empty_list_when_browser_logs_not_supported(
        self,
        capture: ConsoleCapture,
        mock_builtin: MagicMock,
        mock_selenium_library_no_browser_logs: MagicMock,
    ) -> None:
        """Test that capture returns empty list when browser doesn't support console logs."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library_no_browser_logs

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert result == []

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
        capture: ConsoleCapture,
        mock_builtin: MagicMock,
        exception_class: type,
    ) -> None:
        """Test that capture handles WebDriver exceptions gracefully."""
        mock_selenium_library = MagicMock()
        mock_driver = MagicMock()
        mock_driver.log_types = ["browser"]
        mock_driver.get_log.side_effect = exception_class("Browser closed")
        type(mock_selenium_library).driver = PropertyMock(return_value=mock_driver)
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture()

        assert result == []

    def test_is_browser_available_returns_true_when_driver_exists(
        self,
        capture: ConsoleCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that is_browser_available returns True when a driver is available."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.is_browser_available()

        assert result is True

    def test_is_browser_available_returns_false_when_no_driver(
        self, capture: ConsoleCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that is_browser_available returns False when no driver is available."""
        mock_builtin.get_library_instance.side_effect = RuntimeError(
            "No library 'SeleniumLibrary' found."
        )

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.is_browser_available()

        assert result is False

    def test_is_console_log_supported_returns_true_for_chrome(
        self,
        capture: ConsoleCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that is_console_log_supported returns True for Chrome."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.is_console_log_supported()

        assert result is True

    def test_is_console_log_supported_returns_false_for_firefox(
        self,
        capture: ConsoleCapture,
        mock_builtin: MagicMock,
        mock_selenium_library_no_browser_logs: MagicMock,
    ) -> None:
        """Test that is_console_log_supported returns False for Firefox."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library_no_browser_logs

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.is_console_log_supported()

        assert result is False

    def test_get_selenium_library_returns_library_instance(
        self,
        capture: ConsoleCapture,
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
        capture: ConsoleCapture,
        mock_builtin: MagicMock,
        mock_selenium_library: MagicMock,
    ) -> None:
        """Test that get_driver returns the WebDriver instance."""
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.get_driver()

        assert result is mock_selenium_library.driver

    def test_builtin_property_lazy_loads(self, capture: ConsoleCapture) -> None:
        """Test that the builtin property lazy-loads the BuiltIn instance."""
        assert capture._builtin is None

        with patch("trace_viewer.capture.console.BuiltIn") as mock_builtin_class:
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

    def test_transform_log_entry_extracts_all_fields(self, capture: ConsoleCapture) -> None:
        """Test that _transform_log_entry extracts all fields correctly."""
        entry = {
            "level": "SEVERE",
            "message": "Error message",
            "timestamp": 1705678902345,
            "source": "console-api",
        }

        result = capture._transform_log_entry(entry)

        assert result["level"] == "SEVERE"
        assert result["message"] == "Error message"
        assert result["timestamp"] == 1705678902345
        assert result["source"] == "console-api"

    def test_transform_log_entry_handles_missing_fields(self, capture: ConsoleCapture) -> None:
        """Test that _transform_log_entry handles missing fields with defaults."""
        entry = {}

        result = capture._transform_log_entry(entry)

        assert result["level"] == "INFO"
        assert result["message"] == ""
        assert result["timestamp"] == 0
        assert result["source"] == ""

    def test_transform_log_entry_extracts_source_from_message(
        self, capture: ConsoleCapture
    ) -> None:
        """Test that _transform_log_entry extracts URL from message when source missing."""
        entry = {
            "level": "WARNING",
            "message": "https://example.com/script.js 42:13 Some warning",
            "timestamp": 1705678902345,
        }

        result = capture._transform_log_entry(entry)

        assert result["source"] == "https://example.com/script.js"

    def test_capture_filtered_returns_only_severe_and_warning(
        self,
        capture: ConsoleCapture,
        mock_builtin: MagicMock,
    ) -> None:
        """Test that capture_filtered filters by minimum severity level."""
        mock_selenium_library = MagicMock()
        mock_driver = MagicMock()
        mock_driver.log_types = ["browser"]
        mock_driver.get_log.return_value = [
            {"level": "SEVERE", "message": "Error", "timestamp": 1},
            {"level": "WARNING", "message": "Warning", "timestamp": 2},
            {"level": "INFO", "message": "Info", "timestamp": 3},
            {"level": "DEBUG", "message": "Debug", "timestamp": 4},
        ]
        type(mock_selenium_library).driver = PropertyMock(return_value=mock_driver)
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_filtered(min_level="WARNING")

        assert len(result) == 2
        assert result[0]["level"] == "SEVERE"
        assert result[1]["level"] == "WARNING"

    def test_capture_filtered_returns_only_severe(
        self,
        capture: ConsoleCapture,
        mock_builtin: MagicMock,
    ) -> None:
        """Test that capture_filtered with SEVERE returns only errors."""
        mock_selenium_library = MagicMock()
        mock_driver = MagicMock()
        mock_driver.log_types = ["browser"]
        mock_driver.get_log.return_value = [
            {"level": "SEVERE", "message": "Error", "timestamp": 1},
            {"level": "WARNING", "message": "Warning", "timestamp": 2},
        ]
        type(mock_selenium_library).driver = PropertyMock(return_value=mock_driver)
        mock_builtin.get_library_instance.return_value = mock_selenium_library

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_filtered(min_level="SEVERE")

        assert len(result) == 1
        assert result[0]["level"] == "SEVERE"

    def test_capture_filtered_returns_empty_list_when_no_logs(
        self, capture: ConsoleCapture, mock_builtin: MagicMock
    ) -> None:
        """Test that capture_filtered returns empty list when no logs match."""
        mock_builtin.get_library_instance.side_effect = RuntimeError(
            "No library 'SeleniumLibrary' found."
        )

        with patch.object(capture, "_builtin", mock_builtin):
            result = capture.capture_filtered(min_level="SEVERE")

        assert result == []
