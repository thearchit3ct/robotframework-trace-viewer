"""Tests for trace_viewer.storage.compression module."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from trace_viewer.storage.compression import (
    cleanup_traces,
    compress_trace,
    compress_traces_dir,
    truncate_dom,
)


def _create_fake_png(path: Path, size: int = 1000) -> None:
    """Create a fake PNG file with minimal valid header."""
    # Minimal PNG header + padding
    header = b"\x89PNG\r\n\x1a\n"
    path.write_bytes(header + b"\x00" * (size - len(header)))


def _create_trace(traces_dir: Path, name: str, status: str = "PASS", days_ago: int = 0) -> Path:
    """Create a fake trace directory with manifest."""
    trace_dir = traces_dir / name
    trace_dir.mkdir(parents=True)
    keywords_dir = trace_dir / "keywords"
    keywords_dir.mkdir()

    start_time = datetime.now(timezone.utc)
    if days_ago > 0:
        from datetime import timedelta

        start_time = start_time - timedelta(days=days_ago)

    manifest = {
        "test_name": name,
        "status": status,
        "start_time": start_time.isoformat(),
        "duration_ms": 1000,
    }
    (trace_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return trace_dir


class TestTruncateDom:
    """Test DOM truncation."""

    def test_no_truncation_needed(self, tmp_path):
        dom_path = tmp_path / "dom.html"
        dom_path.write_text("<html><body>small</body></html>", encoding="utf-8")
        assert truncate_dom(dom_path, max_size_kb=1) is False

    def test_truncation(self, tmp_path):
        dom_path = tmp_path / "dom.html"
        # Write >1KB of content
        dom_path.write_text("x" * 2000, encoding="utf-8")
        assert truncate_dom(dom_path, max_size_kb=1) is True
        content = dom_path.read_text(encoding="utf-8")
        assert "<!-- DOM truncated by trace-viewer -->" in content
        assert len(content.encode("utf-8")) <= 1024 + 100  # some slack for the comment

    def test_nonexistent_file(self, tmp_path):
        dom_path = tmp_path / "nonexistent.html"
        assert truncate_dom(dom_path) is False


class TestCleanupTraces:
    """Test trace cleanup."""

    def test_no_traces(self, tmp_path):
        result = cleanup_traces(tmp_path)
        assert result["deleted_count"] == 0
        assert result["remaining_count"] == 0

    def test_delete_old_traces(self, tmp_path):
        _create_trace(tmp_path, "old_test", days_ago=60)
        _create_trace(tmp_path, "new_test", days_ago=1)
        result = cleanup_traces(tmp_path, max_days=30)
        assert result["deleted_count"] == 1
        assert result["remaining_count"] == 1
        assert not (tmp_path / "old_test").exists()
        assert (tmp_path / "new_test").exists()

    def test_max_traces_limit(self, tmp_path):
        for i in range(5):
            _create_trace(tmp_path, f"test_{i}", days_ago=i)
        result = cleanup_traces(tmp_path, max_days=365, max_traces=3)
        assert result["remaining_count"] == 3

    def test_keeps_recent_traces(self, tmp_path):
        _create_trace(tmp_path, "recent", days_ago=1)
        result = cleanup_traces(tmp_path, max_days=30)
        assert result["deleted_count"] == 0
        assert (tmp_path / "recent").exists()


class TestCompressTrace:
    """Test single trace compression."""

    def test_no_screenshots(self, tmp_path):
        trace_dir = _create_trace(tmp_path, "no_screenshots")
        result = compress_trace(trace_dir)
        assert result["files_converted"] == 0

    def test_compress_creates_webp(self, tmp_path):
        trace_dir = _create_trace(tmp_path, "with_screenshots")
        kw_dir = trace_dir / "keywords" / "001_click"
        kw_dir.mkdir(parents=True)

        # Create a real PNG using Pillow if available
        try:
            from PIL import Image

            img = Image.new("RGB", (100, 100), "red")
            img.save(kw_dir / "screenshot.png")

            result = compress_trace(trace_dir)
            assert result["files_converted"] == 1
            assert (kw_dir / "screenshot.webp").exists()
            assert result["savings_percent"] >= 0
        except ImportError:
            pytest.skip("Pillow not installed")


class TestCompressTracesDir:
    """Test directory-wide compression."""

    def test_empty_dir(self, tmp_path):
        result = compress_traces_dir(tmp_path)
        assert result["files_converted"] == 0
        assert result["traces_processed"] == 0
