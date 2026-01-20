"""Trace storage writer for persisting trace data to disk.

This module provides the TraceWriter class which manages the structured
storage of Robot Framework trace data including manifests, keyword metadata,
variables, and screenshots.

Supports parallel execution with Pabot by including process identifiers
in trace directory names to avoid conflicts.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


def is_pabot_execution() -> bool:
    """Detect if the current execution is running under Pabot.

    Checks for Pabot-specific environment variables that are set during
    parallel test execution.

    Returns:
        True if running under Pabot, False otherwise.

    Example:
        >>> # When running under Pabot:
        >>> is_pabot_execution()
        True
        >>> # When running standalone:
        >>> is_pabot_execution()
        False
    """
    return (
        os.environ.get("PABOTEXECUTIONPOOLID") is not None
        or os.environ.get("PABOTQUEUEINDEX") is not None
        or os.environ.get("PABOT_QUEUE_INDEX") is not None
        or os.environ.get("PABOTLIBRARYSCOPE") is not None
    )


def get_pabot_id() -> Optional[str]:
    """Get the Pabot execution identifier for the current process.

    Returns the most specific Pabot identifier available, preferring
    PABOTQUEUEINDEX over PABOTEXECUTIONPOOLID.

    Returns:
        The Pabot identifier string (e.g., "1", "2"), or None if not
        running under Pabot.

    Example:
        >>> # When PABOTQUEUEINDEX=3
        >>> get_pabot_id()
        '3'
        >>> # When not running under Pabot:
        >>> get_pabot_id()
        None
    """
    # Try different Pabot environment variables in order of preference
    pabot_id = os.environ.get("PABOTQUEUEINDEX")
    if pabot_id is not None:
        return pabot_id

    pabot_id = os.environ.get("PABOT_QUEUE_INDEX")
    if pabot_id is not None:
        return pabot_id

    pabot_id = os.environ.get("PABOTEXECUTIONPOOLID")
    if pabot_id is not None:
        return pabot_id

    return None


def get_process_identifier() -> Optional[str]:
    """Get a unique process identifier for parallel execution safety.

    When running under Pabot, returns the Pabot-specific identifier.
    This identifier can be used to create unique trace directory names
    that avoid conflicts during parallel test execution.

    Returns:
        A unique process identifier string if running in parallel mode,
        None if running in standard sequential mode.

    Example:
        >>> # When running under Pabot with PABOTQUEUEINDEX=2:
        >>> get_process_identifier()
        'pabot2'
        >>> # When running standalone:
        >>> get_process_identifier()
        None
    """
    pabot_id = get_pabot_id()
    if pabot_id is not None:
        return f"pabot{pabot_id}"
    return None


class TraceWriter:
    """Manages structured trace storage on disk.

    The TraceWriter creates and manages a directory structure for storing
    trace data captured during Robot Framework test execution.

    Directory structure:
        traces/
          test_name_20250119_143022/
            manifest.json
            keywords/
              001_open_browser/
                screenshot.png
                variables.json
                metadata.json
              002_go_to/
                ...

    Attributes:
        base_dir: Base directory for all trace storage.

    Example:
        >>> writer = TraceWriter("./traces")
        >>> trace_dir = writer.create_trace("Login Test")
        >>> kw_dir = writer.create_keyword_dir("Open Browser")
        >>> writer.write_keyword_metadata(kw_dir, {"name": "Open Browser", "status": "PASS"})
    """

    def __init__(self, base_dir: str = "./traces"):
        """Initialize TraceWriter with base directory.

        Args:
            base_dir: Base directory path for trace storage. Will be created
                if it doesn't exist.
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._current_trace_dir: Optional[Path] = None
        self._keyword_counter: int = 0

    @staticmethod
    def slugify(text: str, max_length: int = 50) -> str:
        """Convert text to a valid filename.

        Transforms arbitrary text into a safe filename by:
        - Converting to lowercase
        - Removing special characters (keeping alphanumeric, whitespace, hyphens)
        - Replacing whitespace and hyphens with underscores
        - Truncating to max_length

        Args:
            text: The text to convert to a slug.
            max_length: Maximum length of the resulting slug.

        Returns:
            A filesystem-safe string suitable for use as a filename.
            Returns 'unnamed' if the input produces an empty slug.

        Examples:
            >>> TraceWriter.slugify("Login Should Work!")
            'login_should_work'
            >>> TraceWriter.slugify("Test with CAPS and 123")
            'test_with_caps_and_123'
            >>> TraceWriter.slugify("a" * 100, max_length=10)
            'aaaaaaaaaa'
        """
        # Remove special characters, keep alphanumeric, whitespace, and hyphens
        slug = re.sub(r"[^\w\s-]", "", text.lower())
        # Replace whitespace and hyphens with underscores, strip trailing underscores
        slug = re.sub(r"[-\s]+", "_", slug).strip("_")
        # Return slug truncated to max_length, or 'unnamed' if empty
        return slug[:max_length] if slug else "unnamed"

    def create_trace(self, test_name: str) -> Path:
        """Create a new trace directory for a test.

        Creates a timestamped directory for storing all trace data
        associated with a single test execution. Also creates the
        keywords subdirectory.

        When running under Pabot (parallel execution), the directory name
        includes a process identifier to avoid conflicts between parallel
        test executions.

        Args:
            test_name: Name of the test being traced.

        Returns:
            Path to the created trace directory.

        Example:
            >>> writer = TraceWriter("./traces")
            >>> path = writer.create_trace("Login Test")
            >>> path.name  # e.g., 'login_test_20250119_143022'
            >>> # Under Pabot: 'login_test_20250119_143022_pabot1'
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = self.slugify(test_name)

        # Include process identifier for Pabot parallel execution
        process_id = get_process_identifier()
        trace_name = f"{slug}_{timestamp}_{process_id}" if process_id else f"{slug}_{timestamp}"

        self._current_trace_dir = self.base_dir / trace_name
        self._current_trace_dir.mkdir(parents=True, exist_ok=True)
        (self._current_trace_dir / "keywords").mkdir(exist_ok=True)
        self._keyword_counter = 0
        return self._current_trace_dir

    def create_keyword_dir(self, keyword_name: str) -> Path:
        """Create directory for a keyword within current trace.

        Creates a numbered directory for storing data associated with
        a single keyword execution. Directories are numbered sequentially
        (001, 002, etc.) to preserve execution order.

        Args:
            keyword_name: Name of the keyword.

        Returns:
            Path to the created keyword directory.

        Raises:
            RuntimeError: If no active trace exists (create_trace not called).

        Example:
            >>> writer.create_trace("My Test")
            >>> kw1 = writer.create_keyword_dir("Open Browser")
            >>> kw1.name  # '001_open_browser'
            >>> kw2 = writer.create_keyword_dir("Go To")
            >>> kw2.name  # '002_go_to'
        """
        if self._current_trace_dir is None:
            raise RuntimeError("No active trace. Call create_trace first.")
        self._keyword_counter += 1
        slug = self.slugify(keyword_name, max_length=40)
        dir_name = f"{self._keyword_counter:03d}_{slug}"
        keyword_dir = self._current_trace_dir / "keywords" / dir_name
        keyword_dir.mkdir(parents=True, exist_ok=True)
        return keyword_dir

    def write_manifest(self, data: dict[str, Any]) -> Path:
        """Write manifest.json for current trace.

        The manifest contains metadata about the test execution including
        test name, timing information, status, and capture settings.

        Args:
            data: Dictionary of manifest data to serialize as JSON.

        Returns:
            Path to the written manifest file.

        Raises:
            RuntimeError: If no active trace exists.
        """
        if self._current_trace_dir is None:
            raise RuntimeError("No active trace.")
        manifest_path = self._current_trace_dir / "manifest.json"
        self._write_json_atomic(manifest_path, data)
        return manifest_path

    def write_keyword_metadata(self, keyword_dir: Path, data: dict[str, Any]) -> Path:
        """Write metadata.json for a keyword.

        Keyword metadata includes information such as name, library,
        arguments, timing, status, and hierarchy information.

        Args:
            keyword_dir: Path to the keyword directory.
            data: Dictionary of metadata to serialize as JSON.

        Returns:
            Path to the written metadata file.
        """
        metadata_path = keyword_dir / "metadata.json"
        self._write_json_atomic(metadata_path, data)
        return metadata_path

    def write_keyword_variables(self, keyword_dir: Path, data: dict[str, Any]) -> Path:
        """Write variables.json for a keyword.

        Contains a snapshot of Robot Framework variables at the time
        of keyword execution. Sensitive variables should be masked
        before being passed to this method.

        Args:
            keyword_dir: Path to the keyword directory.
            data: Dictionary of variables to serialize as JSON.

        Returns:
            Path to the written variables file.
        """
        variables_path = keyword_dir / "variables.json"
        self._write_json_atomic(variables_path, data)
        return variables_path

    def write_screenshot(self, keyword_dir: Path, png_data: bytes) -> Path:
        """Write screenshot.png for a keyword.

        Writes the raw PNG bytes to the keyword directory.

        Args:
            keyword_dir: Path to the keyword directory.
            png_data: Raw PNG image bytes.

        Returns:
            Path to the written screenshot file.
        """
        screenshot_path = keyword_dir / "screenshot.png"
        screenshot_path.write_bytes(png_data)
        return screenshot_path

    def write_console_logs(self, keyword_dir: Path, logs: list[dict[str, Any]]) -> Path:
        """Write console.json for a keyword.

        Contains browser console logs captured during keyword execution.
        Each log entry includes level, message, source, and timestamp.

        Args:
            keyword_dir: Path to the keyword directory.
            logs: List of console log entries.

        Returns:
            Path to the written console logs file.
        """
        console_path = keyword_dir / "console.json"
        self._write_json_atomic(console_path, {"logs": logs})
        return console_path

    def write_dom_snapshot(self, keyword_dir: Path, html: str) -> Path:
        """Write dom.html for a keyword.

        Contains the sanitized DOM snapshot captured during keyword execution.
        Script tags are removed from the HTML for security before writing.

        Args:
            keyword_dir: Path to the keyword directory.
            html: The sanitized HTML content of the DOM snapshot.

        Returns:
            Path to the written DOM snapshot file.
        """
        dom_path = keyword_dir / "dom.html"
        dom_path.write_text(html, encoding="utf-8")
        return dom_path

    def write_network_requests(self, keyword_dir: Path, requests: list[dict[str, Any]]) -> Path:
        """Write network.json for a keyword.

        Contains network requests captured during keyword execution via CDP.
        Each request entry includes URL, method, status, headers, and timing.

        Args:
            keyword_dir: Path to the keyword directory.
            requests: List of network request entries.

        Returns:
            Path to the written network file.
        """
        network_path = keyword_dir / "network.json"
        self._write_json_atomic(network_path, {"requests": requests})
        return network_path

    def _write_json_atomic(self, path: Path, data: dict[str, Any]) -> None:
        """Write JSON atomically using write-to-tmp-then-rename pattern.

        This ensures that the file is never in a partial/corrupted state.
        If the process crashes during write, only the .tmp file is affected.

        Args:
            path: Target path for the JSON file.
            data: Dictionary to serialize as JSON.
        """
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        tmp_path.rename(path)

    def get_current_trace_dir(self) -> Optional[Path]:
        """Get the current active trace directory.

        Returns:
            Path to the current trace directory, or None if no trace is active.
        """
        return self._current_trace_dir

    def get_keyword_counter(self) -> int:
        """Get the current keyword counter value.

        Returns:
            The number of keywords created in the current trace.
        """
        return self._keyword_counter
