<p align="center">
  <img src="https://raw.githubusercontent.com/thearchit3ct/robotframework-trace-viewer/main/docs/images/logo.webp" alt="Robot Framework Trace Viewer" width="200">
</p>

<h1 align="center">Robot Framework Trace Viewer</h1>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9%2B-blue.svg" alt="Python 3.9+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://robotframework.org/"><img src="https://img.shields.io/badge/Robot%20Framework-6.0%2B-green.svg" alt="Robot Framework"></a>
  <a href="https://pypi.org/project/robotframework-trace-viewer/"><img src="https://img.shields.io/badge/PyPI-0.2.0-orange.svg" alt="PyPI"></a>
</p>

<p align="center">
  Visual trace viewer for Robot Framework test debugging.<br>
  Capture screenshots, DOM snapshots, network requests, and console logs at each keyword execution.
</p>

## Features

### Core Capture
- **Screenshot Capture**: Automatically captures browser screenshots at each keyword execution
- **DOM Snapshots**: Captures sanitized HTML snapshots of the page state
- **Network Requests**: Records HTTP requests/responses via Chrome DevTools Protocol (CDP)
- **Console Logs**: Captures browser console logs (info, warning, error)
- **Variable Tracking**: Records Robot Framework variables with automatic masking of sensitive data

### Browser Support
- **SeleniumLibrary**: Full support for Selenium WebDriver
- **Browser Library**: Full support for Playwright-based Browser Library

### Analysis Tools
- **Interactive Timeline**: Browse test execution step by step with an intuitive HTML viewer
- **Trace Comparison**: Compare two traces to identify differences in keywords and variables
- **Statistics Dashboard**: Generate aggregated statistics across multiple traces
- **ZIP Export**: Export traces as portable ZIP archives

### Integrations
- **ReportPortal**: Upload traces to ReportPortal for centralized reporting
- **Pabot**: Full support for parallel test execution with Pabot

### Other
- **Offline Viewer**: Generated HTML works completely offline without external dependencies
- **Low Overhead**: Designed for minimal impact on test execution time

## Installation

```bash
pip install robotframework-trace-viewer
```

For development:

```bash
pip install robotframework-trace-viewer[dev]
```

For ReportPortal integration:

```bash
pip install robotframework-trace-viewer reportportal-client
```

## Quick Start

### 1. Run tests with the trace listener

```bash
robot --listener trace_viewer.TraceListener:output_dir=./traces tests/
```

### 2. Open the trace viewer

```bash
trace-viewer open ./traces/my_test_20250119_143022
```

The viewer will open in your default browser, showing a timeline of all keywords with their screenshots, DOM snapshots, network requests, and variables.

## Usage

### Listener Options

| Option | Default | Description |
|--------|---------|-------------|
| `output_dir` | `./traces` | Directory where traces are saved |
| `capture_mode` | `full` | Capture mode: `full`, `on_failure`, `none` |

Example with options:

```bash
robot --listener "trace_viewer.TraceListener:output_dir=./my_traces:capture_mode=full" tests/
```

### CLI Commands

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

Exports a trace directory as a portable ZIP archive containing the viewer and all captured data.

#### Compare two traces

```bash
trace-viewer compare <trace1_path> <trace2_path> -o comparison.html
```

Generates an HTML report comparing two traces, showing:
- Matched, modified, added, and removed keywords
- Variable differences between executions
- Side-by-side comparison view

#### Generate statistics dashboard

```bash
trace-viewer stats <traces_directory> -o dashboard.html
```

Generates an HTML dashboard with aggregated statistics:
- Pass/fail rates and trends
- Duration statistics (min, max, average, median)
- Slowest tests identification
- Flaky test detection

Options:
- `-o, --output`: Output path for the dashboard HTML
- `-O, --open`: Open dashboard in browser after generation

#### Export to ReportPortal

```bash
trace-viewer export-rp <traces_directory> \
  -e https://reportportal.example.com \
  -p my_project \
  -k your_api_key
```

Uploads traces to a ReportPortal server for centralized reporting.

Options:
- `-e, --endpoint`: ReportPortal server URL (or `RP_ENDPOINT` env var)
- `-p, --project`: ReportPortal project name (or `RP_PROJECT` env var)
- `-k, --api-key`: ReportPortal API key (or `RP_API_KEY` env var)
- `-n, --launch-name`: Custom name for the launch
- `--no-screenshots`: Skip uploading screenshots

## Configuration

### Sensitive Data Masking

Variables containing the following keywords are automatically masked:
- `password`
- `secret`
- `token`
- `key`
- `credential`
- `auth`

Example:
```robot
${PASSWORD}=    my_secret_password    # Will be masked as ***MASKED***
```

### Capture Modes

- **full**: Capture screenshot, DOM, network, console, and variables at every keyword (default)
- **on_failure**: Only capture when a test fails
- **none**: Disable screenshot capture, only track metadata

## Captured Data

Each keyword execution captures the following data:

| Data Type | File | Description |
|-----------|------|-------------|
| Metadata | `metadata.json` | Keyword name, library, arguments, status, duration |
| Screenshot | `screenshot.png` | Visual state of the browser |
| DOM Snapshot | `dom.html` | Sanitized HTML of the page |
| Network Requests | `network.json` | HTTP requests/responses captured via CDP |
| Console Logs | `console.json` | Browser console output (log, warn, error) |
| Variables | `variables.json` | Robot Framework variables snapshot |

### Network Capture

Network requests are captured using Chrome DevTools Protocol (CDP) and include:
- Request URL, method, and headers
- Response status, headers, and size
- Request timing and duration
- Resource type (Document, Script, XHR, Fetch, etc.)

**Supported browsers**: Chrome, Chromium, Edge (CDP-compatible browsers)

### Console Capture

Browser console logs are captured including:
- Log level (INFO, WARNING, ERROR)
- Message content
- Source and timestamp

## Examples

### Basic Usage

Run a simple test with trace capture:

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

Execute with trace capture enabled:

```bash
robot --listener trace_viewer.TraceListener:output_dir=./traces tests/login.robot
```

### Using Browser Library

The trace viewer also supports Playwright-based Browser Library:

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

### Comparing Test Executions

Compare a baseline trace with a new execution to identify regressions:

```bash
# Run baseline
robot --listener trace_viewer.TraceListener:output_dir=./baseline tests/

# Run new version
robot --listener trace_viewer.TraceListener:output_dir=./current tests/

# Compare traces
trace-viewer compare ./baseline/login_test_* ./current/login_test_* -o diff.html
```

### Generating Statistics

Generate a dashboard for all traces in a directory:

```bash
trace-viewer stats ./traces -o report.html -O
```

This generates and opens a dashboard showing:
- Total tests: 50
- Pass rate: 92%
- Average duration: 3.2s
- Slowest tests with details

### Parallel Execution with Pabot

The trace viewer fully supports parallel test execution with [Pabot](https://pabot.org/):

```bash
# Install Pabot
pip install robotframework-pabot

# Run tests in parallel with trace capture
pabot --listener trace_viewer.TraceListener:output_dir=./traces tests/
```

Trace directories automatically include a process identifier (`_pabot0`, `_pabot1`, etc.) to prevent conflicts.

### ReportPortal Integration

Upload traces to ReportPortal for team-wide visibility:

```bash
# Using command line options
trace-viewer export-rp ./traces \
  -e https://rp.example.com \
  -p robot_project \
  -k abc123-def456

# Using environment variables
export RP_ENDPOINT=https://rp.example.com
export RP_PROJECT=robot_project
export RP_API_KEY=abc123-def456
trace-viewer export-rp ./traces
```

ReportPortal mapping:
- **Launch**: Collection of trace exports
- **Test**: Individual test case
- **Step**: Keywords within the test

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
          pip install robotframework robotframework-trace-viewer selenium

      - name: Run tests with trace capture
        run: |
          robot --listener trace_viewer.TraceListener:output_dir=./traces tests/

      - name: Generate statistics dashboard
        if: always()
        run: |
          trace-viewer stats ./traces -o traces/dashboard.html

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
└── login_test_20250120_143022/
    ├── manifest.json          # Test metadata (name, status, duration)
    ├── viewer.html            # Interactive HTML viewer
    └── keywords/
        ├── 001_open_browser/
        │   ├── metadata.json  # Keyword name, args, status
        │   ├── screenshot.png # Browser state at keyword end
        │   ├── dom.html       # DOM snapshot
        │   ├── network.json   # Network requests
        │   ├── console.json   # Console logs
        │   └── variables.json # RF variables snapshot
        ├── 002_input_text/
        │   └── ...
        └── 003_click_button/
            └── ...
```

## Interactive Viewer

The HTML viewer provides keyboard navigation for efficient trace browsing:

| Keyboard Shortcut | Action |
|---|---|
| `↑` or `k` | Go to previous keyword |
| `↓` or `j` | Go to next keyword |
| `Home` | Jump to first keyword |
| `End` | Jump to last keyword |
| `Left Click` on keyword | Select and view details |

The viewer displays four panels:
1. **Screenshot**: Visual browser state
2. **Variables**: RF variables at execution time
3. **Console**: Browser console logs
4. **Network**: HTTP requests/responses

## Requirements

- Python 3.9+
- Robot Framework 6.0+ or 7.0+
- SeleniumLibrary 6.0+ or Browser Library 18.0+ (for browser capture)

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
