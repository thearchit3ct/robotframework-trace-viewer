"""Visual diff comparison between trace screenshots using Pillow.

Requires Pillow>=9.0 (optional dependency).
"""

from __future__ import annotations

import base64
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VisualDiffResult:
    """Result of a pixel-level visual comparison between two screenshots.

    Attributes:
        diff_image: PNG-encoded bytes of image_b with a semi-transparent red
            overlay applied to every pixel whose channel difference exceeds
            the comparison threshold.
        similarity: Ratio of unchanged pixels to total pixels, in [0.0, 1.0].
            A value of 1.0 means the images are identical (within threshold).
        changed_pixels: Absolute count of pixels flagged as changed.
        total_pixels: Total number of pixels in the (possibly resized)
            comparison canvas.

    Example:
        >>> result = compute_visual_diff(png_a_bytes, png_b_bytes)
        >>> print(f"Similarity: {result.similarity:.1%}")
        Similarity: 97.3%
        >>> print(f"Changed pixels: {result.changed_pixels}/{result.total_pixels}")
        Changed pixels: 2134/79200
    """

    diff_image: bytes
    similarity: float
    changed_pixels: int
    total_pixels: int


def _require_pillow() -> tuple:
    """Import and return PIL.Image and PIL.ImageDraw, raising on failure.

    Returns:
        A 2-tuple of (PIL.Image module, PIL.ImageDraw module).

    Raises:
        ImportError: If Pillow is not installed with an actionable message.
    """
    try:
        from PIL import Image, ImageDraw  # type: ignore[import-untyped]

        return Image, ImageDraw
    except ImportError as exc:
        raise ImportError(
            "Pillow is required for visual diff comparison. "
            "Install it with: pip install 'pillow>=9.0' "
            "or: pip install 'robotframework-trace-viewer[visual]'"
        ) from exc


def compute_visual_diff(
    image_a: bytes,
    image_b: bytes,
    threshold: int = 30,
) -> VisualDiffResult:
    """Compute a pixel-level visual diff between two PNG screenshots.

    Both images are converted to RGBA before comparison so that any
    alpha-premultiplied or palette-mode input is handled uniformly.
    When the images have different dimensions the smaller image is
    up-scaled to match the larger one using nearest-neighbour resampling
    (preserving crisp pixel boundaries).

    A pixel is considered *changed* when the absolute difference of **any**
    RGB channel exceeds ``threshold``.  The alpha channel is ignored during
    comparison but is preserved in the output diff image.

    The diff image is a copy of ``image_b`` (after optional resize) with a
    semi-transparent red overlay — RGBA ``(128, 0, 0, 128)`` — composited
    over every changed pixel.

    Args:
        image_a: PNG-encoded bytes of the reference (baseline) screenshot.
        image_b: PNG-encoded bytes of the candidate screenshot to compare.
        threshold: Per-channel absolute difference above which a pixel is
            flagged as changed.  Must be in the range [0, 255].  Defaults
            to 30, which filters out minor JPEG/rendering artefacts while
            still catching meaningful changes.

    Returns:
        A :class:`VisualDiffResult` containing the annotated diff image,
        similarity score, changed pixel count, and total pixel count.

    Raises:
        ImportError: If Pillow>=9.0 is not installed.
        ValueError: If ``threshold`` is outside [0, 255].
        OSError: If either byte string cannot be decoded as a valid image.

    Example:
        >>> with open("before.png", "rb") as f:
        ...     png_a = f.read()
        >>> with open("after.png", "rb") as f:
        ...     png_b = f.read()
        >>> result = compute_visual_diff(png_a, png_b, threshold=20)
        >>> print(f"{result.similarity:.1%} similar")
        98.7% similar
    """
    if not 0 <= threshold <= 255:
        raise ValueError(f"threshold must be in [0, 255], got {threshold!r}")

    Image, ImageDraw = _require_pillow()

    # Decode both images and normalise to RGBA.
    img_a: object = Image.open(io.BytesIO(image_a)).convert("RGBA")
    img_b: object = Image.open(io.BytesIO(image_b)).convert("RGBA")

    # Resolve canvas: use the larger of the two dimensions.
    w_a, h_a = img_a.size  # type: ignore[attr-defined]
    w_b, h_b = img_b.size  # type: ignore[attr-defined]
    canvas_w = max(w_a, w_b)
    canvas_h = max(h_a, h_b)

    if (w_a, h_a) != (canvas_w, canvas_h):
        img_a = img_a.resize(  # type: ignore[attr-defined]
            (canvas_w, canvas_h),
            Image.NEAREST,  # type: ignore[attr-defined]
        )
    if (w_b, h_b) != (canvas_w, canvas_h):
        img_b = img_b.resize(  # type: ignore[attr-defined]
            (canvas_w, canvas_h),
            Image.NEAREST,  # type: ignore[attr-defined]
        )

    total_pixels: int = canvas_w * canvas_h

    # Access raw pixel data as flat sequences for fast iteration.
    pixels_a = list(img_a.getdata())  # type: ignore[attr-defined]
    pixels_b = list(img_b.getdata())  # type: ignore[attr-defined]

    # Build a mask of changed pixel positions.
    changed_mask: list[bool] = []
    for pa, pb in zip(pixels_a, pixels_b):
        r_diff = abs(int(pa[0]) - int(pb[0]))
        g_diff = abs(int(pa[1]) - int(pb[1]))
        b_diff = abs(int(pa[2]) - int(pb[2]))
        changed_mask.append(r_diff > threshold or g_diff > threshold or b_diff > threshold)

    changed_pixels: int = sum(changed_mask)

    # Build the diff image: start with a copy of img_b.
    diff_img = img_b.copy()  # type: ignore[attr-defined]

    if changed_pixels > 0:
        # Create a red overlay layer at the same size.
        overlay = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))  # type: ignore[attr-defined]
        overlay_pixels = [(128, 0, 0, 128) if changed else (0, 0, 0, 0) for changed in changed_mask]
        overlay.putdata(overlay_pixels)  # type: ignore[attr-defined]

        # Alpha-composite the overlay onto the diff image.
        diff_img = Image.alpha_composite(diff_img, overlay)  # type: ignore[attr-defined]

    # Serialise the diff image to PNG bytes.
    buffer = io.BytesIO()
    diff_img.save(buffer, format="PNG")  # type: ignore[attr-defined]
    diff_image_bytes = buffer.getvalue()

    similarity: float = 1.0 - (changed_pixels / total_pixels) if total_pixels > 0 else 1.0

    return VisualDiffResult(
        diff_image=diff_image_bytes,
        similarity=similarity,
        changed_pixels=changed_pixels,
        total_pixels=total_pixels,
    )


def _extract_index_prefix(name: str) -> int | None:
    """Extract the leading numeric index from a keyword directory name.

    Keyword directories follow the naming convention ``NNN_keyword_name``
    where ``NNN`` is a zero-padded integer (e.g. ``001_go_to``).

    Args:
        name: Directory basename to parse.

    Returns:
        The integer index, or ``None`` if the name does not match the
        expected pattern.
    """
    match = re.match(r"^(\d+)_", name)
    return int(match.group(1)) if match else None


def _load_screenshot(kw_dir: Path) -> bytes | None:
    """Load screenshot bytes from a keyword directory if present.

    Args:
        kw_dir: Path to the keyword directory (e.g. ``keywords/001_go_to``).

    Returns:
        Raw PNG bytes, or ``None`` when no ``screenshot.png`` exists.
    """
    screenshot_path = kw_dir / "screenshot.png"
    if screenshot_path.exists():
        return screenshot_path.read_bytes()
    return None


def _load_keyword_name(kw_dir: Path) -> str:
    """Read the human-readable keyword name from ``metadata.json``.

    Falls back to the directory basename when the metadata file is absent
    or malformed.

    Args:
        kw_dir: Path to the keyword directory.

    Returns:
        The keyword ``name`` field, or the directory basename as a fallback.
    """
    metadata_path = kw_dir / "metadata.json"
    if metadata_path.exists():
        try:
            with open(metadata_path, encoding="utf-8") as fh:
                data = json.load(fh)
            return str(data.get("name", kw_dir.name))
        except (OSError, json.JSONDecodeError):
            pass
    return kw_dir.name


def compare_traces(
    trace1_dir: Path,
    trace2_dir: Path,
    output_dir: Path | None = None,
    threshold: int = 30,
) -> list[dict]:
    """Compare screenshots across two Robot Framework trace directories.

    Keywords are matched by their numeric index prefix (``001_``, ``002_``,
    etc.).  Only keyword pairs where *both* traces have a ``screenshot.png``
    are compared visually.  When an ``output_dir`` is provided the diff PNG
    for each matched pair is written there as ``diff_NNN_<keyword_name>.png``.

    Args:
        trace1_dir: Path to the first (baseline) trace directory.
        trace2_dir: Path to the second (candidate) trace directory.
        output_dir: Optional directory to save diff PNG images.  The
            directory is created if it does not already exist.
        threshold: Per-channel pixel difference threshold forwarded to
            :func:`compute_visual_diff`.  Defaults to 30.

    Returns:
        A list of comparison-result dictionaries, one per matched keyword
        pair with a screenshot in both traces.  Each dictionary has the
        following keys:

        - ``keyword_name`` (str): Human-readable name of the keyword.
        - ``index`` (int): Numeric index of the keyword.
        - ``similarity`` (float): Similarity score in [0.0, 1.0].
        - ``changed_pixels`` (int): Number of changed pixels.
        - ``total_pixels`` (int): Total pixels in the comparison canvas.
        - ``screenshot_a`` (str): Absolute path to the trace-1 screenshot.
        - ``screenshot_b`` (str): Absolute path to the trace-2 screenshot.
        - ``diff_image_path`` (str | None): Absolute path to the saved diff
          PNG, or ``None`` when ``output_dir`` was not specified.

    Raises:
        FileNotFoundError: If either trace directory does not exist.
        ImportError: If Pillow is not installed.

    Example:
        >>> results = compare_traces(
        ...     Path("./traces/run_1"),
        ...     Path("./traces/run_2"),
        ...     output_dir=Path("./diffs"),
        ... )
        >>> for r in results:
        ...     print(f"{r['keyword_name']}: {r['similarity']:.1%}")
        Go To: 100.0%
        Click Button: 94.2%
    """
    trace1_dir = Path(trace1_dir)
    trace2_dir = Path(trace2_dir)

    if not trace1_dir.exists():
        raise FileNotFoundError(f"Trace directory not found: {trace1_dir}")
    if not trace2_dir.exists():
        raise FileNotFoundError(f"Trace directory not found: {trace2_dir}")

    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    kw_dir_1 = trace1_dir / "keywords"
    kw_dir_2 = trace2_dir / "keywords"

    # Index keyword dirs by their numeric prefix for O(1) lookup.
    def _index_kw_dirs(kw_root: Path) -> dict[int, Path]:
        mapping: dict[int, Path] = {}
        if not kw_root.exists():
            return mapping
        for entry in sorted(kw_root.iterdir()):
            if entry.is_dir():
                idx = _extract_index_prefix(entry.name)
                if idx is not None:
                    mapping[idx] = entry
        return mapping

    map1 = _index_kw_dirs(kw_dir_1)
    map2 = _index_kw_dirs(kw_dir_2)

    # Only compare indices present in both traces.
    common_indices = sorted(set(map1.keys()) & set(map2.keys()))

    results: list[dict] = []

    for idx in common_indices:
        kw1 = map1[idx]
        kw2 = map2[idx]

        png_a = _load_screenshot(kw1)
        png_b = _load_screenshot(kw2)

        # Skip pairs where at least one screenshot is missing.
        if png_a is None or png_b is None:
            continue

        keyword_name = _load_keyword_name(kw1)

        diff_result = compute_visual_diff(png_a, png_b, threshold=threshold)

        # Persist the diff image when an output directory was given.
        diff_image_path: str | None = None
        if output_dir is not None:
            safe_name = re.sub(r"[^\w\-.]", "_", keyword_name.lower())
            diff_filename = f"diff_{idx:03d}_{safe_name}.png"
            diff_path = output_dir / diff_filename
            diff_path.write_bytes(diff_result.diff_image)
            diff_image_path = str(diff_path)

        results.append(
            {
                "keyword_name": keyword_name,
                "index": idx,
                "similarity": diff_result.similarity,
                "changed_pixels": diff_result.changed_pixels,
                "total_pixels": diff_result.total_pixels,
                "screenshot_a": str(kw1 / "screenshot.png"),
                "screenshot_b": str(kw2 / "screenshot.png"),
                "diff_image_path": diff_image_path,
            }
        )

    return results


def _encode_image_as_data_uri(image_path: str) -> str:
    """Encode a PNG file as a ``data:`` URI for embedding in HTML.

    Args:
        image_path: Absolute or relative filesystem path to the PNG.

    Returns:
        A ``data:image/png;base64,…`` string, or an empty string when the
        file cannot be read.
    """
    try:
        raw = Path(image_path).read_bytes()
        encoded = base64.b64encode(raw).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except OSError:
        return ""


def generate_comparison_html(
    results: list[dict],
    trace1_dir: Path,
    trace2_dir: Path,
    output: Path | None = None,
) -> Path:
    """Generate a standalone HTML report comparing two trace runs visually.

    The report contains one section per compared keyword, each with:

    - A **3-panel layout**: Image A (baseline), Image B (candidate), Diff.
    - A **blend slider** that morphs the viewport between A and B so
      reviewers can easily spot changes by scrubbing.
    - A **similarity badge** showing the percentage of unchanged pixels.

    A summary at the top of the page lists:

    - Total number of keywords compared.
    - Average similarity across all comparisons.
    - The keyword with the most changed pixels.

    The report is fully self-contained: all images are embedded as
    Base64-encoded ``data:`` URIs so the file can be opened offline and
    shared without accompanying assets.

    Args:
        results: List of comparison dicts as returned by
            :func:`compare_traces`.  Each dict must contain at minimum the
            keys ``keyword_name``, ``index``, ``similarity``,
            ``changed_pixels``, ``total_pixels``, ``screenshot_a``,
            ``screenshot_b``, and ``diff_image_path``.
        trace1_dir: Path to the first (baseline) trace directory, used for
            display purposes in the report header.
        trace2_dir: Path to the second (candidate) trace directory, used for
            display purposes in the report header.
        output: Optional path where the HTML file will be written.  When
            omitted the file is written as ``visual_comparison.html`` inside
            ``trace1_dir``.

    Returns:
        The :class:`~pathlib.Path` of the generated HTML file.

    Raises:
        ValueError: If ``results`` contains an entry missing required keys.

    Example:
        >>> results = compare_traces(Path("./run_1"), Path("./run_2"))
        >>> report = generate_comparison_html(
        ...     results,
        ...     Path("./run_1"),
        ...     Path("./run_2"),
        ...     output=Path("./comparison_report.html"),
        ... )
        >>> print(f"Report written to: {report}")
        Report written to: ./comparison_report.html
    """
    trace1_dir = Path(trace1_dir)
    trace2_dir = Path(trace2_dir)

    if output is None:
        output = trace1_dir / "visual_comparison.html"
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Compute summary statistics.
    total_compared = len(results)
    avg_similarity: float = (
        sum(r["similarity"] for r in results) / total_compared if total_compared > 0 else 1.0
    )
    most_changed: dict | None = max(results, key=lambda r: r["changed_pixels"]) if results else None
    most_changed_name: str = most_changed["keyword_name"] if most_changed else "N/A"
    most_changed_pct: float = (1.0 - most_changed["similarity"]) * 100.0 if most_changed else 0.0

    # Pre-encode images to data URIs so the file is self-contained.
    encoded_results: list[dict] = []
    for r in results:
        entry = dict(r)
        entry["data_uri_a"] = _encode_image_as_data_uri(r["screenshot_a"])
        entry["data_uri_b"] = _encode_image_as_data_uri(r["screenshot_b"])
        diff_path = r.get("diff_image_path")
        entry["data_uri_diff"] = _encode_image_as_data_uri(diff_path) if diff_path else ""
        encoded_results.append(entry)

    # Build per-keyword HTML sections.
    keyword_sections: list[str] = []
    for entry in encoded_results:
        similarity_pct = entry["similarity"] * 100.0
        changed_pct = (1.0 - entry["similarity"]) * 100.0
        badge_class = (
            "badge-pass"
            if entry["similarity"] >= 0.99
            else ("badge-warn" if entry["similarity"] >= 0.90 else "badge-fail")
        )

        img_a_html = (
            f'<img src="{entry["data_uri_a"]}" alt="Baseline screenshot" />'
            if entry["data_uri_a"]
            else '<p class="no-image">No screenshot</p>'
        )
        img_b_html = (
            f'<img src="{entry["data_uri_b"]}" alt="Candidate screenshot" />'
            if entry["data_uri_b"]
            else '<p class="no-image">No screenshot</p>'
        )
        diff_img_html = (
            f'<img src="{entry["data_uri_diff"]}" alt="Diff overlay" />'
            if entry["data_uri_diff"]
            else '<p class="no-image">Diff not available</p>'
        )

        kw_id = f"kw-{entry['index']:03d}"

        keyword_sections.append(f"""
    <section class="kw-section" id="{kw_id}">
      <div class="kw-header">
        <span class="kw-index">#{entry['index']:03d}</span>
        <span class="kw-name">{_escape_html(entry['keyword_name'])}</span>
        <span class="badge {badge_class}">{similarity_pct:.1f}% similar</span>
        <span class="changed-count">{entry['changed_pixels']:,} / {entry['total_pixels']:,} px changed ({changed_pct:.1f}%)</span>
      </div>

      <div class="blend-control">
        <label for="slider-{kw_id}">Blend A &harr; B</label>
        <input
          type="range" id="slider-{kw_id}" class="blend-slider"
          min="0" max="100" value="0"
          data-target="{kw_id}"
        />
        <span class="blend-label">A</span>
      </div>

      <div class="panels">
        <div class="panel panel-a">
          <div class="panel-label">A &mdash; Baseline</div>
          <div class="panel-image blend-image-a" id="img-a-{kw_id}">
            {img_a_html}
          </div>
        </div>
        <div class="panel panel-b">
          <div class="panel-label">B &mdash; Candidate</div>
          <div class="panel-image blend-image-b" id="img-b-{kw_id}" style="opacity:0;">
            {img_b_html}
          </div>
        </div>
        <div class="panel panel-diff">
          <div class="panel-label">Diff (red = changed)</div>
          <div class="panel-image">
            {diff_img_html}
          </div>
        </div>
      </div>
    </section>""")

    keywords_html = (
        "\n".join(keyword_sections)
        if keyword_sections
        else ('<p class="no-results">No keywords with screenshots found in both traces.</p>')
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Visual Comparison &mdash; {_escape_html(trace1_dir.name)} vs {_escape_html(trace2_dir.name)}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --color-pass:   #22c55e;
      --color-warn:   #f59e0b;
      --color-fail:   #ef4444;
      --color-border: #e5e7eb;
      --color-bg:     #f9fafb;
      --color-card:   #ffffff;
      --color-text:   #111827;
      --color-muted:  #6b7280;
      --radius:       8px;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                   "Helvetica Neue", Arial, sans-serif;
      background: var(--color-bg);
      color: var(--color-text);
      line-height: 1.5;
    }}

    /* ---- Header ---- */
    .page-header {{
      background: var(--color-card);
      border-bottom: 1px solid var(--color-border);
      padding: 20px 32px;
      position: sticky;
      top: 0;
      z-index: 50;
      box-shadow: 0 1px 4px rgba(0,0,0,.06);
    }}
    .page-header h1 {{
      font-size: 1.25rem;
      font-weight: 700;
    }}
    .page-header p {{
      font-size: .875rem;
      color: var(--color-muted);
      margin-top: 2px;
    }}

    /* ---- Summary ---- */
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      padding: 24px 32px;
      background: var(--color-card);
      border-bottom: 1px solid var(--color-border);
    }}
    .summary-item {{
      background: var(--color-bg);
      border: 1px solid var(--color-border);
      border-radius: var(--radius);
      padding: 14px 20px;
      min-width: 160px;
      text-align: center;
    }}
    .summary-item .value {{
      font-size: 1.75rem;
      font-weight: 700;
    }}
    .summary-item .label {{
      font-size: .75rem;
      color: var(--color-muted);
      text-transform: uppercase;
      letter-spacing: .05em;
      margin-top: 4px;
    }}
    .summary-item.highlight-warn .value {{ color: var(--color-warn); }}
    .summary-item.highlight-fail .value {{ color: var(--color-fail); }}

    /* ---- Main content ---- */
    .content {{
      max-width: 1600px;
      margin: 32px auto;
      padding: 0 32px 64px;
    }}

    /* ---- Keyword section ---- */
    .kw-section {{
      background: var(--color-card);
      border: 1px solid var(--color-border);
      border-radius: var(--radius);
      margin-bottom: 32px;
      overflow: hidden;
    }}

    .kw-header {{
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      padding: 16px 20px;
      background: var(--color-bg);
      border-bottom: 1px solid var(--color-border);
    }}
    .kw-index {{
      font-size: .75rem;
      font-weight: 700;
      color: var(--color-muted);
      font-variant-numeric: tabular-nums;
    }}
    .kw-name {{
      font-weight: 600;
      font-size: 1rem;
      flex: 1;
    }}
    .changed-count {{
      font-size: .75rem;
      color: var(--color-muted);
    }}

    /* Similarity badges */
    .badge {{
      display: inline-block;
      padding: 3px 10px;
      border-radius: 9999px;
      font-size: .75rem;
      font-weight: 600;
    }}
    .badge-pass {{ background: #dcfce7; color: #15803d; }}
    .badge-warn {{ background: #fef3c7; color: #b45309; }}
    .badge-fail {{ background: #fee2e2; color: #b91c1c; }}

    /* ---- Blend slider ---- */
    .blend-control {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 20px;
      border-bottom: 1px solid var(--color-border);
      background: var(--color-bg);
      font-size: .875rem;
      color: var(--color-muted);
    }}
    .blend-slider {{
      flex: 1;
      max-width: 320px;
      cursor: pointer;
      accent-color: #6366f1;
    }}
    .blend-label {{
      min-width: 1.5rem;
      font-weight: 600;
      color: var(--color-text);
    }}

    /* ---- 3-panel image grid ---- */
    .panels {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 0;
    }}
    .panel {{
      border-right: 1px solid var(--color-border);
    }}
    .panel:last-child {{
      border-right: none;
    }}
    .panel-label {{
      padding: 8px 12px;
      font-size: .75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: .05em;
      color: var(--color-muted);
      border-bottom: 1px solid var(--color-border);
      background: var(--color-bg);
    }}
    .panel-image {{
      padding: 12px;
      background: #f0f0f0;
      min-height: 120px;
      position: relative;
    }}
    .panel-image img {{
      width: 100%;
      height: auto;
      display: block;
      border-radius: 4px;
    }}
    .no-image {{
      text-align: center;
      padding: 40px 0;
      color: var(--color-muted);
      font-style: italic;
    }}

    /* Blend overlay: panel-b sits on top of panel-a using absolute positioning
       when the slider is active. We implement blend via JS opacity. */
    .panel-a,
    .panel-b {{
      position: relative;
    }}
    .blend-image-b {{
      position: absolute;
      inset: 0;
      padding: 12px;
      pointer-events: none;
    }}

    /* ---- No results ---- */
    .no-results {{
      text-align: center;
      padding: 60px 0;
      color: var(--color-muted);
      font-style: italic;
    }}

    /* ---- Responsive ---- */
    @media (max-width: 900px) {{
      .panels {{ grid-template-columns: 1fr; }}
      .panel {{ border-right: none; border-bottom: 1px solid var(--color-border); }}
      .panel:last-child {{ border-bottom: none; }}
      .blend-image-b {{ position: static; }}
    }}
  </style>
</head>
<body>

  <header class="page-header">
    <h1>Visual Comparison Report</h1>
    <p>
      Baseline: <strong>{_escape_html(str(trace1_dir))}</strong>
      &nbsp;&mdash;&nbsp;
      Candidate: <strong>{_escape_html(str(trace2_dir))}</strong>
    </p>
  </header>

  <div class="summary">
    <div class="summary-item">
      <div class="value">{total_compared}</div>
      <div class="label">Keywords Compared</div>
    </div>
    <div class="summary-item {"highlight-warn" if avg_similarity < 0.99 else ""}">
      <div class="value">{avg_similarity * 100.0:.1f}%</div>
      <div class="label">Avg. Similarity</div>
    </div>
    <div class="summary-item {"highlight-fail" if most_changed_pct > 5 else ""}">
      <div class="value">{most_changed_pct:.1f}%</div>
      <div class="label">Most Changed</div>
    </div>
    <div class="summary-item">
      <div class="value" style="font-size:1rem; padding-top:.25rem;">
        {_escape_html(most_changed_name)}
      </div>
      <div class="label">Most Changed Keyword</div>
    </div>
  </div>

  <main class="content">
    {keywords_html}
  </main>

  <script>
    (function () {{
      'use strict';

      // Blend slider: interpolates opacity between Image A and Image B
      // so the reviewer can scrub between baseline and candidate.
      document.querySelectorAll('.blend-slider').forEach(function (slider) {{
        var targetId = slider.dataset.target;
        var imgBWrapper = document.getElementById('img-b-' + targetId);
        var label = slider.parentElement.querySelector('.blend-label');

        function updateBlend (value) {{
          var t = parseInt(value, 10) / 100;
          if (imgBWrapper) {{
            imgBWrapper.style.opacity = t.toFixed(2);
          }}
          if (label) {{
            label.textContent = t === 0 ? 'A' : (t === 1 ? 'B' : Math.round(t * 100) + '%');
          }}
        }}

        slider.addEventListener('input', function () {{
          updateBlend(slider.value);
        }});

        // Initialise
        updateBlend(slider.value);
      }});
    }})();
  </script>

</body>
</html>"""

    output.write_text(html, encoding="utf-8")
    return output


def _escape_html(text: str) -> str:
    """Escape special HTML characters in ``text``.

    Handles the five characters that must be escaped in HTML content
    (``&``, ``<``, ``>``, ``"``, ``'``) to prevent XSS and rendering
    errors when embedding arbitrary strings in the generated report.

    Args:
        text: Raw string to escape.

    Returns:
        HTML-safe version of the input string.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
