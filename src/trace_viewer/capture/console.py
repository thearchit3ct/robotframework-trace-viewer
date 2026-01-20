"""Console log capture module for Robot Framework trace viewer.

This module provides functionality to capture browser console logs from Selenium WebDriver
when running Robot Framework tests with SeleniumLibrary.

Note: Browser console logs (get_log('browser')) are only supported on Chrome/Chromium.
Firefox and other browsers may not support this feature.
"""

from typing import Any, Optional

from robot.libraries.BuiltIn import BuiltIn
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchWindowException,
    WebDriverException,
)
from selenium.webdriver.remote.webdriver import WebDriver


class ConsoleCapture:
    """Capture browser console logs from Selenium WebDriver in Robot Framework context.

    This class integrates with Robot Framework's BuiltIn library to access
    SeleniumLibrary and capture console logs from the active browser session.

    The capture methods are designed to fail silently when no browser is available
    or when the browser does not support console log capture (e.g., Firefox),
    making it safe to use in tests that may or may not have a supported browser.

    Console logs are captured using Selenium's get_log('browser') API, which
    returns logs since the last call (not cumulative).

    Example:
        >>> capture = ConsoleCapture()
        >>> if capture.is_browser_available():
        ...     logs = capture.capture()
        ...     for log in logs:
        ...         print(f"[{log['level']}] {log['message']}")
    """

    BROWSER_CLOSED_EXCEPTIONS = (
        WebDriverException,
        NoSuchWindowException,
        InvalidSessionIdException,
    )

    # Log levels from Selenium browser logs
    LOG_LEVELS = ("SEVERE", "WARNING", "INFO", "DEBUG", "LOG")

    def __init__(self) -> None:
        """Initialize the console capture instance.

        The BuiltIn library instance is lazily loaded on first access.
        """
        self._builtin: Optional[BuiltIn] = None

    @property
    def builtin(self) -> BuiltIn:
        """Lazy-load BuiltIn library instance.

        Returns:
            BuiltIn: Robot Framework's BuiltIn library instance.
        """
        if self._builtin is None:
            self._builtin = BuiltIn()
        return self._builtin

    def get_selenium_library(self) -> Optional[object]:
        """Retrieve the SeleniumLibrary instance from Robot Framework.

        Returns:
            Optional[object]: The SeleniumLibrary instance if available,
                None otherwise.
        """
        try:
            return self.builtin.get_library_instance("SeleniumLibrary")  # type: ignore[no-any-return]
        except RuntimeError:
            return None

    def get_driver(self) -> Optional[WebDriver]:
        """Retrieve the active Selenium WebDriver.

        Returns:
            Optional[WebDriver]: The active WebDriver instance if a browser
                is open, None otherwise.
        """
        selenium_library = self.get_selenium_library()
        if selenium_library is None:
            return None
        try:
            return selenium_library.driver  # type: ignore[attr-defined, no-any-return]
        except Exception:
            return None

    def is_browser_available(self) -> bool:
        """Check if a browser is currently available for console log capture.

        Returns:
            bool: True if a browser session is active, False otherwise.
        """
        return self.get_driver() is not None

    def is_console_log_supported(self) -> bool:
        """Check if console log capture is supported by the current browser.

        Only Chrome/Chromium supports the 'browser' log type via get_log().
        Firefox and other browsers do not support this feature.

        Returns:
            bool: True if console log capture is supported, False otherwise.
        """
        driver = self.get_driver()
        if driver is None:
            return False
        try:
            # Check if 'browser' is in the available log types
            log_types = driver.log_types  # type: ignore[attr-defined]
            return "browser" in log_types
        except Exception:
            return False

    def capture(self) -> list[dict[str, Any]]:
        """Capture console logs from the current browser window.

        This method handles various error conditions gracefully:
        - No SeleniumLibrary loaded
        - No browser session active
        - Browser does not support console logs (Firefox, etc.)
        - Browser window closed
        - WebDriver communication errors

        Returns:
            list[dict[str, Any]]: List of console log entries, each containing:
                - level: Log level (SEVERE, WARNING, INFO, DEBUG, LOG)
                - message: The log message
                - source: Source of the log entry (if available)
                - timestamp: Timestamp in milliseconds since epoch

            Returns an empty list if capture fails for any reason.

        Note:
            get_log('browser') returns logs since the last call, not
            cumulative logs. Each call clears the log buffer.
        """
        driver = self.get_driver()
        if driver is None:
            return []

        try:
            # Check if browser logging is supported
            if "browser" not in driver.log_types:  # type: ignore[attr-defined]
                return []

            # Get browser logs
            raw_logs = driver.get_log("browser")  # type: ignore[attr-defined]

            # Transform logs to our standardized format
            logs: list[dict[str, Any]] = []
            for entry in raw_logs:
                log_entry = self._transform_log_entry(entry)
                logs.append(log_entry)

            return logs

        except self.BROWSER_CLOSED_EXCEPTIONS:
            return []
        except Exception:
            # Catch any other exceptions (e.g., unsupported log type)
            return []

    def _transform_log_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Transform a raw Selenium log entry to our standardized format.

        Args:
            entry: Raw log entry from Selenium's get_log().

        Returns:
            Standardized log entry dictionary.
        """
        # Selenium log entry format:
        # {
        #     'level': 'SEVERE',
        #     'message': 'https://example.com/script.js 42:13 "Error message"',
        #     'timestamp': 1705678902345,
        #     'source': 'console-api'  # Optional, may not always be present
        # }

        message = entry.get("message", "")
        source = entry.get("source", "")

        # Try to extract source URL from message if source is not provided
        # Chrome format: "url line:col message"
        if not source and " " in message:
            parts = message.split(" ", 1)
            potential_url = parts[0]
            if potential_url.startswith(("http://", "https://", "file://")):
                source = potential_url

        return {
            "level": entry.get("level", "INFO"),
            "message": message,
            "source": source,
            "timestamp": entry.get("timestamp", 0),
        }

    def capture_filtered(self, min_level: str = "WARNING") -> list[dict[str, Any]]:
        """Capture console logs filtered by minimum severity level.

        Args:
            min_level: Minimum log level to capture.
                Options: "SEVERE", "WARNING", "INFO", "DEBUG", "LOG".
                Default is "WARNING" to capture only warnings and errors.

        Returns:
            list[dict[str, Any]]: Filtered list of console log entries.
        """
        all_logs = self.capture()
        if not all_logs:
            return []

        # Define severity order (higher index = less severe)
        severity_order = {
            "SEVERE": 0,
            "WARNING": 1,
            "INFO": 2,
            "DEBUG": 3,
            "LOG": 4,
        }

        min_severity = severity_order.get(min_level.upper(), 2)

        return [
            log
            for log in all_logs
            if severity_order.get(log.get("level", "INFO").upper(), 2) <= min_severity
        ]
