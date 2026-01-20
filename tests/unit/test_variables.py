"""Unit tests for VariablesCapture module."""

import json
import os
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from trace_viewer.capture.variables import VariablesCapture


class TestIsSensitive:
    """Tests for the is_sensitive method."""

    def test_is_sensitive_detects_password(self) -> None:
        """Variables containing 'password' should be detected as sensitive."""
        capture = VariablesCapture()
        assert capture.is_sensitive("PASSWORD") is True
        assert capture.is_sensitive("user_password") is True
        assert capture.is_sensitive("password_field") is True

    def test_is_sensitive_detects_secret(self) -> None:
        """Variables containing 'secret' should be detected as sensitive."""
        capture = VariablesCapture()
        assert capture.is_sensitive("SECRET") is True
        assert capture.is_sensitive("client_secret") is True
        assert capture.is_sensitive("secret_value") is True

    def test_is_sensitive_detects_token(self) -> None:
        """Variables containing 'token' should be detected as sensitive."""
        capture = VariablesCapture()
        assert capture.is_sensitive("TOKEN") is True
        assert capture.is_sensitive("access_token") is True
        assert capture.is_sensitive("token_value") is True

    def test_is_sensitive_detects_api_key(self) -> None:
        """Variables containing 'api_key' or 'key' should be detected as sensitive."""
        capture = VariablesCapture()
        assert capture.is_sensitive("API_KEY") is True
        assert capture.is_sensitive("api_key_value") is True
        assert capture.is_sensitive("encryption_key") is True
        assert capture.is_sensitive("KEY") is True

    def test_is_sensitive_case_insensitive(self) -> None:
        """Sensitive detection should be case insensitive."""
        capture = VariablesCapture()
        assert capture.is_sensitive("PASSWORD") is True
        assert capture.is_sensitive("password") is True
        assert capture.is_sensitive("Password") is True
        assert capture.is_sensitive("PaSsWoRd") is True
        assert capture.is_sensitive("SECRET") is True
        assert capture.is_sensitive("secret") is True
        assert capture.is_sensitive("Secret") is True

    def test_is_sensitive_detects_credential(self) -> None:
        """Variables containing 'credential' should be detected as sensitive."""
        capture = VariablesCapture()
        assert capture.is_sensitive("CREDENTIAL") is True
        assert capture.is_sensitive("user_credential") is True
        assert capture.is_sensitive("credentials") is True

    def test_is_sensitive_detects_auth(self) -> None:
        """Variables containing 'auth' should be detected as sensitive."""
        capture = VariablesCapture()
        assert capture.is_sensitive("AUTH") is True
        assert capture.is_sensitive("auth_header") is True
        assert capture.is_sensitive("authentication") is True

    def test_is_sensitive_returns_false_for_normal_vars(self) -> None:
        """Normal variables should not be detected as sensitive."""
        capture = VariablesCapture()
        assert capture.is_sensitive("USERNAME") is False
        assert capture.is_sensitive("URL") is False
        assert capture.is_sensitive("BROWSER") is False
        assert capture.is_sensitive("TIMEOUT") is False


class TestMaskValue:
    """Tests for the mask_value method."""

    def test_mask_value_masks_sensitive(self) -> None:
        """Sensitive variables should be masked."""
        capture = VariablesCapture()
        assert capture.mask_value("PASSWORD", "secret123") == "***MASKED***"
        assert capture.mask_value("API_KEY", "abc123") == "***MASKED***"
        assert capture.mask_value("secret_token", "xyz789") == "***MASKED***"

    def test_mask_value_truncates_long_values(self) -> None:
        """Long values should be truncated."""
        capture = VariablesCapture()
        long_value = "x" * 600
        result = capture.mask_value("NORMAL_VAR", long_value)
        assert len(result) == capture.MAX_VALUE_LENGTH + len("...[truncated]")
        assert result.endswith("...[truncated]")
        assert result.startswith("x" * 100)

    def test_mask_value_preserves_short_values(self) -> None:
        """Short values should be preserved as-is."""
        capture = VariablesCapture()
        assert capture.mask_value("USERNAME", "john") == "john"
        assert capture.mask_value("URL", "https://example.com") == "https://example.com"

    def test_mask_value_serializes_dict(self) -> None:
        """Dictionary values should be serialized to JSON."""
        capture = VariablesCapture()
        result = capture.mask_value("CONFIG", {"timeout": 30, "retry": 3})
        assert result == '{"timeout": 30, "retry": 3}'

    def test_mask_value_serializes_list(self) -> None:
        """List values should be serialized to JSON."""
        capture = VariablesCapture()
        result = capture.mask_value("ITEMS", ["a", "b", "c"])
        assert result == '["a", "b", "c"]'

    def test_mask_value_handles_non_serializable(self) -> None:
        """Non-serializable values should return a placeholder."""
        capture = VariablesCapture()

        # Mock _serialize_value to raise an exception
        with patch.object(capture, "_serialize_value", side_effect=Exception("Cannot serialize")):
            result = capture.mask_value("OBJECT", object())
            assert result == "<non-serializable>"


class TestSerializeValue:
    """Tests for the _serialize_value method."""

    def test_serialize_string_unchanged(self) -> None:
        """String values should be returned unchanged."""
        capture = VariablesCapture()
        assert capture._serialize_value("hello") == "hello"
        assert capture._serialize_value("test value") == "test value"

    def test_serialize_int(self) -> None:
        """Integer values should be serialized to JSON."""
        capture = VariablesCapture()
        assert capture._serialize_value(42) == "42"

    def test_serialize_float(self) -> None:
        """Float values should be serialized to JSON."""
        capture = VariablesCapture()
        assert capture._serialize_value(3.14) == "3.14"

    def test_serialize_bool(self) -> None:
        """Boolean values should be serialized to JSON."""
        capture = VariablesCapture()
        assert capture._serialize_value(True) == "true"
        assert capture._serialize_value(False) == "false"

    def test_serialize_none(self) -> None:
        """None values should be serialized to JSON null."""
        capture = VariablesCapture()
        assert capture._serialize_value(None) == "null"

    def test_serialize_unicode(self) -> None:
        """Unicode characters should be preserved."""
        capture = VariablesCapture()
        assert capture._serialize_value("cafe") == "cafe"
        # For non-string types with unicode, JSON serialization is used
        result = capture._serialize_value(["cafe", "resume"])
        assert "cafe" in result
        assert "resume" in result


@pytest.fixture
def mock_builtin() -> MagicMock:
    """Create a mock BuiltIn instance."""
    return MagicMock()


@pytest.fixture
def capture_with_mock_builtin(mock_builtin: MagicMock) -> VariablesCapture:
    """Create a VariablesCapture instance with a mocked BuiltIn."""
    capture = VariablesCapture()
    capture._builtin = mock_builtin
    return capture


class TestCapture:
    """Tests for the capture method."""

    def test_capture_groups_by_type(
        self, capture_with_mock_builtin: VariablesCapture, mock_builtin: MagicMock
    ) -> None:
        """Variables should be grouped by type (scalar, list, dict)."""
        mock_variables: dict[str, Any] = {
            "${USERNAME}": "testuser",
            "${PASSWORD}": "secret123",
            "@{ITEMS}": ["a", "b", "c"],
            "&{CONFIG}": {"timeout": "30s"},
        }

        mock_builtin.get_variables.return_value = mock_variables
        result = capture_with_mock_builtin.capture()

        assert "scalar" in result
        assert "list" in result
        assert "dict" in result
        assert result["scalar"]["USERNAME"] == "testuser"
        assert result["scalar"]["PASSWORD"] == "***MASKED***"
        assert "ITEMS" in result["list"]
        assert "CONFIG" in result["dict"]

    def test_capture_handles_exception(
        self, capture_with_mock_builtin: VariablesCapture, mock_builtin: MagicMock
    ) -> None:
        """Capture should return empty dicts on exception."""
        mock_builtin.get_variables.side_effect = RuntimeError("No RF context")
        result = capture_with_mock_builtin.capture()

        assert result == {"scalar": {}, "list": {}, "dict": {}}

    def test_capture_skips_internal_variables(
        self, capture_with_mock_builtin: VariablesCapture, mock_builtin: MagicMock
    ) -> None:
        """Internal RF variables should be skipped."""
        mock_variables: dict[str, Any] = {
            "${USERNAME}": "testuser",
            "${CURDIR}": "/path/to/tests",
            "${EXECDIR}": "/path/to/exec",
            "${TEMPDIR}": "/tmp",
            "${_internal}": "hidden",
        }

        mock_builtin.get_variables.return_value = mock_variables
        result = capture_with_mock_builtin.capture()

        assert "USERNAME" in result["scalar"]
        assert "CURDIR" not in result["scalar"]
        assert "EXECDIR" not in result["scalar"]
        assert "TEMPDIR" not in result["scalar"]
        assert "_internal" not in result["scalar"]

    def test_capture_ignores_unknown_prefixes(
        self, capture_with_mock_builtin: VariablesCapture, mock_builtin: MagicMock
    ) -> None:
        """Variables without valid prefixes should be ignored."""
        mock_variables: dict[str, Any] = {
            "${USERNAME}": "testuser",
            "UNKNOWN": "value",
            "%{ENV_VAR}": "envvalue",
        }

        mock_builtin.get_variables.return_value = mock_variables
        result = capture_with_mock_builtin.capture()

        assert "USERNAME" in result["scalar"]
        assert "UNKNOWN" not in result["scalar"]
        assert "ENV_VAR" not in result["scalar"]


class TestCaptureToFile:
    """Tests for the capture_to_file method."""

    def test_capture_to_file(
        self, capture_with_mock_builtin: VariablesCapture, mock_builtin: MagicMock
    ) -> None:
        """capture_to_file should write JSON to the specified file."""
        mock_variables: dict[str, Any] = {
            "${USERNAME}": "testuser",
            "${PASSWORD}": "secret123",
        }

        mock_builtin.get_variables.return_value = mock_variables

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp_file:
            filepath = tmp_file.name

        try:
            result = capture_with_mock_builtin.capture_to_file(filepath)
            assert result is True

            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            assert data["scalar"]["USERNAME"] == "testuser"
            assert data["scalar"]["PASSWORD"] == "***MASKED***"
        finally:
            os.unlink(filepath)

    def test_capture_to_file_returns_false_on_error(
        self, capture_with_mock_builtin: VariablesCapture, mock_builtin: MagicMock
    ) -> None:
        """capture_to_file should return False on IO error."""
        mock_builtin.get_variables.return_value = {}

        # Try to write to an invalid path
        result = capture_with_mock_builtin.capture_to_file("/nonexistent/directory/file.json")
        assert result is False

    def test_capture_to_file_creates_valid_json(
        self, capture_with_mock_builtin: VariablesCapture, mock_builtin: MagicMock
    ) -> None:
        """The output file should contain valid JSON."""
        mock_variables: dict[str, Any] = {
            "${UNICODE}": "cafe resume",
            "@{ITEMS}": ["item1", "item2"],
            "&{CONFIG}": {"key": "value"},
        }

        mock_builtin.get_variables.return_value = mock_variables

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp_file:
            filepath = tmp_file.name

        try:
            capture_with_mock_builtin.capture_to_file(filepath)

            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            assert "scalar" in data
            assert "list" in data
            assert "dict" in data
        finally:
            os.unlink(filepath)


class TestBuiltInProperty:
    """Tests for the builtin property lazy loading."""

    def test_builtin_lazy_loads(self) -> None:
        """The builtin property should lazy-load the BuiltIn library."""
        capture = VariablesCapture()
        assert capture._builtin is None

        # Patch BuiltIn at its source location since it's imported inline
        mock_builtin_instance = MagicMock()
        mock_builtin_class = MagicMock(return_value=mock_builtin_instance)
        with patch.dict(
            "sys.modules",
            {"robot.libraries.BuiltIn": MagicMock(BuiltIn=mock_builtin_class)},
        ):
            result = capture.builtin

            assert result is mock_builtin_instance
            assert capture._builtin is mock_builtin_instance

    def test_builtin_caches_instance(self) -> None:
        """The builtin property should cache the instance."""
        capture = VariablesCapture()

        # Pre-set the _builtin to simulate caching
        mock_instance = MagicMock()
        capture._builtin = mock_instance

        # Access the property twice
        result1 = capture.builtin
        result2 = capture.builtin

        # Should return the cached instance
        assert result1 is mock_instance
        assert result2 is mock_instance
        assert result1 is result2
