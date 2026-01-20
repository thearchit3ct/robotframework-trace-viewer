"""DOM snapshot capture module for Robot Framework trace viewer.

This module provides functionality to capture DOM snapshots from browser automation
libraries when running Robot Framework tests with SeleniumLibrary or Browser Library.

The captured DOM is sanitized to remove <script> tags for security.

Supported libraries:
- Browser Library (Playwright) - preferred when both are available
- SeleniumLibrary (Selenium WebDriver)
"""

import re
from typing import Any, Optional

from robot.libraries.BuiltIn import BuiltIn
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchWindowException,
    WebDriverException,
)
from selenium.webdriver.remote.webdriver import WebDriver


class DOMCapture:
    """Capture DOM snapshots from browser automation libraries in Robot Framework context.

    This class integrates with Robot Framework's BuiltIn library to access
    SeleniumLibrary or Browser Library (Playwright) and capture the full DOM
    from the active browser session.

    When both libraries are loaded, Browser Library is preferred as it typically
    provides better support with Playwright.

    The captured DOM is automatically sanitized to remove <script> tags for security.

    The capture methods are designed to fail silently when no browser is available,
    making it safe to use in tests that may or may not have a browser open.

    Example:
        >>> capture = DOMCapture()
        >>> if capture.is_browser_available():
        ...     html = capture.capture()
        ...     if html:
        ...         with open('dom.html', 'w', encoding='utf-8') as f:
        ...             f.write(html)
    """

    BROWSER_CLOSED_EXCEPTIONS = (
        WebDriverException,
        NoSuchWindowException,
        InvalidSessionIdException,
    )

    # Regex pattern to match script tags (including their content)
    # Matches <script...>...</script> and <script.../>
    # Handles attributes, whitespace, and multiline content
    SCRIPT_TAG_PATTERN = re.compile(
        r"<script\b[^>]*>[\s\S]*?</script>|<script\b[^>]*/\s*>",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        """Initialize the DOM capture instance.

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
    # HTML Sanitization
    # =========================================================================

    def sanitize_html(self, html: str) -> str:
        """Remove script tags from HTML for security.

        This method removes all <script> tags and their content from the HTML
        to prevent potential XSS attacks when the DOM is rendered in the viewer.

        Args:
            html: The raw HTML string to sanitize.

        Returns:
            str: The sanitized HTML with all script tags removed.

        Example:
            >>> capture = DOMCapture()
            >>> html = '<html><script>alert("xss")</script><body>Hello</body></html>'
            >>> sanitized = capture.sanitize_html(html)
            >>> '<script>' in sanitized
            False
        """
        if not html:
            return html
        return self.SCRIPT_TAG_PATTERN.sub("", html)

    # =========================================================================
    # Browser Library (Playwright) Support
    # =========================================================================

    def get_browser_library(self) -> Optional[Any]:
        """Retrieve the Browser Library instance from Robot Framework.

        Browser Library uses Playwright under the hood and provides
        high-quality DOM capture.

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

    def capture_from_browser_library(self) -> Optional[str]:
        """Capture the DOM using Browser Library (Playwright).

        This method uses Browser Library's internal Playwright page to capture
        the full DOM via JavaScript execution.

        Returns:
            Optional[str]: The full HTML content of the page if capture succeeds,
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

            # Playwright's page.content() returns the full HTML
            html = page.content()
            return self.sanitize_html(html) if html else None
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

    def capture_from_selenium(self) -> Optional[str]:
        """Capture the DOM using SeleniumLibrary.

        This method uses Selenium's execute_script to retrieve the full DOM
        via document.documentElement.outerHTML.

        Returns:
            Optional[str]: The full HTML content of the page if capture succeeds,
                None if capture fails for any reason.
        """
        driver = self.get_selenium_driver()
        if driver is None:
            return None
        try:
            html = driver.execute_script("return document.documentElement.outerHTML;")
            return self.sanitize_html(html) if html else None
        except self.BROWSER_CLOSED_EXCEPTIONS:
            return None
        except Exception:
            return None

    # =========================================================================
    # Unified API
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
        """Check if a browser is currently available for DOM capture.

        This checks both Browser Library (Playwright) and SeleniumLibrary,
        returning True if either has an active browser session.

        Returns:
            bool: True if a browser session is active, False otherwise.
        """
        return self.is_browser_library_available() or self.get_selenium_driver() is not None

    def capture(self) -> Optional[str]:
        """Capture the full DOM from the current browser window.

        This method tries Browser Library (Playwright) first, then falls back
        to SeleniumLibrary. This order is chosen because:
        1. Playwright generally provides better DOM access
        2. If both libraries are loaded, Browser Library is likely the primary

        The captured DOM is automatically sanitized to remove <script> tags.

        This method handles various error conditions gracefully:
        - No browser library loaded
        - No browser session active
        - Browser window closed
        - Driver communication errors

        Returns:
            Optional[str]: The sanitized HTML content of the page if capture
                succeeds, None if capture fails for any reason.
        """
        # Try Browser Library (Playwright) first
        dom = self.capture_from_browser_library()
        if dom is not None:
            return dom

        # Fall back to SeleniumLibrary
        return self.capture_from_selenium()

    def capture_to_file(self, filepath: str) -> bool:
        """Capture the DOM and save it directly to a file.

        Args:
            filepath: The path where the HTML file should be saved.

        Returns:
            bool: True if the DOM was captured and saved successfully,
                False if capture failed or file could not be written.
        """
        data = self.capture()
        if data is None:
            return False
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(data)
            return True
        except OSError:
            return False
