"""Screenshot capture module for Robot Framework trace viewer.

This module provides functionality to capture screenshots from browser automation
libraries when running Robot Framework tests with SeleniumLibrary or Browser Library.

Supported libraries:
- Browser Library (Playwright) - preferred when both are available
- SeleniumLibrary (Selenium WebDriver)
"""

from typing import Any, Optional

from robot.libraries.BuiltIn import BuiltIn
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchWindowException,
    WebDriverException,
)
from selenium.webdriver.remote.webdriver import WebDriver


class ScreenshotCapture:
    """Capture screenshots from browser automation libraries in Robot Framework context.

    This class integrates with Robot Framework's BuiltIn library to access
    SeleniumLibrary or Browser Library (Playwright) and capture screenshots
    from the active browser session.

    When both libraries are loaded, Browser Library is preferred as it typically
    provides better screenshot quality with Playwright.

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

    # =========================================================================
    # Browser Library (Playwright) Support
    # =========================================================================

    def get_browser_library(self) -> Optional[Any]:
        """Retrieve the Browser Library instance from Robot Framework.

        Browser Library uses Playwright under the hood and provides
        high-quality screenshot capture.

        Returns:
            Optional[Any]: The Browser Library instance if available,
                None otherwise.
        """
        try:
            return self.builtin.get_library_instance("Browser")
        except RuntimeError:
            return None

    def is_browser_library_available(self) -> bool:
        """Check if Browser Library is loaded and has an active page.

        Returns:
            bool: True if Browser Library has an active page, False otherwise.
        """
        browser_lib = self.get_browser_library()
        if browser_lib is None:
            return False
        try:
            # Browser Library exposes the Playwright page via library internals
            # Check if there's an active page by attempting to access the catalog
            catalog = getattr(browser_lib, "_playwright_state", None)
            if catalog is None:
                catalog = getattr(browser_lib, "playwright", None)
            if catalog is None:
                return False
            # Try to get the current page - this will fail if no browser is open
            page = catalog.get_current_page() if hasattr(catalog, "get_current_page") else None
            return page is not None
        except Exception:
            return False

    def capture_from_browser_library(self) -> Optional[bytes]:
        """Capture a screenshot using Browser Library (Playwright).

        This method uses Browser Library's internal Playwright page to capture
        a screenshot. It provides full-page screenshot support.

        Returns:
            Optional[bytes]: PNG image data as bytes if capture succeeds,
                None if capture fails for any reason.
        """
        browser_lib = self.get_browser_library()
        if browser_lib is None:
            return None
        try:
            # Access the Playwright state/catalog to get the current page
            catalog = getattr(browser_lib, "_playwright_state", None)
            if catalog is None:
                catalog = getattr(browser_lib, "playwright", None)
            if catalog is None:
                return None

            # Get the current page from the catalog
            page = None
            if hasattr(catalog, "get_current_page"):
                page = catalog.get_current_page()

            if page is None:
                return None

            # Playwright's page.screenshot() returns bytes directly
            return page.screenshot(type="png")  # type: ignore[no-any-return]
        except Exception:
            return None

    # =========================================================================
    # SeleniumLibrary Support
    # =========================================================================

    def get_selenium_library(self) -> Optional[Any]:
        """Retrieve the SeleniumLibrary instance from Robot Framework.

        Returns:
            Optional[Any]: The SeleniumLibrary instance if available,
                None otherwise.
        """
        try:
            return self.builtin.get_library_instance("SeleniumLibrary")
        except RuntimeError:
            return None

    def get_selenium_driver(self) -> Optional[WebDriver]:
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

    def capture_from_selenium(self) -> Optional[bytes]:
        """Capture a screenshot using SeleniumLibrary.

        Returns:
            Optional[bytes]: PNG image data as bytes if capture succeeds,
                None if capture fails for any reason.
        """
        driver = self.get_selenium_driver()
        if driver is None:
            return None
        try:
            return driver.get_screenshot_as_png()
        except self.BROWSER_CLOSED_EXCEPTIONS:
            return None
        except Exception:
            return None

    # =========================================================================
    # Unified API (backwards compatible)
    # =========================================================================

    def get_driver(self) -> Optional[WebDriver]:
        """Retrieve the active Selenium WebDriver (backwards compatible).

        This method is kept for backwards compatibility. For new code,
        consider using the specific library methods.

        Returns:
            Optional[WebDriver]: The active WebDriver instance if a browser
                is open, None otherwise.
        """
        return self.get_selenium_driver()

    def is_browser_available(self) -> bool:
        """Check if a browser is currently available for screenshot capture.

        This checks both Browser Library (Playwright) and SeleniumLibrary,
        returning True if either has an active browser session.

        Returns:
            bool: True if a browser session is active, False otherwise.
        """
        return self.is_browser_library_available() or self.get_selenium_driver() is not None

    def capture(self) -> Optional[bytes]:
        """Capture a PNG screenshot from the current browser window.

        This method tries Browser Library (Playwright) first, then falls back
        to SeleniumLibrary. This order is chosen because:
        1. Playwright generally produces higher quality screenshots
        2. If both libraries are loaded, Browser Library is likely the primary

        This method handles various error conditions gracefully:
        - No browser library loaded
        - No browser session active
        - Browser window closed
        - Driver communication errors

        Returns:
            Optional[bytes]: PNG image data as bytes if capture succeeds,
                None if capture fails for any reason.
        """
        # Try Browser Library (Playwright) first
        screenshot = self.capture_from_browser_library()
        if screenshot is not None:
            return screenshot

        # Fall back to SeleniumLibrary
        return self.capture_from_selenium()

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
