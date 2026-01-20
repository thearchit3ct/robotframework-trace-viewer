"""Storage management for trace data.

This module provides storage utilities for persisting Robot Framework
trace data to disk in a structured format.

Includes support for Pabot parallel execution through process-aware
trace directory naming.
"""

from trace_viewer.storage.trace_writer import (
    TraceWriter,
    get_pabot_id,
    get_process_identifier,
    is_pabot_execution,
)

__all__ = [
    "TraceWriter",
    "is_pabot_execution",
    "get_pabot_id",
    "get_process_identifier",
]
