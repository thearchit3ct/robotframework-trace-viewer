<p align="center">
  <img src="docs/images/logo.webp" alt="Robot Framework Trace Viewer" width="200">
</p>

<h1 align="center">Robot Framework Trace Viewer</h1>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9%2B-blue.svg" alt="Python 3.9+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://robotframework.org/"><img src="https://img.shields.io/badge/Robot%20Framework-6.0%2B-green.svg" alt="Robot Framework"></a>
  <a href="https://test.pypi.org/project/robotframework-trace-viewer/"><img src="https://img.shields.io/badge/TestPyPI-0.1.0-orange.svg" alt="TestPyPI"></a>
</p>

<p align="center">
  Visual trace viewer for Robot Framework test debugging.<br>
  Capture screenshots and variables at each keyword execution and browse them in an interactive HTML viewer.
</p>

## Features

- **Screenshot Capture**: Automatically captures browser screenshots at each keyword execution
- **Variable Tracking**: Records Robot Framework variables with automatic masking of sensitive data
- **Interactive Timeline**: Browse test execution step by step with an intuitive HTML viewer
- **Offline Viewer**: Generated HTML works completely offline without external dependencies
- **Selenium Integration**: Works seamlessly with SeleniumLibrary
- **Low Overhead**: Designed for minimal impact on test execution time

## Installation

```bash
pip install robotframework-trace-viewer
```

For development:

```bash
pip install robotframework-trace-viewer[dev]
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

The viewer will open in your default browser, showing a timeline of all keywords with their screenshots and variables.

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

## Configuration

### Sensitive Data Masking

Variables containing the following keywords are automatically masked:
- `password`
- `secret`
- `token`
- `key`

Example:
```robot
${PASSWORD}=    my_secret_password    # Will be masked as ***MASKED***
```

### Capture Modes

- **full**: Capture screenshot and variables at every keyword (default)
- **on_failure**: Only capture when a test fails
- **none**: Disable screenshot capture, only track metadata

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

### Advanced Capture Modes

Capture everything during test execution:

```bash
robot --listener "trace_viewer.TraceListener:capture_mode=full:output_dir=./traces" tests/
```

Capture only when tests fail (useful for large test suites):

```bash
robot --listener "trace_viewer.TraceListener:capture_mode=on_failure:output_dir=./traces" tests/
```

Disable screenshot capture but keep metadata:

```bash
robot --listener "trace_viewer.TraceListener:capture_mode=none:output_dir=./traces" tests/
```

### Viewing Traces

List all captured traces with summary information:

```bash
trace-viewer list ./traces
```

Output example:
```
Found 3 trace(s):
  [PASS] Login Test
      Path: ./traces/login_test_20250120_143022
      Duration: 2500ms
  [FAIL] Checkout Test
      Path: ./traces/checkout_test_20250120_143045
      Duration: 5200ms
  [PASS] Search Test
      Path: ./traces/search_test_20250120_143100
      Duration: 1800ms
```

Open a specific trace in the viewer:

```bash
trace-viewer open ./traces/login_test_20250120_143022
```

Get detailed information about a trace:

```bash
trace-viewer info ./traces/login_test_20250120_143022
```

### Trace Directory Structure

Understanding the generated trace structure:

```
traces/
└── login_test_20250120_143022/
    ├── manifest.json          # Test metadata (name, status, duration)
    ├── viewer.html            # Interactive HTML viewer
    └── keywords/
        ├── 001_open_browser/
        │   ├── metadata.json  # Keyword name, args, status
        │   ├── screenshot.png # Browser state at keyword end
        │   └── variables.json # RF variables snapshot
        ├── 002_input_text/
        │   ├── metadata.json
        │   ├── screenshot.png
        │   └── variables.json
        ├── 003_input_password/
        │   └── ...
        └── 004_click_button/
            └── ...
```

Each keyword directory contains:
- **metadata.json**: Keyword execution details (name, library, arguments, status, duration)
- **screenshot.png**: Visual state of the browser at the end of keyword execution
- **variables.json**: All Robot Framework variables available at that point (with sensitive data masked)

### Sensitive Data Masking Examples

Variables are automatically masked based on their names:

```robot
*** Variables ***
${USERNAME}           admin_user         # Not masked (safe)
${PASSWORD}           secret123          # Masked as ***MASKED***
${API_KEY}            abcd1234efgh5678   # Masked as ***MASKED***
${SECRET_TOKEN}       xyz789abc          # Masked as ***MASKED***
${DATABASE_URL}       localhost:5432     # Not masked

*** Test Cases ***
API Test
    ${RESPONSE}=    Get Request    ${API_KEY}    /endpoint
    Log    ${RESPONSE}          # Masked in trace
```

In the viewer, sensitive variables will display as `***MASKED***` while others show their full values.

### Integration with CI/CD

Example GitHub Actions workflow:

```yaml
name: Tests with Traces

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install robotframework robotframework-trace-viewer selenium

      - name: Run tests with trace capture
        run: |
          robot --listener trace_viewer.TraceListener:output_dir=./traces tests/

      - name: Upload traces as artifacts
        if: always()
        uses: actions/upload-artifact@v2
        with:
          name: test-traces
          path: traces/
```

### Interactive Viewer Navigation

The HTML viewer provides keyboard navigation for efficient trace browsing:

| Keyboard Shortcut | Action |
|---|---|
| `↑` or `k` | Go to previous keyword |
| `↓` or `j` | Go to next keyword |
| `Home` | Jump to first keyword |
| `End` | Jump to last keyword |
| `Left Click` on keyword | Select and view details |

Use these shortcuts to quickly navigate through test execution steps and review screenshots and variables.

## Project Structure

```
traces/
  my_test_20250119_143022/
    manifest.json           # Test metadata
    viewer.html             # Interactive viewer
    keywords/
      001_open_browser/
        screenshot.png      # Browser state
        variables.json      # RF variables
        metadata.json       # Keyword info
      002_go_to/
        ...
```

## Requirements

- Python 3.9+
- Robot Framework 6.0+ or 7.0+
- SeleniumLibrary 6.0+ (for screenshot capture)

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

Contributions are welcome! Please read our contributing guidelines before submitting pull requests.

## Acknowledgments

Inspired by [Playwright Trace Viewer](https://playwright.dev/docs/trace-viewer).
