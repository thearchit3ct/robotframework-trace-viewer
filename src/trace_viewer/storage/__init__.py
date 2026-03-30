"""Storage management for trace data.

This module provides storage utilities for persisting Robot Framework
trace data to disk in a structured format.

Includes support for Pabot parallel execution through process-aware
trace directory naming, plus optional compression and retention utilities.
"""

from trace_viewer.storage.compression import (
    cleanup_traces,
    compress_trace,
    compress_traces_dir,
    convert_png_to_webp,
    truncate_dom,
)
from trace_viewer.storage.trace_writer import (
    TraceWriter,
    get_pabot_id,
    get_process_identifier,
    is_pabot_execution,
)

__all__ = [
    # Writer
    "TraceWriter",
    # Pabot helpers
    "is_pabot_execution",
    "get_pabot_id",
    "get_process_identifier",
    # Compression / cleanup
    "convert_png_to_webp",
    "compress_trace",
    "compress_traces_dir",
    "truncate_dom",
    "cleanup_traces",
]
