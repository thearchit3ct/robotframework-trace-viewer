"""Capture Robot Framework variables with automatic sensitive data masking."""

import json
from typing import Any, Optional


class VariablesCapture:
    """Capture Robot Framework variables with automatic sensitive data masking.

    This class provides functionality to capture all Robot Framework variables
    during test execution, automatically masking sensitive data like passwords,
    tokens, and API keys.

    Example:
        >>> capture = VariablesCapture()
        >>> variables = capture.capture()
        >>> print(variables["scalar"])
        {"USERNAME": "testuser", "PASSWORD": "***MASKED***"}
    """

    SENSITIVE_PATTERNS: tuple[str, ...] = (
        "password",
        "secret",
        "token",
        "key",
        "credential",
        "auth",
        "api_key",
    )
    MASKED_VALUE: str = "***MASKED***"
    MAX_VALUE_LENGTH: int = 500

    def __init__(self) -> None:
        """Initialize the VariablesCapture instance."""
        self._builtin: Optional[Any] = None

    @property
    def builtin(self) -> Any:
        """Lazy-load and return the Robot Framework BuiltIn library.

        Returns:
            BuiltIn library instance for accessing RF variables.

        Raises:
            RuntimeError: If called outside of Robot Framework context.
        """
        if self._builtin is None:
            from robot.libraries.BuiltIn import BuiltIn

            self._builtin = BuiltIn()
        return self._builtin

    def is_sensitive(self, name: str) -> bool:
        """Check if variable name indicates sensitive data.

        Args:
            name: The variable name to check.

        Returns:
            True if the variable name contains any sensitive pattern,
            False otherwise.

        Example:
            >>> capture = VariablesCapture()
            >>> capture.is_sensitive("PASSWORD")
            True
            >>> capture.is_sensitive("USERNAME")
            False
        """
        name_lower = name.lower()
        return any(pattern in name_lower for pattern in self.SENSITIVE_PATTERNS)

    def mask_value(self, name: str, value: Any) -> str:
        """Mask value if sensitive, otherwise serialize.

        Args:
            name: The variable name (used to determine if sensitive).
            value: The value to potentially mask and serialize.

        Returns:
            The masked placeholder if sensitive, otherwise the serialized
            and potentially truncated value.

        Example:
            >>> capture = VariablesCapture()
            >>> capture.mask_value("PASSWORD", "secret123")
            '***MASKED***'
            >>> capture.mask_value("USERNAME", "john")
            'john'
        """
        if self.is_sensitive(name):
            return self.MASKED_VALUE
        try:
            serialized = self._serialize_value(value)
            if len(serialized) > self.MAX_VALUE_LENGTH:
                return serialized[: self.MAX_VALUE_LENGTH] + "...[truncated]"
            return serialized
        except Exception:
            return "<non-serializable>"

    def _serialize_value(self, value: Any) -> str:
        """Serialize a value to string.

        Args:
            value: The value to serialize.

        Returns:
            String representation of the value.
        """
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value)

    def capture(self) -> dict[str, dict[str, str]]:
        """Capture all RF variables grouped by type.

        Retrieves all Robot Framework variables and organizes them by type
        (scalar, list, dict). Sensitive variables are automatically masked.

        Returns:
            Dictionary with three keys: "scalar", "list", and "dict".
            Each contains a dictionary mapping variable names to their
            (potentially masked) values.

        Example:
            >>> capture = VariablesCapture()
            >>> result = capture.capture()
            >>> result
            {
                "scalar": {"USERNAME": "testuser", "PASSWORD": "***MASKED***"},
                "list": {"ITEMS": '["a", "b", "c"]'},
                "dict": {"CONFIG": '{"timeout": "30s"}'}
            }
        """
        try:
            all_vars = self.builtin.get_variables()
        except Exception:
            return {"scalar": {}, "list": {}, "dict": {}}

        result: dict[str, dict[str, str]] = {"scalar": {}, "list": {}, "dict": {}}

        for full_name, value in all_vars.items():
            # Parse variable type and name from RF format
            if full_name.startswith("&{"):
                var_type = "dict"
                name = full_name[2:-1]  # Remove &{ and }
            elif full_name.startswith("@{"):
                var_type = "list"
                name = full_name[2:-1]  # Remove @{ and }
            elif full_name.startswith("${"):
                var_type = "scalar"
                name = full_name[2:-1]  # Remove ${ and }
            else:
                continue

            # Skip internal RF variables
            if name.startswith("_") or name in ("CURDIR", "EXECDIR", "TEMPDIR"):
                continue

            result[var_type][name] = self.mask_value(name, value)

        return result

    def capture_to_file(self, filepath: str) -> bool:
        """Capture and save variables to a JSON file.

        Args:
            filepath: Path to the output JSON file.

        Returns:
            True if the file was written successfully, False otherwise.

        Example:
            >>> capture = VariablesCapture()
            >>> success = capture.capture_to_file("/tmp/variables.json")
            >>> print(success)
            True
        """
        data = self.capture()
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except OSError:
            return False
