# Features Guide

This guide provides detailed documentation for all features of Robot Framework Trace Viewer.

## Table of Contents

- [Configuration File](#configuration-file)
- [Screenshot Capture](#screenshot-capture)
- [Full-Page Screenshots](#full-page-screenshots)
- [On-Failure Ring Buffer](#on-failure-ring-buffer)
- [DOM Snapshots](#dom-snapshots)
- [Network Request Capture](#network-request-capture)
- [Console Logs Capture](#console-logs-capture)
- [Variable Tracking](#variable-tracking)
- [Custom Masking Patterns](#custom-masking-patterns)
- [Search & Filter Viewer](#search--filter-viewer)
- [Suite-Level Viewer](#suite-level-viewer)
- [Trace Comparison](#trace-comparison)
- [Visual Diff](#visual-diff)
- [GIF Replay](#gif-replay)
- [Statistics Dashboard](#statistics-dashboard)
- [WebP Compression](#webp-compression)
- [Trace Cleanup](#trace-cleanup)
- [PDF Export](#pdf-export)
- [ZIP Export](#zip-export)
- [Pabot Support](#pabot-support)
- [Pabot Merge Timeline](#pabot-merge-timeline)

---

## Configuration File

The trace viewer supports YAML configuration files for persistent settings.

### Config File Locations

The listener searches for config files in this order:

1. `./trace-viewer.yml` (project directory)
2. `~/.trace-viewer.yml` (home directory)

### Precedence Chain

Settings are resolved with this precedence (highest first):

1. **CLI arguments** - Listener parameters passed via `--listener`
2. **Environment variables** - `TRACE_VIEWER_*` prefix
3. **Config file** - `trace-viewer.yml`
4. **Defaults** - Built-in default values

### Generating a Config File

```bash
trace-viewer init
```

### Complete Config Reference

```yaml
# Output directory for traces
output_dir: traces

# Capture mode: full | on_failure | disabled
capture_mode: full

# Screenshot mode: viewport | full_page
screenshot_mode: viewport

# Ring buffer size for on_failure mode (number of keywords to keep)
buffer_size: 10

# Patterns to mask in captured variables (case-insensitive substring match)
masking_patterns:
  - password
  - secret
  - token
  - key
  - credential
  - auth
  - api_key

# Compression settings
compression:
  format: png          # png | webp
  quality: 80          # WebP quality (1-100)
  max_dom_size_kb: 500 # Truncate DOM snapshots larger than this

# Retention policy
retention:
  days: 30             # Delete traces older than N days
  max_traces: 100      # Maximum number of traces to keep

# CI/CD mode (enables on_failure capture + CI-friendly output)
ci_mode: false
```

### Environment Variables

| Variable | Config Key | Example |
|----------|-----------|---------|
| `TRACE_VIEWER_OUTPUT_DIR` | `output_dir` | `./my_traces` |
| `TRACE_VIEWER_CAPTURE_MODE` | `capture_mode` | `on_failure` |
| `TRACE_VIEWER_SCREENSHOT_MODE` | `screenshot_mode` | `full_page` |
| `TRACE_VIEWER_BUFFER_SIZE` | `buffer_size` | `20` |
| `TRACE_VIEWER_CI_MODE` | `ci_mode` | `true` |
| `TRACE_VIEWER_COMPRESSION_FORMAT` | `compression.format` | `webp` |
| `TRACE_VIEWER_COMPRESSION_QUALITY` | `compression.quality` | `70` |

---

## Screenshot Capture

Screenshots are automatically captured at the end of each keyword execution when a browser is active.

### How It Works

1. The listener detects active browser sessions from SeleniumLibrary or Browser Library
2. At the end of each keyword, a screenshot is captured
3. Screenshots are saved as PNG (or WebP if compression is enabled) in the keyword directory

### Supported Libraries

| Library | Method | Notes |
|---------|--------|-------|
| SeleniumLibrary | `driver.get_screenshot_as_png()` | Uses Selenium WebDriver |
| Browser Library | `Take Screenshot` keyword | Uses Playwright |

### Configuration

```bash
# Capture at every keyword (default)
robot --listener "trace_viewer.TraceListener:capture_mode=full" tests/

# Capture only on failure
robot --listener "trace_viewer.TraceListener:capture_mode=on_failure" tests/

# Disable screenshot capture
robot --listener "trace_viewer.TraceListener:capture_mode=disabled" tests/
```

### Graceful Handling

If no browser is open or screenshot capture fails:
- The keyword is still recorded
- No screenshot file is created
- No error is raised (silent skip)

---

## Full-Page Screenshots

Capture the entire scrollable page, not just the visible viewport.

### How It Works

- **Selenium (CDP)**: Uses `Page.captureScreenshot` with `captureBeyondViewport: true`
- **Browser Library**: Uses Playwright's `page.screenshot(full_page=True)`
- **Fallback**: If full-page capture fails, automatically falls back to viewport screenshot

### Configuration

```yaml
# trace-viewer.yml
screenshot_mode: full_page
```

Or via CLI:

```bash
robot --listener "trace_viewer.TraceListener:screenshot_mode=full_page" tests/
```

### Supported Browsers

| Browser | Full-Page Support |
|---------|-------------------|
| Chrome / Chromium | Yes (via CDP) |
| Edge | Yes (via CDP) |
| Firefox | Viewport only (no CDP) |
| Safari | Viewport only |

---

## On-Failure Ring Buffer

In `on_failure` mode, the listener stores captures in an in-memory ring buffer instead of writing to disk.

### How It Works

1. Keywords are captured to a `deque`-based ring buffer (configurable size)
2. Each capture stores: screenshot bytes, variables, console logs, DOM, network data
3. **Test PASSES**: Buffer is cleared, zero disk I/O
4. **Test FAILS**: Buffer is flushed to disk via TraceWriter

### Memory Usage

- Approximately ~100KB per keyword capture (viewport screenshot)
- Default buffer of 10 keywords = ~1MB memory
- Memory is released immediately on buffer clear/flush

### Configuration

```yaml
# trace-viewer.yml
capture_mode: on_failure
buffer_size: 15  # Keep last 15 keywords
```

### Use Cases

- CI/CD pipelines: Only save traces for debugging failed tests
- Performance: No disk I/O overhead for passing tests
- Storage: Significantly reduces trace storage in large test suites

---

## DOM Snapshots

DOM snapshots capture the HTML structure of the page at each keyword execution.

### How It Works

1. Page source is retrieved via `driver.page_source` (Selenium) or `Get Page Source` (Browser Library)
2. HTML is sanitized to remove potentially harmful content
3. Sanitized HTML is saved as `dom.html` in the keyword directory

### Sanitization

The following elements are removed for security:
- `<script>` tags (prevents JavaScript execution)
- Event handlers (`onclick`, `onload`, etc.)

The following are preserved:
- HTML structure
- Inline styles
- CSS classes
- Form values

### DOM Truncation

Large DOM snapshots are truncated to prevent excessive storage. Configure via:

```yaml
compression:
  max_dom_size_kb: 500  # Truncate DOMs larger than 500KB
```

When truncated, metadata includes `dom_truncated: true`.

---

## Network Request Capture

Network requests are captured using Chrome DevTools Protocol (CDP) for comprehensive HTTP monitoring.

### Supported Methods

| Library | Method | Notes |
|---------|--------|-------|
| SeleniumLibrary | CDP via `execute_cdp_cmd` | Chrome/Chromium/Edge |
| Browser Library | Playwright page events | All browsers |

### Browser Library Network Capture

When using Browser Library, network requests are captured natively via Playwright:

```python
page.on('request', handler)
page.on('response', handler)
```

This provides the same output format as CDP-based capture, with support for all Playwright-supported browsers.

### Captured Data

Each network request includes:

```json
{
  "requests": [
    {
      "request_id": "ABC123",
      "url": "https://api.example.com/data",
      "method": "GET",
      "resource_type": "XHR",
      "status": 200,
      "size": 1234,
      "duration_ms": 150,
      "mime_type": "application/json"
    }
  ]
}
```

---

## Console Logs Capture

Browser console logs are captured to help debug JavaScript issues.

### How It Works

1. Browser logs are retrieved via `driver.get_log('browser')` (Selenium)
2. Logs are filtered and formatted
3. Logs are saved as `console.json` in the keyword directory

### Log Levels

| Level | Description |
|-------|-------------|
| INFO | General information (`console.log`) |
| WARNING | Warnings (`console.warn`) |
| ERROR | Errors (`console.error`) |
| SEVERE | Critical errors and exceptions |

---

## Variable Tracking

Robot Framework variables are captured at each keyword execution with automatic sensitive data masking.

### How It Works

1. All RF variables are retrieved via BuiltIn library
2. Variables are categorized (scalar, list, dict)
3. Sensitive values are masked
4. Variables are saved as `variables.json`

### Sensitive Data Masking

Variables matching configured patterns are automatically masked as `***MASKED***`.

Default patterns: `password`, `secret`, `token`, `key`, `credential`, `auth`, `api_key`.

---

## Custom Masking Patterns

Configure your own sensitive data patterns beyond the defaults.

### Configuration

```yaml
# trace-viewer.yml
masking_patterns:
  - password
  - secret
  - token
  - key
  - credential
  - auth
  - api_key
  - ssn              # Social Security Number
  - credit_card      # Credit card data
  - bank_account     # Banking details
```

### How It Works

- Patterns are compiled as regex at listener startup (one-time cost)
- Matching is case-insensitive substring match on variable names
- Matched variable values are replaced with `***MASKED***`

---

## Search & Filter Viewer

The interactive HTML viewer includes search and filter capabilities.

### Features

- **Text search**: Filter keywords by name
- **Status filter**: Dropdown to show ALL / PASS / FAIL / SKIP keywords
- **Result counter**: Shows number of matching keywords

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `/` | Focus the search input |
| `Escape` | Clear search and filter |

### How It Works

Keywords are filtered in real-time using JavaScript, matching against `data-name`, `data-status`, and `data-search-text` attributes on each keyword item.

---

## Suite-Level Viewer

Generate an aggregate view of multiple test traces.

### CLI Usage

```bash
trace-viewer suite ./traces -o suite.html -O
```

### What It Shows

- **Stats bar**: Total tests, passed, failed, pass rate percentage
- **Test list sidebar**: Each test with name, status badge (green/red), and duration
- **Click-through**: Click any test to open its individual viewer

### Embedding vs Linking

- For up to 30 tests: Viewers are embedded for offline use
- For more than 30 tests: Links to individual viewers to keep file size manageable

### Programmatic Usage

```python
from trace_viewer.viewer.suite_generator import SuiteViewerGenerator

generator = SuiteViewerGenerator()
output_path = generator.generate(traces_dir, output_path=Path("suite.html"))
```

---

## Trace Comparison

Compare two traces to identify differences in test execution.

### CLI Usage

```bash
trace-viewer compare ./baseline/test_login ./current/test_login -o comparison.html
```

### Keyword States

| State | Description |
|-------|-------------|
| Matched | Same keyword name, same position |
| Modified | Same keyword name, different arguments or status |
| Added | Keyword exists only in trace 2 |
| Removed | Keyword exists only in trace 1 |

### Report Contents

- Summary statistics (total, matched, modified, added, removed)
- Side-by-side keyword comparison
- Variable differences highlighted
- Screenshot comparison (if available)

---

## Visual Diff

Pixel-level comparison of screenshots between two traces.

### CLI Usage

```bash
trace-viewer compare-visual ./baseline/test ./current/test -o diff.html -O
```

### How It Works

1. Screenshots from matching keywords are loaded as Pillow images
2. Pixel-by-pixel comparison with configurable threshold (default: 30 per channel)
3. Changed pixels are overlaid in red on a semi-transparent diff image
4. Similarity score calculated: `1.0 - (changed_pixels / total_pixels)`

### Output

For each keyword pair:

```python
{
    "keyword": "Click Button",
    "similarity": 0.87,
    "changed_pixels": 10400,
    "total_pixels": 80000,
    "diff_image": b"..."  # PNG bytes with red overlay
}
```

### HTML Report

Three-panel view for each keyword:
1. **Baseline**: Screenshot from trace 1
2. **Candidate**: Screenshot from trace 2
3. **Diff**: Red overlay showing changed pixels

### Requirements

Requires Pillow: `pip install robotframework-trace-viewer[media]`

---

## GIF Replay

Generate animated GIF or HTML slideshow from trace screenshots.

### CLI Usage

```bash
# Animated GIF
trace-viewer replay ./traces/login_test --format gif --fps 2 --width 800 -o replay.gif

# HTML slideshow
trace-viewer replay ./traces/login_test --format html -o replay.html
```

### GIF Generation

- Screenshots are loaded in keyword order
- Each frame is resized to `max_width` while maintaining aspect ratio
- FPS controls animation speed (default: 2)
- Output is a standard GIF file viewable in any browser or image viewer

### HTML Slideshow

- Self-contained HTML with embedded screenshots (base64)
- Play/Pause/Step controls
- Keyboard navigation (Space, arrows)
- Keyword name and metadata displayed below each frame

### Programmatic Usage

```python
from trace_viewer.media.gif_generator import generate_gif, generate_slideshow

# Generate GIF
gif_path = generate_gif(trace_dir, fps=3, max_width=1024)

# Generate HTML slideshow
html_path = generate_slideshow(trace_dir, output=Path("slideshow.html"))
```

### Requirements

GIF format requires Pillow: `pip install robotframework-trace-viewer[media]`

---

## Statistics Dashboard

Generate aggregated statistics across multiple traces.

### CLI Usage

```bash
trace-viewer stats ./traces -o dashboard.html -O
```

### Statistics Included

#### Summary
- Total tests
- Passed / Failed / Skipped counts
- Pass rate percentage

#### Duration Statistics
- Minimum, Maximum, Average, Median, P95

#### Slowest Tests
- Top 10 slowest tests with durations and links to viewers

#### Flaky Tests
- Tests with inconsistent results (same name, different outcomes)

---

## WebP Compression

Convert PNG screenshots to WebP format for significant storage savings.

### CLI Usage

```bash
trace-viewer compress ./traces --quality 80
```

### How It Works

1. Scans all `screenshot.png` files in trace directories
2. Converts each to WebP using Pillow
3. Removes original PNG after successful conversion
4. Reports total savings

### Typical Savings

| Quality | Size Reduction |
|---------|----------------|
| 90 | 50-60% |
| 80 | 60-70% |
| 70 | 70-80% |
| 60 | 75-85% |

### Viewer Compatibility

The HTML viewer includes fallback support:

```html
<img src="screenshot.webp" onerror="this.src='screenshot.png'">
```

### Requirements

Requires Pillow: `pip install robotframework-trace-viewer[media]`

---

## Trace Cleanup

Manage storage by removing old traces based on retention policy.

### CLI Usage

```bash
trace-viewer cleanup ./traces --days 30 --max-traces 100
```

### Policy Rules

1. **Age-based**: Delete traces with `start_time` older than `--days` days
2. **Count-based**: Keep only the `--max-traces` most recent traces

Both rules can be combined. Age-based deletion runs first, then count-based.

### Configuration

Set retention policy in config file for consistent behavior:

```yaml
retention:
  days: 30
  max_traces: 100
```

---

## PDF Export

Export a trace as a professional PDF report.

### CLI Usage

```bash
trace-viewer export-pdf ./traces/login_test -o report.pdf
```

### Report Structure

1. **Cover page**: Test name, suite, status, date, duration, tags
2. **Per-keyword pages**: Screenshot (resized to fit), arguments, variables, status
3. **Summary page**: Total keywords, pass/fail breakdown

### Options

| Option | Description |
|--------|-------------|
| `--screenshots-only` | Include only screenshots, skip variables and metadata |

### Requirements

Requires weasyprint: `pip install robotframework-trace-viewer[pdf]`

Note: weasyprint may require system libraries. See [weasyprint documentation](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation) for platform-specific installation.

---

## ZIP Export

Export traces as portable ZIP archives.

### CLI Usage

```bash
trace-viewer export ./traces/test_login_20250120 -o login_trace.zip
```

### Archive Contents

```
login_trace.zip
+-- manifest.json
+-- viewer.html
+-- keywords/
    +-- 001_open_browser/
    |   +-- metadata.json
    |   +-- screenshot.png
    |   +-- dom.html
    |   +-- network.json
    |   +-- console.json
    |   +-- variables.json
    +-- ...
```

---

## Pabot Support

Full support for parallel test execution with Pabot.

### How It Works

1. Pabot spawns multiple robot processes
2. Each process sets environment variables (`PABOTQUEUEINDEX`, etc.)
3. The trace listener detects these variables
4. Trace directory names include the worker ID suffix

### Trace Naming

| Execution Type | Directory Name |
|----------------|----------------|
| Standard robot | `test_login_20250120_143022` |
| Pabot worker 0 | `test_login_20250120_143022_pabot0` |
| Pabot worker 1 | `test_login_20250120_143022_pabot1` |

### Usage

```bash
pabot --processes 4 --listener trace_viewer.TraceListener:output_dir=./traces tests/
```

---

## Pabot Merge Timeline

Merge parallel traces from multiple Pabot workers into a unified timeline.

### CLI Usage

```bash
trace-viewer merge ./traces -o merged/
```

### How It Works

1. Scans trace directories for Pabot suffixes (`_pabot0`, `_pabot1`, etc.)
2. Parses manifest files to extract timing and worker information
3. Builds a chronological timeline sorted by `start_time`
4. Generates a Gantt-style HTML visualization

### Timeline View

The timeline shows:
- Horizontal swimlanes per worker (pabot0, pabot1, etc.)
- Test bars sized by duration
- Color coding: green (PASS), red (FAIL)
- Test names and durations on hover

### Programmatic Usage

```python
from trace_viewer.integrations.pabot_merger import PabotMerger

merger = PabotMerger(traces_dir)
traces = merger.scan_traces()
output_dir = merger.merge(output=Path("merged/"))
```
