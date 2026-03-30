# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-03-30

### Added

#### Configuration & Masking (F8, F9)
- **Config File Support**: `trace-viewer.yml` configuration file
  - Auto-discovery: `./trace-viewer.yml` then `~/.trace-viewer.yml`
  - Full precedence chain: CLI args > env vars > config file > defaults
  - Environment variables: `TRACE_VIEWER_*` prefix for all settings
  - CLI command: `trace-viewer init` generates default config with comments
- **Custom Masking Patterns**: Configurable sensitive data patterns
  - Define patterns in `trace-viewer.yml` under `masking_patterns`
  - Patterns compiled as regex once at startup for performance
  - Default patterns: password, secret, token, key, credential, auth, api_key

#### Capture Enhancements (F1, F6, F10)
- **Ring Buffer On-Failure Mode**: Smart capture for CI efficiency
  - In `on_failure` mode, captures are stored in-memory ring buffer (~1MB for 10 keywords)
  - Passing tests: buffer cleared, zero disk I/O
  - Failing tests: buffer flushed to disk with full data
  - Configurable buffer size via `buffer_size` setting
- **Full-Page Screenshots**: Capture entire scrollable page
  - Selenium: CDP `Page.captureScreenshot` with `captureBeyondViewport`
  - Browser Library: Playwright `page.screenshot(full_page=True)`
  - Automatic fallback to viewport if full-page fails
  - Configurable via `screenshot_mode: full_page`
- **Browser Library Network Capture**: Native Playwright network monitoring
  - Captures requests/responses via Playwright page events
  - Same output format as CDP-based capture
  - Automatic detection of Browser Library

#### Viewer Enhancements (F5, F4)
- **Search & Filter in Viewer**: Find keywords quickly
  - Text search input above keyword list
  - Status dropdown filter: ALL / PASS / FAIL / SKIP
  - Keyboard shortcuts: `/` to focus search, `Escape` to clear
  - Result counter display
- **Suite-Level Summary Viewer**: Aggregate view of multiple tests
  - Stats bar: total, passed, failed counts with pass rate
  - Sidebar with test list (name, status, duration)
  - Click-through to individual test viewers
  - CLI command: `trace-viewer suite <traces_dir>`

#### Media & Comparison (F2, F3)
- **GIF Replay**: Animate trace screenshots
  - `generate_gif()`: Creates animated GIF from screenshots
  - `generate_slideshow()`: HTML with play/pause/step controls
  - Configurable FPS and max width
  - CLI command: `trace-viewer replay <trace> [--format gif|html]`
  - Requires: `pip install robotframework-trace-viewer[media]`
- **Visual Diff**: Pixel-level screenshot comparison
  - Pixel-by-pixel comparison via Pillow (no OpenCV dependency)
  - Red overlay on changed pixels with configurable threshold
  - Similarity score (0.0 - 1.0) and changed pixel count
  - HTML report: 3 panels (Baseline, Candidate, Diff) with slider
  - CLI command: `trace-viewer compare-visual <trace1> <trace2>`
  - Requires: `pip install robotframework-trace-viewer[media]`

#### Storage & Compression (F7)
- **WebP Compression**: Significant storage savings
  - PNG to WebP conversion: 60-80% size reduction
  - Configurable quality (1-100)
  - Viewer fallback: `<img onerror>` for backward compatibility
  - CLI command: `trace-viewer compress <dir> [--quality 80]`
  - Requires: `pip install robotframework-trace-viewer[media]`
- **Trace Cleanup**: Retention policy enforcement
  - Delete traces older than N days
  - Cap total number of traces
  - CLI command: `trace-viewer cleanup <dir> [--days 30] [--max-traces 100]`
- **DOM Truncation**: Configurable `max_dom_size_kb` to limit snapshot size

#### Export & Integrations (F11, F12, F13)
- **PDF Export**: Professional trace reports
  - Cover page with test info, status, date
  - One page per keyword with screenshot, args, variables
  - Option `--screenshots-only` for compact reports
  - CLI command: `trace-viewer export-pdf <trace> [-o report.pdf]`
  - Requires: `pip install robotframework-trace-viewer[pdf]`
- **Pabot Merge**: Unified timeline for parallel traces
  - Scans Pabot worker directories (`_pabot0`, `_pabot1`, etc.)
  - Generates Gantt-style timeline HTML with swimlanes per worker
  - Chronological ordering by start time
  - CLI command: `trace-viewer merge <traces_dir> [-o merged/]`
- **CI/CD Publishing**: Platform-specific output generation
  - **Jenkins**: `index.html` compatible with HTML Publisher Plugin
  - **GitLab**: `trace-summary.md` for merge request comments
  - CI mode flag for listener: `ci_mode: true` in config
  - CLI command: `trace-viewer publish <dir> [--format jenkins|gitlab]`

### Changed
- Listener `__init__` now accepts `screenshot_mode`, `buffer_size`, and `config` parameters
- Viewer HTML now includes search bar and status filter dropdown
- Dependencies: added `pyyaml>=6.0` as required dependency

### New CLI Commands
- `trace-viewer init` - Generate default config file
- `trace-viewer suite` - Generate suite-level summary viewer
- `trace-viewer replay` - Generate GIF or HTML slideshow
- `trace-viewer compare-visual` - Pixel-level screenshot comparison
- `trace-viewer compress` - Convert PNG screenshots to WebP
- `trace-viewer cleanup` - Remove old traces by retention policy
- `trace-viewer export-pdf` - Export trace as PDF report
- `trace-viewer merge` - Merge Pabot parallel traces
- `trace-viewer publish` - Publish for Jenkins or GitLab

### New Optional Dependencies
- `Pillow>=9.0` (extra: `media`) - GIF, visual diff, WebP compression
- `weasyprint>=60.0` (extra: `pdf`) - PDF export

## [0.2.0] - 2025-01-20

### Added

#### Core Capture Features
- **DOM Capture**: Capture sanitized HTML snapshots of page state at each keyword
  - Automatic script tag removal for security
  - Inline style preservation
  - Compact HTML output
- **Console Logs Capture**: Record browser console output
  - Captures log, warn, and error levels
  - Includes source and timestamp
  - Works with SeleniumLibrary's `get_log('browser')`
- **Network Request Capture**: Record HTTP requests/responses via Chrome DevTools Protocol
  - Request URL, method, headers
  - Response status, headers, size
  - Timing and duration metrics
  - Supports Chrome, Chromium, Edge browsers

#### Browser Support
- **Browser Library Support**: Full integration with Playwright-based Browser Library
  - Screenshot capture via `Take Screenshot`
  - Page content capture via `Get Page Source`
  - Automatic browser detection

#### Analysis Tools
- **Trace Comparison**: Compare two traces to identify differences
  - Keyword alignment with match/modified/added/removed states
  - Variable diff highlighting
  - HTML comparison report generation
  - CLI command: `trace-viewer compare <trace1> <trace2>`
- **Statistics Dashboard**: Generate aggregated statistics across traces
  - Pass/fail rates and trends
  - Duration statistics (min, max, avg, median, p95)
  - Slowest tests identification
  - Flaky test detection
  - HTML dashboard with charts
  - CLI command: `trace-viewer stats <traces_dir>`
- **ZIP Export**: Export traces as portable archives
  - Includes viewer and all captured data
  - CLI command: `trace-viewer export <trace> -o archive.zip`

#### Integrations
- **ReportPortal Integration**: Upload traces to ReportPortal
  - Launch/Test/Step hierarchy mapping
  - Screenshot attachments
  - Attribute and tag support
  - Environment variable configuration
  - CLI command: `trace-viewer export-rp`
- **Pabot Support**: Full parallel execution support
  - Automatic worker ID detection via environment variables
  - Unique trace directory naming (`_pabot0`, `_pabot1`, etc.)
  - No trace file conflicts in parallel runs

#### Viewer Enhancements
- **Network Panel**: Display captured network requests in viewer
  - Request method, URL, status
  - Response size and duration
  - Expandable request/response details
- **Console Panel**: Display browser console logs in viewer
  - Color-coded log levels
  - Timestamp display

### Changed
- Viewer HTML now includes four panels: Screenshot, Variables, Console, Network
- Trace directory structure now includes `dom.html`, `console.json`, `network.json`

### Fixed
- mypy type errors in comparator.py with proper cast usage
- mypy type errors in stats dashboard with type: ignore comments

## [0.1.3] - 2025-01-20

### Fixed
- Logo now displays correctly on PyPI (use absolute GitHub URL)

## [0.1.2] - 2025-01-20

### Fixed
- Screenshots now display correctly in the viewer
- ViewerGenerator now properly resolves screenshot paths from keyword metadata

## [0.1.1] - 2025-01-20

### Fixed
- Viewer HTML is now generated per-test in `end_test` instead of `end_suite`
- Each test trace now includes its own `viewer.html` file

## [0.1.0] - 2025-01-20

### Added
- Initial release of robotframework-trace-viewer
- TraceListener: Robot Framework Listener API v3 implementation
  - Captures test execution at keyword level
  - Supports capture modes: full, on_failure, disabled
- Screenshot capture via Selenium WebDriver
  - Automatic detection of SeleniumLibrary
  - Graceful handling when no browser is open
- Variable capture with automatic sensitive data masking
  - Masks variables containing: password, secret, token, key, credential, auth, api_key
  - Supports scalar, list, and dict variable types
- Structured trace storage
  - JSON manifest with test metadata
  - Per-keyword directories with metadata, variables, and screenshots
  - Atomic file writes for data integrity
- Interactive HTML viewer
  - Keyboard navigation (arrow keys, j/k, Home/End)
  - Sidebar with keyword list
  - Screenshot display with zoom
  - Variable and metadata panels
  - Works completely offline
- CLI commands
  - `trace-viewer open <path>` - Open trace in browser
  - `trace-viewer list <dir>` - List available traces
  - `trace-viewer info <path>` - Display trace details
- Comprehensive test suite
  - Unit tests for all modules
  - Integration tests for full flow
- CI/CD pipeline
  - GitHub Actions for testing on Python 3.9-3.12
  - Automated publishing to TestPyPI and PyPI

### Compatibility
- Python 3.9, 3.10, 3.11, 3.12
- Robot Framework 6.0+, 7.0+
- SeleniumLibrary 6.0+

[Unreleased]: https://github.com/thearchit3ct/robotframework-trace-viewer/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/thearchit3ct/robotframework-trace-viewer/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/thearchit3ct/robotframework-trace-viewer/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/thearchit3ct/robotframework-trace-viewer/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/thearchit3ct/robotframework-trace-viewer/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/thearchit3ct/robotframework-trace-viewer/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/thearchit3ct/robotframework-trace-viewer/releases/tag/v0.1.0
