"""Trace comparison module for comparing two Robot Framework traces.

This module provides the TraceComparator class which compares two traces
and generates a side-by-side comparison HTML report.
"""

import json
from pathlib import Path
from typing import Any, Optional, cast

from .generator import ViewerGenerator


class TraceComparator:
    """Compares two Robot Framework traces and generates comparison reports.

    The TraceComparator loads trace data from two directories, aligns keywords
    by name and index, computes differences in variables and metadata, and
    generates a standalone HTML comparison viewer.

    Attributes:
        trace1_dir: Path to the first trace directory.
        trace2_dir: Path to the second trace directory.
        trace1_data: Loaded data from the first trace.
        trace2_data: Loaded data from the second trace.

    Example:
        >>> comparator = TraceComparator(Path("./trace1"), Path("./trace2"))
        >>> comparison_data = comparator.compare()
        >>> output_path = comparator.generate_html(Path("./comparison.html"))
    """

    def __init__(self, trace1_dir: Path, trace2_dir: Path) -> None:
        """Initialize TraceComparator with two trace directories.

        Args:
            trace1_dir: Path to the first trace directory (left side).
            trace2_dir: Path to the second trace directory (right side).

        Raises:
            FileNotFoundError: If either trace directory doesn't exist or
                doesn't contain a valid manifest.json.
        """
        self.trace1_dir = Path(trace1_dir)
        self.trace2_dir = Path(trace2_dir)

        # Validate directories exist
        if not self.trace1_dir.exists():
            raise FileNotFoundError(f"Trace directory not found: {self.trace1_dir}")
        if not self.trace2_dir.exists():
            raise FileNotFoundError(f"Trace directory not found: {self.trace2_dir}")

        # Load trace data
        self.trace1_data = self._load_trace(self.trace1_dir)
        self.trace2_data = self._load_trace(self.trace2_dir)

    def _load_trace(self, trace_dir: Path) -> dict[str, Any]:
        """Load trace data from a directory.

        Reads manifest.json and keyword data from the trace directory.

        Args:
            trace_dir: Path to the trace directory.

        Returns:
            Dictionary containing trace data with manifest and keywords.

        Raises:
            FileNotFoundError: If manifest.json doesn't exist.
            json.JSONDecodeError: If manifest.json is invalid.
        """
        manifest_path = trace_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        # Use ViewerGenerator's method to load keywords
        generator = ViewerGenerator()
        keywords = generator._load_keywords_from_dir(trace_dir)

        return {
            **manifest,
            "keywords": keywords,
            "trace_dir": str(trace_dir),
            "trace_name": trace_dir.name,
        }

    def compare(self) -> dict[str, Any]:
        """Compare two traces and return comparison data.

        Performs comparison of:
        - Test metadata (name, status, duration)
        - Keywords (aligned by name and index)
        - Variables at each keyword
        - Screenshots presence

        Returns:
            Dictionary containing comparison data suitable for the HTML viewer.
        """
        comparison = {
            "trace1": {
                "name": self.trace1_data.get("trace_name", "Trace 1"),
                "test_name": self.trace1_data.get("test_name", "Unknown"),
                "suite_name": self.trace1_data.get("suite_name", ""),
                "status": self.trace1_data.get("status", "UNKNOWN"),
                "duration_ms": self.trace1_data.get("duration_ms", 0),
                "start_time": self.trace1_data.get("start_time", ""),
                "message": self.trace1_data.get("message", ""),
                "keywords_count": len(self.trace1_data.get("keywords", [])),
                "trace_dir": str(self.trace1_dir),
            },
            "trace2": {
                "name": self.trace2_data.get("trace_name", "Trace 2"),
                "test_name": self.trace2_data.get("test_name", "Unknown"),
                "suite_name": self.trace2_data.get("suite_name", ""),
                "status": self.trace2_data.get("status", "UNKNOWN"),
                "duration_ms": self.trace2_data.get("duration_ms", 0),
                "start_time": self.trace2_data.get("start_time", ""),
                "message": self.trace2_data.get("message", ""),
                "keywords_count": len(self.trace2_data.get("keywords", [])),
                "trace_dir": str(self.trace2_dir),
            },
            "metadata_diff": self._compare_metadata(),
            "keywords_comparison": self._compare_keywords(),
            "summary": {},
        }

        # Calculate summary statistics
        keywords_comparison = cast(list[dict[str, Any]], comparison["keywords_comparison"])
        comparison["summary"] = self._calculate_summary(keywords_comparison)

        return comparison

    def _compare_metadata(self) -> dict[str, dict[str, Any]]:
        """Compare trace metadata between the two traces.

        Returns:
            Dictionary of metadata fields with their values and diff status.
        """
        fields_to_compare = [
            ("test_name", "Test Name"),
            ("suite_name", "Suite Name"),
            ("status", "Status"),
            ("duration_ms", "Duration (ms)"),
            ("rf_version", "RF Version"),
            ("browser", "Browser"),
        ]

        diff = {}
        for field, label in fields_to_compare:
            val1 = self.trace1_data.get(field)
            val2 = self.trace2_data.get(field)
            diff[field] = {
                "label": label,
                "trace1": val1,
                "trace2": val2,
                "changed": val1 != val2,
            }

        return diff

    def _compare_keywords(self) -> list[dict[str, Any]]:
        """Compare keywords between the two traces.

        Keywords are aligned by index first, then name matching is used
        to detect reordering or additions/removals.

        Returns:
            List of keyword comparison entries, each containing:
            - index: Position in the comparison list
            - trace1_kw: Keyword from trace 1 (or None if missing)
            - trace2_kw: Keyword from trace 2 (or None if missing)
            - match_type: 'matched', 'added', 'removed', 'modified'
            - variable_diff: Dictionary of variable differences
        """
        kw1_list = self.trace1_data.get("keywords", [])
        kw2_list = self.trace2_data.get("keywords", [])

        # Build keyword maps by index
        kw1_by_index = {kw.get("index", i + 1): kw for i, kw in enumerate(kw1_list)}
        kw2_by_index = {kw.get("index", i + 1): kw for i, kw in enumerate(kw2_list)}

        # Get all indices
        all_indices = sorted(set(kw1_by_index.keys()) | set(kw2_by_index.keys()))

        comparisons = []
        for idx in all_indices:
            kw1 = kw1_by_index.get(idx)
            kw2 = kw2_by_index.get(idx)

            comparison_entry = self._compare_single_keyword(idx, kw1, kw2)
            comparisons.append(comparison_entry)

        return comparisons

    def _compare_single_keyword(
        self,
        index: int,
        kw1: Optional[dict[str, Any]],
        kw2: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compare a single keyword between the two traces.

        Args:
            index: The keyword index.
            kw1: Keyword from trace 1 (or None).
            kw2: Keyword from trace 2 (or None).

        Returns:
            Comparison entry for this keyword.
        """
        entry = {
            "index": index,
            "trace1_kw": kw1,
            "trace2_kw": kw2,
            "match_type": "matched",
            "name_match": True,
            "status_match": True,
            "duration_diff": 0,
            "variable_diff": {},
        }

        # Determine match type
        if kw1 is None and kw2 is not None:
            entry["match_type"] = "added"
            entry["name_match"] = False
        elif kw1 is not None and kw2 is None:
            entry["match_type"] = "removed"
            entry["name_match"] = False
        elif kw1 is not None and kw2 is not None:
            # Both exist - check for modifications
            name1 = kw1.get("name", "")
            name2 = kw2.get("name", "")
            entry["name_match"] = name1 == name2

            status1 = kw1.get("status", "")
            status2 = kw2.get("status", "")
            entry["status_match"] = status1 == status2

            duration1 = kw1.get("duration_ms", 0)
            duration2 = kw2.get("duration_ms", 0)
            entry["duration_diff"] = duration2 - duration1

            # Compare variables
            vars1 = kw1.get("variables", {})
            vars2 = kw2.get("variables", {})
            entry["variable_diff"] = self._compare_variables(vars1, vars2)

            # Determine if modified
            if not entry["name_match"] or not entry["status_match"] or entry["variable_diff"]:
                entry["match_type"] = "modified"

        return entry

    def _compare_variables(
        self,
        vars1: dict[str, Any],
        vars2: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Compare variables between two keyword snapshots.

        Args:
            vars1: Variables from trace 1.
            vars2: Variables from trace 2.

        Returns:
            Dictionary of variable differences with:
            - added: Variables only in vars2
            - removed: Variables only in vars1
            - changed: Variables with different values
        """
        diff = {}

        all_vars = set(vars1.keys()) | set(vars2.keys())

        for var_name in all_vars:
            val1 = vars1.get(var_name)
            val2 = vars2.get(var_name)

            if var_name not in vars1:
                diff[var_name] = {
                    "type": "added",
                    "trace1": None,
                    "trace2": val2,
                }
            elif var_name not in vars2:
                diff[var_name] = {
                    "type": "removed",
                    "trace1": val1,
                    "trace2": None,
                }
            elif val1 != val2:
                diff[var_name] = {
                    "type": "changed",
                    "trace1": val1,
                    "trace2": val2,
                }

        return diff

    def _calculate_summary(self, keyword_comparisons: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculate summary statistics from keyword comparisons.

        Args:
            keyword_comparisons: List of keyword comparison entries.

        Returns:
            Summary statistics dictionary.
        """
        total = len(keyword_comparisons)
        matched = sum(1 for kw in keyword_comparisons if kw["match_type"] == "matched")
        modified = sum(1 for kw in keyword_comparisons if kw["match_type"] == "modified")
        added = sum(1 for kw in keyword_comparisons if kw["match_type"] == "added")
        removed = sum(1 for kw in keyword_comparisons if kw["match_type"] == "removed")

        status_changes = sum(1 for kw in keyword_comparisons if not kw.get("status_match", True))
        variable_changes = sum(1 for kw in keyword_comparisons if kw.get("variable_diff"))

        return {
            "total_keywords": total,
            "matched": matched,
            "modified": modified,
            "added": added,
            "removed": removed,
            "status_changes": status_changes,
            "variable_changes": variable_changes,
        }

    def generate_html(self, output_path: Path) -> Path:
        """Generate comparison HTML file.

        Creates a standalone HTML file with side-by-side comparison of the
        two traces, including keyword alignment, variable diffs, and
        screenshot comparison.

        Args:
            output_path: Path where the HTML file will be written.

        Returns:
            Path to the generated HTML file.
        """
        comparison_data = self.compare()

        # Generate HTML
        html_content = self._generate_comparison_html(comparison_data)

        # Ensure parent directory exists
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the file
        output_path.write_text(html_content, encoding="utf-8")

        return output_path

    def _generate_comparison_html(self, comparison_data: dict[str, Any]) -> str:
        """Generate the HTML content for the comparison viewer.

        Args:
            comparison_data: The comparison data dictionary.

        Returns:
            HTML string for the comparison viewer.
        """
        # Serialize comparison data to JSON for embedding
        json_data = json.dumps(comparison_data, ensure_ascii=False, indent=2, default=str)

        trace1_name = comparison_data["trace1"]["test_name"]
        trace2_name = comparison_data["trace2"]["test_name"]

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trace Comparison - {trace1_name} vs {trace2_name}</title>
    <style>
        /* Reset and base styles */
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
            --color-not-run: #6b7280;
            --color-not-run-bg: #f3f4f6;
            --color-added: #3b82f6;
            --color-added-bg: #dbeafe;
            --color-removed: #f97316;
            --color-removed-bg: #ffedd5;
            --color-changed: #8b5cf6;
            --color-changed-bg: #ede9fe;
            --bg-primary: #ffffff;
            --bg-secondary: #f9fafb;
            --bg-tertiary: #f3f4f6;
            --text-primary: #111827;
            --text-secondary: #6b7280;
            --border-color: #e5e7eb;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: var(--bg-secondary);
            color: var(--text-primary);
            line-height: 1.5;
            min-height: 100vh;
        }}

        /* Header */
        .header {{
            background: var(--bg-primary);
            border-bottom: 1px solid var(--border-color);
            padding: 16px 24px;
            position: sticky;
            top: 0;
            z-index: 100;
        }}

        .header-content {{
            max-width: 1800px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .header-title {{
            font-size: 1.25rem;
            font-weight: 600;
        }}

        .header-subtitle {{
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-top: 4px;
        }}

        /* Summary panel */
        .summary-panel {{
            background: var(--bg-primary);
            border-bottom: 1px solid var(--border-color);
            padding: 16px 24px;
        }}

        .summary-content {{
            max-width: 1800px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 16px;
        }}

        .summary-item {{
            text-align: center;
            padding: 12px;
            background: var(--bg-tertiary);
            border-radius: 8px;
        }}

        .summary-value {{
            font-size: 1.5rem;
            font-weight: 700;
        }}

        .summary-label {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-top: 4px;
        }}

        .summary-item.matched .summary-value {{ color: var(--color-pass); }}
        .summary-item.modified .summary-value {{ color: var(--color-changed); }}
        .summary-item.added .summary-value {{ color: var(--color-added); }}
        .summary-item.removed .summary-value {{ color: var(--color-removed); }}

        /* Main container */
        .main-container {{
            max-width: 1800px;
            margin: 0 auto;
            padding: 24px;
        }}

        /* Metadata comparison */
        .metadata-section {{
            background: var(--bg-primary);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 24px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }}

        .section-title {{
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border-color);
        }}

        .metadata-grid {{
            display: grid;
            grid-template-columns: 150px 1fr 1fr;
            gap: 8px;
            font-size: 0.875rem;
        }}

        .metadata-header {{
            font-weight: 600;
            color: var(--text-secondary);
            padding: 8px;
            background: var(--bg-tertiary);
            border-radius: 4px;
        }}

        .metadata-cell {{
            padding: 8px;
            border-radius: 4px;
        }}

        .metadata-cell.changed {{
            background: var(--color-changed-bg);
        }}

        /* Keywords comparison */
        .keywords-section {{
            background: var(--bg-primary);
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }}

        .keyword-row {{
            display: grid;
            grid-template-columns: 50px 1fr 1fr;
            gap: 16px;
            padding: 16px;
            border-bottom: 1px solid var(--border-color);
            cursor: pointer;
            transition: background-color 0.15s ease;
        }}

        .keyword-row:last-child {{
            border-bottom: none;
        }}

        .keyword-row:hover {{
            background: var(--bg-tertiary);
        }}

        .keyword-row.selected {{
            background: var(--bg-tertiary);
        }}

        .keyword-index {{
            font-size: 0.875rem;
            color: var(--text-secondary);
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .keyword-side {{
            padding: 12px;
            border-radius: 8px;
            background: var(--bg-tertiary);
        }}

        .keyword-side.missing {{
            background: var(--bg-tertiary);
            opacity: 0.5;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-secondary);
            font-style: italic;
        }}

        .keyword-side.added {{
            border-left: 3px solid var(--color-added);
        }}

        .keyword-side.removed {{
            border-left: 3px solid var(--color-removed);
        }}

        .keyword-side.modified {{
            border-left: 3px solid var(--color-changed);
        }}

        .keyword-name {{
            font-weight: 500;
            margin-bottom: 4px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .keyword-meta {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            display: flex;
            gap: 12px;
        }}

        .status-badge {{
            display: inline-flex;
            align-items: center;
            padding: 2px 8px;
            border-radius: 9999px;
            font-size: 0.625rem;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .status-badge.pass {{
            background-color: var(--color-pass-bg);
            color: var(--color-pass);
        }}

        .status-badge.fail {{
            background-color: var(--color-fail-bg);
            color: var(--color-fail);
        }}

        .status-badge.skip {{
            background-color: var(--color-skip-bg);
            color: var(--color-skip);
        }}

        .status-badge.not-run {{
            background-color: var(--color-not-run-bg);
            color: var(--color-not-run);
        }}

        .match-badge {{
            display: inline-flex;
            align-items: center;
            padding: 2px 8px;
            border-radius: 9999px;
            font-size: 0.625rem;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .match-badge.matched {{
            background-color: var(--color-pass-bg);
            color: var(--color-pass);
        }}

        .match-badge.modified {{
            background-color: var(--color-changed-bg);
            color: var(--color-changed);
        }}

        .match-badge.added {{
            background-color: var(--color-added-bg);
            color: var(--color-added);
        }}

        .match-badge.removed {{
            background-color: var(--color-removed-bg);
            color: var(--color-removed);
        }}

        /* Details panel */
        .details-panel {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: var(--bg-primary);
            border-top: 1px solid var(--border-color);
            box-shadow: 0 -4px 6px rgba(0, 0, 0, 0.1);
            max-height: 50vh;
            overflow-y: auto;
            transform: translateY(100%);
            transition: transform 0.3s ease;
        }}

        .details-panel.open {{
            transform: translateY(0);
        }}

        .details-content {{
            padding: 20px 24px;
            max-width: 1800px;
            margin: 0 auto;
        }}

        .details-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}

        .details-title {{
            font-size: 1rem;
            font-weight: 600;
        }}

        .close-btn {{
            background: none;
            border: none;
            font-size: 1.25rem;
            cursor: pointer;
            color: var(--text-secondary);
            padding: 4px 8px;
            border-radius: 4px;
        }}

        .close-btn:hover {{
            background: var(--bg-tertiary);
        }}

        /* Screenshots comparison */
        .screenshots-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 20px;
        }}

        .screenshot-container {{
            background: var(--bg-tertiary);
            border-radius: 8px;
            overflow: hidden;
        }}

        .screenshot-label {{
            padding: 8px 12px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--border-color);
        }}

        .screenshot-container img {{
            width: 100%;
            height: auto;
            display: block;
        }}

        .no-screenshot {{
            padding: 40px;
            text-align: center;
            color: var(--text-secondary);
            font-style: italic;
        }}

        /* Variables diff */
        .variables-diff {{
            margin-top: 20px;
        }}

        .variables-diff h4 {{
            font-size: 0.875rem;
            font-weight: 600;
            margin-bottom: 12px;
        }}

        .variable-row {{
            display: grid;
            grid-template-columns: 200px 1fr 1fr;
            gap: 12px;
            padding: 8px;
            font-size: 0.875rem;
            border-bottom: 1px solid var(--border-color);
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace;
        }}

        .variable-row:last-child {{
            border-bottom: none;
        }}

        .variable-name {{
            font-weight: 500;
            color: #7c3aed;
        }}

        .variable-value {{
            word-break: break-all;
        }}

        .variable-value.added {{
            background: var(--color-added-bg);
            padding: 2px 6px;
            border-radius: 4px;
        }}

        .variable-value.removed {{
            background: var(--color-removed-bg);
            padding: 2px 6px;
            border-radius: 4px;
            text-decoration: line-through;
        }}

        .variable-value.changed {{
            background: var(--color-changed-bg);
            padding: 2px 6px;
            border-radius: 4px;
        }}

        .variable-value.empty {{
            color: var(--text-secondary);
            font-style: italic;
        }}

        /* Responsive */
        @media (max-width: 1024px) {{
            .screenshots-grid {{
                grid-template-columns: 1fr;
            }}

            .keyword-row {{
                grid-template-columns: 40px 1fr;
            }}

            .keyword-row > .keyword-side:last-child {{
                grid-column: 2;
            }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <div>
                <h1 class="header-title">Trace Comparison</h1>
                <p class="header-subtitle" id="comparison-subtitle"></p>
            </div>
        </div>
    </header>

    <div class="summary-panel">
        <div class="summary-content" id="summary-panel"></div>
    </div>

    <main class="main-container">
        <section class="metadata-section">
            <h2 class="section-title">Test Metadata</h2>
            <div class="metadata-grid" id="metadata-grid"></div>
        </section>

        <section class="keywords-section">
            <h2 class="section-title">Keywords Comparison</h2>
            <div id="keywords-list"></div>
        </section>
    </main>

    <aside class="details-panel" id="details-panel">
        <div class="details-content">
            <div class="details-header">
                <h3 class="details-title" id="details-title">Keyword Details</h3>
                <button class="close-btn" id="close-details">&times;</button>
            </div>
            <div id="details-body"></div>
        </div>
    </aside>

    <script>
        // Comparison data injected by the generator
        const COMPARISON_DATA = {json_data};

        (function() {{
            'use strict';

            let selectedKeywordIndex = null;

            const elements = {{
                subtitle: document.getElementById('comparison-subtitle'),
                summaryPanel: document.getElementById('summary-panel'),
                metadataGrid: document.getElementById('metadata-grid'),
                keywordsList: document.getElementById('keywords-list'),
                detailsPanel: document.getElementById('details-panel'),
                detailsTitle: document.getElementById('details-title'),
                detailsBody: document.getElementById('details-body'),
                closeDetails: document.getElementById('close-details')
            }};

            function escapeHtml(str) {{
                if (str === null || str === undefined) return '';
                const div = document.createElement('div');
                div.textContent = String(str);
                return div.innerHTML;
            }}

            function formatDuration(ms) {{
                if (ms < 1000) return `${{ms}}ms`;
                if (ms < 60000) return `${{(ms / 1000).toFixed(2)}}s`;
                const minutes = Math.floor(ms / 60000);
                const seconds = ((ms % 60000) / 1000).toFixed(1);
                return `${{minutes}}m ${{seconds}}s`;
            }}

            function getStatusClass(status) {{
                const statusMap = {{
                    'PASS': 'pass',
                    'FAIL': 'fail',
                    'SKIP': 'skip',
                    'NOT RUN': 'not-run',
                    'NOT_RUN': 'not-run'
                }};
                return statusMap[status?.toUpperCase()] || 'not-run';
            }}

            function initializeHeader() {{
                const t1 = COMPARISON_DATA.trace1;
                const t2 = COMPARISON_DATA.trace2;
                elements.subtitle.textContent = `${{t1.test_name}} vs ${{t2.test_name}}`;
            }}

            function initializeSummary() {{
                const summary = COMPARISON_DATA.summary;
                elements.summaryPanel.innerHTML = `
                    <div class="summary-item">
                        <div class="summary-value">${{summary.total_keywords}}</div>
                        <div class="summary-label">Total Keywords</div>
                    </div>
                    <div class="summary-item matched">
                        <div class="summary-value">${{summary.matched}}</div>
                        <div class="summary-label">Matched</div>
                    </div>
                    <div class="summary-item modified">
                        <div class="summary-value">${{summary.modified}}</div>
                        <div class="summary-label">Modified</div>
                    </div>
                    <div class="summary-item added">
                        <div class="summary-value">${{summary.added}}</div>
                        <div class="summary-label">Added</div>
                    </div>
                    <div class="summary-item removed">
                        <div class="summary-value">${{summary.removed}}</div>
                        <div class="summary-label">Removed</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-value">${{summary.status_changes}}</div>
                        <div class="summary-label">Status Changes</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-value">${{summary.variable_changes}}</div>
                        <div class="summary-label">Variable Changes</div>
                    </div>
                `;
            }}

            function initializeMetadata() {{
                const diff = COMPARISON_DATA.metadata_diff;
                let html = `
                    <div class="metadata-header">Field</div>
                    <div class="metadata-header">${{escapeHtml(COMPARISON_DATA.trace1.name)}}</div>
                    <div class="metadata-header">${{escapeHtml(COMPARISON_DATA.trace2.name)}}</div>
                `;

                for (const [field, data] of Object.entries(diff)) {{
                    const changedClass = data.changed ? 'changed' : '';
                    let val1 = data.trace1;
                    let val2 = data.trace2;

                    if (field === 'duration_ms') {{
                        val1 = formatDuration(val1 || 0);
                        val2 = formatDuration(val2 || 0);
                    }}

                    html += `
                        <div class="metadata-cell">${{escapeHtml(data.label)}}</div>
                        <div class="metadata-cell ${{changedClass}}">${{escapeHtml(val1 || '-')}}</div>
                        <div class="metadata-cell ${{changedClass}}">${{escapeHtml(val2 || '-')}}</div>
                    `;
                }}

                elements.metadataGrid.innerHTML = html;
            }}

            function renderKeywordSide(kw, side, matchType) {{
                if (!kw) {{
                    return `<div class="keyword-side missing">No keyword at this index</div>`;
                }}

                let sideClass = '';
                if (matchType === 'added' && side === 'trace2') sideClass = 'added';
                if (matchType === 'removed' && side === 'trace1') sideClass = 'removed';
                if (matchType === 'modified') sideClass = 'modified';

                const statusClass = getStatusClass(kw.status);
                const hasScreenshot = kw.screenshot ? '&#128247;' : '';

                return `
                    <div class="keyword-side ${{sideClass}}">
                        <div class="keyword-name">
                            ${{escapeHtml(kw.name)}}
                            <span class="status-badge ${{statusClass}}">${{kw.status || 'N/A'}}</span>
                        </div>
                        <div class="keyword-meta">
                            <span>${{formatDuration(kw.duration_ms || 0)}}</span>
                            <span>${{hasScreenshot}}</span>
                        </div>
                    </div>
                `;
            }}

            function initializeKeywords() {{
                const comparisons = COMPARISON_DATA.keywords_comparison;
                let html = '';

                for (const comp of comparisons) {{
                    html += `
                        <div class="keyword-row" data-index="${{comp.index}}">
                            <div class="keyword-index">
                                ${{comp.index}}
                                <span class="match-badge ${{comp.match_type}}">${{comp.match_type}}</span>
                            </div>
                            ${{renderKeywordSide(comp.trace1_kw, 'trace1', comp.match_type)}}
                            ${{renderKeywordSide(comp.trace2_kw, 'trace2', comp.match_type)}}
                        </div>
                    `;
                }}

                elements.keywordsList.innerHTML = html;

                // Add click handlers
                document.querySelectorAll('.keyword-row').forEach(row => {{
                    row.addEventListener('click', () => {{
                        const index = parseInt(row.dataset.index, 10);
                        selectKeyword(index);
                    }});
                }});
            }}

            function selectKeyword(index) {{
                selectedKeywordIndex = index;

                // Update selection UI
                document.querySelectorAll('.keyword-row').forEach(row => {{
                    row.classList.toggle('selected', parseInt(row.dataset.index, 10) === index);
                }});

                // Find comparison data for this index
                const comp = COMPARISON_DATA.keywords_comparison.find(c => c.index === index);
                if (!comp) return;

                showDetails(comp);
            }}

            function showDetails(comp) {{
                elements.detailsTitle.textContent = `Keyword ${{comp.index}} Details`;

                let html = '';

                // Screenshots section
                html += '<div class="screenshots-grid">';
                html += renderScreenshot(comp.trace1_kw, COMPARISON_DATA.trace1, 'Trace 1');
                html += renderScreenshot(comp.trace2_kw, COMPARISON_DATA.trace2, 'Trace 2');
                html += '</div>';

                // Variables diff
                if (comp.variable_diff && Object.keys(comp.variable_diff).length > 0) {{
                    html += '<div class="variables-diff">';
                    html += '<h4>Variable Differences</h4>';
                    html += renderVariableDiff(comp);
                    html += '</div>';
                }}

                elements.detailsBody.innerHTML = html;
                elements.detailsPanel.classList.add('open');
            }}

            function renderScreenshot(kw, traceInfo, label) {{
                if (!kw || !kw.screenshot) {{
                    return `
                        <div class="screenshot-container">
                            <div class="screenshot-label">${{label}}</div>
                            <div class="no-screenshot">No screenshot available</div>
                        </div>
                    `;
                }}

                // Build the full screenshot path
                const tracePath = traceInfo.trace_dir;
                const screenshotPath = kw.screenshot;

                return `
                    <div class="screenshot-container">
                        <div class="screenshot-label">${{label}}</div>
                        <img src="file://${{tracePath}}/${{screenshotPath}}"
                             alt="Screenshot from ${{label}}"
                             onerror="this.parentElement.innerHTML='<div class=\\'no-screenshot\\'>Failed to load screenshot</div>'" />
                    </div>
                `;
            }}

            function renderVariableDiff(comp) {{
                const diff = comp.variable_diff;
                if (!diff || Object.keys(diff).length === 0) {{
                    return '<p style="color: var(--text-secondary); font-style: italic;">No variable differences</p>';
                }}

                let html = '';
                for (const [name, data] of Object.entries(diff)) {{
                    const val1 = data.trace1 !== null && data.trace1 !== undefined
                        ? (typeof data.trace1 === 'object' ? JSON.stringify(data.trace1) : String(data.trace1))
                        : '';
                    const val2 = data.trace2 !== null && data.trace2 !== undefined
                        ? (typeof data.trace2 === 'object' ? JSON.stringify(data.trace2) : String(data.trace2))
                        : '';

                    let class1 = '', class2 = '';
                    if (data.type === 'added') {{
                        class1 = 'empty';
                        class2 = 'added';
                    }} else if (data.type === 'removed') {{
                        class1 = 'removed';
                        class2 = 'empty';
                    }} else if (data.type === 'changed') {{
                        class1 = 'changed';
                        class2 = 'changed';
                    }}

                    html += `
                        <div class="variable-row">
                            <div class="variable-name">${{escapeHtml(name)}}</div>
                            <div class="variable-value ${{class1}}">${{val1 || '(none)'}}</div>
                            <div class="variable-value ${{class2}}">${{val2 || '(none)'}}</div>
                        </div>
                    `;
                }}

                return html;
            }}

            function hideDetails() {{
                elements.detailsPanel.classList.remove('open');
                selectedKeywordIndex = null;
                document.querySelectorAll('.keyword-row').forEach(row => {{
                    row.classList.remove('selected');
                }});
            }}

            function handleKeyboard(event) {{
                if (event.key === 'Escape') {{
                    hideDetails();
                }}
            }}

            function initialize() {{
                initializeHeader();
                initializeSummary();
                initializeMetadata();
                initializeKeywords();

                elements.closeDetails.addEventListener('click', hideDetails);
                document.addEventListener('keydown', handleKeyboard);
            }}

            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', initialize);
            }} else {{
                initialize();
            }}
        }})();
    </script>
</body>
</html>"""

        return html
