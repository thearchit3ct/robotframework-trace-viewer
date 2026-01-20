"""Capture agents for trace viewer.

This module provides capture agents for collecting data during Robot Framework
test execution, including screenshots and variable snapshots.
"""

from trace_viewer.capture.screenshot import ScreenshotCapture
from trace_viewer.capture.variables import VariablesCapture

__all__ = ["ScreenshotCapture", "VariablesCapture"]
