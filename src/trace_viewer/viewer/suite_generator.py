"""Suite-level summary viewer generator for Robot Framework trace data.

This module provides the SuiteViewerGenerator class which scans a traces
directory and generates a standalone HTML suite summary page. The summary
page shows aggregate statistics (total/passed/failed/skipped, pass rate,
total duration) and allows navigating between individual test viewers.

For suites with 30 tests or fewer, each test viewer is embedded in an
iframe within the summary page. For larger suites, the summary links
directly to each individual viewer.html file instead.
"""

import json
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Maximum number of tests for which individual viewers are embedded as iframes.
# Above this threshold, the suite page links to viewers instead of embedding.
_IFRAME_EMBED_THRESHOLD = 30


class SuiteViewerGenerator:
    """Generates a standalone HTML suite summary page from a traces directory.

    The SuiteViewerGenerator scans a directory for valid trace subdirectories
    (each containing a ``manifest.json``), aggregates summary statistics, and
    produces a single ``suite_viewer.html`` that allows the user to browse all
    tests in a suite without leaving the page.

    For suites with at most 30 tests the individual ``viewer.html`` files are
    embedded as iframes directly inside the suite page, giving an instant
    side-by-side navigation experience.  For larger suites only hyperlinks are
    rendered to keep the initial page load fast.

    Attributes:
        template_path: Absolute path to the ``suite_viewer.html`` template.

    Example:
        >>> generator = SuiteViewerGenerator()
        >>> output = generator.generate(Path("./traces"), open_browser=True)
        >>> print(f"Suite viewer generated at: {output}")
    """

    def __init__(self) -> None:
        """Initialise SuiteViewerGenerator with the default template path."""
        self.template_path: Path = Path(__file__).parent / "templates" / "suite_viewer.html"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        traces_dir: Path,
        output_path: Optional[Path] = None,
        open_browser: bool = False,
    ) -> Path:
        """Generate the suite summary HTML file.

        Scans *traces_dir* for subdirectories that contain a ``manifest.json``
        file, loads the key fields from each manifest, computes aggregate
        statistics, and writes a standalone ``suite_viewer.html`` to
        *output_path* (defaulting to ``<traces_dir>/suite_viewer.html``).

        Args:
            traces_dir: Path to the directory that contains individual trace
                subdirectories.  Each subdirectory must have a ``manifest.json``
                to be included in the summary.
            output_path: Optional path for the generated HTML file.  When
                ``None`` the file is written to ``<traces_dir>/suite_viewer.html``.
            open_browser: When ``True``, opens the generated file in the
                default web browser immediately after writing it.

        Returns:
            Absolute path to the generated ``suite_viewer.html`` file.

        Raises:
            FileNotFoundError: If *traces_dir* does not exist or if the
                ``suite_viewer.html`` template is missing.
            OSError: If the output file cannot be written.

        Example:
            >>> generator = SuiteViewerGenerator()
            >>> output = generator.generate(
            ...     Path("./e2e_traces"),
            ...     output_path=Path("/tmp/suite.html"),
            ...     open_browser=False,
            ... )
        """
        traces_dir = Path(traces_dir)
        if not traces_dir.exists():
            raise FileNotFoundError(f"Traces directory not found: {traces_dir}")

        if not self.template_path.exists():
            raise FileNotFoundError(f"Suite viewer template not found: {self.template_path}")

        # Resolve output path
        resolved_output: Path
        if output_path is None:
            resolved_output = traces_dir / "suite_viewer.html"
        else:
            resolved_output = Path(output_path)
            if resolved_output.suffix.lower() != ".html":
                resolved_output = resolved_output.with_suffix(".html")

        resolved_output.parent.mkdir(parents=True, exist_ok=True)

        # Load trace manifests
        traces = self._load_traces(traces_dir)

        # Compute aggregate statistics
        stats = self._calculate_stats(traces)

        # Determine suite name from the directory name
        suite_name = traces_dir.name

        # Decide rendering mode: embed iframes vs. plain links
        embed_iframes = len(traces) <= _IFRAME_EMBED_THRESHOLD

        # Build the per-test data payload sent to the template
        suite_data = self._build_suite_data(
            traces=traces,
            stats=stats,
            suite_name=suite_name,
            traces_dir=traces_dir,
            output_path=resolved_output,
            embed_iframes=embed_iframes,
        )

        # Read template and inject data
        template = self.template_path.read_text(encoding="utf-8")
        json_payload = json.dumps(suite_data, ensure_ascii=False, indent=2, default=str)
        html = template.replace("{{SUITE_DATA}}", json_payload)
        html = html.replace("{{SUITE_NAME}}", _escape_html(suite_name))

        resolved_output.write_text(html, encoding="utf-8")

        if open_browser:
            webbrowser.open(f"file://{resolved_output.absolute()}")

        return resolved_output

    # ------------------------------------------------------------------
    # Helper: loading
    # ------------------------------------------------------------------

    def _load_traces(self, traces_dir: Path) -> list[dict[str, Any]]:
        """Load summary data from all valid trace subdirectories.

        A subdirectory is considered a valid trace if it contains a
        ``manifest.json`` file at its root.  Only the fields required for the
        suite summary page are extracted; the full keyword tree is intentionally
        excluded to keep the payload small.

        Args:
            traces_dir: Directory to scan for trace subdirectories.

        Returns:
            List of trace summary dictionaries sorted by ``start_time``
            in descending order (most recent first).  Each dict contains:

            - ``test_name`` (str)
            - ``suite_name`` (str)
            - ``status`` (str): ``"PASS"``, ``"FAIL"``, ``"SKIP"``, or ``"NOT_RUN"``
            - ``duration_ms`` (int)
            - ``start_time`` (str): ISO 8601 timestamp or empty string
            - ``keywords_count`` (int)
            - ``message`` (str): failure / skip message or empty string
            - ``trace_dir`` (str): absolute path to the trace directory
            - ``trace_name`` (str): directory name (used to build viewer URL)
        """
        traces: list[dict[str, Any]] = []

        for item in sorted(traces_dir.iterdir()):
            if not item.is_dir():
                continue

            manifest_path = item / "manifest.json"
            if not manifest_path.exists():
                continue

            try:
                with open(manifest_path, encoding="utf-8") as fh:
                    manifest: dict[str, Any] = json.load(fh)
            except (OSError, json.JSONDecodeError):
                # Skip corrupted or unreadable manifests silently
                continue

            traces.append(
                {
                    "test_name": manifest.get("test_name", item.name),
                    "suite_name": manifest.get("suite_name", ""),
                    "status": manifest.get("status", "NOT_RUN"),
                    "duration_ms": int(manifest.get("duration_ms", 0)),
                    "start_time": manifest.get("start_time", ""),
                    "keywords_count": int(manifest.get("keywords_count", 0)),
                    "message": manifest.get("message", ""),
                    "trace_dir": str(item.resolve()),
                    "trace_name": item.name,
                }
            )

        # Sort most-recent first; fall back to directory-name order when no timestamp
        traces.sort(key=lambda t: t["start_time"], reverse=True)
        return traces

    # ------------------------------------------------------------------
    # Helper: statistics
    # ------------------------------------------------------------------

    def _calculate_stats(self, traces: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculate aggregate statistics across all traces.

        Args:
            traces: List of trace summary dicts as returned by
                :meth:`_load_traces`.

        Returns:
            Dictionary with the following keys:

            - ``total`` (int): Total number of tests
            - ``passed`` (int): Tests with status ``"PASS"``
            - ``failed`` (int): Tests with status ``"FAIL"``
            - ``skipped`` (int): Tests with status ``"SKIP"``
            - ``other`` (int): Tests with any other status
            - ``pass_rate`` (float): Percentage of passing tests (0-100, 1 dp)
            - ``total_duration_ms`` (int): Sum of all test durations in ms
            - ``generated_at`` (str): ISO 8601 timestamp of generation time
        """
        total = len(traces)
        passed = sum(1 for t in traces if t["status"] == "PASS")
        failed = sum(1 for t in traces if t["status"] == "FAIL")
        skipped = sum(1 for t in traces if t["status"] == "SKIP")
        other = total - passed - failed - skipped
        pass_rate = round(passed / total * 100, 1) if total > 0 else 0.0
        total_duration_ms = sum(t["duration_ms"] for t in traces)

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "other": other,
            "pass_rate": pass_rate,
            "total_duration_ms": total_duration_ms,
            "generated_at": datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # Helper: payload assembly
    # ------------------------------------------------------------------

    def _build_suite_data(
        self,
        traces: list[dict[str, Any]],
        stats: dict[str, Any],
        suite_name: str,
        traces_dir: Path,
        output_path: Path,
        embed_iframes: bool,
    ) -> dict[str, Any]:
        """Assemble the full data payload injected into the HTML template.

        For each trace, a relative ``viewer_url`` is computed from the
        ``suite_viewer.html`` output file to the individual ``viewer.html``
        so that the generated file is portable (links remain valid after
        moving the whole traces directory).

        Args:
            traces: Trace summary dicts from :meth:`_load_traces`.
            stats: Aggregate statistics from :meth:`_calculate_stats`.
            suite_name: Human-readable name of the suite.
            traces_dir: Path to the traces root directory.
            output_path: Resolved output path for ``suite_viewer.html``.
            embed_iframes: When ``True`` the template will embed viewers as
                iframes; when ``False`` it renders plain hyperlinks.

        Returns:
            Dict suitable for JSON serialisation and template injection.
        """
        tests: list[dict[str, Any]] = []

        for trace in traces:
            trace_dir_path = Path(trace["trace_dir"])
            viewer_html = trace_dir_path / "viewer.html"

            # Build a relative URL from the output HTML to the viewer file.
            # If the viewer.html does not exist yet we still record the
            # expected relative path so the link is correct once generated.
            try:
                relative_url = str(viewer_html.relative_to(output_path.parent))
            except ValueError:
                # Fallback to absolute path as a file:// URL when the viewer
                # lives outside the output directory (unusual but possible).
                relative_url = viewer_html.as_uri()

            tests.append(
                {
                    "test_name": trace["test_name"],
                    "suite_name": trace["suite_name"],
                    "status": trace["status"],
                    "duration_ms": trace["duration_ms"],
                    "start_time": trace["start_time"],
                    "keywords_count": trace["keywords_count"],
                    "message": trace["message"],
                    "viewer_url": relative_url,
                    "viewer_exists": viewer_html.exists(),
                }
            )

        return {
            "suite_name": suite_name,
            "stats": stats,
            "tests": tests,
            "embed_iframes": embed_iframes,
        }


# ---------------------------------------------------------------------------
# Module-level utility
# ---------------------------------------------------------------------------


def _escape_html(text: str) -> str:
    """Escape special HTML characters in *text*.

    This minimal helper avoids a dependency on ``html`` module aliases and is
    intentionally kept private.  It is used only for the ``{{SUITE_NAME}}``
    placeholder which appears inside an HTML attribute value.

    Args:
        text: Raw text to escape.

    Returns:
        HTML-safe version of *text*.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
