"""GIF and slideshow generator from trace screenshots.

Requires Pillow>=9.0 (optional dependency).

This module provides two independent export paths for a trace directory:

1. ``generate_gif`` — assembles ``screenshot.png`` files found under
   ``<trace_dir>/keywords/*/screenshot.png`` into an animated GIF.  Frames are
   sorted by keyword directory name (which starts with a zero-padded index) so
   the animation follows chronological execution order.

2. ``generate_slideshow`` — produces a self-contained ``slideshow.html`` with
   all screenshots base64-embedded, play/pause controls, per-step navigation,
   speed selector, and keyword name/status overlay.  No external dependencies
   are required; the file can be opened directly in any modern browser.

Edge cases handled by both functions:
- No screenshots found: raises ``FileNotFoundError`` with an actionable message.
- Single screenshot: produces a valid (static) GIF / single-frame slideshow.
- Missing ``metadata.json``: slideshow falls back to directory-name labels.
- Non-power-of-two resize dimensions: Pillow handles arbitrary integer sizes.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _collect_screenshot_paths(trace_dir: Path) -> list[Path]:
    """Return screenshot paths sorted by keyword directory name.

    Scans ``<trace_dir>/keywords/*/screenshot.png`` and sorts the results by
    the parent directory name.  Keyword directories are named with a
    zero-padded numeric prefix (e.g. ``001_open_browser``) so lexicographic
    sort gives chronological order.

    Args:
        trace_dir: Root trace directory produced by ``TraceListener``.

    Returns:
        Sorted list of existing screenshot ``Path`` objects.
    """
    keywords_dir = trace_dir / "keywords"
    if not keywords_dir.is_dir():
        return []

    screenshots = sorted(
        (kw_dir / "screenshot.png")
        for kw_dir in keywords_dir.iterdir()
        if kw_dir.is_dir() and (kw_dir / "screenshot.png").is_file()
    )
    return screenshots


def _load_keyword_metadata(kw_dir: Path) -> dict[str, str]:
    """Load keyword metadata from ``metadata.json`` if present.

    Args:
        kw_dir: Keyword directory (e.g. ``<trace_dir>/keywords/001_open_browser``).

    Returns:
        Dictionary with at least ``"name"`` and ``"status"`` keys.
        Falls back to the directory name and ``"UNKNOWN"`` when the file is
        absent or cannot be parsed.
    """
    metadata_path = kw_dir / "metadata.json"
    fallback: dict[str, str] = {"name": kw_dir.name, "status": "UNKNOWN"}

    if not metadata_path.is_file():
        return fallback

    try:
        with open(metadata_path, encoding="utf-8") as fh:
            data: dict[str, object] = json.load(fh)
        return {
            "name": str(data.get("name", kw_dir.name)),
            "status": str(data.get("status", "UNKNOWN")),
        }
    except (OSError, json.JSONDecodeError):
        return fallback


def _resize_image(image: object, max_width: int) -> object:
    """Resize a Pillow Image so its width does not exceed *max_width*.

    The aspect ratio is preserved.  Images that are already narrower than
    *max_width* are returned unchanged.

    Args:
        image: A ``PIL.Image.Image`` instance.
        max_width: Maximum pixel width for the output image.

    Returns:
        The original image (if no resize needed) or a new resized ``Image``.
    """
    # We accept ``object`` for the type so callers do not need a Pillow import
    # at the module level.  Attribute access is safe because callers guarantee
    # the object is a real PIL Image.
    width, height = image.size  # type: ignore[attr-defined]
    if width <= max_width:
        return image
    ratio = max_width / width
    new_height = max(1, int(height * ratio))
    # LANCZOS is the highest-quality downsampling filter in Pillow.
    resampling = _get_resampling_filter()
    return image.resize((max_width, new_height), resampling)  # type: ignore[attr-defined]


def _get_resampling_filter() -> object:
    """Return the best available Pillow resampling filter.

    Pillow>=9.1 deprecated ``Image.ANTIALIAS`` in favour of
    ``Image.Resampling.LANCZOS``.  This helper supports both.

    Returns:
        Pillow resampling constant suitable for high-quality downscaling.
    """
    try:
        from PIL import Image  # type: ignore[import]

        return Image.Resampling.LANCZOS
    except AttributeError:
        from PIL import Image  # type: ignore[import]

        return Image.LANCZOS  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_gif(
    trace_dir: Path,
    output: Path | None = None,
    fps: int = 2,
    max_width: int = 800,
) -> Path:
    """Assemble trace screenshots into an animated GIF.

    Screenshots are collected from ``<trace_dir>/keywords/*/screenshot.png``
    and sorted by keyword directory name so that frames appear in the same
    order as test execution.  Each frame is resized to *max_width* while
    preserving the original aspect ratio.

    Args:
        trace_dir: Root trace directory produced by ``TraceListener``.
        output: Destination file path for the GIF.  Defaults to
            ``<trace_dir>/replay.gif``.
        fps: Frames per second.  Controls how long each frame is displayed
            (``duration = 1000 / fps`` milliseconds).  Must be >= 1.
        max_width: Maximum pixel width of each frame.  Frames are downscaled
            proportionally when they exceed this width; they are never
            upscaled.

    Returns:
        Absolute path to the generated GIF file.

    Raises:
        ImportError: If Pillow is not installed.  The message explains how to
            install the optional dependency.
        FileNotFoundError: If no screenshots are found under *trace_dir*.
        ValueError: If *fps* is less than 1.

    Example:
        >>> from pathlib import Path
        >>> gif_path = generate_gif(Path("./traces/login_test_20250120"))
        >>> print(f"GIF written to {gif_path}")
    """
    # Validate fps before doing any I/O.
    if fps < 1:
        raise ValueError(f"fps must be >= 1, got {fps!r}")

    # Fail fast with a clear message if Pillow is absent.
    try:
        from PIL import Image  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "Pillow is required to generate GIF files.  "
            "Install it with:  pip install 'Pillow>=9.0'"
        ) from exc

    screenshot_paths = _collect_screenshot_paths(trace_dir)
    if not screenshot_paths:
        raise FileNotFoundError(
            f"No screenshots found under '{trace_dir / 'keywords'}'.  "
            "Run TraceListener with capture_mode='full' to collect screenshots."
        )

    output_path = output if output is not None else trace_dir / "replay.gif"

    # Load and resize all frames.
    frames: list[object] = []
    for path in screenshot_paths:
        img = Image.open(path).convert("RGBA")
        img = _resize_image(img, max_width)
        # GIF supports palette mode only; convert keeping transparency.
        frames.append(img.convert("P", palette=Image.Palette.ADAPTIVE))  # type: ignore[attr-defined]

    duration_ms = max(1, 1000 // fps)

    first_frame = frames[0]
    rest_frames = frames[1:]

    save_kwargs: dict[str, object] = {
        "format": "GIF",
        "save_all": True,
        "loop": 0,  # loop indefinitely
        "duration": duration_ms,
        "optimize": False,  # optimisation can corrupt palette on some images
    }
    if rest_frames:
        save_kwargs["append_images"] = rest_frames

    first_frame.save(output_path, **save_kwargs)  # type: ignore[attr-defined]
    return output_path.resolve() if isinstance(output_path, Path) else Path(output_path).resolve()


def generate_slideshow(
    trace_dir: Path,
    output: Path | None = None,
) -> Path:
    """Generate a self-contained HTML slideshow from trace screenshots.

    All screenshots are base64-encoded and embedded directly in the HTML so
    the resulting file is fully offline-capable and portable.  Keyword name
    and status are shown below each frame using metadata loaded from
    ``metadata.json`` files in each keyword directory.

    The slideshow supports:
    - **Play / Pause**: auto-advance through frames at a configurable speed.
    - **Prev / Next**: manual single-step navigation.
    - **Speed selector**: 0.5x, 1x (default), 2x, 4x playback speeds.
    - **Progress bar**: visual indicator of current position.
    - **Status colouring**: frame border and label are coloured green (PASS),
      red (FAIL), or grey (UNKNOWN/other).

    Args:
        trace_dir: Root trace directory produced by ``TraceListener``.
        output: Destination file path for the HTML.  Defaults to
            ``<trace_dir>/slideshow.html``.

    Returns:
        Absolute path to the generated HTML file.

    Raises:
        FileNotFoundError: If no screenshots are found under *trace_dir*.

    Example:
        >>> from pathlib import Path
        >>> html_path = generate_slideshow(Path("./traces/login_test_20250120"))
        >>> print(f"Slideshow written to {html_path}")
    """
    screenshot_paths = _collect_screenshot_paths(trace_dir)
    if not screenshot_paths:
        raise FileNotFoundError(
            f"No screenshots found under '{trace_dir / 'keywords'}'.  "
            "Run TraceListener with capture_mode='full' to collect screenshots."
        )

    output_path = output if output is not None else trace_dir / "slideshow.html"

    # Build the frame data list: base64 image + keyword metadata.
    frames_data: list[dict[str, str]] = []
    for path in screenshot_paths:
        kw_dir = path.parent
        metadata = _load_keyword_metadata(kw_dir)
        raw_bytes = path.read_bytes()
        b64 = base64.b64encode(raw_bytes).decode("ascii")
        frames_data.append(
            {
                "src": f"data:image/png;base64,{b64}",
                "name": metadata["name"],
                "status": metadata["status"],
                "folder": kw_dir.name,
            }
        )

    # Serialise frame data for the inline JavaScript.
    frames_json = json.dumps(frames_data, ensure_ascii=False)

    test_name = _load_test_name(trace_dir)
    total = len(frames_data)

    html = _render_slideshow_html(
        test_name=test_name,
        total=total,
        frames_json=frames_json,
    )

    output_path.write_text(html, encoding="utf-8")
    return output_path.resolve() if isinstance(output_path, Path) else Path(output_path).resolve()


# ---------------------------------------------------------------------------
# Slideshow rendering helpers
# ---------------------------------------------------------------------------


def _load_test_name(trace_dir: Path) -> str:
    """Read the test name from ``manifest.json`` if available.

    Args:
        trace_dir: Root trace directory.

    Returns:
        Test name string, or the directory name as a fallback.
    """
    manifest_path = trace_dir / "manifest.json"
    if not manifest_path.is_file():
        return trace_dir.name
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            data: dict[str, object] = json.load(fh)
        return str(data.get("test_name", trace_dir.name))
    except (OSError, json.JSONDecodeError):
        return trace_dir.name


def _render_slideshow_html(
    test_name: str,
    total: int,
    frames_json: str,
) -> str:
    """Render the complete slideshow HTML document.

    Args:
        test_name: Human-readable test name shown in the title bar and heading.
        total: Total number of frames (used for initialising the UI counter).
        frames_json: JSON-serialised list of frame dictionaries, each with
            ``src``, ``name``, ``status``, and ``folder`` keys.

    Returns:
        Complete UTF-8 HTML document as a string.
    """
    # Use a raw-string template so curly braces inside CSS/JS are not
    # interpreted by Python's str.format.  We substitute our own placeholders
    # using a simple replace strategy with sentinel tokens that cannot appear
    # in the data (double-underscore-wrapped uppercase identifiers).
    template = _SLIDESHOW_HTML_TEMPLATE
    html = (
        template.replace("__TEST_NAME__", _escape_html(test_name))
        .replace("__TOTAL__", str(total))
        .replace("__FRAMES_JSON__", frames_json)
    )
    return html


def _escape_html(text: str) -> str:
    """Escape characters that are special in HTML attribute values and text nodes.

    Args:
        text: Raw string that may contain ``<``, ``>``, ``&``, or ``"``.

    Returns:
        HTML-safe string.
    """
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# Slideshow HTML template
# ---------------------------------------------------------------------------

# The template uses __SENTINEL__ placeholders instead of {braces} so that the
# surrounding CSS/JS braces are preserved verbatim.  Substitution is performed
# by _render_slideshow_html via str.replace.

_SLIDESHOW_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Slideshow — __TEST_NAME__</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                   Helvetica, Arial, sans-serif;
      background: #0f1117;
      color: #e2e8f0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 1.5rem 1rem;
    }

    h1 {
      font-size: 1.25rem;
      font-weight: 600;
      margin-bottom: 1rem;
      text-align: center;
      color: #a0aec0;
      max-width: 900px;
      word-break: break-word;
    }

    /* ---- Frame container ---- */
    .frame-wrap {
      position: relative;
      max-width: 900px;
      width: 100%;
      border: 3px solid #4a5568;
      border-radius: 8px;
      overflow: hidden;
      background: #1a202c;
      transition: border-color 0.2s;
    }
    .frame-wrap.pass  { border-color: #48bb78; }
    .frame-wrap.fail  { border-color: #fc8181; }
    .frame-wrap.skip  { border-color: #f6ad55; }

    .frame-wrap img {
      display: block;
      width: 100%;
      height: auto;
    }

    /* ---- Keyword label overlay ---- */
    .kw-label {
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      background: rgba(0, 0, 0, 0.72);
      padding: 0.4rem 0.75rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.8rem;
      backdrop-filter: blur(4px);
    }
    .kw-label .kw-name {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo,
                   monospace;
    }
    .badge {
      display: inline-block;
      padding: 0.15rem 0.45rem;
      border-radius: 4px;
      font-size: 0.7rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      flex-shrink: 0;
    }
    .badge.pass { background: #276749; color: #c6f6d5; }
    .badge.fail { background: #742a2a; color: #fed7d7; }
    .badge.skip { background: #7b341e; color: #feebc8; }
    .badge.unknown { background: #2d3748; color: #a0aec0; }

    /* ---- Progress bar ---- */
    .progress-bar-wrap {
      max-width: 900px;
      width: 100%;
      height: 4px;
      background: #2d3748;
      border-radius: 2px;
      margin: 0.6rem 0;
      overflow: hidden;
    }
    .progress-bar {
      height: 100%;
      background: #63b3ed;
      border-radius: 2px;
      transition: width 0.15s ease;
    }

    /* ---- Counter ---- */
    .counter {
      font-size: 0.85rem;
      color: #718096;
      margin-bottom: 0.75rem;
    }

    /* ---- Controls ---- */
    .controls {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      flex-wrap: wrap;
      justify-content: center;
      max-width: 900px;
      width: 100%;
    }

    button {
      padding: 0.45rem 1rem;
      border-radius: 6px;
      border: 1px solid #4a5568;
      background: #2d3748;
      color: #e2e8f0;
      font-size: 0.85rem;
      cursor: pointer;
      transition: background 0.15s, border-color 0.15s;
    }
    button:hover { background: #3d4f66; border-color: #63b3ed; }
    button:active { background: #1a202c; }
    button:disabled { opacity: 0.4; cursor: not-allowed; }

    button#btn-play-pause {
      min-width: 5.5rem;
      background: #2b4c7e;
      border-color: #4299e1;
      font-weight: 600;
    }
    button#btn-play-pause:hover { background: #2c5282; }
    button#btn-play-pause.playing { background: #742a2a; border-color: #fc8181; }

    select#speed-select {
      padding: 0.45rem 0.5rem;
      border-radius: 6px;
      border: 1px solid #4a5568;
      background: #2d3748;
      color: #e2e8f0;
      font-size: 0.85rem;
      cursor: pointer;
    }
    select#speed-select:focus { outline: 2px solid #63b3ed; }

    /* ---- Single-frame notice ---- */
    .single-frame-notice {
      margin-top: 0.5rem;
      font-size: 0.78rem;
      color: #718096;
    }
  </style>
</head>
<body>
  <h1>__TEST_NAME__</h1>

  <div class="frame-wrap" id="frame-wrap">
    <img id="frame-img" src="" alt="Screenshot">
    <div class="kw-label">
      <span class="kw-name" id="kw-name"></span>
      <span class="badge" id="kw-badge"></span>
    </div>
  </div>

  <div class="progress-bar-wrap">
    <div class="progress-bar" id="progress-bar" style="width:0%"></div>
  </div>

  <div class="counter" id="counter">1 / __TOTAL__</div>

  <div class="controls">
    <button id="btn-prev" title="Previous step">&larr; Prev</button>
    <button id="btn-play-pause" title="Play / Pause">&#9654; Play</button>
    <button id="btn-next" title="Next step">Next &rarr;</button>
    <label for="speed-select" style="font-size:0.82rem;color:#a0aec0;">Speed:</label>
    <select id="speed-select" title="Playback speed">
      <option value="2">0.5x</option>
      <option value="1" selected>1x</option>
      <option value="0.5">2x</option>
      <option value="0.25">4x</option>
    </select>
  </div>

  <script>
    (function () {
      "use strict";

      // ------------------------------------------------------------------ //
      // Data injected by the generator                                      //
      // ------------------------------------------------------------------ //
      var FRAMES = __FRAMES_JSON__;
      var TOTAL  = FRAMES.length;

      // ------------------------------------------------------------------ //
      // State                                                                //
      // ------------------------------------------------------------------ //
      var currentIndex = 0;
      var playing      = false;
      var timer        = null;

      // ------------------------------------------------------------------ //
      // DOM refs                                                             //
      // ------------------------------------------------------------------ //
      var frameWrap   = document.getElementById("frame-wrap");
      var frameImg    = document.getElementById("frame-img");
      var kwName      = document.getElementById("kw-name");
      var kwBadge     = document.getElementById("kw-badge");
      var counter     = document.getElementById("counter");
      var progressBar = document.getElementById("progress-bar");
      var btnPrev     = document.getElementById("btn-prev");
      var btnNext     = document.getElementById("btn-next");
      var btnPlay     = document.getElementById("btn-play-pause");
      var speedSel    = document.getElementById("speed-select");

      // ------------------------------------------------------------------ //
      // Rendering                                                            //
      // ------------------------------------------------------------------ //
      function statusClass(status) {
        var s = (status || "").toUpperCase();
        if (s === "PASS")  return "pass";
        if (s === "FAIL")  return "fail";
        if (s === "SKIP")  return "skip";
        return "unknown";
      }

      function render(index) {
        if (TOTAL === 0) return;
        var frame = FRAMES[index];
        var cls   = statusClass(frame.status);

        frameImg.src = frame.src;
        kwName.textContent = frame.name;

        kwBadge.textContent = frame.status || "UNKNOWN";
        kwBadge.className   = "badge " + cls;

        // Remove previous status class from frame wrapper.
        frameWrap.classList.remove("pass", "fail", "skip", "unknown");
        frameWrap.classList.add(cls);

        counter.textContent = (index + 1) + " / " + TOTAL;

        var pct = TOTAL > 1 ? (index / (TOTAL - 1)) * 100 : 100;
        progressBar.style.width = pct.toFixed(1) + "%";

        btnPrev.disabled = (index === 0);
        btnNext.disabled = (index === TOTAL - 1);
      }

      // ------------------------------------------------------------------ //
      // Navigation                                                           //
      // ------------------------------------------------------------------ //
      function goTo(index) {
        currentIndex = Math.max(0, Math.min(TOTAL - 1, index));
        render(currentIndex);
      }

      function step(delta) {
        var next = currentIndex + delta;
        if (next < 0 || next >= TOTAL) {
          // Reached a boundary while playing — pause.
          if (playing) togglePlay();
          return;
        }
        goTo(next);
      }

      // ------------------------------------------------------------------ //
      // Playback                                                             //
      // ------------------------------------------------------------------ //
      function intervalMs() {
        var mult = parseFloat(speedSel.value) || 1;
        // Base interval = 1000 ms per frame; multiply by speed factor.
        return Math.max(100, Math.round(1000 * mult));
      }

      function scheduleNext() {
        clearTimeout(timer);
        timer = setTimeout(function () {
          if (!playing) return;
          if (currentIndex >= TOTAL - 1) {
            togglePlay();
            return;
          }
          step(1);
          scheduleNext();
        }, intervalMs());
      }

      function togglePlay() {
        if (TOTAL <= 1) return;   // Nothing to play.
        playing = !playing;
        if (playing) {
          // If we are at the end, restart from the beginning.
          if (currentIndex >= TOTAL - 1) goTo(0);
          btnPlay.textContent = "\u23f8 Pause";
          btnPlay.classList.add("playing");
          scheduleNext();
        } else {
          clearTimeout(timer);
          btnPlay.textContent = "\u25b6 Play";
          btnPlay.classList.remove("playing");
        }
      }

      // ------------------------------------------------------------------ //
      // Event listeners                                                      //
      // ------------------------------------------------------------------ //
      btnPrev.addEventListener("click", function () { step(-1); });
      btnNext.addEventListener("click", function () { step(1); });
      btnPlay.addEventListener("click", togglePlay);

      speedSel.addEventListener("change", function () {
        if (playing) {
          // Restart timer with new interval.
          clearTimeout(timer);
          scheduleNext();
        }
      });

      document.addEventListener("keydown", function (e) {
        switch (e.key) {
          case "ArrowLeft":  step(-1);    break;
          case "ArrowRight": step(1);     break;
          case " ":          togglePlay(); e.preventDefault(); break;
          default: break;
        }
      });

      // ------------------------------------------------------------------ //
      // Handle single-frame edge case                                        //
      // ------------------------------------------------------------------ //
      if (TOTAL <= 1) {
        btnPlay.disabled = true;
        var notice = document.createElement("p");
        notice.className = "single-frame-notice";
        notice.textContent =
          "Only one screenshot was captured. Navigation controls are disabled.";
        document.querySelector(".controls").after(notice);
      }

      // ------------------------------------------------------------------ //
      // Initial render                                                       //
      // ------------------------------------------------------------------ //
      goTo(0);
    }());
  </script>
</body>
</html>
"""
