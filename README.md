<p align="center">
  <img src="https://raw.githubusercontent.com/thearchit3ct/robotframework-trace-viewer/main/docs/images/logo.webp" alt="Robot Framework Trace Viewer" width="200">
</p>

<h1 align="center">Robot Framework Trace Viewer</h1>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9%2B-blue.svg" alt="Python 3.9+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://robotframework.org/"><img src="https://img.shields.io/badge/Robot%20Framework-6.0%2B-green.svg" alt="Robot Framework"></a>
  <a href="https://pypi.org/project/robotframework-trace-viewer/"><img src="https://img.shields.io/badge/PyPI-0.3.0-orange.svg" alt="PyPI"></a>
</p>

<p align="center">
  Visual trace viewer for Robot Framework test debugging.<br>
  Capture screenshots, DOM snapshots, network requests, and console logs at each keyword execution.
</p>

## Features

### Core Capture
- **Screenshot Capture**: Automatically captures browser screenshots at each keyword execution
- **Full-Page Screenshots**: Capture the entire page beyond the viewport (CDP & Playwright)
- **DOM Snapshots**: Captures sanitized HTML snapshots of the page state
- **Network Requests**: Records HTTP requests/responses via Chrome DevTools Protocol (CDP)
- **Browser Library Network**: Native Playwright network capture via Browser Library
- **Console Logs**: Captures browser console logs (info, warning, error)
- **Variable Tracking**: Records Robot Framework variables with automatic masking of sensitive data
- **Custom Masking Patterns**: Configure your own sensitive data patterns via config file

### Capture Modes
- **Full Mode**: Capture everything at every keyword (default)
- **On-Failure Mode**: Ring buffer keeps last N keywords in memory, flushes to disk only when a test fails (zero disk I/O for passing tests)
- **Disabled Mode**: No screenshot capture, only metadata tracking

### Configuration
- **Config File**: `trace-viewer.yml` with auto-discovery (project root or home directory)
- **Precedence Chain**: CLI args > environment variables > config file > defaults
- **Environment Variables**: All settings configurable via `TRACE_VIEWER_*` env vars

### Browser Support
- **SeleniumLibrary**: Full support for Selenium WebDriver
- **Browser Library**: Full support for Playwright-based Browser Library

### Analysis Tools
- **Interactive Timeline**: Browse test execution step by step with an intuitive HTML viewer
- **Search & Filter**: Search keywords by name and filter by status (PASS/FAIL/SKIP) in the viewer
- **Trace Comparison**: Compare two traces to identify differences in keywords and variables
- **Visual Diff**: Pixel-level screenshot comparison with diff overlay and similarity score
- **Suite Viewer**: Aggregate view of multiple test traces with pass/fail statistics
- **Statistics Dashboard**: Generate aggregated statistics across multiple traces
- **GIF Replay**: Generate animated GIF or HTML slideshow from trace screenshots
- **PDF Export**: Export traces as professional PDF reports (via weasyprint)
- **ZIP Export**: Export traces as portable ZIP archives

### Integrations
- **ReportPortal**: Upload traces to ReportPortal for centralized reporting
- **Pabot**: Full support for parallel test execution with Pabot
- **Pabot Merge**: Merge parallel traces into a unified Gantt-style timeline
- **Jenkins Publishing**: Generate `index.html` compatible with HTML Publisher Plugin
- **GitLab Publishing**: Generate `trace-summary.md` for merge request comments
- **CI Mode**: `--ci` flag enables on_failure capture + CI-friendly output

### Storage & Compression
- **WebP Compression**: Convert PNG screenshots to WebP (60-80% size reduction)
- **Trace Cleanup**: Automatic retention policy (configurable days + max traces)
- **DOM Truncation**: Large DOM snapshots truncated to configurable limit

### Other
- **Offline Viewer**: Generated HTML works completely offline without external dependencies
- **Low Overhead**: Designed for minimal impact on test execution time

## Installation

```bash
pip install robotframework-trace-viewer
```

With media support (GIF generation, visual diff):

```bash
pip install robotframework-trace-viewer[media]
```

With PDF export:

```bash
pip install robotframework-trace-viewer[pdf]
```

With all optional dependencies:

```bash
pip install robotframework-trace-viewer[all]
```

For development:

```bash
pip install robotframework-trace-viewer[dev]
```

## Quick Start

### 1. Generate a configuration file (optional)

```bash
trace-viewer init
```

This creates a `trace-viewer.yml` with documented defaults.

### 2. Run tests with the trace listener

```bash
robot --listener trace_viewer.TraceListener:output_dir=./traces tests/
```

### 3. Open the trace viewer

```bash
trace-viewer open ./traces/my_test_20250119_143022
```

The viewer will open in your default browser, showing a timeline of all keywords with their screenshots, DOM snapshots, network requests, and variables.

## Usage

### Listener Options

| Option | Default | Description |
|--------|---------|-------------|
| `output_dir` | `./traces` | Directory where traces are saved |
| `capture_mode` | `full` | Capture mode: `full`, `on_failure`, `disabled` |
| `screenshot_mode` | `viewport` | Screenshot mode: `viewport`, `full_page` |
| `buffer_size` | `10` | Ring buffer size for `on_failure` mode |
| `config` | auto-discover | Path to `trace-viewer.yml` config file |

Example with options:

```bash
robot --listener "trace_viewer.TraceListener:output_dir=./my_traces:capture_mode=full" tests/

# On-failure mode: only saves traces for failing tests
robot --listener "trace_viewer.TraceListener:capture_mode=on_failure:buffer_size=15" tests/

# Full-page screenshots
robot --listener "trace_viewer.TraceListener:screenshot_mode=full_page" tests/
```

### Configuration File

Create a `trace-viewer.yml` in your project root:

```yaml
# Output directory for traces
output_dir: traces

# Capture mode: full | on_failure | disabled
capture_mode: full

# Screenshot mode: viewport | full_page
screenshot_mode: viewport

# Ring buffer size for on_failure mode
buffer_size: 10

# Patterns to mask in captured variables
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
  days: 30
  max_traces: 100

# CI/CD mode
ci_mode: false
```

Override any setting with environment variables:

```bash
export TRACE_VIEWER_CAPTURE_MODE=on_failure
export TRACE_VIEWER_BUFFER_SIZE=20
export TRACE_VIEWER_CI_MODE=true
```

### CLI Commands

#### Initialize config

```bash
trace-viewer init [--output path]
```

Generates a default `trace-viewer.yml` configuration file.

#### Open a trace

```bash
trace-viewer open <trace_path>
```

Opens the trace viewer in your default browser.

#### List available traces

```bash
trace-viewer list <traces_directory>
```

Lists all traces in the specified directory with summary information.

#### Show trace info

```bash
trace-viewer info <trace_path>
```

Displays detailed information about a specific trace.

#### Export trace as ZIP

```bash
trace-viewer export <trace_path> -o archive.zip
```

#### Compare two traces

```bash
trace-viewer compare <trace1_path> <trace2_path> -o comparison.html
```

#### Visual diff (pixel comparison)

```bash
trace-viewer compare-visual <trace1_path> <trace2_path> -o diff_report.html
```

Generates a report with side-by-side screenshots, diff overlay, and similarity scores.

#### Generate statistics dashboard

```bash
trace-viewer stats <traces_directory> -o dashboard.html -O
```

#### Generate suite viewer

```bash
trace-viewer suite <traces_directory> -o suite.html -O
```

Generates an aggregate view with pass/fail statistics and links to individual traces.

#### Generate GIF/slideshow replay

```bash
# Animated GIF
trace-viewer replay <trace_dir> --format gif --fps 2 --width 800

# HTML slideshow with play/pause controls
trace-viewer replay <trace_dir> --format html
```

#### Compress screenshots (PNG to WebP)

```bash
trace-viewer compress <traces_directory> --quality 80
```

#### Clean up old traces

```bash
trace-viewer cleanup <traces_directory> --days 30 --max-traces 100
```

#### Export to PDF

```bash
trace-viewer export-pdf <trace_dir> -o report.pdf [--screenshots-only]
```

Requires `weasyprint`: `pip install robotframework-trace-viewer[pdf]`

#### Merge Pabot parallel traces

```bash
trace-viewer merge <traces_directory> -o merged/
```

Generates a unified Gantt-style timeline across all Pabot workers.

#### Publish for CI/CD

```bash
# Jenkins (HTML Publisher compatible)
trace-viewer publish <traces_directory> --format jenkins -o trace-reports/

# GitLab (Markdown for MR comments)
trace-viewer publish <traces_directory> --format gitlab -o trace-reports/
```

#### Export to ReportPortal

```bash
trace-viewer export-rp <traces_directory> \
  -e https://reportportal.example.com \
  -p my_project \
  -k your_api_key
```

## Captured Data

Each keyword execution captures the following data:

| Data Type | File | Description |
|-----------|------|-------------|
| Metadata | `metadata.json` | Keyword name, library, arguments, status, duration |
| Screenshot | `screenshot.png` / `screenshot.webp` | Visual state of the browser |
| DOM Snapshot | `dom.html` | Sanitized HTML of the page |
| Network Requests | `network.json` | HTTP requests/responses captured via CDP |
| Console Logs | `console.json` | Browser console output (log, warn, error) |
| Variables | `variables.json` | Robot Framework variables snapshot |

## Examples

### Basic Usage

```robot
*** Settings ***
Library    SeleniumLibrary

*** Test Cases ***
Login Test
    Open Browser    https://example.com    chrome
    Input Text    id=username    testuser
    Input Password    id=password    secret123
    Click Button    id=login
    Page Should Contain    Welcome
    [Teardown]    Close Browser
```

```bash
robot --listener trace_viewer.TraceListener:output_dir=./traces tests/login.robot
```

### On-Failure Mode (CI optimized)

Only capture traces when tests fail — ideal for CI where you only need debugging data for failures:

```bash
robot --listener "trace_viewer.TraceListener:capture_mode=on_failure:buffer_size=10" tests/
```

The ring buffer keeps the last 10 keywords in memory. If a test passes, the buffer is discarded (zero disk I/O). If a test fails, the buffer is flushed to disk with full screenshots and data.

### Full-Page Screenshots

Capture the entire scrollable page, not just the viewport:

```bash
robot --listener "trace_viewer.TraceListener:screenshot_mode=full_page" tests/
```

### Using Browser Library

```robot
*** Settings ***
Library    Browser

*** Test Cases ***
Login Test With Playwright
    New Browser    chromium    headless=false
    New Page    https://example.com
    Fill Text    id=username    testuser
    Fill Text    id=password    secret123
    Click    id=login
    Get Text    body    contains    Welcome
    [Teardown]    Close Browser
```

### Parallel Execution with Pabot

```bash
# Run tests in parallel with trace capture
pabot --processes 4 --listener trace_viewer.TraceListener:output_dir=./traces tests/

# Merge parallel traces into timeline
trace-viewer merge ./traces -o merged/
```

### Complete CI Pipeline

```bash
# 1. Run tests with on_failure mode
robot --listener "trace_viewer.TraceListener:capture_mode=on_failure" tests/

# 2. Compress screenshots for storage efficiency
trace-viewer compress ./traces --quality 80

# 3. Generate suite summary
trace-viewer suite ./traces -o traces/suite.html

# 4. Publish for Jenkins
trace-viewer publish ./traces --format jenkins -o trace-reports/

# 5. Clean up old traces
trace-viewer cleanup ./traces --days 30
```

### CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: Tests with Traces

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install robotframework robotframework-trace-viewer[media] selenium

      - name: Run tests with trace capture
        run: |
          robot --listener "trace_viewer.TraceListener:capture_mode=on_failure" tests/

      - name: Generate reports
        if: always()
        run: |
          trace-viewer compress ./traces --quality 80
          trace-viewer suite ./traces -o traces/suite.html
          trace-viewer publish ./traces --format jenkins -o trace-reports/

      - name: Upload traces as artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-traces
          path: traces/
```

## Trace Directory Structure

```
traces/
+-- login_test_20250120_143022/
|   +-- manifest.json          # Test metadata (name, status, duration)
|   +-- viewer.html            # Interactive HTML viewer
|   +-- keywords/
|       +-- 001_open_browser/
|       |   +-- metadata.json  # Keyword name, args, status
|       |   +-- screenshot.png # Browser state at keyword end
|       |   +-- dom.html       # DOM snapshot
|       |   +-- network.json   # Network requests
|       |   +-- console.json   # Console logs
|       |   +-- variables.json # RF variables snapshot
|       +-- 002_input_text/
|       |   +-- ...
|       +-- 003_click_button/
|           +-- ...
```

## Interactive Viewer

The HTML viewer provides keyboard navigation and search:

| Keyboard Shortcut | Action |
|---|---|
| `Arrow Up` or `k` | Go to previous keyword |
| `Arrow Down` or `j` | Go to next keyword |
| `Home` | Jump to first keyword |
| `End` | Jump to last keyword |
| `/` | Focus search bar |
| `Escape` | Clear search |

The viewer displays four panels:
1. **Screenshot**: Visual browser state
2. **Variables**: RF variables at execution time
3. **Console**: Browser console logs
4. **Network**: HTTP requests/responses

Search and filter by keyword name or status (ALL/PASS/FAIL/SKIP) at the top of the keyword list.

## Requirements

- Python 3.9+
- Robot Framework 6.0+ or 7.0+
- SeleniumLibrary 6.0+ or Browser Library 18.0+ (for browser capture)

### Optional Dependencies

| Extra | Package | Purpose |
|-------|---------|---------|
| `media` | Pillow >= 9.0 | GIF generation, visual diff, WebP compression |
| `pdf` | weasyprint >= 60.0 | PDF export |
| `all` | Both above | All optional features |

## Development

### Setup

```bash
git clone https://github.com/thearchit3ct/robotframework-trace-viewer.git
cd robotframework-trace-viewer
pip install -e ".[dev]"
```

### Run tests

```bash
pytest tests/
```

### Code formatting

```bash
black src/ tests/ --line-length=100
ruff check src/ tests/
mypy src/
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) before submitting pull requests.

## Acknowledgments

Inspired by [Playwright Trace Viewer](https://playwright.dev/docs/trace-viewer).
