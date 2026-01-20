"""TraceListener - Robot Framework Listener API v3 implementation for trace capture.

This module provides the main listener that hooks into Robot Framework's execution
and captures trace data (keywords, timing, status) for later visualization.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from robot.api.interfaces import ListenerV3

from trace_viewer.capture.screenshot import ScreenshotCapture
from trace_viewer.capture.variables import VariablesCapture
from trace_viewer.storage.trace_writer import TraceWriter

# ViewerGenerator may not exist yet - import conditionally
try:
    from trace_viewer.viewer.generator import ViewerGenerator

    _HAS_VIEWER_GENERATOR = True
except ImportError:
    _HAS_VIEWER_GENERATOR = False
    ViewerGenerator = None  # type: ignore[misc, assignment]

logger = logging.getLogger(__name__)


def slugify(text: str, max_length: int = 50) -> str:
    """Convert text to a valid filename-safe slug.

    Args:
        text: The text to convert to a slug.
        max_length: Maximum length of the resulting slug.

    Returns:
        A lowercase string with only alphanumeric characters, underscores, and hyphens.

    Examples:
        >>> slugify("Login Should Work")
        'login_should_work'
        >>> slugify("Test with special chars: @#$%!")
        'test_with_special_chars'
        >>> slugify("  Multiple   Spaces  ")
        'multiple_spaces'
    """
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and special characters with underscores
    text = re.sub(r"[^\w\s-]", "", text)
    # Replace whitespace sequences with single underscore
    text = re.sub(r"[\s_]+", "_", text)
    # Remove leading/trailing underscores
    text = text.strip("_")
    # Truncate to max length
    if len(text) > max_length:
        text = text[:max_length].rstrip("_")
    return text


def get_iso_timestamp() -> str:
    """Get current timestamp in ISO 8601 format with timezone.

    Returns:
        ISO 8601 formatted timestamp string with UTC timezone.

    Example:
        >>> # Returns something like: '2025-01-19T14:30:22.123456+00:00'
    """
    return datetime.now(timezone.utc).isoformat()


def write_json_atomic(file_path: Path, data: dict[str, Any]) -> None:
    """Write JSON data to file atomically.

    Writes to a temporary file first, then renames to the target path.
    This prevents partial writes from corrupting the file.

    Args:
        file_path: The target file path.
        data: The dictionary to serialize as JSON.
    """
    # Create parent directory if needed
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temporary file in the same directory (for atomic rename)
    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp", prefix=file_path.stem + "_", dir=file_path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        # Atomic rename
        shutil.move(tmp_path, file_path)
    except Exception:
        # Clean up temp file on error
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


CaptureMode = Literal["full", "on_failure", "disabled"]


class TraceListener(ListenerV3):
    """Robot Framework Listener for capturing execution traces.

    This listener captures keyword execution data and creates a structured
    trace that can be visualized later. It implements the Listener API v3.

    Args:
        output_dir: Directory where trace data will be saved.
        capture_mode: When to capture screenshots and variables.
            - "full": Capture at every keyword end.
            - "on_failure": Only capture when a keyword fails.
            - "disabled": No screenshot/variable capture.

    Attributes:
        ROBOT_LISTENER_API_VERSION: API version (always 3).

    Example:
        ```bash
        robot --listener trace_viewer.TraceListener:output_dir=./traces tests/
        ```
    """

    ROBOT_LISTENER_API_VERSION = 3

    def __init__(
        self,
        output_dir: str = "./traces",
        capture_mode: str = "full",
    ) -> None:
        """Initialize the TraceListener.

        Args:
            output_dir: Directory where trace data will be saved.
            capture_mode: Capture mode ('full', 'on_failure', or 'disabled').
        """
        self.output_dir = Path(output_dir)
        self.capture_mode: CaptureMode = (
            capture_mode  # type: ignore[assignment]
            if capture_mode in ("full", "on_failure", "disabled")
            else "full"
        )

        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize capture modules
        self.trace_writer = TraceWriter(str(self.output_dir))
        self.screenshot_capture = ScreenshotCapture()
        self.variables_capture = VariablesCapture()
        self.viewer_generator: Any | None = None
        if _HAS_VIEWER_GENERATOR and ViewerGenerator is not None:
            self.viewer_generator = ViewerGenerator()

        # Suite-level state
        self.trace_data: dict[str, Any] = {}
        self.suite_name: str = ""
        self.suite_source: str = ""

        # Test-level state
        self.current_test: dict[str, Any] = {}
        self.current_test_dir: Path | None = None
        self.keyword_index: int = 0

        # Keyword tracking for nesting
        self.keyword_stack: list[dict[str, Any]] = []

        # Track current keyword directory for capture
        self._current_keyword_dir: Path | None = None

    def start_suite(self, data: Any, result: Any) -> None:
        """Called when a test suite starts.

        Creates the trace folder structure and initializes trace_data.

        Args:
            data: Suite execution data (contains name, source, etc.).
            result: Suite result object (for status tracking).
        """
        self.suite_name = data.name
        self.suite_source = str(data.source) if data.source else ""

        self.trace_data = {
            "version": "1.0.0",
            "tool_version": "0.1.3",
            "suite_name": self.suite_name,
            "suite_source": self.suite_source,
            "capture_mode": self.capture_mode,
            "tests": [],
        }

    def start_test(self, data: Any, result: Any) -> None:
        """Called when a test case starts.

        Creates a unique folder for the test based on name and timestamp.
        Initializes the current_test data structure.

        Args:
            data: Test execution data (contains name, doc, tags, etc.).
            result: Test result object (for status tracking).
        """
        # Use trace_writer to create the trace directory
        self.current_test_dir = self.trace_writer.create_trace(data.name)
        folder_name = self.current_test_dir.name

        # Initialize test data
        self.current_test = {
            "name": data.name,
            "longname": data.longname,
            "doc": data.doc or "",
            "tags": list(data.tags) if data.tags else [],
            "start_time": get_iso_timestamp(),
            "end_time": None,
            "status": None,
            "message": None,
            "folder": folder_name,
            "keywords": [],
        }

        # Reset keyword tracking
        self.keyword_index = 0
        self.keyword_stack = []

    def start_keyword(self, data: Any, result: Any) -> None:
        """Called when a keyword starts execution.

        Creates a folder for the keyword and records start information.
        Handles nesting by tracking parent keywords.

        Args:
            data: Keyword execution data (name, args, assign, etc.).
            result: Keyword result object (for status tracking).
        """
        if self.current_test_dir is None:
            return

        # Increment keyword index
        self.keyword_index += 1

        # Use trace_writer to create keyword directory
        keyword_dir = self.trace_writer.create_keyword_dir(data.name)
        folder_name = keyword_dir.name
        self._current_keyword_dir = keyword_dir

        # Determine nesting level and parent
        level = len(self.keyword_stack) + 1
        parent_keyword = self.keyword_stack[-1]["name"] if self.keyword_stack else None

        # Build keyword data
        keyword_data: dict[str, Any] = {
            "index": self.keyword_index,
            "name": data.name,
            "library": getattr(data, "libname", "") or "",
            "type": getattr(data, "type", "KEYWORD"),
            "args": list(data.args) if data.args else [],
            "assign": list(data.assign) if data.assign else [],
            "start_time": get_iso_timestamp(),
            "end_time": None,
            "duration_ms": None,
            "status": None,
            "message": None,
            "parent_keyword": parent_keyword,
            "level": level,
            "folder": folder_name,
        }

        # Push to stack for nesting tracking
        self.keyword_stack.append(keyword_data)

    def _should_capture(self, status: str) -> bool:
        """Determine whether to capture screenshot/variables based on capture_mode.

        Args:
            status: The keyword status ('PASS', 'FAIL', etc.).

        Returns:
            True if capture should be performed, False otherwise.
        """
        if self.capture_mode == "disabled":
            return False
        if self.capture_mode == "on_failure":
            return status == "FAIL"
        # capture_mode == "full"
        return True

    def end_keyword(self, data: Any, result: Any) -> None:
        """Called when a keyword finishes execution.

        Records end time, status, and message. Saves metadata.json.
        Captures screenshots and variables based on capture_mode.

        Args:
            data: Keyword execution data.
            result: Keyword result object (contains status, message, elapsed_time).
        """
        if self.current_test_dir is None or not self.keyword_stack:
            return

        # Pop keyword from stack
        keyword_data = self.keyword_stack.pop()

        # Calculate duration
        end_time = get_iso_timestamp()
        keyword_data["end_time"] = end_time

        # Get elapsed time from result if available, otherwise calculate
        if hasattr(result, "elapsed_time"):
            # elapsed_time is a timedelta in RF 7+
            elapsed = result.elapsed_time
            if hasattr(elapsed, "total_seconds"):
                keyword_data["duration_ms"] = int(elapsed.total_seconds() * 1000)
            else:
                keyword_data["duration_ms"] = int(elapsed * 1000)
        else:
            keyword_data["duration_ms"] = 0

        # Record status and message
        status = str(result.status) if hasattr(result, "status") else "UNKNOWN"
        keyword_data["status"] = status
        keyword_data["message"] = str(result.message) if hasattr(result, "message") else ""

        # Get keyword directory
        keyword_dir = self.current_test_dir / "keywords" / keyword_data["folder"]

        # Capture screenshot and variables if capture_mode allows
        if self._should_capture(status):
            # Capture screenshot
            try:
                screenshot_data = self.screenshot_capture.capture()
                if screenshot_data is not None:
                    self.trace_writer.write_screenshot(keyword_dir, screenshot_data)
                    keyword_data["has_screenshot"] = True
                else:
                    keyword_data["has_screenshot"] = False
            except Exception as e:
                logger.debug("Screenshot capture failed: %s", e)
                keyword_data["has_screenshot"] = False

            # Capture variables
            try:
                variables = self.variables_capture.capture()
                if variables:
                    self.trace_writer.write_keyword_variables(keyword_dir, variables)
                    keyword_data["has_variables"] = True
                else:
                    keyword_data["has_variables"] = False
            except Exception as e:
                logger.debug("Variables capture failed: %s", e)
                keyword_data["has_variables"] = False
        else:
            keyword_data["has_screenshot"] = False
            keyword_data["has_variables"] = False

        # Save metadata.json in keyword folder using trace_writer
        self.trace_writer.write_keyword_metadata(keyword_dir, keyword_data)

        # Add to current test's keyword list
        self.current_test["keywords"].append(keyword_data)

    def end_test(self, data: Any, result: Any) -> None:
        """Called when a test case finishes.

        Finalizes test data and saves manifest.json using trace_writer.

        Args:
            data: Test execution data.
            result: Test result object (contains status, message, elapsed_time).
        """
        if self.current_test_dir is None:
            return

        # Finalize test data
        self.current_test["end_time"] = get_iso_timestamp()
        self.current_test["status"] = str(result.status) if hasattr(result, "status") else "UNKNOWN"
        self.current_test["message"] = str(result.message) if hasattr(result, "message") else ""

        # Calculate duration
        if hasattr(result, "elapsed_time"):
            elapsed = result.elapsed_time
            if hasattr(elapsed, "total_seconds"):
                self.current_test["duration_ms"] = int(elapsed.total_seconds() * 1000)
            else:
                self.current_test["duration_ms"] = int(elapsed * 1000)
        else:
            self.current_test["duration_ms"] = 0

        self.current_test["keywords_count"] = len(self.current_test["keywords"])

        # Build manifest
        manifest = {
            "version": "1.0.0",
            "tool_version": "0.1.3",
            "test_name": self.current_test["name"],
            "test_longname": self.current_test["longname"],
            "suite_name": self.suite_name,
            "suite_source": self.suite_source,
            "doc": self.current_test["doc"],
            "tags": self.current_test["tags"],
            "start_time": self.current_test["start_time"],
            "end_time": self.current_test["end_time"],
            "duration_ms": self.current_test["duration_ms"],
            "status": self.current_test["status"],
            "message": self.current_test["message"],
            "keywords_count": self.current_test["keywords_count"],
            "capture_mode": self.capture_mode,
        }

        # Save manifest.json using trace_writer
        self.trace_writer.write_manifest(manifest)

        # Generate viewer.html for this test
        if self.viewer_generator is not None:
            try:
                # Prepare viewer data with keywords
                viewer_data = {
                    **manifest,
                    "keywords": self.current_test["keywords"],
                }
                self.viewer_generator.generate(self.current_test_dir, viewer_data)
            except Exception as e:
                logger.warning("Viewer generation failed for test %s: %s", manifest["test_name"], e)

        # Add test reference to trace_data
        self.trace_data["tests"].append(
            {
                "name": self.current_test["name"],
                "folder": self.current_test["folder"],
                "status": self.current_test["status"],
            }
        )

        # Reset test state
        self.current_test = {}
        self.current_test_dir = None
        self.keyword_index = 0
        self.keyword_stack = []

    def end_suite(self, data: Any, result: Any) -> None:
        """Called when a test suite finishes.

        Currently a no-op, but can be extended for suite-level summary generation.

        Args:
            data: Suite execution data.
            result: Suite result object.
        """
        # Viewer generation is now done per-test in end_test
        pass
