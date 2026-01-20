"""Capture agents for trace viewer.

This module provides capture agents for collecting data during Robot Framework
test execution, including screenshots, variable snapshots, browser console logs,
DOM snapshots, and network requests.
"""

from trace_viewer.capture.console import ConsoleCapture
from trace_viewer.capture.dom import DOMCapture
from trace_viewer.capture.network import NetworkCapture
from trace_viewer.capture.screenshot import ScreenshotCapture
from trace_viewer.capture.variables import VariablesCapture

__all__ = [
    "ConsoleCapture",
    "DOMCapture",
    "NetworkCapture",
    "ScreenshotCapture",
    "VariablesCapture",
]
