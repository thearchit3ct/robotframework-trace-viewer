"""Ring buffer for in-memory keyword capture in on_failure mode.

When capture_mode is 'on_failure', keyword captures are stored in a fixed-size
ring buffer in memory (no disk I/O). When a test fails, the buffer is flushed
to disk. When a test passes, the buffer is cleared.

Memory usage: ~100KB per capture × buffer_size (default 10) ≈ ~1MB.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class KeywordCapture:
    """In-memory representation of a keyword capture.

    Stores all captured data (screenshot, variables, etc.) in memory
    until the test outcome is known.

    Attributes:
        index: Keyword execution index.
        name: Keyword name.
        folder: Path to the keyword directory on disk.
        metadata: Keyword metadata dictionary.
        screenshot: PNG screenshot bytes.
        variables: Captured RF variables.
        console_logs: Browser console log entries.
        dom: DOM HTML snapshot.
        network: Network request entries.
    """

    index: int
    name: str
    folder: str
    metadata: dict[str, Any] = field(default_factory=dict)
    screenshot: bytes | None = None
    variables: dict[str, Any] | None = None
    console_logs: list[dict[str, Any]] | None = None
    dom: str | None = None
    network: list[dict[str, Any]] | None = None


class RingBuffer:
    """Fixed-size ring buffer for keyword captures.

    Uses a deque with maxlen to automatically evict oldest captures
    when the buffer is full. This keeps memory bounded.

    Args:
        maxlen: Maximum number of captures to retain.

    Example:
        >>> buffer = RingBuffer(maxlen=5)
        >>> buffer.push(KeywordCapture(index=1, name="Open Browser", folder="/tmp/001"))
        >>> len(buffer)
        1
        >>> captures = buffer.flush_all()
        >>> len(captures)
        1
        >>> len(buffer)
        0
    """

    def __init__(self, maxlen: int = 10) -> None:
        """Initialize ring buffer with given capacity."""
        self._buffer: deque[KeywordCapture] = deque(maxlen=maxlen)
        self._maxlen = maxlen

    def push(self, capture: KeywordCapture) -> None:
        """Add a capture to the buffer.

        If the buffer is full, the oldest capture is automatically evicted.

        Args:
            capture: KeywordCapture to add.
        """
        self._buffer.append(capture)

    def flush_all(self) -> list[KeywordCapture]:
        """Remove and return all captures from the buffer.

        Returns:
            List of all captures in insertion order.
        """
        captures = list(self._buffer)
        self._buffer.clear()
        return captures

    def clear(self) -> None:
        """Remove all captures from the buffer without returning them."""
        self._buffer.clear()

    def __len__(self) -> int:
        """Return the number of captures in the buffer."""
        return len(self._buffer)

    @property
    def maxlen(self) -> int:
        """Return the maximum capacity of the buffer."""
        return self._maxlen

    @property
    def is_full(self) -> bool:
        """Check if the buffer is at maximum capacity."""
        return len(self._buffer) == self._maxlen
