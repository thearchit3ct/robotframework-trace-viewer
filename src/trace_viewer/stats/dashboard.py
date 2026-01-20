"""Statistics dashboard module for aggregating and visualizing trace data.

This module provides the StatsDashboard class which analyzes multiple traces
and generates an HTML dashboard with statistics and visualizations.
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class StatsDashboard:
    """Generates statistics dashboard from multiple Robot Framework traces.

    The StatsDashboard class scans a traces directory, aggregates statistics
    from all test executions, and generates an interactive HTML dashboard.

    Statistics include:
    - Total tests, pass/fail/skip rates
    - Average/min/max test durations
    - Top slowest tests
    - Keyword execution counts and durations
    - Timeline of test executions

    Attributes:
        traces_dir: Path to the directory containing traces.
        traces: List of loaded trace data.

    Example:
        >>> dashboard = StatsDashboard(Path("./traces"))
        >>> stats = dashboard.calculate_statistics()
        >>> dashboard.generate_html(Path("./dashboard.html"))
    """

    def __init__(self, traces_dir: Path) -> None:
        """Initialize StatsDashboard with traces directory.

        Args:
            traces_dir: Path to the directory containing trace folders.

        Raises:
            FileNotFoundError: If traces_dir doesn't exist.
        """
        self.traces_dir = Path(traces_dir)
        if not self.traces_dir.exists():
            raise FileNotFoundError(f"Traces directory not found: {self.traces_dir}")

        self.traces: list[dict[str, Any]] = []
        self._load_traces()

    def _load_traces(self) -> None:
        """Load all trace manifests from the traces directory."""
        for item in self.traces_dir.iterdir():
            if item.is_dir():
                manifest_path = item / "manifest.json"
                if manifest_path.exists():
                    try:
                        with open(manifest_path, encoding="utf-8") as f:
                            manifest = json.load(f)
                        manifest["trace_dir"] = str(item)
                        manifest["trace_name"] = item.name
                        self.traces.append(manifest)
                    except (OSError, json.JSONDecodeError):
                        continue

    def calculate_statistics(self) -> dict[str, Any]:
        """Calculate aggregate statistics from all traces.

        Returns:
            Dictionary containing comprehensive statistics including:
            - summary: Overall test counts and pass rates
            - duration_stats: Duration statistics (avg, min, max, total)
            - status_distribution: Breakdown by status
            - keyword_stats: Keyword execution statistics
            - timeline: Tests sorted by date
            - slowest_tests: Top 10 slowest tests
            - test_name_stats: Statistics grouped by test name
        """
        if not self.traces:
            return self._empty_statistics()

        # Basic counts
        total = len(self.traces)
        passed = sum(1 for t in self.traces if t.get("status") == "PASS")
        failed = sum(1 for t in self.traces if t.get("status") == "FAIL")
        skipped = sum(1 for t in self.traces if t.get("status") == "SKIP")
        other = total - passed - failed - skipped

        # Duration statistics
        durations = [t.get("duration_ms", 0) for t in self.traces]
        valid_durations = [d for d in durations if d > 0]

        duration_stats = {
            "total_ms": sum(durations),
            "average_ms": (
                int(sum(valid_durations) / len(valid_durations)) if valid_durations else 0
            ),
            "min_ms": min(valid_durations) if valid_durations else 0,
            "max_ms": max(valid_durations) if valid_durations else 0,
        }

        # Status distribution
        status_distribution = {
            "PASS": passed,
            "FAIL": failed,
            "SKIP": skipped,
            "OTHER": other,
        }

        # Keyword statistics
        keyword_stats = self._calculate_keyword_stats()

        # Timeline (sorted by date)
        timeline = self._build_timeline()

        # Slowest tests
        slowest_tests = sorted(
            [
                {
                    "name": t.get("test_name", "Unknown"),
                    "duration_ms": t.get("duration_ms", 0),
                    "status": t.get("status", "UNKNOWN"),
                    "trace_name": t.get("trace_name", ""),
                    "start_time": t.get("start_time", ""),
                }
                for t in self.traces
            ],
            key=lambda x: x["duration_ms"],
            reverse=True,
        )[:10]

        # Test name statistics (for identifying flaky tests)
        test_name_stats = self._calculate_test_name_stats()

        return {
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "other": other,
                "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
                "fail_rate": round(failed / total * 100, 1) if total > 0 else 0,
            },
            "duration_stats": duration_stats,
            "status_distribution": status_distribution,
            "keyword_stats": keyword_stats,
            "timeline": timeline,
            "slowest_tests": slowest_tests,
            "test_name_stats": test_name_stats,
            "generated_at": datetime.now().isoformat(),
        }

    def _empty_statistics(self) -> dict[str, Any]:
        """Return empty statistics structure when no traces exist."""
        return {
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "other": 0,
                "pass_rate": 0,
                "fail_rate": 0,
            },
            "duration_stats": {
                "total_ms": 0,
                "average_ms": 0,
                "min_ms": 0,
                "max_ms": 0,
            },
            "status_distribution": {"PASS": 0, "FAIL": 0, "SKIP": 0, "OTHER": 0},
            "keyword_stats": {"total": 0, "unique": 0, "by_name": {}},
            "timeline": [],
            "slowest_tests": [],
            "test_name_stats": [],
            "generated_at": datetime.now().isoformat(),
        }

    def _calculate_keyword_stats(self) -> dict[str, Any]:
        """Calculate keyword-level statistics."""
        keyword_counts: dict[str, int] = defaultdict(int)
        keyword_durations: dict[str, list[int]] = defaultdict(list)
        keyword_failures: dict[str, int] = defaultdict(int)
        total_keywords = 0

        for trace in self.traces:
            trace_dir = Path(trace.get("trace_dir", ""))
            keywords_dir = trace_dir / "keywords"

            if not keywords_dir.exists():
                continue

            for kw_dir in keywords_dir.iterdir():
                if not kw_dir.is_dir():
                    continue

                metadata_path = kw_dir / "metadata.json"
                if metadata_path.exists():
                    try:
                        with open(metadata_path, encoding="utf-8") as f:
                            kw_data = json.load(f)

                        name = kw_data.get("name", "Unknown")
                        duration = kw_data.get("duration_ms", 0)
                        status = kw_data.get("status", "")

                        keyword_counts[name] += 1
                        keyword_durations[name].append(duration)
                        if status == "FAIL":
                            keyword_failures[name] += 1
                        total_keywords += 1
                    except (OSError, json.JSONDecodeError):
                        continue

        # Calculate per-keyword statistics
        by_name = {}
        for name, count in keyword_counts.items():
            durations = keyword_durations[name]
            by_name[name] = {
                "count": count,
                "failures": keyword_failures[name],
                "avg_duration_ms": int(sum(durations) / len(durations)) if durations else 0,
                "total_duration_ms": sum(durations),
            }

        # Sort by count descending, take top 20
        top_keywords = dict(sorted(by_name.items(), key=lambda x: x[1]["count"], reverse=True)[:20])

        return {
            "total": total_keywords,
            "unique": len(keyword_counts),
            "by_name": top_keywords,
        }

    def _build_timeline(self) -> list[dict[str, Any]]:
        """Build timeline of test executions sorted by date."""
        timeline = []
        for trace in self.traces:
            start_time = trace.get("start_time", "")
            if start_time:
                timeline.append(
                    {
                        "test_name": trace.get("test_name", "Unknown"),
                        "status": trace.get("status", "UNKNOWN"),
                        "start_time": start_time,
                        "duration_ms": trace.get("duration_ms", 0),
                        "trace_name": trace.get("trace_name", ""),
                    }
                )

        # Sort by start time descending (most recent first)
        timeline.sort(key=lambda x: x["start_time"], reverse=True)
        return timeline[:50]  # Limit to 50 most recent

    def _calculate_test_name_stats(self) -> list[dict[str, Any]]:
        """Calculate statistics grouped by test name to identify flaky tests."""
        by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for trace in self.traces:
            test_name = trace.get("test_name", "Unknown")
            by_name[test_name].append(
                {
                    "status": trace.get("status", "UNKNOWN"),
                    "duration_ms": trace.get("duration_ms", 0),
                    "start_time": trace.get("start_time", ""),
                }
            )

        stats = []
        for name, executions in by_name.items():
            total = len(executions)
            passed = sum(1 for e in executions if e["status"] == "PASS")
            failed = sum(1 for e in executions if e["status"] == "FAIL")
            durations = [e["duration_ms"] for e in executions]

            # Calculate flakiness (if both passed and failed)
            is_flaky = passed > 0 and failed > 0
            flakiness_score = min(passed, failed) / total * 100 if is_flaky and total > 0 else 0

            stats.append(
                {
                    "name": name,
                    "total_runs": total,
                    "passed": passed,
                    "failed": failed,
                    "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
                    "avg_duration_ms": int(sum(durations) / len(durations)) if durations else 0,
                    "is_flaky": is_flaky,
                    "flakiness_score": round(flakiness_score, 1),
                }
            )

        # Sort by flakiness score descending, then by total runs
        # Type ignore needed because mypy can't infer dict value types
        stats.sort(
            key=lambda x: (-x["flakiness_score"], -x["total_runs"])  # type: ignore[operator]
        )
        return stats[:20]

    def generate_html(self, output_path: Optional[Path] = None) -> Path:
        """Generate HTML dashboard file.

        Args:
            output_path: Optional path for the output file. If not specified,
                creates 'dashboard.html' in the traces directory.

        Returns:
            Path to the generated HTML file.
        """
        if output_path is None:
            output_path = self.traces_dir / "dashboard.html"
        else:
            output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        stats = self.calculate_statistics()
        html_content = self._generate_dashboard_html(stats)

        output_path.write_text(html_content, encoding="utf-8")
        return output_path

    def _generate_dashboard_html(self, stats: dict[str, Any]) -> str:
        """Generate the HTML content for the dashboard.

        Args:
            stats: Statistics dictionary from calculate_statistics().

        Returns:
            HTML string for the dashboard.
        """
        json_data = json.dumps(stats, ensure_ascii=False, indent=2, default=str)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Statistics Dashboard</title>
    <style>
        *, *::before, *::after {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        :root {{
            --color-pass: #22c55e;
            --color-pass-bg: #dcfce7;
            --color-fail: #ef4444;
            --color-fail-bg: #fee2e2;
            --color-skip: #eab308;
            --color-skip-bg: #fef9c3;
            --color-flaky: #f97316;
            --color-flaky-bg: #ffedd5;
            --bg-primary: #ffffff;
            --bg-secondary: #f9fafb;
            --bg-tertiary: #f3f4f6;
            --text-primary: #111827;
            --text-secondary: #6b7280;
            --border-color: #e5e7eb;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-secondary);
            color: var(--text-primary);
            line-height: 1.5;
            min-height: 100vh;
            padding: 24px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        .header {{
            margin-bottom: 24px;
        }}

        .header h1 {{
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 4px;
        }}

        .header .subtitle {{
            color: var(--text-secondary);
            font-size: 0.875rem;
        }}

        .grid {{
            display: grid;
            gap: 24px;
        }}

        .summary-grid {{
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        }}

        .card {{
            background: var(--bg-primary);
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            padding: 20px;
        }}

        .card-title {{
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--text-secondary);
            margin-bottom: 12px;
        }}

        .stat-value {{
            font-size: 2.5rem;
            font-weight: 700;
            line-height: 1;
        }}

        .stat-value.pass {{ color: var(--color-pass); }}
        .stat-value.fail {{ color: var(--color-fail); }}

        .stat-label {{
            color: var(--text-secondary);
            font-size: 0.875rem;
            margin-top: 4px;
        }}

        .pass-rate {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .rate-bar {{
            flex: 1;
            height: 8px;
            background: var(--bg-tertiary);
            border-radius: 4px;
            overflow: hidden;
        }}

        .rate-fill {{
            height: 100%;
            background: var(--color-pass);
            border-radius: 4px;
            transition: width 0.3s ease;
        }}

        .rate-fill.low {{
            background: var(--color-fail);
        }}

        .table-container {{
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }}

        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}

        th {{
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            font-size: 0.75rem;
        }}

        tr:hover {{
            background: var(--bg-tertiary);
        }}

        .status-badge {{
            display: inline-flex;
            align-items: center;
            padding: 2px 8px;
            border-radius: 9999px;
            font-size: 0.6875rem;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .status-badge.pass {{
            background: var(--color-pass-bg);
            color: var(--color-pass);
        }}

        .status-badge.fail {{
            background: var(--color-fail-bg);
            color: var(--color-fail);
        }}

        .status-badge.skip {{
            background: var(--color-skip-bg);
            color: var(--color-skip);
        }}

        .status-badge.flaky {{
            background: var(--color-flaky-bg);
            color: var(--color-flaky);
        }}

        .two-col {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }}

        @media (max-width: 768px) {{
            .two-col {{
                grid-template-columns: 1fr;
            }}
        }}

        .timeline-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 8px 0;
            border-bottom: 1px solid var(--border-color);
        }}

        .timeline-item:last-child {{
            border-bottom: none;
        }}

        .timeline-status {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }}

        .timeline-status.pass {{ background: var(--color-pass); }}
        .timeline-status.fail {{ background: var(--color-fail); }}
        .timeline-status.skip {{ background: var(--color-skip); }}

        .timeline-name {{
            flex: 1;
            font-weight: 500;
        }}

        .timeline-meta {{
            color: var(--text-secondary);
            font-size: 0.75rem;
        }}

        .keyword-bar {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 0;
            border-bottom: 1px solid var(--border-color);
        }}

        .keyword-bar:last-child {{
            border-bottom: none;
        }}

        .keyword-name {{
            width: 200px;
            font-weight: 500;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .keyword-bar-fill {{
            flex: 1;
            height: 20px;
            background: var(--bg-tertiary);
            border-radius: 4px;
            overflow: hidden;
            position: relative;
        }}

        .keyword-bar-inner {{
            height: 100%;
            background: #3b82f6;
            border-radius: 4px;
        }}

        .keyword-count {{
            width: 60px;
            text-align: right;
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>Test Statistics Dashboard</h1>
            <p class="subtitle" id="generated-at"></p>
        </header>

        <div class="grid summary-grid" id="summary-cards"></div>

        <div class="two-col" style="margin-top: 24px;">
            <div class="card">
                <h2 class="card-title">Recent Tests</h2>
                <div id="timeline"></div>
            </div>
            <div class="card">
                <h2 class="card-title">Slowest Tests</h2>
                <div class="table-container" id="slowest-table"></div>
            </div>
        </div>

        <div class="two-col" style="margin-top: 24px;">
            <div class="card">
                <h2 class="card-title">Top Keywords by Execution Count</h2>
                <div id="keywords-chart"></div>
            </div>
            <div class="card">
                <h2 class="card-title">Flaky Tests</h2>
                <div class="table-container" id="flaky-table"></div>
            </div>
        </div>
    </div>

    <script>
        const STATS = {json_data};

        function formatDuration(ms) {{
            if (ms < 1000) return `${{ms}}ms`;
            if (ms < 60000) return `${{(ms/1000).toFixed(2)}}s`;
            const min = Math.floor(ms/60000);
            const sec = ((ms%60000)/1000).toFixed(1);
            return `${{min}}m ${{sec}}s`;
        }}

        function formatDate(isoString) {{
            if (!isoString) return 'N/A';
            const date = new Date(isoString);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        }}

        function escapeHtml(str) {{
            const div = document.createElement('div');
            div.textContent = String(str);
            return div.innerHTML;
        }}

        function getStatusClass(status) {{
            return (status || '').toLowerCase();
        }}

        function renderSummaryCards() {{
            const s = STATS.summary;
            const d = STATS.duration_stats;
            const passRateClass = s.pass_rate >= 80 ? '' : 'low';

            document.getElementById('summary-cards').innerHTML = `
                <div class="card">
                    <h2 class="card-title">Total Tests</h2>
                    <div class="stat-value">${{s.total}}</div>
                </div>
                <div class="card">
                    <h2 class="card-title">Passed</h2>
                    <div class="stat-value pass">${{s.passed}}</div>
                    <div class="stat-label">${{s.pass_rate}}% pass rate</div>
                </div>
                <div class="card">
                    <h2 class="card-title">Failed</h2>
                    <div class="stat-value fail">${{s.failed}}</div>
                    <div class="stat-label">${{s.fail_rate}}% fail rate</div>
                </div>
                <div class="card">
                    <h2 class="card-title">Pass Rate</h2>
                    <div class="pass-rate">
                        <span class="stat-value" style="font-size: 1.5rem">${{s.pass_rate}}%</span>
                        <div class="rate-bar">
                            <div class="rate-fill ${{passRateClass}}" style="width: ${{s.pass_rate}}%"></div>
                        </div>
                    </div>
                </div>
                <div class="card">
                    <h2 class="card-title">Average Duration</h2>
                    <div class="stat-value" style="font-size: 1.5rem">${{formatDuration(d.average_ms)}}</div>
                    <div class="stat-label">Min: ${{formatDuration(d.min_ms)}} / Max: ${{formatDuration(d.max_ms)}}</div>
                </div>
                <div class="card">
                    <h2 class="card-title">Total Duration</h2>
                    <div class="stat-value" style="font-size: 1.5rem">${{formatDuration(d.total_ms)}}</div>
                </div>
            `;
        }}

        function renderTimeline() {{
            const timeline = STATS.timeline.slice(0, 15);
            if (timeline.length === 0) {{
                document.getElementById('timeline').innerHTML = '<p style="color: var(--text-secondary); font-style: italic;">No tests found</p>';
                return;
            }}

            const html = timeline.map(t => `
                <div class="timeline-item">
                    <div class="timeline-status ${{getStatusClass(t.status)}}"></div>
                    <span class="timeline-name">${{escapeHtml(t.test_name)}}</span>
                    <span class="timeline-meta">${{formatDuration(t.duration_ms)}}</span>
                </div>
            `).join('');

            document.getElementById('timeline').innerHTML = html;
        }}

        function renderSlowestTests() {{
            const tests = STATS.slowest_tests;
            if (tests.length === 0) {{
                document.getElementById('slowest-table').innerHTML = '<p style="color: var(--text-secondary); font-style: italic;">No tests found</p>';
                return;
            }}

            const html = `
                <table>
                    <thead>
                        <tr>
                            <th>Test</th>
                            <th>Duration</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${{tests.map(t => `
                            <tr>
                                <td>${{escapeHtml(t.name)}}</td>
                                <td>${{formatDuration(t.duration_ms)}}</td>
                                <td><span class="status-badge ${{getStatusClass(t.status)}}">${{t.status}}</span></td>
                            </tr>
                        `).join('')}}
                    </tbody>
                </table>
            `;

            document.getElementById('slowest-table').innerHTML = html;
        }}

        function renderKeywordsChart() {{
            const keywords = STATS.keyword_stats.by_name;
            const entries = Object.entries(keywords).slice(0, 10);

            if (entries.length === 0) {{
                document.getElementById('keywords-chart').innerHTML = '<p style="color: var(--text-secondary); font-style: italic;">No keyword data</p>';
                return;
            }}

            const maxCount = Math.max(...entries.map(([_, v]) => v.count));

            const html = entries.map(([name, data]) => `
                <div class="keyword-bar">
                    <span class="keyword-name" title="${{escapeHtml(name)}}">${{escapeHtml(name)}}</span>
                    <div class="keyword-bar-fill">
                        <div class="keyword-bar-inner" style="width: ${{(data.count / maxCount) * 100}}%"></div>
                    </div>
                    <span class="keyword-count">${{data.count}}</span>
                </div>
            `).join('');

            document.getElementById('keywords-chart').innerHTML = html;
        }}

        function renderFlakyTests() {{
            const flaky = STATS.test_name_stats.filter(t => t.is_flaky);
            if (flaky.length === 0) {{
                document.getElementById('flaky-table').innerHTML = '<p style="color: var(--text-secondary); font-style: italic;">No flaky tests detected</p>';
                return;
            }}

            const html = `
                <table>
                    <thead>
                        <tr>
                            <th>Test</th>
                            <th>Runs</th>
                            <th>Pass Rate</th>
                            <th>Flakiness</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${{flaky.map(t => `
                            <tr>
                                <td>${{escapeHtml(t.name)}}</td>
                                <td>${{t.total_runs}}</td>
                                <td>${{t.pass_rate}}%</td>
                                <td><span class="status-badge flaky">${{t.flakiness_score}}%</span></td>
                            </tr>
                        `).join('')}}
                    </tbody>
                </table>
            `;

            document.getElementById('flaky-table').innerHTML = html;
        }}

        function init() {{
            document.getElementById('generated-at').textContent = 'Generated: ' + formatDate(STATS.generated_at);
            renderSummaryCards();
            renderTimeline();
            renderSlowestTests();
            renderKeywordsChart();
            renderFlakyTests();
        }}

        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', init);
        }} else {{
            init();
        }}
    </script>
</body>
</html>"""
