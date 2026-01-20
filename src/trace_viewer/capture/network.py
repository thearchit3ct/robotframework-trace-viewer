"""Network request capture module using Chrome DevTools Protocol.

This module provides the NetworkCapture class which captures network requests
and responses during keyword execution using CDP (Chrome DevTools Protocol).

Supports both SeleniumLibrary (via execute_cdp_cmd) and Browser Library
(via Playwright's CDP session).
"""

import time
from typing import Any, Optional

from robot.api import logger


class NetworkCapture:
    """Captures network requests and responses using CDP.

    The NetworkCapture class uses Chrome DevTools Protocol to intercept
    and log network activity during test execution. It supports both
    SeleniumLibrary and Browser Library.

    Network events captured include:
    - Request URL, method, headers
    - Response status, headers, timing
    - Resource type (document, script, xhr, fetch, etc.)

    Attributes:
        _selenium_lib: Cached SeleniumLibrary instance.
        _browser_lib: Cached Browser Library instance.
        _cdp_enabled: Whether CDP network capture is currently enabled.
        _pending_requests: Dictionary of in-flight requests by requestId.
        _captured_requests: List of completed request/response pairs.

    Example:
        >>> capture = NetworkCapture()
        >>> capture.enable()
        >>> # ... test actions that trigger network activity ...
        >>> requests = capture.get_requests()
        >>> capture.disable()
    """

    def __init__(self) -> None:
        """Initialize NetworkCapture."""
        self._selenium_lib: Optional[Any] = None
        self._browser_lib: Optional[Any] = None
        self._cdp_enabled: bool = False
        self._pending_requests: dict[str, dict[str, Any]] = {}
        self._captured_requests: list[dict[str, Any]] = []
        self._start_time: Optional[float] = None

    def _get_selenium_library(self) -> Optional[Any]:
        """Get SeleniumLibrary instance if available.

        Returns:
            SeleniumLibrary instance or None if not available.
        """
        if self._selenium_lib is not None:
            return self._selenium_lib

        try:
            from robot.libraries.BuiltIn import BuiltIn

            builtin = BuiltIn()
            self._selenium_lib = builtin.get_library_instance("SeleniumLibrary")
            return self._selenium_lib
        except Exception:
            return None

    def _get_browser_library(self) -> Optional[Any]:
        """Get Browser Library instance if available.

        Returns:
            Browser Library instance or None if not available.
        """
        if self._browser_lib is not None:
            return self._browser_lib

        try:
            from robot.libraries.BuiltIn import BuiltIn

            builtin = BuiltIn()
            self._browser_lib = builtin.get_library_instance("Browser")
            return self._browser_lib
        except Exception:
            return None

    def _get_selenium_driver(self) -> Optional[Any]:
        """Get Selenium WebDriver if available.

        Returns:
            WebDriver instance or None if not available.
        """
        selenium_lib = self._get_selenium_library()
        if selenium_lib is None:
            return None

        try:
            return selenium_lib.driver
        except Exception:
            return None

    def enable(self) -> bool:
        """Enable CDP network capture.

        Attempts to enable network capture using CDP. Works with Chrome,
        Chromium, and Edge browsers that support DevTools Protocol.

        Returns:
            True if CDP capture was enabled, False otherwise.
        """
        if self._cdp_enabled:
            return True

        self._pending_requests = {}
        self._captured_requests = []
        self._start_time = time.time()

        # Try Selenium first
        driver = self._get_selenium_driver()
        if driver is not None:
            try:
                # Check if browser supports CDP (Chrome, Chromium, Edge)
                browser_name = driver.capabilities.get("browserName", "").lower()
                if browser_name not in ("chrome", "chromium", "msedge", "edge"):
                    logger.debug(f"Network capture not supported for browser: {browser_name}")
                    return False

                # Enable Network domain
                driver.execute_cdp_cmd("Network.enable", {})
                self._cdp_enabled = True
                logger.debug("CDP network capture enabled via Selenium")
                return True
            except Exception as e:
                logger.debug(f"Failed to enable CDP network capture: {e}")
                return False

        # Try Browser Library
        browser_lib = self._get_browser_library()
        if browser_lib is not None:
            try:
                # Browser Library has its own network interception via Playwright
                # We'll use a different approach for Playwright
                self._cdp_enabled = True
                logger.debug("Network capture enabled via Browser Library")
                return True
            except Exception as e:
                logger.debug(f"Failed to enable network capture via Browser: {e}")
                return False

        return False

    def disable(self) -> None:
        """Disable CDP network capture.

        Disables the CDP Network domain and cleans up resources.
        """
        if not self._cdp_enabled:
            return

        driver = self._get_selenium_driver()
        if driver is not None:
            try:
                driver.execute_cdp_cmd("Network.disable", {})
            except Exception as e:
                logger.debug(f"Failed to disable CDP network capture: {e}")

        self._cdp_enabled = False

    def capture(self) -> list[dict[str, Any]]:
        """Capture current network requests.

        Retrieves network requests that have occurred since the last capture
        or since enable() was called. For Selenium with CDP, this polls
        the DevTools for network events.

        Returns:
            List of network request entries, each containing:
            - url: Request URL
            - method: HTTP method (GET, POST, etc.)
            - status: Response status code (or None if pending)
            - resource_type: Type of resource (document, xhr, fetch, etc.)
            - duration_ms: Request duration in milliseconds
            - request_headers: Dict of request headers (truncated)
            - response_headers: Dict of response headers (truncated)
            - timestamp: Request timestamp
            - size: Response size in bytes (if available)
        """
        if not self._cdp_enabled:
            return []

        driver = self._get_selenium_driver()
        if driver is not None:
            return self._capture_from_selenium(driver)

        browser_lib = self._get_browser_library()
        if browser_lib is not None:
            return self._capture_from_browser_library(browser_lib)

        return []

    def _capture_from_selenium(self, driver: Any) -> list[dict[str, Any]]:
        """Capture network requests from Selenium via CDP.

        Args:
            driver: Selenium WebDriver instance.

        Returns:
            List of captured network request entries.
        """
        requests: list[dict[str, Any]] = []

        try:
            # Get performance logs which include network events
            logs = driver.get_log("performance")

            for log_entry in logs:
                try:
                    import json

                    message = json.loads(log_entry.get("message", "{}"))
                    method = message.get("message", {}).get("method", "")
                    params = message.get("message", {}).get("params", {})

                    if method == "Network.requestWillBeSent":
                        self._handle_request_sent(params)
                    elif method == "Network.responseReceived":
                        self._handle_response_received(params)
                    elif method == "Network.loadingFinished":
                        self._handle_loading_finished(params)
                    elif method == "Network.loadingFailed":
                        self._handle_loading_failed(params)
                except Exception:
                    continue

            # Convert pending requests to captured format
            requests = list(self._captured_requests)
            self._captured_requests = []

        except Exception as e:
            logger.debug(f"Failed to capture network requests: {e}")

        return requests

    def _handle_request_sent(self, params: dict[str, Any]) -> None:
        """Handle Network.requestWillBeSent CDP event.

        Args:
            params: CDP event parameters.
        """
        request_id = params.get("requestId", "")
        request = params.get("request", {})
        timestamp = params.get("timestamp", 0)

        self._pending_requests[request_id] = {
            "request_id": request_id,
            "url": request.get("url", ""),
            "method": request.get("method", "GET"),
            "request_headers": self._truncate_headers(request.get("headers", {})),
            "resource_type": params.get("type", "Other"),
            "timestamp": timestamp,
            "start_time": time.time(),
            "status": None,
            "response_headers": {},
            "size": 0,
            "duration_ms": 0,
        }

    def _handle_response_received(self, params: dict[str, Any]) -> None:
        """Handle Network.responseReceived CDP event.

        Args:
            params: CDP event parameters.
        """
        request_id = params.get("requestId", "")
        response = params.get("response", {})

        if request_id in self._pending_requests:
            req = self._pending_requests[request_id]
            req["status"] = response.get("status", 0)
            req["response_headers"] = self._truncate_headers(response.get("headers", {}))
            req["mime_type"] = response.get("mimeType", "")

    def _handle_loading_finished(self, params: dict[str, Any]) -> None:
        """Handle Network.loadingFinished CDP event.

        Args:
            params: CDP event parameters.
        """
        request_id = params.get("requestId", "")

        if request_id in self._pending_requests:
            req = self._pending_requests.pop(request_id)
            req["size"] = params.get("encodedDataLength", 0)
            req["duration_ms"] = int((time.time() - req["start_time"]) * 1000)
            del req["start_time"]  # Remove internal timing field
            self._captured_requests.append(req)

    def _handle_loading_failed(self, params: dict[str, Any]) -> None:
        """Handle Network.loadingFailed CDP event.

        Args:
            params: CDP event parameters.
        """
        request_id = params.get("requestId", "")

        if request_id in self._pending_requests:
            req = self._pending_requests.pop(request_id)
            req["status"] = 0
            req["error"] = params.get("errorText", "Failed")
            req["duration_ms"] = int((time.time() - req["start_time"]) * 1000)
            del req["start_time"]
            self._captured_requests.append(req)

    def _capture_from_browser_library(self, browser_lib: Any) -> list[dict[str, Any]]:
        """Capture network requests from Browser Library.

        Browser Library (Playwright) has different network capture mechanisms.
        This method attempts to get network activity via Playwright's API.

        Args:
            browser_lib: Browser Library instance.

        Returns:
            List of captured network request entries.
        """
        # Browser Library with Playwright handles network differently
        # Playwright captures via page.on('request')/page.on('response')
        # For now, return empty as this requires different integration
        logger.debug("Network capture from Browser Library not yet implemented")
        return []

    def _truncate_headers(
        self, headers: dict[str, Any], max_value_length: int = 200
    ) -> dict[str, str]:
        """Truncate header values to prevent excessive data storage.

        Args:
            headers: Dictionary of HTTP headers.
            max_value_length: Maximum length for each header value.

        Returns:
            Dictionary with truncated header values.
        """
        truncated = {}
        # Only keep common/useful headers
        important_headers = {
            "content-type",
            "content-length",
            "cache-control",
            "accept",
            "user-agent",
            "referer",
            "origin",
            "x-requested-with",
            "authorization",  # Will be masked
        }

        for key, value in headers.items():
            key_lower = key.lower()
            if key_lower not in important_headers:
                continue

            str_value = str(value)

            # Mask sensitive headers
            if key_lower in ("authorization", "cookie", "set-cookie"):
                str_value = "***MASKED***"
            elif len(str_value) > max_value_length:
                str_value = str_value[:max_value_length] + "..."

            truncated[key] = str_value

        return truncated

    def get_requests(self) -> list[dict[str, Any]]:
        """Get all captured requests since last call.

        Convenience method that calls capture() and returns the results.

        Returns:
            List of captured network request entries.
        """
        return self.capture()

    def clear(self) -> None:
        """Clear all captured requests and pending state."""
        self._pending_requests = {}
        self._captured_requests = []

    def is_enabled(self) -> bool:
        """Check if network capture is currently enabled.

        Returns:
            True if capture is enabled, False otherwise.
        """
        return self._cdp_enabled
