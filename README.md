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
