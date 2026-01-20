"""Trace storage writer for persisting trace data to disk.

This module provides the TraceWriter class which manages the structured
storage of Robot Framework trace data including manifests, keyword metadata,
variables, and screenshots.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


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

        Args:
            test_name: Name of the test being traced.

        Returns:
            Path to the created trace directory.

        Example:
            >>> writer = TraceWriter("./traces")
            >>> path = writer.create_trace("Login Test")
            >>> path.name  # e.g., 'login_test_20250119_143022'
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = self.slugify(test_name)
        trace_name = f"{slug}_{timestamp}"
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
