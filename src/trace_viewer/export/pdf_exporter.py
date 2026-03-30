"""PDF export for trace viewer reports.

Requires weasyprint>=60.0 (optional dependency).
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# CSS status colours mirror the viewer's colour scheme.
_STATUS_COLOURS: dict[str, str] = {
    "PASS": "#2e7d32",
    "FAIL": "#c62828",
    "SKIP": "#f57f17",
    "NOT RUN": "#757575",
}

_PAGE_CSS = """\
@page {
    size: A4;
    margin: 18mm 16mm 18mm 16mm;
    @bottom-center {
        content: counter(page) " / " counter(pages);
        font-size: 9pt;
        color: #9e9e9e;
    }
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: "DejaVu Sans", "Helvetica Neue", Arial, sans-serif;
    font-size: 10pt;
    color: #212121;
    line-height: 1.5;
}

/* ── Cover page ─────────────────────────────────────────────────── */
.cover {
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-height: 240mm;
    page-break-after: always;
    padding: 24mm 0;
}

.cover__tool {
    font-size: 9pt;
    color: #9e9e9e;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 10mm;
}

.cover__test-name {
    font-size: 22pt;
    font-weight: 700;
    color: #212121;
    word-break: break-word;
    margin-bottom: 3mm;
}

.cover__suite {
    font-size: 12pt;
    color: #616161;
    margin-bottom: 10mm;
}

.cover__badge {
    display: inline-block;
    padding: 2mm 6mm;
    border-radius: 3mm;
    font-size: 13pt;
    font-weight: 700;
    color: #ffffff;
    width: fit-content;
    margin-bottom: 10mm;
}

.cover__meta {
    font-size: 9pt;
    color: #757575;
}

.cover__meta dt {
    font-weight: 600;
    display: inline;
}

.cover__meta dd {
    display: inline;
    margin-left: 1mm;
    margin-right: 6mm;
}

/* ── Keyword sections ────────────────────────────────────────────── */
.kw-section {
    page-break-inside: avoid;
    margin-bottom: 8mm;
    border: 0.3mm solid #e0e0e0;
    border-radius: 2mm;
    overflow: hidden;
}

.kw-header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    padding: 2.5mm 4mm;
    background: #f5f5f5;
    border-bottom: 0.3mm solid #e0e0e0;
}

.kw-header__index {
    font-size: 8pt;
    color: #9e9e9e;
    margin-right: 3mm;
    flex-shrink: 0;
}

.kw-header__name {
    font-size: 10pt;
    font-weight: 600;
    flex: 1;
    word-break: break-all;
}

.kw-header__status {
    font-size: 8pt;
    font-weight: 700;
    padding: 0.5mm 2.5mm;
    border-radius: 1.5mm;
    color: #ffffff;
    margin-left: 3mm;
    flex-shrink: 0;
}

.kw-header__duration {
    font-size: 8pt;
    color: #757575;
    margin-left: 3mm;
    flex-shrink: 0;
}

.kw-body {
    padding: 3mm 4mm;
}

.kw-args {
    font-size: 8.5pt;
    color: #546e7a;
    margin-bottom: 2.5mm;
    word-break: break-all;
}

.kw-screenshot {
    text-align: center;
    margin: 2mm 0;
}

.kw-screenshot img {
    max-width: 100%;
    max-height: 120mm;
    border: 0.2mm solid #bdbdbd;
    border-radius: 1mm;
}

.kw-no-screenshot {
    font-size: 8pt;
    color: #bdbdbd;
    font-style: italic;
    margin: 2mm 0;
}

.kw-variables {
    margin-top: 3mm;
}

.kw-variables summary {
    font-size: 8pt;
    font-weight: 600;
    color: #546e7a;
    cursor: default;
    margin-bottom: 1mm;
}

.vars-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 7.5pt;
}

.vars-table th,
.vars-table td {
    text-align: left;
    padding: 0.8mm 2mm;
    border: 0.2mm solid #e0e0e0;
    word-break: break-all;
}

.vars-table th {
    background: #eeeeee;
    font-weight: 600;
}

/* ── Section divider ─────────────────────────────────────────────── */
.section-title {
    font-size: 11pt;
    font-weight: 700;
    color: #424242;
    margin: 6mm 0 3mm 0;
    padding-bottom: 1mm;
    border-bottom: 0.5mm solid #e0e0e0;
}
"""


class PDFExporter:
    """Exports a Robot Framework trace directory to a print-ready PDF report.

    The report consists of:
    - A cover page with test name, suite, execution date, status, and duration.
    - One section per keyword containing a screenshot, keyword metadata,
      and optionally a variables snapshot.

    This class depends on ``weasyprint`` (>=60.0), which is declared as an
    optional dependency. An :class:`ImportError` is raised at construction
    time when the library is not installed, providing a clear remediation
    message.

    Example:
        >>> exporter = PDFExporter()
        >>> output = exporter.export(Path("./traces/login_test_20250120_143022"))
        >>> print(output)
        PosixPath('.../login_test_20250120_143022/report.pdf')
    """

    def __init__(self) -> None:
        """Initialize the PDFExporter, verifying the weasyprint dependency.

        Raises:
            ImportError: If weasyprint is not installed, with installation
                instructions in the exception message.
        """
        try:
            import weasyprint  # noqa: F401  (existence check)

            self._weasyprint = weasyprint
        except ImportError as exc:
            raise ImportError(
                "PDF export requires 'weasyprint>=60.0'.\n"
                "Install it with:  pip install 'robotframework-trace-viewer[pdf]'\n"
                "or directly with: pip install 'weasyprint>=60.0'"
            ) from exc

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def export(
        self,
        trace_dir: Path,
        output: Path | None = None,
        screenshots_only: bool = False,
    ) -> Path:
        """Export a trace directory to a PDF file.

        Loads ``manifest.json`` and all keyword metadata / screenshots from
        *trace_dir*, generates an HTML report, then converts it to PDF using
        weasyprint.

        Args:
            trace_dir: Path to a trace directory produced by
                :class:`~trace_viewer.storage.trace_writer.TraceWriter`.
                Must contain ``manifest.json``.
            output: Destination path for the generated PDF.  When *None*
                (default) the file is written to ``trace_dir/report.pdf``.
            screenshots_only: When *True*, the variables snapshot table is
                omitted from each keyword section, producing a more compact
                report.

        Returns:
            The absolute path to the generated PDF file.

        Raises:
            FileNotFoundError: If *trace_dir* does not exist or does not
                contain a ``manifest.json`` file.
            json.JSONDecodeError: If ``manifest.json`` is malformed.

        Example:
            >>> exporter = PDFExporter()
            >>> pdf = exporter.export(
            ...     Path("./traces/login_test_20250120_143022"),
            ...     screenshots_only=True,
            ... )
        """
        trace_dir = trace_dir.resolve()

        if not trace_dir.exists():
            raise FileNotFoundError(f"Trace directory does not exist: {trace_dir}")

        manifest_path = trace_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest.json not found in: {trace_dir}")

        with manifest_path.open(encoding="utf-8") as fh:
            manifest: dict[str, Any] = json.load(fh)

        keywords = self._load_keywords(trace_dir)

        html = self._generate_report_html(manifest, keywords, trace_dir, screenshots_only)

        resolved_output = output.resolve() if output else trace_dir / "report.pdf"

        logger.debug("Converting HTML to PDF -> %s", resolved_output)
        document = self._weasyprint.HTML(string=html, base_url=str(trace_dir)).write_pdf()
        resolved_output.write_bytes(document)

        logger.info("PDF report written: %s", resolved_output)
        return resolved_output

    # ------------------------------------------------------------------ #
    # HTML generation                                                      #
    # ------------------------------------------------------------------ #

    def _generate_report_html(
        self,
        manifest: dict[str, Any],
        keywords: list[dict[str, Any]],
        trace_dir: Path,
        screenshots_only: bool,
    ) -> str:
        """Build a complete, self-contained HTML document for PDF rendering.

        The document embeds all CSS inline and encodes every screenshot as a
        base64 data URI so the resulting PDF is fully portable.

        Design decisions:
        - ``@page`` CSS targets A4 paper with symmetric margins.
        - The cover page uses ``page-break-after: always``.
        - Each keyword section uses ``page-break-inside: avoid``.
        - Screenshots are capped at 120 mm height via CSS so they never
          overflow onto a second page alone.
        - Missing screenshots are replaced by an italic placeholder message.

        Args:
            manifest: Parsed ``manifest.json`` dictionary.
            keywords: List of keyword data dictionaries (may be empty).
            trace_dir: Trace directory, used to resolve screenshot paths.
            screenshots_only: When *True*, per-keyword variable tables are
                omitted.

        Returns:
            A Unicode string containing the complete HTML document.
        """
        test_name = manifest.get("test_name", "Unknown Test")
        suite_name = manifest.get("suite_name", "")
        status = manifest.get("status", "NOT RUN")
        start_time = manifest.get("start_time", "")
        duration_ms = manifest.get("duration_ms", 0)
        tool_version = manifest.get("tool_version", "")

        status_colour = _STATUS_COLOURS.get(status, _STATUS_COLOURS["NOT RUN"])
        duration_text = _format_duration(duration_ms)

        cover_html = self._build_cover_html(
            test_name=test_name,
            suite_name=suite_name,
            status=status,
            status_colour=status_colour,
            start_time=start_time,
            duration_text=duration_text,
            keywords_count=len(keywords),
            tool_version=tool_version,
        )

        if not keywords:
            body_html = "<p style='color:#9e9e9e;font-style:italic;'>No keywords were captured for this trace.</p>"
        else:
            kw_sections = [
                self._build_keyword_html(kw, trace_dir, screenshots_only) for kw in keywords
            ]
            body_html = '<h2 class="section-title">Keywords</h2>\n' + "\n".join(kw_sections)

        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '<meta charset="UTF-8"/>\n'
            f"<title>{_escape(test_name)}</title>\n"
            f"<style>{_PAGE_CSS}</style>\n"
            "</head>\n"
            "<body>\n"
            f"{cover_html}\n"
            f"{body_html}\n"
            "</body>\n"
            "</html>"
        )

    # ------------------------------------------------------------------ #
    # Cover page                                                           #
    # ------------------------------------------------------------------ #

    def _build_cover_html(
        self,
        *,
        test_name: str,
        suite_name: str,
        status: str,
        status_colour: str,
        start_time: str,
        duration_text: str,
        keywords_count: int,
        tool_version: str,
    ) -> str:
        """Render the cover-page HTML fragment.

        Args:
            test_name: Human-readable test name.
            suite_name: Parent suite name (may be empty).
            status: Execution status string (PASS / FAIL / SKIP / NOT RUN).
            status_colour: Hex colour code matching the status.
            start_time: ISO-8601 start timestamp string.
            duration_text: Pre-formatted duration string (e.g. "1.2 s").
            keywords_count: Total number of keywords in the trace.
            tool_version: Version string of the trace-viewer tool.

        Returns:
            HTML string for the cover section.
        """
        tool_label = f"Robot Framework Trace Viewer {tool_version}".strip()
        suite_fragment = f'<p class="cover__suite">{_escape(suite_name)}</p>' if suite_name else ""

        return (
            '<section class="cover">\n'
            f'  <p class="cover__tool">{_escape(tool_label)}</p>\n'
            f'  <h1 class="cover__test-name">{_escape(test_name)}</h1>\n'
            f"  {suite_fragment}\n"
            f'  <span class="cover__badge" style="background:{status_colour}">'
            f"{_escape(status)}</span>\n"
            '  <dl class="cover__meta">\n'
            f"    <dt>Date:</dt><dd>{_escape(start_time)}</dd>\n"
            f"    <dt>Duration:</dt><dd>{_escape(duration_text)}</dd>\n"
            f"    <dt>Keywords:</dt><dd>{keywords_count}</dd>\n"
            "  </dl>\n"
            "</section>"
        )

    # ------------------------------------------------------------------ #
    # Keyword section                                                      #
    # ------------------------------------------------------------------ #

    def _build_keyword_html(
        self,
        keyword: dict[str, Any],
        trace_dir: Path,
        screenshots_only: bool,
    ) -> str:
        """Render a single keyword section as an HTML fragment.

        Each section contains:
        - A header bar with index, name, status badge, and duration.
        - The keyword arguments (if any).
        - A screenshot image (base64-encoded) or a placeholder when absent.
        - A variables table (unless *screenshots_only* is *True*).

        Args:
            keyword: Keyword data dictionary loaded from ``metadata.json``
                and optionally augmented with ``variables``.
            trace_dir: Trace directory, used to resolve the screenshot path.
            screenshots_only: When *True*, the variables table is suppressed.

        Returns:
            HTML string for one keyword section.
        """
        index = keyword.get("index", 0)
        name = keyword.get("name", "Unknown")
        status = keyword.get("status", "NOT RUN")
        duration_ms = keyword.get("duration_ms", 0)
        args: list[Any] = keyword.get("args", [])
        variables: dict[str, Any] = keyword.get("variables", {})
        message = keyword.get("message", "")

        status_colour = _STATUS_COLOURS.get(status, _STATUS_COLOURS["NOT RUN"])
        duration_text = _format_duration(duration_ms)

        # Header
        args_text = ", ".join(str(a) for a in args) if args else ""
        args_fragment = f'<p class="kw-args">Args: {_escape(args_text)}</p>' if args_text else ""
        message_fragment = (
            f'<p class="kw-args" style="color:#c62828">Error: {_escape(message)}</p>'
            if message and status == "FAIL"
            else ""
        )

        # Screenshot
        screenshot_fragment = self._build_screenshot_html(keyword, trace_dir)

        # Variables
        variables_fragment = ""
        if not screenshots_only and variables:
            variables_fragment = self._build_variables_html(variables)

        return (
            '<div class="kw-section">\n'
            '  <div class="kw-header">\n'
            f'    <span class="kw-header__index">#{index:03d}</span>\n'
            f'    <span class="kw-header__name">{_escape(name)}</span>\n'
            f'    <span class="kw-header__status" style="background:{status_colour}">'
            f"{_escape(status)}</span>\n"
            f'    <span class="kw-header__duration">{_escape(duration_text)}</span>\n'
            "  </div>\n"
            '  <div class="kw-body">\n'
            f"    {args_fragment}\n"
            f"    {message_fragment}\n"
            f"    {screenshot_fragment}\n"
            f"    {variables_fragment}\n"
            "  </div>\n"
            "</div>"
        )

    # ------------------------------------------------------------------ #
    # Screenshot embedding                                                 #
    # ------------------------------------------------------------------ #

    def _build_screenshot_html(self, keyword: dict[str, Any], trace_dir: Path) -> str:
        """Build an ``<img>`` tag with an embedded base64 PNG, or a placeholder.

        The method resolves the screenshot path using the same lookup strategy
        as :class:`~trace_viewer.viewer.generator.ViewerGenerator`:

        1. If ``keyword["screenshot"]`` is a relative path string, it is
           resolved against *trace_dir*.
        2. If ``keyword["has_screenshot"]`` is *True* and ``keyword["folder"]``
           is set, the conventional path
           ``keywords/<folder>/screenshot.png`` is tried.
        3. If neither yields an existing file, a text placeholder is returned.

        Missing files are silently handled and produce a placeholder.

        Args:
            keyword: Keyword data dictionary.
            trace_dir: Trace root directory for path resolution.

        Returns:
            HTML fragment string (either an ``<img>`` tag or a placeholder
            ``<p>`` element).
        """
        screenshot_path: Path | None = None

        raw = keyword.get("screenshot")
        if raw:
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = trace_dir / candidate
            if candidate.exists():
                screenshot_path = candidate

        if screenshot_path is None and keyword.get("has_screenshot") and keyword.get("folder"):
            candidate = trace_dir / "keywords" / keyword["folder"] / "screenshot.png"
            if candidate.exists():
                screenshot_path = candidate

        if screenshot_path is None:
            return '<p class="kw-no-screenshot">No screenshot available.</p>'

        try:
            png_bytes = screenshot_path.read_bytes()
            b64 = base64.b64encode(png_bytes).decode("ascii")
            return (
                '<div class="kw-screenshot">\n'
                f'  <img src="data:image/png;base64,{b64}" alt="screenshot"/>\n'
                "</div>"
            )
        except OSError as exc:
            logger.warning("Could not read screenshot %s: %s", screenshot_path, exc)
            return '<p class="kw-no-screenshot">Screenshot could not be loaded.</p>'

    # ------------------------------------------------------------------ #
    # Variables table                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_variables_html(variables: dict[str, Any]) -> str:
        """Render a compact HTML table from a variables dictionary.

        The ``variables`` dict may contain nested dicts (e.g. ``scalar``,
        ``list``, ``dict`` sub-keys as written by the capture module) or be a
        flat mapping of variable name to value.  Both layouts are handled:

        - If the top-level values are themselves dicts, the table is rendered
          per-namespace with a header row for each namespace.
        - Otherwise the flat mapping is rendered as a two-column table.

        Args:
            variables: Variables dictionary from ``variables.json`` or the
                merged keyword data dict.

        Returns:
            HTML string containing a ``<details>`` element with the table.
        """
        if not variables:
            return ""

        # Detect namespace layout (scalar/list/dict keys from capture module)
        namespaced = all(isinstance(v, dict) for v in variables.values())

        rows: list[str] = []
        if namespaced:
            for namespace, mapping in variables.items():
                if not isinstance(mapping, dict) or not mapping:
                    continue
                rows.append(
                    f'<tr><th colspan="2" style="background:#e3f2fd">'
                    f"{_escape(namespace)}</th></tr>"
                )
                for var_name, var_value in mapping.items():
                    rows.append(
                        f"<tr><td>{_escape(str(var_name))}</td>"
                        f"<td>{_escape(str(var_value))}</td></tr>"
                    )
        else:
            for var_name, var_value in variables.items():
                rows.append(
                    f"<tr><td>{_escape(str(var_name))}</td>"
                    f"<td>{_escape(str(var_value))}</td></tr>"
                )

        if not rows:
            return ""

        table_body = "\n".join(rows)
        return (
            '<details class="kw-variables" open>\n'
            "  <summary>Variables</summary>\n"
            '  <table class="vars-table">\n'
            "    <thead><tr><th>Name</th><th>Value</th></tr></thead>\n"
            f"    <tbody>{table_body}</tbody>\n"
            "  </table>\n"
            "</details>"
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _load_keywords(self, trace_dir: Path) -> list[dict[str, Any]]:
        """Load all keyword data from a trace directory.

        Mirrors the loading logic in
        :meth:`~trace_viewer.viewer.generator.ViewerGenerator._load_keywords_from_dir`
        but also merges ``variables.json`` into each keyword dict for use in
        the PDF variable tables.

        Args:
            trace_dir: Root of the trace directory.

        Returns:
            List of keyword dicts sorted by directory name (execution order).
            Returns an empty list when the ``keywords/`` subdirectory is absent
            or contains no valid entries.
        """
        keywords_dir = trace_dir / "keywords"
        if not keywords_dir.exists():
            logger.debug("No keywords/ directory in %s", trace_dir)
            return []

        keyword_dirs = sorted(p for p in keywords_dir.iterdir() if p.is_dir())
        result: list[dict[str, Any]] = []

        for kw_dir in keyword_dirs:
            keyword = self._load_single_keyword(kw_dir)
            if keyword is not None:
                result.append(keyword)

        return result

    @staticmethod
    def _load_single_keyword(kw_dir: Path) -> dict[str, Any] | None:
        """Load and merge data for one keyword directory.

        Reads ``metadata.json`` (required) and ``variables.json`` (optional),
        then records screenshot availability.

        Args:
            kw_dir: Path to the keyword subdirectory (e.g. ``001_go_to``).

        Returns:
            A merged keyword dictionary, or *None* if ``metadata.json`` is
            absent or contains invalid JSON.
        """
        metadata_path = kw_dir / "metadata.json"
        if not metadata_path.exists():
            logger.debug("Skipping %s: no metadata.json", kw_dir)
            return None

        try:
            with metadata_path.open(encoding="utf-8") as fh:
                keyword: dict[str, Any] = json.load(fh)
        except json.JSONDecodeError as exc:
            logger.warning("Invalid metadata.json in %s: %s", kw_dir, exc)
            return None

        # Variables (optional)
        variables_path = kw_dir / "variables.json"
        if variables_path.exists():
            try:
                with variables_path.open(encoding="utf-8") as fh:
                    keyword["variables"] = json.load(fh)
            except json.JSONDecodeError as exc:
                logger.warning("Invalid variables.json in %s: %s", kw_dir, exc)
                keyword["variables"] = {}
        else:
            keyword.setdefault("variables", {})

        # Screenshot presence
        screenshot_path = kw_dir / "screenshot.png"
        if screenshot_path.exists():
            keyword["screenshot"] = f"keywords/{kw_dir.name}/screenshot.png"
        else:
            keyword.setdefault("screenshot", None)

        return keyword


# ------------------------------------------------------------------ #
# Module-level helpers                                                #
# ------------------------------------------------------------------ #


def _escape(text: str) -> str:
    """Escape special HTML characters in *text*.

    Replaces ``&``, ``<``, ``>``, ``"``, and ``'`` with their HTML entity
    equivalents to prevent XSS and broken markup in the generated report.

    Args:
        text: Raw string to escape.

    Returns:
        HTML-safe string.

    Examples:
        >>> _escape("<script>alert('xss')</script>")
        '&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;'
        >>> _escape("PASS & done")
        'PASS &amp; done'
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _format_duration(duration_ms: int | float) -> str:
    """Format a duration in milliseconds as a human-readable string.

    The output adapts to the magnitude:
    - Sub-second values are shown in milliseconds (e.g. ``"850 ms"``).
    - Values under one minute are shown in seconds to one decimal place
      (e.g. ``"12.3 s"``).
    - Longer values are shown as ``"Xm Ys"`` (e.g. ``"2m 5s"``).

    Args:
        duration_ms: Duration in milliseconds.

    Returns:
        Human-readable duration string.

    Examples:
        >>> _format_duration(0)
        '0 ms'
        >>> _format_duration(850)
        '850 ms'
        >>> _format_duration(12345)
        '12.3 s'
        >>> _format_duration(125000)
        '2m 5s'
    """
    ms = int(duration_ms)
    if ms < 1000:
        return f"{ms} ms"
    seconds = ms / 1000.0
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes = int(seconds) // 60
    remaining_s = int(seconds) % 60
    return f"{minutes}m {remaining_s}s"
