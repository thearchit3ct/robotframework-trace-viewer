"""Unit tests for the NetworkCapture module."""

from unittest.mock import MagicMock, patch


class TestNetworkCapture:
    """Tests for NetworkCapture class."""

    def test_capture_returns_empty_list_when_no_selenium_library(self) -> None:
        """Capture returns empty list when SeleniumLibrary is not available."""
        from trace_viewer.capture.network import NetworkCapture

        capture = NetworkCapture()
        result = capture.capture()
        assert result == []

    def test_capture_returns_empty_list_when_no_browser_open(self) -> None:
        """Capture returns empty list when no browser is open."""
        from trace_viewer.capture.network import NetworkCapture

        with patch(
            "trace_viewer.capture.network.NetworkCapture._get_selenium_library"
        ) as mock_get_lib:
            mock_lib = MagicMock()
            mock_lib.driver = None
            mock_get_lib.return_value = mock_lib

            capture = NetworkCapture()
            result = capture.capture()
            assert result == []

    def test_enable_returns_true_with_chrome_browser(self) -> None:
        """Enable returns True with Chrome browser that supports CDP."""
        from trace_viewer.capture.network import NetworkCapture

        with patch(
            "trace_viewer.capture.network.NetworkCapture._get_selenium_driver"
        ) as mock_driver:
            mock_driver_instance = MagicMock()
            mock_driver_instance.capabilities = {"browserName": "chrome"}
            mock_driver_instance.execute_cdp_cmd = MagicMock()
            mock_driver.return_value = mock_driver_instance

            capture = NetworkCapture()
            result = capture.enable()

            assert result is True
            assert capture.is_enabled() is True
            mock_driver_instance.execute_cdp_cmd.assert_called_once_with("Network.enable", {})

    def test_enable_returns_false_with_firefox_browser(self) -> None:
        """Enable returns False with Firefox browser that doesn't support CDP."""
        from trace_viewer.capture.network import NetworkCapture

        with patch(
            "trace_viewer.capture.network.NetworkCapture._get_selenium_driver"
        ) as mock_driver:
            mock_driver_instance = MagicMock()
            mock_driver_instance.capabilities = {"browserName": "firefox"}
            mock_driver.return_value = mock_driver_instance

            capture = NetworkCapture()
            result = capture.enable()

            assert result is False
            assert capture.is_enabled() is False

    def test_enable_returns_false_when_no_driver(self) -> None:
        """Enable returns False when no driver is available."""
        from trace_viewer.capture.network import NetworkCapture

        with patch(
            "trace_viewer.capture.network.NetworkCapture._get_selenium_driver"
        ) as mock_driver:
            mock_driver.return_value = None

            with patch(
                "trace_viewer.capture.network.NetworkCapture._get_browser_library"
            ) as mock_browser:
                mock_browser.return_value = None

                capture = NetworkCapture()
                result = capture.enable()

                assert result is False

    def test_disable_calls_network_disable(self) -> None:
        """Disable calls Network.disable CDP command."""
        from trace_viewer.capture.network import NetworkCapture

        with patch(
            "trace_viewer.capture.network.NetworkCapture._get_selenium_driver"
        ) as mock_driver:
            mock_driver_instance = MagicMock()
            mock_driver_instance.capabilities = {"browserName": "chrome"}
            mock_driver_instance.execute_cdp_cmd = MagicMock()
            mock_driver.return_value = mock_driver_instance

            capture = NetworkCapture()
            capture.enable()
            capture.disable()

            # Check that Network.disable was called
            calls = mock_driver_instance.execute_cdp_cmd.call_args_list
            assert len(calls) == 2
            assert calls[1][0] == ("Network.disable", {})

    def test_disable_does_nothing_when_not_enabled(self) -> None:
        """Disable does nothing when capture was not enabled."""
        from trace_viewer.capture.network import NetworkCapture

        capture = NetworkCapture()
        capture.disable()  # Should not raise

    def test_clear_resets_state(self) -> None:
        """Clear resets internal state."""
        from trace_viewer.capture.network import NetworkCapture

        capture = NetworkCapture()
        capture._pending_requests = {"test": {"url": "http://test.com"}}
        capture._captured_requests = [{"url": "http://example.com"}]

        capture.clear()

        assert capture._pending_requests == {}
        assert capture._captured_requests == []

    def test_is_enabled_returns_correct_state(self) -> None:
        """is_enabled returns correct state."""
        from trace_viewer.capture.network import NetworkCapture

        capture = NetworkCapture()
        assert capture.is_enabled() is False

        # Force enable state
        capture._cdp_enabled = True
        assert capture.is_enabled() is True


class TestNetworkCaptureRequestHandling:
    """Tests for request handling methods."""

    def test_handle_request_sent_stores_pending_request(self) -> None:
        """_handle_request_sent stores pending request data."""
        from trace_viewer.capture.network import NetworkCapture

        capture = NetworkCapture()
        params = {
            "requestId": "123",
            "request": {
                "url": "https://example.com/api",
                "method": "POST",
                "headers": {"content-type": "application/json"},
            },
            "type": "XHR",
            "timestamp": 1000.0,
        }

        capture._handle_request_sent(params)

        assert "123" in capture._pending_requests
        req = capture._pending_requests["123"]
        assert req["url"] == "https://example.com/api"
        assert req["method"] == "POST"
        assert req["resource_type"] == "XHR"

    def test_handle_response_received_updates_pending_request(self) -> None:
        """_handle_response_received updates pending request with response data."""
        from trace_viewer.capture.network import NetworkCapture

        capture = NetworkCapture()
        # First add a pending request
        capture._pending_requests["123"] = {
            "request_id": "123",
            "url": "https://example.com/api",
            "method": "GET",
            "status": None,
            "response_headers": {},
        }

        params = {
            "requestId": "123",
            "response": {
                "status": 200,
                "headers": {"content-type": "application/json"},
                "mimeType": "application/json",
            },
        }

        capture._handle_response_received(params)

        req = capture._pending_requests["123"]
        assert req["status"] == 200
        assert req["mime_type"] == "application/json"

    def test_handle_loading_finished_moves_to_captured(self) -> None:
        """_handle_loading_finished moves request from pending to captured."""
        import time

        from trace_viewer.capture.network import NetworkCapture

        capture = NetworkCapture()
        # Add a pending request with start_time
        capture._pending_requests["123"] = {
            "request_id": "123",
            "url": "https://example.com/api",
            "method": "GET",
            "status": 200,
            "start_time": time.time() - 0.5,  # 500ms ago
            "response_headers": {},
            "size": 0,
        }

        params = {
            "requestId": "123",
            "encodedDataLength": 1024,
        }

        capture._handle_loading_finished(params)

        assert "123" not in capture._pending_requests
        assert len(capture._captured_requests) == 1
        req = capture._captured_requests[0]
        assert req["size"] == 1024
        assert req["duration_ms"] > 0

    def test_handle_loading_failed_moves_to_captured_with_error(self) -> None:
        """_handle_loading_failed moves request to captured with error info."""
        import time

        from trace_viewer.capture.network import NetworkCapture

        capture = NetworkCapture()
        capture._pending_requests["123"] = {
            "request_id": "123",
            "url": "https://example.com/api",
            "method": "GET",
            "status": None,
            "start_time": time.time() - 0.1,
            "response_headers": {},
        }

        params = {
            "requestId": "123",
            "errorText": "net::ERR_CONNECTION_REFUSED",
        }

        capture._handle_loading_failed(params)

        assert "123" not in capture._pending_requests
        assert len(capture._captured_requests) == 1
        req = capture._captured_requests[0]
        assert req["status"] == 0
        assert req["error"] == "net::ERR_CONNECTION_REFUSED"


class TestNetworkCaptureTruncateHeaders:
    """Tests for header truncation."""

    def test_truncate_headers_keeps_important_headers(self) -> None:
        """_truncate_headers keeps only important headers."""
        from trace_viewer.capture.network import NetworkCapture

        capture = NetworkCapture()
        headers = {
            "content-type": "application/json",
            "content-length": "1234",
            "x-custom-header": "value",
            "x-another-header": "value2",
            "accept": "application/json",
        }

        result = capture._truncate_headers(headers)

        assert "content-type" in result
        assert "content-length" in result
        assert "accept" in result
        assert "x-custom-header" not in result
        assert "x-another-header" not in result

    def test_truncate_headers_masks_authorization(self) -> None:
        """_truncate_headers masks sensitive headers."""
        from trace_viewer.capture.network import NetworkCapture

        capture = NetworkCapture()
        headers = {
            "authorization": "Bearer super-secret-token",
            "content-type": "application/json",
        }

        result = capture._truncate_headers(headers)

        assert result["authorization"] == "***MASKED***"
        assert result["content-type"] == "application/json"

    def test_truncate_headers_truncates_long_values(self) -> None:
        """_truncate_headers truncates overly long values."""
        from trace_viewer.capture.network import NetworkCapture

        capture = NetworkCapture()
        long_value = "x" * 300
        headers = {
            "content-type": long_value,
        }

        result = capture._truncate_headers(headers, max_value_length=100)

        assert len(result["content-type"]) == 103  # 100 + "..."
        assert result["content-type"].endswith("...")


class TestNetworkCaptureGetRequests:
    """Tests for get_requests method."""

    def test_get_requests_calls_capture(self) -> None:
        """get_requests calls capture and returns results."""
        from trace_viewer.capture.network import NetworkCapture

        capture = NetworkCapture()
        capture._cdp_enabled = True
        capture._captured_requests = [{"url": "https://example.com", "status": 200}]

        with patch.object(capture, "capture", return_value=[{"url": "test"}]) as mock:
            capture.get_requests()
            mock.assert_called_once()


class TestNetworkCaptureEdgeCases:
    """Edge case tests for NetworkCapture."""

    def test_capture_handles_exception_gracefully(self) -> None:
        """Capture handles exceptions and returns empty list."""
        from trace_viewer.capture.network import NetworkCapture

        with patch(
            "trace_viewer.capture.network.NetworkCapture._get_selenium_driver"
        ) as mock_driver:
            mock_driver_instance = MagicMock()
            mock_driver_instance.get_log = MagicMock(side_effect=Exception("Log error"))
            mock_driver.return_value = mock_driver_instance

            capture = NetworkCapture()
            capture._cdp_enabled = True
            result = capture._capture_from_selenium(mock_driver_instance)

            assert result == []

    def test_enable_handles_cdp_exception(self) -> None:
        """Enable handles CDP command exception gracefully."""
        from trace_viewer.capture.network import NetworkCapture

        with patch(
            "trace_viewer.capture.network.NetworkCapture._get_selenium_driver"
        ) as mock_driver:
            mock_driver_instance = MagicMock()
            mock_driver_instance.capabilities = {"browserName": "chrome"}
            mock_driver_instance.execute_cdp_cmd = MagicMock(side_effect=Exception("CDP error"))
            mock_driver.return_value = mock_driver_instance

            capture = NetworkCapture()
            result = capture.enable()

            assert result is False

    def test_double_enable_returns_true(self) -> None:
        """Calling enable twice returns True on second call."""
        from trace_viewer.capture.network import NetworkCapture

        capture = NetworkCapture()
        capture._cdp_enabled = True

        result = capture.enable()
        assert result is True

    def test_handle_response_for_unknown_request_does_nothing(self) -> None:
        """_handle_response_received ignores unknown request IDs."""
        from trace_viewer.capture.network import NetworkCapture

        capture = NetworkCapture()
        params = {
            "requestId": "unknown",
            "response": {"status": 200},
        }

        capture._handle_response_received(params)

        assert "unknown" not in capture._pending_requests

    def test_edge_browser_is_supported(self) -> None:
        """Edge browser is recognized as supporting CDP."""
        from trace_viewer.capture.network import NetworkCapture

        with patch(
            "trace_viewer.capture.network.NetworkCapture._get_selenium_driver"
        ) as mock_driver:
            mock_driver_instance = MagicMock()
            mock_driver_instance.capabilities = {"browserName": "msedge"}
            mock_driver_instance.execute_cdp_cmd = MagicMock()
            mock_driver.return_value = mock_driver_instance

            capture = NetworkCapture()
            result = capture.enable()

            assert result is True

    def test_chromium_browser_is_supported(self) -> None:
        """Chromium browser is recognized as supporting CDP."""
        from trace_viewer.capture.network import NetworkCapture

        with patch(
            "trace_viewer.capture.network.NetworkCapture._get_selenium_driver"
        ) as mock_driver:
            mock_driver_instance = MagicMock()
            mock_driver_instance.capabilities = {"browserName": "chromium"}
            mock_driver_instance.execute_cdp_cmd = MagicMock()
            mock_driver.return_value = mock_driver_instance

            capture = NetworkCapture()
            result = capture.enable()

            assert result is True
