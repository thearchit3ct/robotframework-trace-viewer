"""Screenshot capture module for Robot Framework trace viewer.

This module provides functionality to capture screenshots from Selenium WebDriver
when running Robot Framework tests with SeleniumLibrary.
"""

from typing import Optional

from robot.libraries.BuiltIn import BuiltIn
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchWindowException,
    WebDriverException,
)
from selenium.webdriver.remote.webdriver import WebDriver


class ScreenshotCapture:
    """Capture screenshots from Selenium WebDriver in Robot Framework context.

    This class integrates with Robot Framework's BuiltIn library to access
    SeleniumLibrary and capture screenshots from the active browser session.

    The capture methods are designed to fail silently when no browser is available,
    making it safe to use in tests that may or may not have a browser open.

    Example:
        >>> capture = ScreenshotCapture()
        >>> if capture.is_browser_available():
        ...     png_data = capture.capture()
        ...     if png_data:
        ...         with open('screenshot.png', 'wb') as f:
        ...             f.write(png_data)
    """

    BROWSER_CLOSED_EXCEPTIONS = (
        WebDriverException,
        NoSuchWindowException,
        InvalidSessionIdException,
    )

    def __init__(self) -> None:
        """Initialize the screenshot capture instance.

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
            return self.builtin.get_library_instance("SeleniumLibrary")
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
            return selenium_library.driver  # type: ignore[attr-defined]
        except Exception:
            return None

    def is_browser_available(self) -> bool:
        """Check if a browser is currently available for screenshot capture.

        Returns:
            bool: True if a browser session is active, False otherwise.
        """
        return self.get_driver() is not None

    def capture(self) -> Optional[bytes]:
        """Capture a PNG screenshot from the current browser window.

        This method handles various error conditions gracefully:
        - No SeleniumLibrary loaded
        - No browser session active
        - Browser window closed
        - WebDriver communication errors

        Returns:
            Optional[bytes]: PNG image data as bytes if capture succeeds,
                None if capture fails for any reason.
        """
        driver = self.get_driver()
        if driver is None:
            return None
        try:
            return driver.get_screenshot_as_png()
        except self.BROWSER_CLOSED_EXCEPTIONS:
            return None
        except Exception:
            return None

    def capture_to_file(self, filepath: str) -> bool:
        """Capture a screenshot and save it directly to a file.

        Args:
            filepath: The path where the PNG file should be saved.

        Returns:
            bool: True if the screenshot was captured and saved successfully,
                False if capture failed or file could not be written.
        """
        data = self.capture()
        if data is None:
            return False
        try:
            with open(filepath, "wb") as f:
                f.write(data)
            return True
        except OSError:
            return False
