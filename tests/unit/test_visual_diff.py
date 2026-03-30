"""Tests for trace_viewer.comparison.visual_diff module."""

import json
from pathlib import Path

import pytest

try:
    from PIL import Image

    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


def _create_image_bytes(color: str, size: tuple = (100, 100)) -> bytes:
    """Create PNG bytes for a solid color image."""
    if not HAS_PILLOW:
        pytest.skip("Pillow not installed")
    import io

    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_trace_with_screenshots(base_dir: Path, name: str, colors: list) -> Path:
    """Create a fake trace with colored screenshots."""
    trace_dir = base_dir / name
    trace_dir.mkdir()
    keywords_dir = trace_dir / "keywords"
    keywords_dir.mkdir()

    manifest = {"test_name": name, "status": "PASS", "duration_ms": 1000}
    (trace_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    for i, color in enumerate(colors):
        kw_dir = keywords_dir / f"{i + 1:03d}_step_{i}"
        kw_dir.mkdir()
        if HAS_PILLOW:
            img = Image.new("RGB", (100, 100), color)
            img.save(kw_dir / "screenshot.png")
        metadata = {"index": i + 1, "name": f"Step {i}", "status": "PASS"}
        (kw_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    return trace_dir


@pytest.mark.skipif(not HAS_PILLOW, reason="Pillow not installed")
class TestComputeVisualDiff:
    """Test pixel-level visual comparison."""

    def test_identical_images(self):
        from trace_viewer.comparison.visual_diff import compute_visual_diff

        img_bytes = _create_image_bytes("red")
        result = compute_visual_diff(img_bytes, img_bytes)
        assert result.similarity == 1.0
        assert result.changed_pixels == 0

    def test_completely_different(self):
        from trace_viewer.comparison.visual_diff import compute_visual_diff

        img_a = _create_image_bytes("red")
        img_b = _create_image_bytes("blue")
        result = compute_visual_diff(img_a, img_b)
        assert result.similarity < 1.0
        assert result.changed_pixels > 0
        assert result.total_pixels == 100 * 100

    def test_diff_image_is_valid_png(self):
        from trace_viewer.comparison.visual_diff import compute_visual_diff

        img_a = _create_image_bytes("red")
        img_b = _create_image_bytes("green")
        result = compute_visual_diff(img_a, img_b)
        assert result.diff_image[:4] == b"\x89PNG"

    def test_threshold_sensitivity(self):
        from trace_viewer.comparison.visual_diff import compute_visual_diff

        img_a = _create_image_bytes("red")
        # Slightly different red
        img = Image.new("RGB", (100, 100), (240, 0, 0))
        import io

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_b = buf.getvalue()

        # Low threshold: should detect changes
        result_low = compute_visual_diff(img_a, img_b, threshold=5)
        # High threshold: should not detect changes
        result_high = compute_visual_diff(img_a, img_b, threshold=50)
        assert result_high.changed_pixels <= result_low.changed_pixels


@pytest.mark.skipif(not HAS_PILLOW, reason="Pillow not installed")
class TestCompareTraces:
    """Test trace-level visual comparison."""

    def test_matching_traces(self, tmp_path):
        from trace_viewer.comparison.visual_diff import compare_traces

        trace1 = _create_trace_with_screenshots(tmp_path, "trace1", ["red", "green"])
        trace2 = _create_trace_with_screenshots(tmp_path, "trace2", ["red", "blue"])
        results = compare_traces(trace1, trace2)
        assert len(results) == 2
        assert results[0]["similarity"] == 1.0  # Both red
        assert results[1]["similarity"] < 1.0  # Green vs blue

    def test_no_screenshots(self, tmp_path):
        from trace_viewer.comparison.visual_diff import compare_traces

        trace1 = tmp_path / "trace1"
        trace1.mkdir()
        (trace1 / "keywords").mkdir()
        trace2 = tmp_path / "trace2"
        trace2.mkdir()
        (trace2 / "keywords").mkdir()
        results = compare_traces(trace1, trace2)
        assert len(results) == 0


@pytest.mark.skipif(not HAS_PILLOW, reason="Pillow not installed")
class TestGenerateComparisonHtml:
    """Test HTML comparison report generation."""

    def test_generate_report(self, tmp_path):
        from trace_viewer.comparison.visual_diff import (
            compare_traces,
            generate_comparison_html,
        )

        trace1 = _create_trace_with_screenshots(tmp_path, "trace1", ["red", "green"])
        trace2 = _create_trace_with_screenshots(tmp_path, "trace2", ["red", "blue"])
        results = compare_traces(trace1, trace2)
        output = tmp_path / "diff.html"
        generate_comparison_html(results, trace1, trace2, output)
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
