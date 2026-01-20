# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/thearchit3ct/robotframework-trace-viewer/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/thearchit3ct/robotframework-trace-viewer/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/thearchit3ct/robotframework-trace-viewer/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/thearchit3ct/robotframework-trace-viewer/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/thearchit3ct/robotframework-trace-viewer/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/thearchit3ct/robotframework-trace-viewer/releases/tag/v0.1.0
