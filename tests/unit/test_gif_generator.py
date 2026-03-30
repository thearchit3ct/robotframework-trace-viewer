"""Tests for trace_viewer.media.gif_generator module."""

import json
from pathlib import Path

import pytest

try:
    from PIL import Image

    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

from trace_viewer.media.gif_generator import generate_gif, generate_slideshow


def _create_trace_with_screenshots(tmp_path: Path, num_keywords: int = 3) -> Path:
    """Create a fake trace directory with screenshots."""
    trace_dir = tmp_path / "test_trace"
    trace_dir.mkdir()

    manifest = {
        "test_name": "Test With Screenshots",
        "status": "PASS",
        "duration_ms": 3000,
    }
    (trace_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    keywords_dir = trace_dir / "keywords"
    keywords_dir.mkdir()

    for i in range(num_keywords):
        kw_dir = keywords_dir / f"{i + 1:03d}_keyword_{i}"
        kw_dir.mkdir()

        # Create a real PNG with Pillow
        if HAS_PILLOW:
            colors = ["red", "green", "blue", "yellow", "purple"]
            img = Image.new("RGB", (200, 150), colors[i % len(colors)])
            img.save(kw_dir / "screenshot.png")

        # Create metadata
        metadata = {
            "index": i + 1,
            "name": f"Keyword {i}",
            "status": "PASS" if i < num_keywords - 1 else "FAIL",
            "duration_ms": 100 * (i + 1),
        }
        (kw_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    return trace_dir


@pytest.mark.skipif(not HAS_PILLOW, reason="Pillow not installed")
class TestGenerateGif:
    """Test GIF generation."""

    def test_basic_gif(self, tmp_path):
        trace_dir = _create_trace_with_screenshots(tmp_path)
        output = generate_gif(trace_dir)
        assert output.exists()
        assert output.suffix == ".gif"
        assert output.stat().st_size > 0

    def test_custom_output(self, tmp_path):
        trace_dir = _create_trace_with_screenshots(tmp_path)
        custom_output = tmp_path / "custom.gif"
        output = generate_gif(trace_dir, output=custom_output)
        assert output == custom_output.resolve()
        assert custom_output.exists()

    def test_custom_fps(self, tmp_path):
        trace_dir = _create_trace_with_screenshots(tmp_path)
        output = generate_gif(trace_dir, fps=5)
        assert output.exists()

    def test_no_screenshots(self, tmp_path):
        trace_dir = tmp_path / "empty_trace"
        trace_dir.mkdir()
        (trace_dir / "keywords").mkdir()
        with pytest.raises(FileNotFoundError):
            generate_gif(trace_dir)

    def test_single_screenshot(self, tmp_path):
        trace_dir = _create_trace_with_screenshots(tmp_path, num_keywords=1)
        output = generate_gif(trace_dir)
        assert output.exists()


class TestGenerateSlideshow:
    """Test slideshow HTML generation."""

    @pytest.mark.skipif(not HAS_PILLOW, reason="Pillow not installed")
    def test_basic_slideshow(self, tmp_path):
        trace_dir = _create_trace_with_screenshots(tmp_path)
        output = generate_slideshow(trace_dir)
        assert output.exists()
        assert output.suffix == ".html"
        content = output.read_text(encoding="utf-8")
        assert "slideshow" in content.lower() or "Keyword" in content

    def test_no_screenshots(self, tmp_path):
        trace_dir = tmp_path / "empty_trace"
        trace_dir.mkdir()
        (trace_dir / "keywords").mkdir()
        with pytest.raises(FileNotFoundError):
            generate_slideshow(trace_dir)
