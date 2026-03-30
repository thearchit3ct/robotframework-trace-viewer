"""CI/CD integration for publishing trace reports.

Supports Jenkins HTML Publisher Plugin and GitLab CI MR comments.

Typical usage:

    >>> publisher = CICDPublisher(Path("./traces"), format="jenkins")
    >>> output_dir = publisher.publish()
    >>> print(f"Report published to: {output_dir}")

    >>> # Auto-detect CI environment
    >>> ci_env = get_ci_environment()
    >>> if ci_env:
    ...     publisher = CICDPublisher(Path("./traces"), format=ci_env)
    ...     publisher.publish()
"""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Status badge CSS classes and display labels used in the Jenkins HTML report.
_STATUS_BADGE: dict[str, dict[str, str]] = {
    "PASS": {"css": "pass", "label": "PASS"},
    "FAIL": {"css": "fail", "label": "FAIL"},
    "SKIP": {"css": "skip", "label": "SKIP"},
}

# GitLab emoji per status.
_GITLAB_EMOJI: dict[str, str] = {
    "PASS": ":white_check_mark:",
    "FAIL": ":x:",
    "SKIP": ":warning:",
}

_VALID_FORMATS = frozenset({"jenkins", "gitlab"})


def get_ci_environment() -> Optional[str]:
    """Detect the current CI environment from standard environment variables.

    Checks for well-known environment variables set by popular CI platforms.
    The detection order is: Jenkins, GitLab, GitHub Actions.

    Returns:
        A string identifying the CI platform ("jenkins", "gitlab", or "github"),
        or ``None`` when not running inside a CI environment.

    Example:
        >>> import os
        >>> os.environ["JENKINS_URL"] = "http://jenkins.example.com"
        >>> get_ci_environment()
        'jenkins'
        >>> del os.environ["JENKINS_URL"]
        >>> get_ci_environment() is None
        True
    """
    if os.environ.get("JENKINS_URL") or os.environ.get("BUILD_NUMBER"):
        return "jenkins"

    if os.environ.get("GITLAB_CI") or os.environ.get("CI_PROJECT_ID"):
        return "gitlab"

    if os.environ.get("GITHUB_ACTIONS"):
        return "github"

    return None


class CICDPublisher:
    """Publishes Robot Framework trace reports for CI/CD consumption.

    Generates HTML index reports compatible with the Jenkins HTML Publisher
    Plugin and Markdown summary files suitable for GitLab MR comments.

    The publisher scans a directory of traces (each containing a
    ``manifest.json`` file), aggregates pass/fail/skip statistics, and
    produces a self-contained report directory that can be archived as a
    CI artifact.

    Attributes:
        traces_dir: Root directory that contains the individual trace folders.
        format: Target CI format, either ``"jenkins"`` or ``"gitlab"``.

    Example:
        >>> publisher = CICDPublisher(Path("./traces"), format="jenkins")
        >>> output = publisher.publish()
        >>> print(output)
        PosixPath('trace-reports')

        >>> publisher = CICDPublisher(Path("./traces"), format="gitlab")
        >>> output = publisher.publish(output_dir=Path("./ci-artifacts"))
    """

    def __init__(
        self,
        traces_dir: Path,
        format: str = "jenkins",  # noqa: A002 – intentional parameter name
    ) -> None:
        """Initialize CICDPublisher.

        Args:
            traces_dir: Path to the directory containing trace folders.
                Each trace folder must contain a ``manifest.json`` file.
            format: Target CI format.  Must be ``"jenkins"`` or ``"gitlab"``.

        Raises:
            ValueError: If *format* is not one of the supported values.
            FileNotFoundError: If *traces_dir* does not exist.
        """
        if format not in _VALID_FORMATS:
            raise ValueError(
                f"Unsupported format {format!r}. " f"Choose one of: {sorted(_VALID_FORMATS)}"
            )

        self.traces_dir = Path(traces_dir)
        self.format = format

        if not self.traces_dir.exists():
            raise FileNotFoundError(f"Traces directory not found: {self.traces_dir}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def publish(self, output_dir: Optional[Path] = None) -> Path:
        """Publish the trace report to the appropriate CI format.

        Dispatches to :meth:`publish_jenkins` or :meth:`publish_gitlab`
        based on the *format* set at construction time.

        Args:
            output_dir: Optional output directory.  When ``None``, each
                sub-publisher uses its own default location.

        Returns:
            Path to the directory that contains the generated report.

        Example:
            >>> publisher = CICDPublisher(Path("./traces"))
            >>> report_dir = publisher.publish()
        """
        if self.format == "jenkins":
            return self.publish_jenkins(output_dir)

        return self.publish_gitlab(output_dir)

    def publish_jenkins(self, output_dir: Optional[Path] = None) -> Path:
        """Generate a Jenkins HTML Publisher Plugin compatible report.

        Creates an ``index.html`` file that lists all traces with status
        badges, links to individual ``viewer.html`` files, and displays
        summary statistics (pass/fail/skip counts) at the top.  Individual
        ``viewer.html`` files are copied into the output directory so the
        report is fully self-contained.

        The default output directory (``trace-reports/``) matches the
        conventional path used in Jenkins pipeline ``publishHTML`` steps.

        Args:
            output_dir: Directory where the report will be written.
                Defaults to ``trace-reports/`` in the current working
                directory.

        Returns:
            Path to the output directory containing the generated report.

        Example:
            >>> publisher = CICDPublisher(Path("./traces"))
            >>> out = publisher.publish_jenkins(Path("./artifacts/trace-reports"))
            >>> (out / "index.html").exists()
            True
        """
        if output_dir is None:
            output_dir = Path("trace-reports")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        traces = self._load_traces()
        stats = self._compute_stats(traces)

        # Copy viewer.html files and collect relative paths for the index.
        for trace in traces:
            trace_dir = Path(trace["trace_dir"])
            viewer_src = trace_dir / "viewer.html"

            if viewer_src.exists():
                dest_dir = output_dir / trace_dir.name
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(viewer_src, dest_dir / "viewer.html")
                trace["viewer_rel_path"] = f"{trace_dir.name}/viewer.html"
            else:
                trace["viewer_rel_path"] = None

        html = self._render_jenkins_html(traces, stats)
        index_path = output_dir / "index.html"
        index_path.write_text(html, encoding="utf-8")

        logger.info(
            "Jenkins report written to %s (%d traces: %d passed, %d failed, %d skipped)",
            output_dir,
            stats["total"],
            stats["passed"],
            stats["failed"],
            stats["skipped"],
        )

        return output_dir

    def publish_gitlab(self, output_dir: Optional[Path] = None) -> Path:
        """Generate a GitLab CI compatible Markdown summary and HTML report.

        Produces two artefacts inside *output_dir*:

        * ``trace-summary.md`` — a Markdown file formatted for GitLab MR
          comments, including a table with test name, status (with GitLab
          emoji), duration, and a link to the individual viewer, plus a
          summary line.
        * The same HTML report that :meth:`publish_jenkins` produces, so
          a single artifact directory can serve both purposes.

        Args:
            output_dir: Directory where artefacts will be written.
                Defaults to ``trace-reports/`` in the current working
                directory.

        Returns:
            Path to the output directory containing the generated artefacts.

        Example:
            >>> publisher = CICDPublisher(Path("./traces"), format="gitlab")
            >>> out = publisher.publish_gitlab()
            >>> (out / "trace-summary.md").exists()
            True
        """
        if output_dir is None:
            output_dir = Path("trace-reports")

        output_dir = Path(output_dir)

        # Reuse the full HTML report generation.
        self.publish_jenkins(output_dir)

        # Reload traces so viewer_rel_path is populated correctly.
        traces = self._load_traces()
        for trace in traces:
            trace_dir = Path(trace["trace_dir"])
            rel_path = output_dir / trace_dir.name / "viewer.html"
            trace["viewer_rel_path"] = (
                f"{trace_dir.name}/viewer.html" if rel_path.exists() else None
            )

        stats = self._compute_stats(traces)
        markdown = self._render_gitlab_markdown(traces, stats)
        summary_path = output_dir / "trace-summary.md"
        summary_path.write_text(markdown, encoding="utf-8")

        logger.info(
            "GitLab summary written to %s",
            summary_path,
        )

        return output_dir

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_traces(self) -> list[dict]:
        """Scan *traces_dir* for manifest files and return trace metadata.

        Each item in the returned list is the deserialized content of a
        ``manifest.json`` file augmented with two extra keys:

        * ``"trace_dir"`` — absolute ``str`` path to the trace directory.
        * ``"trace_name"`` — directory basename (used as the display name
          when ``"test_name"`` is absent).

        Traces are sorted by ``"start_time"`` in ascending order (oldest
        first) so the index report follows a natural chronological order.

        Returns:
            List of trace metadata dictionaries, sorted by start time.
        """
        traces: list[dict] = []

        for item in self.traces_dir.iterdir():
            if not item.is_dir():
                continue

            manifest_path = item / "manifest.json"
            if not manifest_path.exists():
                continue

            try:
                with open(manifest_path, encoding="utf-8") as fh:
                    manifest = json.load(fh)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Skipping %s — could not read manifest: %s", item, exc)
                continue

            manifest["trace_dir"] = str(item)
            manifest["trace_name"] = item.name
            traces.append(manifest)

        # Sort chronologically (oldest first; missing start_time goes last).
        traces.sort(key=lambda t: t.get("start_time") or "")

        return traces

    @staticmethod
    def _compute_stats(traces: list[dict]) -> dict:
        """Aggregate pass/fail/skip counts from a list of trace dicts.

        Args:
            traces: List of trace metadata dictionaries, as returned by
                :meth:`_load_traces`.

        Returns:
            Dictionary with keys ``total``, ``passed``, ``failed``,
            ``skipped``, and ``other``.
        """
        passed = sum(1 for t in traces if t.get("status") == "PASS")
        failed = sum(1 for t in traces if t.get("status") == "FAIL")
        skipped = sum(1 for t in traces if t.get("status") in ("SKIP", "NOT RUN", "NOT_RUN"))
        total = len(traces)
        other = total - passed - failed - skipped

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "other": other,
        }

    # ------------------------------------------------------------------
    # HTML rendering (Jenkins)
    # ------------------------------------------------------------------

    @staticmethod
    def _status_badge_html(status: str) -> str:
        """Return an inline HTML badge element for the given RF status.

        Args:
            status: Robot Framework status string (``"PASS"``, ``"FAIL"``,
                ``"SKIP"``, or any other value).

        Returns:
            HTML ``<span>`` element representing the status badge.
        """
        info = _STATUS_BADGE.get(status.upper(), {"css": "other", "label": status or "UNKNOWN"})
        return f'<span class="status-badge {info["css"]}">' f'{info["label"]}' f"</span>"

    @staticmethod
    def _format_duration(duration_ms: int) -> str:
        """Format a millisecond duration as a human-readable string.

        Args:
            duration_ms: Duration in milliseconds.

        Returns:
            Formatted string such as ``"1.23s"`` or ``"2m 05.0s"``.
        """
        if duration_ms <= 0:
            return "—"
        if duration_ms < 1_000:
            return f"{duration_ms}ms"
        if duration_ms < 60_000:
            return f"{duration_ms / 1_000:.2f}s"
        minutes = duration_ms // 60_000
        seconds = (duration_ms % 60_000) / 1_000
        return f"{minutes}m {seconds:04.1f}s"

    def _render_jenkins_html(self, traces: list[dict], stats: dict) -> str:
        """Render the Jenkins index HTML string.

        Args:
            traces: Trace metadata list (each item may contain a
                ``"viewer_rel_path"`` key set by the caller).
            stats: Aggregate statistics dict from :meth:`_compute_stats`.

        Returns:
            Complete HTML document as a string.
        """
        rows_html = self._render_jenkins_rows(traces)
        pass_rate = round(stats["passed"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0.0

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Robot Framework Trace Report</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --pass:   #22c55e; --pass-bg:   #dcfce7;
      --fail:   #ef4444; --fail-bg:   #fee2e2;
      --skip:   #eab308; --skip-bg:   #fef9c3;
      --other:  #6b7280; --other-bg:  #f3f4f6;
      --border: #e5e7eb;
      --bg:     #f9fafb;
      --surface:#ffffff;
      --text:   #111827;
      --muted:  #6b7280;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 24px;
    }}

    .container {{ max-width: 1200px; margin: 0 auto; }}

    h1 {{ font-size: 1.5rem; font-weight: 700; margin-bottom: 4px; }}
    .subtitle {{ color: var(--muted); font-size: 0.875rem; margin-bottom: 24px; }}

    /* Summary bar */
    .summary {{
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
      margin-bottom: 24px;
    }}

    .stat-card {{
      background: var(--surface);
      border-radius: 10px;
      padding: 16px 20px;
      box-shadow: 0 1px 3px rgba(0,0,0,.08);
      min-width: 120px;
      text-align: center;
    }}

    .stat-card .value {{
      font-size: 2rem;
      font-weight: 700;
      line-height: 1;
    }}

    .stat-card .label {{
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      color: var(--muted);
      margin-top: 4px;
    }}

    .value.pass  {{ color: var(--pass); }}
    .value.fail  {{ color: var(--fail); }}
    .value.skip  {{ color: var(--skip); }}

    /* Progress bar */
    .progress-wrap {{
      background: var(--border);
      border-radius: 4px;
      height: 8px;
      overflow: hidden;
      margin-bottom: 24px;
    }}

    .progress-pass  {{ height: 100%; float: left; background: var(--pass); }}
    .progress-fail  {{ height: 100%; float: left; background: var(--fail); }}
    .progress-skip  {{ height: 100%; float: left; background: var(--skip); }}

    /* Table */
    .table-wrap {{ overflow-x: auto; }}

    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--surface);
      border-radius: 10px;
      overflow: hidden;
      box-shadow: 0 1px 3px rgba(0,0,0,.08);
      font-size: 0.875rem;
    }}

    thead tr {{ background: var(--bg); }}

    th, td {{
      padding: 12px 16px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}

    th {{
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      color: var(--muted);
    }}

    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #f8fafc; }}

    /* Badges */
    .status-badge {{
      display: inline-flex;
      align-items: center;
      padding: 2px 10px;
      border-radius: 9999px;
      font-size: 0.6875rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.02em;
    }}

    .status-badge.pass  {{ background: var(--pass-bg);  color: var(--pass); }}
    .status-badge.fail  {{ background: var(--fail-bg);  color: var(--fail); }}
    .status-badge.skip  {{ background: var(--skip-bg);  color: var(--skip); }}
    .status-badge.other {{ background: var(--other-bg); color: var(--other); }}

    a {{ color: #2563eb; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    .no-viewer {{ color: var(--muted); font-style: italic; font-size: 0.8rem; }}
  </style>
</head>
<body>
<div class="container">
  <h1>Robot Framework Trace Report</h1>
  <p class="subtitle">
    {stats["total"]} test(s) &mdash;
    generated by robotframework-trace-viewer
  </p>

  <div class="summary">
    <div class="stat-card">
      <div class="value">{stats["total"]}</div>
      <div class="label">Total</div>
    </div>
    <div class="stat-card">
      <div class="value pass">{stats["passed"]}</div>
      <div class="label">Passed</div>
    </div>
    <div class="stat-card">
      <div class="value fail">{stats["failed"]}</div>
      <div class="label">Failed</div>
    </div>
    <div class="stat-card">
      <div class="value skip">{stats["skipped"]}</div>
      <div class="label">Skipped</div>
    </div>
    <div class="stat-card">
      <div class="value">{pass_rate}%</div>
      <div class="label">Pass Rate</div>
    </div>
  </div>

  <div class="progress-wrap">
    <div class="progress-pass"
         style="width:{(stats['passed'] / stats['total'] * 100) if stats['total'] else 0:.1f}%"></div>
    <div class="progress-fail"
         style="width:{(stats['failed'] / stats['total'] * 100) if stats['total'] else 0:.1f}%"></div>
    <div class="progress-skip"
         style="width:{(stats['skipped'] / stats['total'] * 100) if stats['total'] else 0:.1f}%"></div>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Test Name</th>
          <th>Suite</th>
          <th>Status</th>
          <th>Duration</th>
          <th>Viewer</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>
</div>
</body>
</html>"""

    def _render_jenkins_rows(self, traces: list[dict]) -> str:
        """Render the ``<tr>`` elements for the Jenkins index table.

        Args:
            traces: Trace metadata list with optional ``"viewer_rel_path"``
                key.

        Returns:
            HTML string of concatenated ``<tr>`` elements.
        """
        if not traces:
            return (
                '<tr><td colspan="6" '
                'style="text-align:center;color:var(--muted);font-style:italic;">'
                "No traces found."
                "</td></tr>"
            )

        rows: list[str] = []
        for index, trace in enumerate(traces, start=1):
            test_name = trace.get("test_name") or trace.get("trace_name") or "Unknown"
            suite_name = trace.get("suite_name") or "—"
            status = (trace.get("status") or "UNKNOWN").upper()
            duration_ms = trace.get("duration_ms") or 0
            viewer_rel = trace.get("viewer_rel_path")

            badge = self._status_badge_html(status)
            duration_str = self._format_duration(duration_ms)

            if viewer_rel:
                viewer_cell = f'<a href="{viewer_rel}">View trace</a>'
            else:
                viewer_cell = '<span class="no-viewer">no viewer</span>'

            # Escape user-supplied strings to prevent XSS in the static report.
            safe_name = _html_escape(test_name)
            safe_suite = _html_escape(suite_name)

            rows.append(
                f"<tr>"
                f"<td>{index}</td>"
                f"<td>{safe_name}</td>"
                f"<td>{safe_suite}</td>"
                f"<td>{badge}</td>"
                f"<td>{duration_str}</td>"
                f"<td>{viewer_cell}</td>"
                f"</tr>"
            )

        return "\n        ".join(rows)

    # ------------------------------------------------------------------
    # Markdown rendering (GitLab)
    # ------------------------------------------------------------------

    def _render_gitlab_markdown(self, traces: list[dict], stats: dict) -> str:
        """Render the GitLab MR comment Markdown string.

        The output uses GitLab flavoured Markdown with emoji shortcuts such
        as ``:white_check_mark:`` for PASS, ``:x:`` for FAIL, and
        ``:warning:`` for SKIP/skipped states.

        Args:
            traces: Trace metadata list with optional ``"viewer_rel_path"``
                key.
            stats: Aggregate statistics dict from :meth:`_compute_stats`.

        Returns:
            Complete Markdown document as a string.
        """
        header = (
            "## Robot Framework Trace Report\n\n"
            "| Test Name | Status | Duration | Viewer |\n"
            "| --- | :---: | ---: | --- |\n"
        )

        table_rows: list[str] = []
        for trace in traces:
            test_name = trace.get("test_name") or trace.get("trace_name") or "Unknown"
            status = (trace.get("status") or "UNKNOWN").upper()
            duration_ms = trace.get("duration_ms") or 0
            viewer_rel = trace.get("viewer_rel_path")

            emoji = _GITLAB_EMOJI.get(status, ":grey_question:")
            duration_str = self._format_duration(duration_ms)

            viewer_cell = f"[View trace]({viewer_rel})" if viewer_rel else "*(no viewer)*"

            # Escape pipe characters in test names to avoid breaking the table.
            safe_name = test_name.replace("|", "\\|")

            table_rows.append(
                f"| {safe_name} | {emoji} {status} | {duration_str} | {viewer_cell} |"
            )

        summary_line = (
            f"\n**Summary:** "
            f":white_check_mark: {stats['passed']} passed, "
            f":x: {stats['failed']} failed, "
            f":warning: {stats['skipped']} skipped "
            f"— {stats['total']} total\n"
        )

        return header + "\n".join(table_rows) + summary_line


# ---------------------------------------------------------------------------
# Internal utility
# ---------------------------------------------------------------------------


def _html_escape(text: str) -> str:
    """Escape HTML special characters to prevent injection in static reports.

    Args:
        text: Raw string to escape.

    Returns:
        HTML-safe string with ``&``, ``<``, ``>``, ``"``, and ``'``
        replaced by their named entity equivalents.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
