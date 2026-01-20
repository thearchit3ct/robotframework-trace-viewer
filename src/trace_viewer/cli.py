"""Command-line interface for Robot Framework Trace Viewer."""

import json
import webbrowser
from pathlib import Path
from typing import Any

import click

from trace_viewer import __version__


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


if __name__ == "__main__":
    main()
