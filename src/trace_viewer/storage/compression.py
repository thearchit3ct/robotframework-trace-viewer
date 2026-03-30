"""Compression and cleanup utilities for trace storage.

Supports WebP conversion for screenshots and trace retention policies.
Requires Pillow>=9.0 for WebP conversion (optional).

Usage example::

    from pathlib import Path
    from trace_viewer.storage.compression import compress_traces_dir, cleanup_traces

    # Convert all screenshots in a traces directory to WebP
    stats = compress_traces_dir(Path("./traces"), quality=80)
    print(f"Saved {stats['savings_percent']:.1f}% space")

    # Remove stale traces
    result = cleanup_traces(Path("./traces"), max_days=30, max_traces=100)
    print(f"Deleted {result['deleted_count']} trace(s)")
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _import_pillow() -> Any:
    """Lazily import Pillow's Image module.

    Returns:
        The ``PIL.Image`` module.

    Raises:
        ImportError: If Pillow is not installed, with a helpful install message.
    """
    try:
        from PIL import Image  # type: ignore[import-untyped]

        return Image
    except ImportError as exc:
        raise ImportError(
            "Pillow is required for WebP conversion. " "Install it with: pip install 'Pillow>=9.0'"
        ) from exc


def _load_manifest(trace_dir: Path) -> dict[str, Any] | None:
    """Load manifest.json from a trace directory.

    Args:
        trace_dir: Path to a single trace directory.

    Returns:
        Parsed manifest dict, or None if the file does not exist or is invalid.
    """
    manifest_path = trace_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            return json.load(fh)  # type: ignore[no-any-return]
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read manifest %s: %s", manifest_path, exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def convert_png_to_webp(
    png_path: Path,
    quality: int = 80,
    remove_original: bool = True,
) -> Path:
    """Convert a single PNG file to WebP format using Pillow.

    Args:
        png_path: Absolute path to the source PNG file.
        quality: WebP encoding quality (1-100). Higher values produce larger
            files with better image fidelity. Default is 80.
        remove_original: If True (default), the original PNG file is deleted
            after a successful conversion.

    Returns:
        Path to the newly created WebP file (same directory, ``.webp`` suffix).

    Raises:
        ImportError: If Pillow is not installed.
        FileNotFoundError: If ``png_path`` does not exist.
        OSError: If the file cannot be read or written.

    Example::

        from pathlib import Path
        from trace_viewer.storage.compression import convert_png_to_webp

        webp_path = convert_png_to_webp(Path("/traces/001_open_browser/screenshot.png"))
        print(webp_path)  # /traces/001_open_browser/screenshot.webp
    """
    Image = _import_pillow()

    if not png_path.is_file():
        raise FileNotFoundError(f"Source PNG not found: {png_path}")

    webp_path = png_path.with_suffix(".webp")

    with Image.open(png_path) as img:
        # Preserve transparency (RGBA) if present; otherwise convert to RGB for
        # slightly smaller files.  WebP supports both modes natively.
        if img.mode not in ("RGBA", "RGB"):
            img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
        img.save(webp_path, format="WEBP", quality=quality, method=6)

    if remove_original:
        png_path.unlink()

    return webp_path


def compress_trace(trace_dir: Path, quality: int = 80) -> dict[str, Any]:
    """Convert all ``screenshot.png`` files in a trace directory to WebP.

    Recursively searches ``trace_dir`` for files named ``screenshot.png`` and
    converts each one.  Files that have already been converted (a sibling
    ``screenshot.webp`` exists without a corresponding ``screenshot.png``) are
    skipped automatically.

    Args:
        trace_dir: Path to a single test trace directory (e.g.
            ``traces/login_test_20250119_143022``).
        quality: WebP quality (1-100). Passed to :func:`convert_png_to_webp`.

    Returns:
        A stats dictionary with the following keys:

        - ``files_converted`` (int): Number of PNG files converted.
        - ``original_size_bytes`` (int): Combined size of original PNG files.
        - ``compressed_size_bytes`` (int): Combined size of resulting WebP files.
        - ``savings_percent`` (float): Percentage of space saved
          (0.0 if no files were converted).

    Example::

        stats = compress_trace(Path("traces/login_test_20250119_143022"))
        print(stats["savings_percent"])  # e.g. 42.3
    """
    files_converted = 0
    original_size = 0
    compressed_size = 0

    png_files = list(trace_dir.rglob("screenshot.png"))

    for png_path in png_files:
        # Skip if WebP already exists alongside PNG (partial previous run)
        webp_path = png_path.with_suffix(".webp")
        if webp_path.exists():
            logger.debug("Skipping already-converted screenshot: %s", png_path)
            continue

        try:
            original_bytes = png_path.stat().st_size
            webp_path = convert_png_to_webp(png_path, quality=quality, remove_original=True)
            compressed_bytes = webp_path.stat().st_size

            original_size += original_bytes
            compressed_size += compressed_bytes
            files_converted += 1
        except ImportError:
            raise
        except Exception as exc:
            logger.warning("Failed to convert %s: %s", png_path, exc)

    savings_percent = (1.0 - compressed_size / original_size) * 100.0 if original_size > 0 else 0.0

    return {
        "files_converted": files_converted,
        "original_size_bytes": original_size,
        "compressed_size_bytes": compressed_size,
        "savings_percent": round(savings_percent, 2),
    }


def compress_traces_dir(traces_dir: Path, quality: int = 80) -> dict[str, Any]:
    """Apply :func:`compress_trace` to every trace subdirectory.

    Iterates over all immediate subdirectories of ``traces_dir`` and compresses
    screenshots within each one.  Non-directory entries are silently skipped.

    Args:
        traces_dir: Root traces directory containing individual trace folders.
        quality: WebP quality (1-100).

    Returns:
        Aggregate stats dictionary with the same keys as :func:`compress_trace`
        plus ``traces_processed`` (int).

    Example::

        from pathlib import Path
        from trace_viewer.storage.compression import compress_traces_dir

        stats = compress_traces_dir(Path("./traces"))
        print(f"{stats['traces_processed']} traces processed, "
              f"{stats['files_converted']} screenshots converted, "
              f"{stats['savings_percent']:.1f}% space saved")
    """
    if not traces_dir.is_dir():
        return {
            "traces_processed": 0,
            "files_converted": 0,
            "original_size_bytes": 0,
            "compressed_size_bytes": 0,
            "savings_percent": 0.0,
        }

    traces_processed = 0
    total_files_converted = 0
    total_original_size = 0
    total_compressed_size = 0

    for entry in sorted(traces_dir.iterdir()):
        if not entry.is_dir():
            continue

        stats = compress_trace(entry, quality=quality)
        traces_processed += 1
        total_files_converted += stats["files_converted"]
        total_original_size += stats["original_size_bytes"]
        total_compressed_size += stats["compressed_size_bytes"]

    savings_percent = (
        (1.0 - total_compressed_size / total_original_size) * 100.0
        if total_original_size > 0
        else 0.0
    )

    return {
        "traces_processed": traces_processed,
        "files_converted": total_files_converted,
        "original_size_bytes": total_original_size,
        "compressed_size_bytes": total_compressed_size,
        "savings_percent": round(savings_percent, 2),
    }


def truncate_dom(dom_path: Path, max_size_kb: int = 500) -> bool:
    """Truncate an oversized DOM HTML snapshot.

    If the file at ``dom_path`` is larger than ``max_size_kb`` kilobytes, it
    is truncated at the byte boundary and a sentinel comment is appended so
    that consumers can detect the truncation:

    .. code-block:: html

        <!-- DOM truncated by trace-viewer -->

    The file is re-written in-place.  If the file is within the size limit,
    it is left untouched.

    Args:
        dom_path: Absolute path to the ``dom.html`` file.
        max_size_kb: Maximum allowed file size in kilobytes. Default is 500.

    Returns:
        ``True`` if the file was truncated, ``False`` if it was already within
        the size limit or does not exist.

    Example::

        from pathlib import Path
        from trace_viewer.storage.compression import truncate_dom

        was_truncated = truncate_dom(Path("traces/001_open_browser/dom.html"), max_size_kb=500)
        if was_truncated:
            print("DOM was too large and has been truncated.")
    """
    if not dom_path.is_file():
        return False

    max_bytes = max_size_kb * 1024
    file_size = dom_path.stat().st_size

    if file_size <= max_bytes:
        return False

    # Read up to max_bytes, decode leniently to avoid errors at multi-byte
    # character boundaries, then re-encode to determine actual byte count.
    raw = dom_path.read_bytes()
    truncated_raw = raw[:max_bytes]

    # Decode with error replacement so we don't break on partial UTF-8 sequences.
    truncated_html = truncated_raw.decode("utf-8", errors="replace")
    truncated_html += "\n<!-- DOM truncated by trace-viewer -->"

    dom_path.write_text(truncated_html, encoding="utf-8")
    return True


def cleanup_traces(
    traces_dir: Path,
    max_days: int = 30,
    max_traces: int = 100,
) -> dict[str, Any]:
    """Delete stale trace directories according to a retention policy.

    Two independent rules are applied in order:

    1. **Age rule**: Any trace whose ``start_time`` (from ``manifest.json``) is
       older than ``max_days`` is deleted, regardless of the total count.
    2. **Count rule**: If, after the age rule, more than ``max_traces`` traces
       remain, the oldest traces (by ``start_time``) are deleted until the
       count reaches ``max_traces``.

    Trace directories that lack a readable ``manifest.json`` are excluded from
    sorting but are not automatically deleted; they may be in-progress writes.

    Args:
        traces_dir: Root traces directory containing individual trace folders.
        max_days: Traces older than this many days are deleted. Default is 30.
        max_traces: Maximum number of traces to keep after age-based cleanup.
            Default is 100.

    Returns:
        A result dictionary with the following keys:

        - ``deleted_count`` (int): Total number of traces deleted.
        - ``deleted_dirs`` (list[str]): Names of deleted trace directories.
        - ``remaining_count`` (int): Number of traces left after cleanup.

    Example::

        from pathlib import Path
        from trace_viewer.storage.compression import cleanup_traces

        result = cleanup_traces(Path("./traces"), max_days=7, max_traces=50)
        print(f"Removed {result['deleted_count']} old trace(s); "
              f"{result['remaining_count']} remain.")
    """
    if not traces_dir.is_dir():
        return {"deleted_count": 0, "deleted_dirs": [], "remaining_count": 0}

    # Collect all candidate subdirectories with their manifests.
    entries: list[tuple[datetime, Path]] = []
    unreadable: list[Path] = []

    for entry in traces_dir.iterdir():
        if not entry.is_dir():
            continue
        manifest = _load_manifest(entry)
        if manifest is None:
            unreadable.append(entry)
            continue
        start_time_raw = manifest.get("start_time")
        if not start_time_raw:
            unreadable.append(entry)
            continue
        try:
            # ISO 8601 with optional timezone; fromisoformat handles both.
            start_dt = datetime.fromisoformat(str(start_time_raw))
            # Normalise to UTC-aware for comparison.
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            unreadable.append(entry)
            continue
        entries.append((start_dt, entry))

    # Sort ascending (oldest first).
    entries.sort(key=lambda t: t[0])

    deleted_dirs: list[str] = []
    now_utc = datetime.now(tz=timezone.utc)
    cutoff = now_utc.timestamp() - max_days * 86400

    # --- Age-based deletion ---
    surviving: list[tuple[datetime, Path]] = []
    for start_dt, entry in entries:
        if start_dt.timestamp() < cutoff:
            try:
                shutil.rmtree(entry)
                deleted_dirs.append(entry.name)
                logger.info("Deleted old trace (age rule): %s", entry.name)
            except OSError as exc:
                logger.warning("Could not delete trace %s: %s", entry.name, exc)
        else:
            surviving.append((start_dt, entry))

    # --- Count-based deletion ---
    while len(surviving) > max_traces:
        start_dt, entry = surviving.pop(0)  # oldest first
        try:
            shutil.rmtree(entry)
            deleted_dirs.append(entry.name)
            logger.info("Deleted trace (count rule): %s", entry.name)
        except OSError as exc:
            logger.warning("Could not delete trace %s: %s", entry.name, exc)

    remaining_count = len(surviving) + len(unreadable)

    return {
        "deleted_count": len(deleted_dirs),
        "deleted_dirs": deleted_dirs,
        "remaining_count": remaining_count,
    }
