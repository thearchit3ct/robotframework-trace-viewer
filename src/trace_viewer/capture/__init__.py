"""Capture agents for trace viewer.

This module provides capture agents for collecting data during Robot Framework
test execution, including screenshots, variable snapshots, and browser console logs.
"""

from trace_viewer.capture.console import ConsoleCapture
from trace_viewer.capture.screenshot import ScreenshotCapture
from trace_viewer.capture.variables import VariablesCapture

__all__ = ["ConsoleCapture", "ScreenshotCapture", "VariablesCapture"]
