"""HTML viewer generator for trace data.

This module provides the ViewerGenerator class which generates static HTML
viewer files from Robot Framework trace data.
"""

import json
from pathlib import Path
from typing import Any, Optional


class ViewerGenerator:
    """Generates static HTML viewer from trace data.

    The ViewerGenerator reads a template HTML file and injects trace data
    to create a standalone, offline-capable viewer for Robot Framework
    test execution traces.

    Attributes:
        template_path: Path to the HTML template file.

    Example:
        >>> generator = ViewerGenerator()
        >>> trace_data = {"test_name": "Login Test", "keywords": [...]}
        >>> output_path = generator.generate(Path("./traces/test1"), trace_data)
        >>> print(f"Viewer generated at: {output_path}")
    """

    def __init__(self) -> None:
        """Initialize ViewerGenerator with default template path."""
        self.template_path = Path(__file__).parent / "templates" / "viewer.html"

    def generate(self, trace_dir: Path, trace_data: dict[str, Any]) -> Path:
        """Generate viewer.html in the trace directory.

        Reads the HTML template, prepares the trace data for the viewer,
        and writes the final HTML file with embedded data.

        Args:
            trace_dir: Path to the trace directory where viewer.html will be written.
            trace_data: Dictionary containing trace data (manifest + keywords).

        Returns:
            Path to the generated viewer.html file.

        Raises:
            FileNotFoundError: If the template file doesn't exist.
            ValueError: If trace_data is invalid.

        Example:
            >>> generator = ViewerGenerator()
            >>> trace_dir = Path("./traces/login_test_20250120_143022")
            >>> trace_data = {
            ...     "test_name": "Login Should Work",
            ...     "suite_name": "Authentication",
            ...     "status": "PASS",
            ...     "duration_ms": 5000,
            ...     "keywords": [...]
            ... }
            >>> output = generator.generate(trace_dir, trace_data)
        """
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found: {self.template_path}")

        if not isinstance(trace_data, dict):
            raise ValueError("trace_data must be a dictionary")

        # Read the template
        template = self.template_path.read_text(encoding="utf-8")

        # Prepare viewer data with relative screenshot paths
        viewer_data = self._prepare_viewer_data(trace_dir, trace_data)

        # Serialize data to JSON
        json_data = json.dumps(viewer_data, ensure_ascii=False, indent=2, default=str)

        # Replace placeholders
        html = template.replace("{{TRACE_DATA}}", json_data)
        html = html.replace("{{TEST_NAME}}", viewer_data.get("test_name", "Trace Viewer"))

        # Write the viewer
        output_path = trace_dir / "viewer.html"
        output_path.write_text(html, encoding="utf-8")

        return output_path

    def _prepare_viewer_data(self, trace_dir: Path, trace_data: dict[str, Any]) -> dict[str, Any]:
        """Prepare data structure for the viewer.

        Transforms raw trace data into the format expected by the viewer
        JavaScript code. Converts absolute paths to relative paths for
        screenshots and ensures all required fields are present.

        Args:
            trace_dir: Path to the trace directory.
            trace_data: Raw trace data dictionary.

        Returns:
            Prepared data dictionary for the viewer.
        """
        viewer_data = {
            "test_name": trace_data.get("test_name", "Unknown Test"),
            "suite_name": trace_data.get("suite_name", ""),
            "status": trace_data.get("status", "NOT RUN"),
            "message": trace_data.get("message", ""),
            "start_time": trace_data.get("start_time", ""),
            "duration_ms": trace_data.get("duration_ms", 0),
            "keywords": [],
        }

        # Process keywords
        keywords = trace_data.get("keywords", [])
        for kw in keywords:
            processed_kw = self._process_keyword(trace_dir, kw)
            viewer_data["keywords"].append(processed_kw)

        return viewer_data

    def _process_keyword(self, trace_dir: Path, keyword: dict[str, Any]) -> dict[str, Any]:
        """Process a single keyword for the viewer.

        Ensures all required fields are present and converts screenshot
        paths to be relative to the viewer.html file.

        Args:
            trace_dir: Path to the trace directory.
            keyword: Raw keyword data dictionary.

        Returns:
            Processed keyword dictionary.
        """
        processed = {
            "index": keyword.get("index", 0),
            "name": keyword.get("name", "Unknown"),
            "status": keyword.get("status", "NOT RUN"),
            "duration_ms": keyword.get("duration_ms", 0),
            "args": keyword.get("args", []),
            "variables": keyword.get("variables", {}),
            "level": keyword.get("level", 0),
            "parent": keyword.get("parent"),
            "message": keyword.get("message", ""),
        }

        # Handle screenshot path
        screenshot = keyword.get("screenshot")
        if screenshot:
            # Convert to relative path if it's absolute
            screenshot_path = Path(screenshot)
            if screenshot_path.is_absolute():
                try:
                    # Make relative to trace_dir
                    processed["screenshot"] = str(screenshot_path.relative_to(trace_dir))
                except ValueError:
                    # Path is not relative to trace_dir, use as-is
                    processed["screenshot"] = screenshot
            else:
                # Already relative, use as-is
                processed["screenshot"] = screenshot
        else:
            processed["screenshot"] = None

        return processed

    def generate_from_manifest(self, trace_dir: Path) -> Path:
        """Generate viewer from an existing trace directory.

        Reads the manifest.json and keyword metadata from the trace directory
        and generates the viewer.html file.

        Args:
            trace_dir: Path to the trace directory containing manifest.json.

        Returns:
            Path to the generated viewer.html file.

        Raises:
            FileNotFoundError: If manifest.json doesn't exist in trace_dir.
            json.JSONDecodeError: If manifest.json is invalid.

        Example:
            >>> generator = ViewerGenerator()
            >>> output = generator.generate_from_manifest(Path("./traces/test1"))
        """
        manifest_path = trace_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        # Load keywords from keyword directories
        keywords = self._load_keywords_from_dir(trace_dir)

        # Merge manifest with keywords
        trace_data = {**manifest, "keywords": keywords}

        return self.generate(trace_dir, trace_data)

    def _load_keywords_from_dir(self, trace_dir: Path) -> list[dict[str, Any]]:
        """Load keyword data from the keywords subdirectory.

        Scans the keywords/ directory for keyword directories (001_name, 002_name, etc.)
        and loads metadata.json and variables.json from each.

        Args:
            trace_dir: Path to the trace directory.

        Returns:
            List of keyword dictionaries sorted by index.
        """
        keywords = []
        keywords_dir = trace_dir / "keywords"

        if not keywords_dir.exists():
            return keywords

        # Sort directories by name (which starts with index number)
        keyword_dirs = sorted(keywords_dir.iterdir()) if keywords_dir.exists() else []

        for kw_dir in keyword_dirs:
            if not kw_dir.is_dir():
                continue

            keyword = self._load_keyword_from_dir(kw_dir)
            if keyword:
                keywords.append(keyword)

        return keywords

    def _load_keyword_from_dir(self, kw_dir: Path) -> Optional[dict[str, Any]]:
        """Load a single keyword from its directory.

        Args:
            kw_dir: Path to the keyword directory.

        Returns:
            Keyword dictionary or None if loading fails.
        """
        keyword = {}

        # Load metadata
        metadata_path = kw_dir / "metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, encoding="utf-8") as f:
                    keyword = json.load(f)
            except json.JSONDecodeError:
                return None

        # Load variables
        variables_path = kw_dir / "variables.json"
        if variables_path.exists():
            try:
                with open(variables_path, encoding="utf-8") as f:
                    keyword["variables"] = json.load(f)
            except json.JSONDecodeError:
                keyword["variables"] = {}

        # Check for screenshot
        screenshot_path = kw_dir / "screenshot.png"
        if screenshot_path.exists():
            # Use relative path from trace_dir
            keyword["screenshot"] = f"keywords/{kw_dir.name}/screenshot.png"
        else:
            keyword["screenshot"] = None

        return keyword if keyword else None
