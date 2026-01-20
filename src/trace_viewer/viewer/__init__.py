"""HTML viewer generation for traces.

This module provides components for generating static HTML viewers
that display Robot Framework test execution traces.
"""

from .comparator import TraceComparator
from .generator import ViewerGenerator

__all__ = ["ViewerGenerator", "TraceComparator"]
