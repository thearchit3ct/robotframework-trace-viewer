"""Command-line interface for Robot Framework Trace Viewer."""

import json
import webbrowser
import zipfile
from pathlib import Path
from typing import Any, Optional

import click

from trace_viewer import __version__
from trace_viewer.viewer.comparator import TraceComparator


@click.group()
@click.version_option(version=__version__, prog_name="trace-viewer")
def main() -> None:
    """Robot Framework Trace Viewer - Visual debugging for RF tests."""
    pass


@main.command("open")
@click.argument("trace_path", type=click.Path(exists=True))
def open_trace(trace_path: str) -> None:
    """Open a trace in the default web browser.

    Searches for viewer.html or index.html in the trace directory and opens
    it in the default web browser.

    Args:
        trace_path: Path to the trace directory.

    Raises:
        SystemExit: If no viewer.html or index.html is found.
    """
    path = Path(trace_path)

    # Search for viewer.html or index.html
    viewer_file = None
    for name in ["viewer.html", "index.html"]:
        candidate = path / name
        if candidate.exists():
            viewer_file = candidate
            break

    if viewer_file is None:
        click.echo(f"Error: No viewer.html found in {trace_path}", err=True)
        raise SystemExit(1)

    click.echo(f"Opening {viewer_file}")
    webbrowser.open(f"file://{viewer_file.absolute()}")


@main.command("list")
@click.argument("traces_dir", type=click.Path(exists=True), default="./traces")
def list_traces(traces_dir: str) -> None:
    """List available traces in a directory.

    Scans a directory for trace folders and displays a summary of each
    including test name, status, path, and duration. Results are sorted
    by date in descending order.

    Args:
        traces_dir: Path to the directory containing trace folders.
            Defaults to './traces'.
    """
    path = Path(traces_dir)
    traces: list[dict[str, Any]] = []

    for item in path.iterdir():
        if item.is_dir():
            manifest = item / "manifest.json"
            if manifest.exists():
                with open(manifest, encoding="utf-8") as f:
                    data = json.load(f)
                traces.append(
                    {
                        "path": str(item),
                        "name": data.get("test_name", item.name),
                        "status": data.get("status", "UNKNOWN"),
                        "date": data.get("start_time", ""),
                        "duration_ms": data.get("duration_ms", 0),
                    }
                )

    if not traces:
        click.echo("No traces found.")
        return

    # Sort by date descending
    traces.sort(key=lambda x: x["date"], reverse=True)

    click.echo(f"Found {len(traces)} trace(s):\n")
    for t in traces:
        status_color = "green" if t["status"] == "PASS" else "red"
        click.echo(f"  [{click.style(t['status'], fg=status_color)}] {t['name']}")
        click.echo(f"      Path: {t['path']}")
        click.echo(f"      Duration: {t['duration_ms']}ms")
        click.echo()


@main.command()
@click.argument("trace_path", type=click.Path(exists=True))
def info(trace_path: str) -> None:
    """Display detailed information about a trace.

    Reads the manifest.json from a trace directory and displays comprehensive
    information including test name, status, suite details, timing, keyword
    count, and the first 10 keywords with their statuses.

    Args:
        trace_path: Path to the trace directory.

    Raises:
        SystemExit: If manifest.json is not found in the trace directory.
    """
    path = Path(trace_path)
    manifest = path / "manifest.json"

    if not manifest.exists():
        click.echo(f"Error: No manifest.json found in {trace_path}", err=True)
        raise SystemExit(1)

    with open(manifest, encoding="utf-8") as f:
        data = json.load(f)

    status = data.get("status", "UNKNOWN")
    status_color = "green" if status == "PASS" else "red"

    click.echo(f"\nTrace: {click.style(data.get('test_name', 'Unknown'), bold=True)}")
    click.echo(f"Status: {click.style(status, fg=status_color)}")
    click.echo(f"Suite: {data.get('suite_name', 'N/A')}")
    click.echo(f"Source: {data.get('suite_source', 'N/A')}")
    click.echo(f"Start: {data.get('start_time', 'N/A')}")
    click.echo(f"Duration: {data.get('duration_ms', 0)}ms")
    click.echo(f"Keywords: {data.get('keywords_count', 0)}")

    if data.get("message"):
        click.echo(f"\nMessage: {data['message']}")

    # List keywords
    keywords_dir = path / "keywords"
    if keywords_dir.exists():
        keywords = sorted(keywords_dir.iterdir())
        click.echo(f"\nKeywords ({len(keywords)}):")
        for kw_dir in keywords[:10]:  # Display first 10
            metadata_file = kw_dir / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, encoding="utf-8") as f:
                    kw_data = json.load(f)
                kw_status = kw_data.get("status", "?")
                if kw_status == "PASS":
                    kw_color = "green"
                elif kw_status == "FAIL":
                    kw_color = "red"
                else:
                    kw_color = "yellow"
                click.echo(
                    f"  [{click.style(kw_status, fg=kw_color)}] {kw_data.get('name', kw_dir.name)}"
                )
        if len(keywords) > 10:
            click.echo(f"  ... and {len(keywords) - 10} more")


@main.command()
@click.argument("trace_path", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output ZIP file path. Defaults to <trace_name>.zip in current directory.",
)
def export(trace_path: str, output: Optional[str]) -> None:
    """Export a trace as a standalone ZIP archive.

    Creates a ZIP file containing all trace files including manifest.json,
    keywords directory with metadata and screenshots, and viewer.html.
    The ZIP can be shared and opened on any machine without requiring
    the trace-viewer tool.

    Args:
        trace_path: Path to the trace directory to export.
        output: Optional output path for the ZIP file. If not specified,
            creates <trace_name>.zip in the current directory.

    Raises:
        SystemExit: If manifest.json is not found in the trace directory
            or if the ZIP file cannot be created.

    Examples:
        trace-viewer export ./traces/my_test_20250119_143022
        trace-viewer export ./traces/my_test --output /tmp/my_trace.zip
    """
    path = Path(trace_path)
    manifest = path / "manifest.json"

    if not manifest.exists():
        click.echo(f"Error: No manifest.json found in {trace_path}", err=True)
        click.echo("This does not appear to be a valid trace directory.", err=True)
        raise SystemExit(1)

    # Determine output path
    if output is None:
        output_path = Path.cwd() / f"{path.name}.zip"
    else:
        output_path = Path(output)
        # Ensure .zip extension
        if output_path.suffix.lower() != ".zip":
            output_path = output_path.with_suffix(".zip")

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        _create_trace_zip(path, output_path)
        click.echo(f"Trace exported to: {output_path}")
        click.echo(f"Archive size: {output_path.stat().st_size:,} bytes")
    except OSError as e:
        click.echo(f"Error: Failed to create ZIP archive: {e}", err=True)
        raise SystemExit(1) from None


def _create_trace_zip(trace_dir: Path, output_path: Path) -> None:
    """Create a ZIP archive containing all trace files.

    Recursively adds all files from the trace directory to the ZIP archive,
    preserving the directory structure. Files are stored with paths relative
    to the trace directory root.

    Args:
        trace_dir: Path to the trace directory to archive.
        output_path: Path where the ZIP file will be created.

    Raises:
        OSError: If the ZIP file cannot be created or written.
    """
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in trace_dir.rglob("*"):
            if file_path.is_file():
                # Calculate relative path from trace directory
                arcname = file_path.relative_to(trace_dir)
                zf.write(file_path, arcname)


@main.command()
@click.argument("trace1_path", type=click.Path(exists=True))
@click.argument("trace2_path", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output HTML file path. Defaults to 'comparison.html' in current directory.",
)
@click.option(
    "--open",
    "-O",
    "open_browser",
    is_flag=True,
    default=False,
    help="Open the comparison in the default web browser after generation.",
)
def compare(trace1_path: str, trace2_path: str, output: Optional[str], open_browser: bool) -> None:
    """Compare two traces and generate a side-by-side comparison report.

    Compares two Robot Framework trace directories and generates an HTML
    report showing differences in keywords, variables, and metadata.
    Screenshots from both traces are displayed side by side.

    Args:
        trace1_path: Path to the first trace directory (left side).
        trace2_path: Path to the second trace directory (right side).
        output: Optional output path for the HTML file. If not specified,
            creates 'comparison.html' in the current directory.
        open_browser: If True, opens the comparison in the default browser.

    Raises:
        SystemExit: If either trace directory is invalid or comparison fails.

    Examples:
        trace-viewer compare ./traces/test_v1 ./traces/test_v2
        trace-viewer compare ./trace1 ./trace2 --output /tmp/diff.html
        trace-viewer compare ./trace1 ./trace2 -O  # Open in browser
    """
    trace1 = Path(trace1_path)
    trace2 = Path(trace2_path)

    # Validate trace directories
    if not (trace1 / "manifest.json").exists():
        click.echo(f"Error: No manifest.json found in {trace1_path}", err=True)
        click.echo("This does not appear to be a valid trace directory.", err=True)
        raise SystemExit(1)

    if not (trace2 / "manifest.json").exists():
        click.echo(f"Error: No manifest.json found in {trace2_path}", err=True)
        click.echo("This does not appear to be a valid trace directory.", err=True)
        raise SystemExit(1)

    # Determine output path
    if output is None:
        output_path = Path.cwd() / "comparison.html"
    else:
        output_path = Path(output)
        # Ensure .html extension
        if output_path.suffix.lower() != ".html":
            output_path = output_path.with_suffix(".html")

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        click.echo("Comparing traces:")
        click.echo(f"  Trace 1: {trace1}")
        click.echo(f"  Trace 2: {trace2}")

        comparator = TraceComparator(trace1, trace2)
        comparison_data = comparator.compare()

        # Display summary
        summary = comparison_data["summary"]
        click.echo("\nComparison Summary:")
        click.echo(f"  Total keywords: {summary['total_keywords']}")

        matched = summary["matched"]
        modified = summary["modified"]
        added = summary["added"]
        removed = summary["removed"]

        click.echo(
            f"  Matched: {click.style(str(matched), fg='green')}, "
            f"Modified: {click.style(str(modified), fg='yellow')}, "
            f"Added: {click.style(str(added), fg='blue')}, "
            f"Removed: {click.style(str(removed), fg='red')}"
        )

        if summary["status_changes"] > 0:
            click.echo(
                f"  Status changes: {click.style(str(summary['status_changes']), fg='yellow')}"
            )
        if summary["variable_changes"] > 0:
            click.echo(
                f"  Variable changes: {click.style(str(summary['variable_changes']), fg='yellow')}"
            )

        # Generate HTML
        comparator.generate_html(output_path)
        click.echo(f"\nComparison report generated: {output_path}")

        if open_browser:
            click.echo("Opening in browser...")
            webbrowser.open(f"file://{output_path.absolute()}")

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from None
    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON in trace data: {e}", err=True)
        raise SystemExit(1) from None
    except OSError as e:
        click.echo(f"Error: Failed to generate comparison: {e}", err=True)
        raise SystemExit(1) from None


@main.command()
@click.argument("traces_dir", type=click.Path(exists=True), default="./traces")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output HTML file path. Defaults to 'dashboard.html' in traces directory.",
)
@click.option(
    "--open",
    "-O",
    "open_browser",
    is_flag=True,
    default=False,
    help="Open the dashboard in the default web browser after generation.",
)
def stats(traces_dir: str, output: Optional[str], open_browser: bool) -> None:
    """Generate a statistics dashboard from multiple traces.

    Scans a traces directory and generates an HTML dashboard with aggregate
    statistics including pass/fail rates, test durations, flaky tests, and
    keyword usage.

    Args:
        traces_dir: Path to the directory containing trace folders.
            Defaults to './traces'.
        output: Optional output path for the HTML file. If not specified,
            creates 'dashboard.html' in the traces directory.
        open_browser: If True, opens the dashboard in the default browser.

    Raises:
        SystemExit: If the traces directory is invalid or dashboard generation fails.

    Examples:
        trace-viewer stats ./traces
        trace-viewer stats ./traces --output /tmp/dashboard.html
        trace-viewer stats ./traces -O  # Open in browser
    """
    from trace_viewer.stats.dashboard import StatsDashboard

    traces_path = Path(traces_dir)

    try:
        click.echo(f"Scanning traces in: {traces_path}")

        dashboard = StatsDashboard(traces_path)
        stats_data = dashboard.calculate_statistics()

        # Display summary
        summary = stats_data["summary"]
        click.echo(f"\nFound {summary['total']} trace(s):")
        click.echo(
            f"  {click.style(str(summary['passed']), fg='green')} passed, "
            f"{click.style(str(summary['failed']), fg='red')} failed, "
            f"{click.style(str(summary['skipped']), fg='yellow')} skipped"
        )
        click.echo(f"  Pass rate: {summary['pass_rate']}%")

        # Generate dashboard
        if output is None:
            output_path = traces_path / "dashboard.html"
        else:
            output_path = Path(output)
            if output_path.suffix.lower() != ".html":
                output_path = output_path.with_suffix(".html")

        dashboard.generate_html(output_path)
        click.echo(f"\nDashboard generated: {output_path}")

        if open_browser:
            click.echo("Opening in browser...")
            webbrowser.open(f"file://{output_path.absolute()}")

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from None
    except OSError as e:
        click.echo(f"Error: Failed to generate dashboard: {e}", err=True)
        raise SystemExit(1) from None


@main.command("export-rp")
@click.argument("traces_dir", type=click.Path(exists=True), default="./traces")
@click.option(
    "--endpoint",
    "-e",
    envvar="RP_ENDPOINT",
    required=True,
    help="ReportPortal server URL. Can also be set via RP_ENDPOINT env var.",
)
@click.option(
    "--project",
    "-p",
    envvar="RP_PROJECT",
    required=True,
    help="ReportPortal project name. Can also be set via RP_PROJECT env var.",
)
@click.option(
    "--api-key",
    "-k",
    envvar="RP_API_KEY",
    required=True,
    help="ReportPortal API key. Can also be set via RP_API_KEY env var.",
)
@click.option(
    "--launch-name",
    "-n",
    default=None,
    help="Name for the launch in ReportPortal.",
)
@click.option(
    "--no-screenshots",
    is_flag=True,
    default=False,
    help="Skip uploading screenshots.",
)
def export_rp(
    traces_dir: str,
    endpoint: str,
    project: str,
    api_key: str,
    launch_name: Optional[str],
    no_screenshots: bool,
) -> None:
    """Export traces to ReportPortal.

    Uploads all traces from a directory to a ReportPortal server for
    centralized reporting and analysis.

    Requires the 'reportportal-client' package to be installed:
        pip install reportportal-client

    Args:
        traces_dir: Path to the directory containing trace folders.
            Defaults to './traces'.
        endpoint: ReportPortal server URL.
        project: ReportPortal project name.
        api_key: ReportPortal API key (UUID token).
        launch_name: Optional name for the launch.
        no_screenshots: If True, skip uploading screenshots.

    Raises:
        SystemExit: If export fails or ReportPortal client is not installed.

    Examples:
        trace-viewer export-rp ./traces -e https://rp.example.com -p myproject -k abc123
        RP_ENDPOINT=... RP_PROJECT=... RP_API_KEY=... trace-viewer export-rp
    """
    try:
        from trace_viewer.integrations.reportportal import ReportPortalExporter
    except ImportError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo(
            "Install with: pip install reportportal-client",
            err=True,
        )
        raise SystemExit(1) from None

    traces_path = Path(traces_dir)

    try:
        click.echo("Exporting traces to ReportPortal...")
        click.echo(f"  Endpoint: {endpoint}")
        click.echo(f"  Project: {project}")
        click.echo(f"  Traces: {traces_path}")

        exporter = ReportPortalExporter(
            endpoint=endpoint,
            project=project,
            api_key=api_key,
            launch_name=launch_name,
        )

        results = exporter.export_traces(
            traces_path,
            include_screenshots=not no_screenshots,
        )

        # Display results
        click.echo("\nExport complete:")
        click.echo(f"  Total traces: {results['total']}")
        click.echo(f"  Exported: {click.style(str(results['exported']), fg='green')}")
        if results["failed"] > 0:
            click.echo(f"  Failed: {click.style(str(results['failed']), fg='red')}")
            for error in results.get("errors", []):
                click.echo(f"    - {error['trace']}: {error['error']}", err=True)

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from None
    except Exception as e:
        click.echo(f"Error: Failed to export to ReportPortal: {e}", err=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
