"""Merge traces from parallel Pabot execution into a unified timeline.

Scans for Pabot-generated trace directories, parses manifests, and generates
a unified suite viewer with swimlanes showing parallel execution.
"""

import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Regex to capture an optional pabot suffix at the end of a trace directory name.
# Matches patterns like: "my_test_20250119_143022_pabot0" or "my_test_20250119_pabot12"
_PABOT_SUFFIX_RE = re.compile(r"_pabot(\d+)$", re.IGNORECASE)


def extract_worker_id(trace_dir_name: str) -> str:
    """Parse a trace directory name to extract the Pabot worker identifier.

    Looks for a trailing ``_pabotN`` segment (case-insensitive) where *N* is
    one or more digits.  When no such segment is found the trace is assumed to
    be a plain sequential Robot Framework run.

    Args:
        trace_dir_name: The bare directory name (not the full path).
            Examples: ``"login_test_20250119_143022_pabot1"``,
            ``"smoke_test_20250120_pabot0"``, ``"regression_20250121"``.

    Returns:
        ``"pabot0"``, ``"pabot1"``, … for Pabot workers, or
        ``"sequential"`` when no Pabot suffix is found.

    Examples:
        >>> extract_worker_id("login_test_20250119_143022_pabot1")
        'pabot1'
        >>> extract_worker_id("smoke_test_20250120_pabot0")
        'pabot0'
        >>> extract_worker_id("regression_20250121_143022")
        'sequential'
        >>> extract_worker_id("pabot")
        'sequential'
    """
    match = _PABOT_SUFFIX_RE.search(trace_dir_name)
    if match:
        return f"pabot{match.group(1)}"
    return "sequential"


class PabotMerger:
    """Merge Robot Framework traces from parallel Pabot execution.

    Scans a directory that contains per-test trace sub-directories produced by
    the ``TraceListener`` during a ``pabot`` run.  Each sub-directory may carry
    a ``_pabotN`` suffix appended by :class:`~trace_viewer.storage.TraceWriter`
    when ``PABOTQUEUEINDEX`` is set.

    The merger:

    1. Discovers every sub-directory that contains a ``manifest.json``.
    2. Labels each trace with a *worker_id* (``"pabot0"``, ``"pabot1"``, …, or
       ``"sequential"``).
    3. Generates a self-contained Gantt-style HTML timeline that groups tests
       into horizontal swimlanes – one per worker.
    4. Copies individual ``viewer.html`` files into the output directory so
       that clicking on a Gantt block navigates to the detailed trace.

    Attributes:
        traces_dir: Root directory that is scanned for trace sub-directories.
        traces: List of trace metadata dictionaries populated by
            :meth:`scan_traces`.

    Example:
        >>> merger = PabotMerger(Path("./e2e_traces_pabot"))
        >>> output_dir = merger.merge()
        >>> print(f"Merged viewer written to: {output_dir / 'timeline.html'}")
    """

    def __init__(self, traces_dir: Path) -> None:
        """Initialize PabotMerger.

        Args:
            traces_dir: Path to the directory containing per-test trace
                sub-directories.  The directory does not need to exist at
                construction time; existence is validated when
                :meth:`scan_traces` is called.
        """
        self.traces_dir = Path(traces_dir)
        self.traces: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan_traces(self) -> list[dict[str, Any]]:
        """Discover and load all trace manifests under :attr:`traces_dir`.

        Iterates over every immediate sub-directory of :attr:`traces_dir`.  A
        sub-directory is considered a valid trace when it contains a
        ``manifest.json`` file.

        Each returned dictionary is the deserialized manifest enriched with
        two additional keys:

        - ``"trace_dir"`` (``str``): absolute path to the trace sub-directory.
        - ``"worker_id"`` (``str``): extracted via :func:`extract_worker_id`.

        The returned list is sorted by ``"start_time"`` in ascending order so
        that earlier tests appear first.  Traces whose ``start_time`` is
        missing or unparseable sort to the end.

        Returns:
            Sorted list of trace metadata dictionaries.  Also stored on
            ``self.traces`` as a side-effect.

        Raises:
            FileNotFoundError: If :attr:`traces_dir` does not exist.

        Example:
            >>> merger = PabotMerger(Path("./traces"))
            >>> traces = merger.scan_traces()
            >>> for t in traces:
            ...     print(t["worker_id"], t["test_name"])
        """
        if not self.traces_dir.exists():
            raise FileNotFoundError(f"Traces directory not found: {self.traces_dir}")

        found: list[dict[str, Any]] = []

        for entry in self.traces_dir.iterdir():
            if not entry.is_dir():
                continue

            manifest_path = entry / "manifest.json"
            if not manifest_path.exists():
                logger.debug("Skipping directory without manifest: %s", entry)
                continue

            try:
                with open(manifest_path, encoding="utf-8") as fh:
                    manifest: dict[str, Any] = json.load(fh)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to read manifest %s: %s", manifest_path, exc)
                continue

            manifest["trace_dir"] = str(entry)
            manifest["worker_id"] = extract_worker_id(entry.name)
            found.append(manifest)

        # Sort by start_time; traces without a valid timestamp sort last.
        found.sort(key=lambda t: _parse_iso_datetime(t.get("start_time", "")))

        self.traces = found
        logger.debug("Discovered %d trace(s) in %s", len(found), self.traces_dir)
        return found

    def merge(self, output_dir: Optional[Path] = None) -> Path:
        """Merge all discovered traces into a unified HTML timeline viewer.

        Steps performed:

        1. :meth:`scan_traces` is called (or re-called) to refresh
           ``self.traces``.
        2. Individual ``viewer.html`` files are copied into *output_dir* using
           the original trace directory name as a sub-folder so that relative
           links remain valid.
        3. :meth:`generate_timeline_html` writes ``timeline.html`` into
           *output_dir*.

        Args:
            output_dir: Directory where the merged output is written.
                Defaults to ``traces_dir / "merged"``.

        Returns:
            Path to *output_dir* (which now contains ``timeline.html`` and
            one sub-folder per trace).

        Raises:
            FileNotFoundError: If :attr:`traces_dir` does not exist.

        Example:
            >>> merger = PabotMerger(Path("./e2e_traces_pabot"))
            >>> out = merger.merge(Path("/tmp/merged_output"))
            >>> # Open out / "timeline.html" in a browser
        """
        self.scan_traces()

        if output_dir is None:
            output_dir = self.traces_dir / "merged"

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Copy individual viewer files so Gantt click-through links work.
        for trace in self.traces:
            src_dir = Path(trace["trace_dir"])
            viewer_src = src_dir / "viewer.html"
            if viewer_src.exists():
                dest_sub = output_dir / src_dir.name
                dest_sub.mkdir(parents=True, exist_ok=True)
                shutil.copy2(viewer_src, dest_sub / "viewer.html")
                # Copy keyword assets (screenshots, etc.) so viewer works stand-alone.
                kw_src = src_dir / "keywords"
                if kw_src.exists():
                    kw_dest = dest_sub / "keywords"
                    if kw_dest.exists():
                        shutil.rmtree(kw_dest)
                    shutil.copytree(kw_src, kw_dest)
            else:
                logger.debug("No viewer.html found in %s; skipping asset copy.", src_dir)

        timeline_path = self.generate_timeline_html(self.traces, output_dir)
        logger.info("Merged timeline written to: %s", timeline_path)
        return output_dir

    def generate_timeline_html(self, traces: list[dict[str, Any]], output: Path) -> Path:
        """Generate a self-contained Gantt-chart HTML file.

        The generated page shows:

        - A **summary bar** at the top with total test count, pass/fail/skip
          breakdown, wall-clock duration, and a parallel speedup estimate.
        - One **swimlane row** per worker (``pabot0``, ``pabot1``, …, and a
          ``sequential`` row when non-Pabot traces are present).
        - Coloured blocks inside each lane representing individual tests.
          Block width is proportional to the test duration relative to the
          total timeline.  Colours follow the convention used elsewhere in the
          project: green = PASS, red = FAIL, yellow = SKIP, grey = other.
        - **Hover tooltips** that show the test name, worker, status, and
          formatted duration.
        - **Click-through navigation** to the individual ``viewer.html`` when
          one exists in the sibling directory.

        The file is entirely self-contained (inline CSS and JS; no external
        network requests).

        Args:
            traces: List of trace metadata dictionaries as returned by
                :meth:`scan_traces`.
            output: Directory in which to write ``timeline.html``.

        Returns:
            Path to the written ``timeline.html`` file.

        Example:
            >>> merger = PabotMerger(Path("./traces"))
            >>> traces = merger.scan_traces()
            >>> timeline = merger.generate_timeline_html(traces, Path("/tmp/out"))
        """
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        html = _build_timeline_html(traces)
        timeline_path = output / "timeline.html"
        timeline_path.write_text(html, encoding="utf-8")
        return timeline_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_iso_datetime(value: str) -> datetime:
    """Parse an ISO 8601 datetime string, returning a sentinel on failure.

    Args:
        value: ISO 8601 string (e.g. ``"2026-01-20T06:19:26.053783+00:00"``).

    Returns:
        A :class:`~datetime.datetime` instance.  Returns
        ``datetime.max`` (timezone-aware) when *value* is empty or cannot be
        parsed, so that unparseable traces sort to the end.
    """
    if not value:
        return datetime.max.replace(tzinfo=timezone.utc)
    try:
        # Python 3.7+: fromisoformat handles most ISO 8601 variants except
        # the trailing "Z" shorthand for UTC.
        normalised = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalised)
    except (ValueError, TypeError):
        return datetime.max.replace(tzinfo=timezone.utc)


def _format_duration(ms: float) -> str:
    """Format a millisecond duration into a human-readable string.

    Args:
        ms: Duration in milliseconds.

    Returns:
        A compact string such as ``"123 ms"``, ``"1.23 s"``, or ``"2m 03s"``.
    """
    if ms < 1000:
        return f"{ms:.0f} ms"
    seconds = ms / 1000
    if seconds < 60:
        return f"{seconds:.2f} s"
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes}m {remainder:04.1f}s"


def _status_color(status: str) -> tuple[str, str]:
    """Return (background, border) CSS colour pair for a test status.

    Colours mirror the CSS variables used in ``viewer.html``:
    - PASS  -> green
    - FAIL  -> red
    - SKIP  -> yellow/amber
    - other -> grey

    Args:
        status: Status string (``"PASS"``, ``"FAIL"``, ``"SKIP"``, …).

    Returns:
        A ``(background_hex, border_hex)`` tuple.
    """
    status_upper = status.upper()
    if status_upper == "PASS":
        return ("#dcfce7", "#22c55e")
    if status_upper == "FAIL":
        return ("#fee2e2", "#ef4444")
    if status_upper in ("SKIP", "SKIPPED"):
        return ("#fef9c3", "#eab308")
    return ("#f3f4f6", "#6b7280")


def _calculate_summary(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate statistics for the summary bar.

    Args:
        traces: List of trace metadata dictionaries.

    Returns:
        Dictionary with keys:
        - ``total`` (int): total number of traces.
        - ``passed`` (int): count with status PASS.
        - ``failed`` (int): count with status FAIL.
        - ``skipped`` (int): count with status SKIP / SKIPPED.
        - ``wall_time_ms`` (float): wall-clock duration in ms from the
          earliest start to the latest end across all traces.
        - ``sum_duration_ms`` (float): sum of individual test durations.
        - ``speedup`` (float): ratio of sum_duration to wall_time (> 1
          means parallelism helped; 1.0 when wall_time is zero or there are
          no traces).
        - ``workers`` (list[str]): sorted unique worker identifiers.
    """
    total = len(traces)
    passed = sum(1 for t in traces if t.get("status", "").upper() == "PASS")
    failed = sum(1 for t in traces if t.get("status", "").upper() == "FAIL")
    skipped = sum(1 for t in traces if t.get("status", "").upper() in ("SKIP", "SKIPPED"))

    start_times = [_parse_iso_datetime(t.get("start_time", "")) for t in traces]
    end_times = [_parse_iso_datetime(t.get("end_time", "")) for t in traces]

    # Filter out sentinel values (datetime.max) before computing wall time.
    sentinel = datetime.max.replace(tzinfo=timezone.utc)
    valid_starts = [dt for dt in start_times if dt != sentinel]
    valid_ends = [dt for dt in end_times if dt != sentinel]

    if valid_starts and valid_ends:
        earliest = min(valid_starts)
        latest = max(valid_ends)
        wall_time_ms = max((latest - earliest).total_seconds() * 1000, 0.0)
    else:
        wall_time_ms = 0.0

    sum_duration_ms = sum(float(t.get("duration_ms", 0)) for t in traces)

    speedup = round(sum_duration_ms / wall_time_ms, 2) if wall_time_ms > 0 else 1.0

    workers = sorted({t.get("worker_id", "sequential") for t in traces})

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "wall_time_ms": wall_time_ms,
        "sum_duration_ms": sum_duration_ms,
        "speedup": speedup,
        "workers": workers,
    }


def _build_gantt_data(
    traces: list[dict[str, Any]],
) -> tuple[float, float, list[dict[str, Any]]]:
    """Prepare normalised Gantt bar data relative to the earliest start time.

    Each returned record includes ``start_offset_ms`` and ``duration_ms``
    expressed relative to time-zero (the earliest start across all traces).
    This makes it trivial for the JS layer to compute CSS ``left`` and
    ``width`` percentages.

    Args:
        traces: List of trace metadata dictionaries.

    Returns:
        A 3-tuple ``(time_zero_ms, total_span_ms, bars)`` where:

        - ``time_zero_ms``: Unix timestamp in ms of the earliest start.
        - ``total_span_ms``: Span of the whole timeline in ms
          (``latest_end - earliest_start``).  At least 1 to avoid
          division-by-zero.
        - ``bars``: List of dicts each with keys:
          ``worker_id``, ``test_name``, ``status``, ``duration_ms``,
          ``start_offset_ms``, ``viewer_path`` (relative path to
          ``viewer.html`` or empty string).
    """
    sentinel = datetime.max.replace(tzinfo=timezone.utc)

    start_datetimes = [_parse_iso_datetime(t.get("start_time", "")) for t in traces]
    end_datetimes = [_parse_iso_datetime(t.get("end_time", "")) for t in traces]

    valid_starts = [dt for dt in start_datetimes if dt != sentinel]
    valid_ends = [dt for dt in end_datetimes if dt != sentinel]

    if not valid_starts:
        # No parseable timestamps: place all bars at offset 0 with their
        # stated durations so the chart still renders something useful.
        time_zero_ms = 0.0
        total_span_ms = max(float(t.get("duration_ms", 0)) for t in traces) if traces else 1.0
    else:
        earliest = min(valid_starts)
        latest = max(valid_ends) if valid_ends else earliest
        time_zero_ms = earliest.timestamp() * 1000
        total_span_ms = max((latest - earliest).total_seconds() * 1000, 1.0)

    bars: list[dict[str, Any]] = []
    for i, trace in enumerate(traces):
        start_dt = start_datetimes[i]
        offset_ms = start_dt.timestamp() * 1000 - time_zero_ms if start_dt != sentinel else 0.0

        # Determine relative path to the individual viewer.html.  The merger
        # copies viewer files into a sibling folder named after the trace dir.
        trace_dir_name = Path(trace["trace_dir"]).name
        viewer_html = Path(trace["trace_dir"]) / "viewer.html"
        viewer_path = f"{trace_dir_name}/viewer.html" if viewer_html.exists() else ""

        bars.append(
            {
                "worker_id": trace.get("worker_id", "sequential"),
                "test_name": trace.get("test_name", "Unknown"),
                "suite_name": trace.get("suite_name", ""),
                "status": trace.get("status", "NOT RUN"),
                "duration_ms": float(trace.get("duration_ms", 0)),
                "start_offset_ms": max(offset_ms, 0.0),
                "viewer_path": viewer_path,
            }
        )

    return time_zero_ms, total_span_ms, bars


def _build_timeline_html(traces: list[dict[str, Any]]) -> str:
    """Render the complete self-contained timeline HTML string.

    Args:
        traces: List of trace metadata dictionaries as returned by
            :meth:`PabotMerger.scan_traces`.

    Returns:
        A complete HTML document string.
    """
    summary = _calculate_summary(traces)
    _time_zero_ms, total_span_ms, bars = _build_gantt_data(traces)

    workers: list[str] = summary["workers"]
    if not workers:
        workers = ["sequential"]

    # Serialise bar data as JSON for the inline script.
    bars_json = json.dumps(bars, indent=2, ensure_ascii=False, default=str)
    workers_json = json.dumps(workers, ensure_ascii=False)

    pass_pct = round(summary["passed"] / summary["total"] * 100) if summary["total"] else 0
    fail_pct = round(summary["failed"] / summary["total"] * 100) if summary["total"] else 0
    skip_pct = round(summary["skipped"] / summary["total"] * 100) if summary["total"] else 0

    wall_fmt = _format_duration(summary["wall_time_ms"])
    sum_fmt = _format_duration(summary["sum_duration_ms"])
    speedup_fmt = f"{summary['speedup']:.2f}x"

    no_traces_msg = (
        "<p style='color:#6b7280;text-align:center;padding:48px 0;font-size:1rem;'>"
        "No traces found in this directory.</p>"
        if not traces
        else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Pabot Parallel Execution Timeline</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --color-pass:      #22c55e;
      --color-pass-bg:   #dcfce7;
      --color-fail:      #ef4444;
      --color-fail-bg:   #fee2e2;
      --color-skip:      #eab308;
      --color-skip-bg:   #fef9c3;
      --color-neutral:   #6b7280;
      --color-neutral-bg:#f3f4f6;
      --bg-primary:      #ffffff;
      --bg-secondary:    #f9fafb;
      --border-color:    #e5e7eb;
      --text-primary:    #111827;
      --text-secondary:  #6b7280;
      --radius:          6px;
      --lane-height:     44px;
      --label-width:     120px;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                   'Helvetica Neue', Arial, sans-serif;
      background: var(--bg-secondary);
      color: var(--text-primary);
      line-height: 1.5;
      min-height: 100vh;
    }}

    /* ---- Header ---- */
    .header {{
      background: var(--bg-primary);
      border-bottom: 1px solid var(--border-color);
      padding: 16px 24px;
    }}
    .header h1 {{
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--text-primary);
    }}
    .header p {{
      font-size: 0.875rem;
      color: var(--text-secondary);
      margin-top: 2px;
    }}

    /* ---- Summary bar ---- */
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      padding: 16px 24px;
      background: var(--bg-primary);
      border-bottom: 1px solid var(--border-color);
    }}
    .stat-card {{
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      padding: 10px 16px;
      min-width: 120px;
      text-align: center;
    }}
    .stat-card .value {{
      font-size: 1.5rem;
      font-weight: 700;
      line-height: 1.2;
    }}
    .stat-card .label {{
      font-size: 0.75rem;
      color: var(--text-secondary);
      margin-top: 2px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .stat-pass   {{ color: var(--color-pass); }}
    .stat-fail   {{ color: var(--color-fail); }}
    .stat-skip   {{ color: var(--color-skip); }}
    .stat-neutral{{ color: var(--color-neutral); }}

    /* ---- Progress bar ---- */
    .progress-bar {{
      display: flex;
      height: 6px;
      border-radius: 3px;
      overflow: hidden;
      margin: 0 24px 12px;
    }}
    .progress-bar .seg-pass  {{ background: var(--color-pass); }}
    .progress-bar .seg-fail  {{ background: var(--color-fail); }}
    .progress-bar .seg-skip  {{ background: var(--color-skip); }}
    .progress-bar .seg-other {{ background: var(--color-neutral); flex: 1; }}

    /* ---- Gantt chart ---- */
    .gantt-wrapper {{
      padding: 24px;
    }}
    .gantt-title {{
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 12px;
    }}
    .gantt-chart {{
      background: var(--bg-primary);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      overflow: hidden;
    }}
    .gantt-row {{
      display: flex;
      align-items: center;
      border-bottom: 1px solid var(--border-color);
      min-height: var(--lane-height);
    }}
    .gantt-row:last-child {{ border-bottom: none; }}
    .lane-label {{
      flex-shrink: 0;
      width: var(--label-width);
      padding: 0 12px;
      font-size: 0.8125rem;
      font-weight: 600;
      color: var(--text-secondary);
      background: var(--bg-secondary);
      border-right: 1px solid var(--border-color);
      height: 100%;
      display: flex;
      align-items: center;
      font-family: 'SF Mono', 'Fira Code', monospace;
    }}
    .lane-track {{
      flex: 1;
      position: relative;
      height: var(--lane-height);
      overflow: hidden;
    }}

    /* ---- Individual test blocks ---- */
    .test-block {{
      position: absolute;
      top: 6px;
      height: calc(var(--lane-height) - 12px);
      border-radius: 4px;
      border-width: 1px;
      border-style: solid;
      cursor: default;
      display: flex;
      align-items: center;
      padding: 0 6px;
      font-size: 0.6875rem;
      font-weight: 500;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      transition: filter 0.15s ease;
      min-width: 4px;
    }}
    .test-block:hover {{
      filter: brightness(0.92);
      z-index: 10;
    }}
    .test-block.clickable {{ cursor: pointer; }}
    .test-block.clickable:hover {{ filter: brightness(0.88) drop-shadow(0 2px 4px rgba(0,0,0,.15)); }}

    /* ---- Tooltip ---- */
    .tooltip {{
      position: fixed;
      z-index: 9999;
      background: #1f2937;
      color: #f9fafb;
      border-radius: 6px;
      padding: 10px 14px;
      font-size: 0.8125rem;
      pointer-events: none;
      max-width: 320px;
      box-shadow: 0 4px 12px rgba(0,0,0,.3);
      display: none;
    }}
    .tooltip .tt-name   {{ font-weight: 700; margin-bottom: 4px; word-break: break-word; }}
    .tooltip .tt-suite  {{ color: #9ca3af; font-size: 0.75rem; margin-bottom: 4px; }}
    .tooltip .tt-row    {{ display: flex; gap: 8px; }}
    .tooltip .tt-badge  {{
      display: inline-block;
      padding: 1px 7px;
      border-radius: 10px;
      font-size: 0.6875rem;
      font-weight: 700;
      letter-spacing: 0.04em;
    }}
    .tt-pass  {{ background: #166534; color: #dcfce7; }}
    .tt-fail  {{ background: #7f1d1d; color: #fee2e2; }}
    .tt-skip  {{ background: #713f12; color: #fef9c3; }}
    .tt-other {{ background: #374151; color: #e5e7eb; }}

    /* ---- Legend ---- */
    .legend {{
      display: flex;
      gap: 20px;
      padding: 0 24px 24px;
      font-size: 0.8125rem;
      color: var(--text-secondary);
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .legend-swatch {{
      width: 14px;
      height: 14px;
      border-radius: 3px;
      border: 1px solid;
    }}

    /* ---- Empty state ---- */
    .empty-state {{
      padding: 48px 24px;
      text-align: center;
      color: var(--text-secondary);
    }}
  </style>
</head>
<body>

<div class="header">
  <h1>Pabot Parallel Execution Timeline</h1>
  <p>Unified Gantt view across {len(workers)} worker(s) &mdash; {summary['total']} test(s)</p>
</div>

<!-- Summary statistics -->
<div class="summary">
  <div class="stat-card">
    <div class="value stat-neutral">{summary['total']}</div>
    <div class="label">Total</div>
  </div>
  <div class="stat-card">
    <div class="value stat-pass">{summary['passed']}</div>
    <div class="label">Passed ({pass_pct}%)</div>
  </div>
  <div class="stat-card">
    <div class="value stat-fail">{summary['failed']}</div>
    <div class="label">Failed ({fail_pct}%)</div>
  </div>
  <div class="stat-card">
    <div class="value stat-skip">{summary['skipped']}</div>
    <div class="label">Skipped ({skip_pct}%)</div>
  </div>
  <div class="stat-card">
    <div class="value stat-neutral">{wall_fmt}</div>
    <div class="label">Wall time</div>
  </div>
  <div class="stat-card">
    <div class="value stat-neutral">{sum_fmt}</div>
    <div class="label">Sum of tests</div>
  </div>
  <div class="stat-card">
    <div class="value stat-pass">{speedup_fmt}</div>
    <div class="label">Parallel speedup</div>
  </div>
</div>

<!-- Pass/fail progress bar -->
<div class="progress-bar" style="height:8px;margin-top:12px;">
  <div class="seg-pass"  style="width:{pass_pct}%"></div>
  <div class="seg-fail"  style="width:{fail_pct}%"></div>
  <div class="seg-skip"  style="width:{skip_pct}%"></div>
  <div class="seg-other"></div>
</div>

<!-- Gantt chart -->
<div class="gantt-wrapper">
  <div class="gantt-title">Execution Timeline</div>
  <div class="gantt-chart" id="ganttChart">
    {no_traces_msg}
    <!-- rows are injected by the script below -->
  </div>
</div>

<!-- Legend -->
<div class="legend">
  <div class="legend-item">
    <div class="legend-swatch" style="background:#dcfce7;border-color:#22c55e;"></div>
    PASS
  </div>
  <div class="legend-item">
    <div class="legend-swatch" style="background:#fee2e2;border-color:#ef4444;"></div>
    FAIL
  </div>
  <div class="legend-item">
    <div class="legend-swatch" style="background:#fef9c3;border-color:#eab308;"></div>
    SKIP
  </div>
  <div class="legend-item">
    <div class="legend-swatch" style="background:#f3f4f6;border-color:#6b7280;"></div>
    OTHER
  </div>
</div>

<!-- Floating tooltip -->
<div class="tooltip" id="tooltip"></div>

<script>
  "use strict";

  const BARS    = {bars_json};
  const WORKERS = {workers_json};
  const TOTAL_SPAN_MS = {total_span_ms};

  // --- Colour mapping -------------------------------------------------------
  const STATUS_COLORS = {{
    PASS:    {{ bg: "#dcfce7", border: "#22c55e" }},
    FAIL:    {{ bg: "#fee2e2", border: "#ef4444" }},
    SKIP:    {{ bg: "#fef9c3", border: "#eab308" }},
    SKIPPED: {{ bg: "#fef9c3", border: "#eab308" }},
  }};
  const DEFAULT_COLOR = {{ bg: "#f3f4f6", border: "#6b7280" }};

  function colorFor(status) {{
    return STATUS_COLORS[status.toUpperCase()] || DEFAULT_COLOR;
  }}

  function ttClass(status) {{
    const s = status.toUpperCase();
    if (s === "PASS")                   return "tt-pass";
    if (s === "FAIL")                   return "tt-fail";
    if (s === "SKIP" || s === "SKIPPED") return "tt-skip";
    return "tt-other";
  }}

  // --- Duration formatting --------------------------------------------------
  function fmtMs(ms) {{
    if (ms < 1000)  return ms.toFixed(0) + " ms";
    const s = ms / 1000;
    if (s  < 60)   return s.toFixed(2)  + " s";
    const m = Math.floor(s / 60);
    const r = s - m * 60;
    return m + "m " + r.toFixed(1).padStart(4, "0") + "s";
  }}

  // --- Build Gantt rows -----------------------------------------------------
  function buildChart() {{
    const chart = document.getElementById("ganttChart");
    if (!BARS.length) return;

    // Group bars by worker_id, preserving WORKERS order.
    const byWorker = {{}};
    WORKERS.forEach(w => {{ byWorker[w] = []; }});
    BARS.forEach(bar => {{
      const w = bar.worker_id || "sequential";
      if (!byWorker[w]) byWorker[w] = [];
      byWorker[w].push(bar);
    }});

    WORKERS.forEach(workerId => {{
      const row = document.createElement("div");
      row.className = "gantt-row";

      const label = document.createElement("div");
      label.className = "lane-label";
      label.textContent = workerId;
      row.appendChild(label);

      const track = document.createElement("div");
      track.className = "lane-track";

      const barsInLane = byWorker[workerId] || [];
      barsInLane.forEach(bar => {{
        const block = document.createElement("div");
        block.className = "test-block";

        const col = colorFor(bar.status);
        block.style.background    = col.bg;
        block.style.borderColor   = col.border;
        block.style.color         = col.border;  // use border colour for text

        // Position: left% and width% relative to total span.
        const leftPct  = (bar.start_offset_ms  / TOTAL_SPAN_MS) * 100;
        const widthPct = Math.max((bar.duration_ms / TOTAL_SPAN_MS) * 100, 0.2);
        block.style.left  = leftPct  + "%";
        block.style.width = widthPct + "%";

        // Only show label text when the block is wide enough.
        block.textContent = bar.test_name;

        // Navigation to individual viewer.
        if (bar.viewer_path) {{
          block.classList.add("clickable");
          block.title = "Click to open trace viewer";
          block.addEventListener("click", () => {{
            window.location.href = bar.viewer_path;
          }});
        }}

        // Tooltip events.
        block.addEventListener("mouseenter", ev => showTooltip(ev, bar));
        block.addEventListener("mousemove",  ev => moveTooltip(ev));
        block.addEventListener("mouseleave", hideTooltip);

        track.appendChild(block);
      }});

      row.appendChild(track);
      chart.appendChild(row);
    }});
  }}

  // --- Tooltip logic --------------------------------------------------------
  const TOOLTIP_OFFSET_X = 14;
  const TOOLTIP_OFFSET_Y = 14;

  function showTooltip(ev, bar) {{
    const tt  = document.getElementById("tooltip");
    const cls = ttClass(bar.status);
    tt.innerHTML = `
      <div class="tt-name">${{bar.test_name}}</div>
      ${{bar.suite_name ? '<div class="tt-suite">' + bar.suite_name + '</div>' : ""}}
      <div class="tt-row">
        <span class="tt-badge ${{cls}}">${{bar.status}}</span>
        <span>${{fmtMs(bar.duration_ms)}}</span>
        <span style="color:#9ca3af;font-size:0.75rem;">${{bar.worker_id}}</span>
      </div>
    `;
    tt.style.display = "block";
    moveTooltip(ev);
  }}

  function moveTooltip(ev) {{
    const tt = document.getElementById("tooltip");
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let x = ev.clientX + TOOLTIP_OFFSET_X;
    let y = ev.clientY + TOOLTIP_OFFSET_Y;
    if (x + 320 > vw) x = ev.clientX - 320 - TOOLTIP_OFFSET_X;
    if (y + 120 > vh) y = ev.clientY - 120 - TOOLTIP_OFFSET_Y;
    tt.style.left = x + "px";
    tt.style.top  = y + "px";
  }}

  function hideTooltip() {{
    document.getElementById("tooltip").style.display = "none";
  }}

  // Boot.
  buildChart();
</script>
</body>
</html>"""

    return html
