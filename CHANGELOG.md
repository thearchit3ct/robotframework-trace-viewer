# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/thearchit3ct/robotframework-trace-viewer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/thearchit3ct/robotframework-trace-viewer/releases/tag/v0.1.0
