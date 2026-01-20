# CLI Reference

Complete reference for the `trace-viewer` command-line interface.

## Installation

The CLI is installed automatically with the package:

```bash
pip install robotframework-trace-viewer
```

## Global Help

```bash
trace-viewer --help
```

```
Usage: trace-viewer [OPTIONS] COMMAND [ARGS]...

  Robot Framework Trace Viewer CLI

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  compare    Compare two traces and generate a diff report.
  export     Export a trace directory as a ZIP archive.
  export-rp  Export traces to ReportPortal.
  info       Display detailed information about a trace.
  list       List all traces in a directory.
  open       Open a trace in the default browser.
  stats      Generate statistics dashboard for traces.
```

---

## Commands

### open

Open a trace in the default browser.

```bash
trace-viewer open <trace_path>
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `trace_path` | Yes | Path to the trace directory |

#### Examples

```bash
# Open a specific trace
trace-viewer open ./traces/login_test_20250120_143022

# Open with full path
trace-viewer open /home/user/project/traces/test_checkout_20250120
```

#### Behavior

1. Validates the trace directory exists
2. Checks for `viewer.html` in the directory
3. Opens the viewer in the default system browser

---

### list

List all traces in a directory with summary information.

```bash
trace-viewer list [traces_directory]
```

#### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `traces_directory` | No | `./traces` | Directory containing traces |

#### Examples

```bash
# List traces in default directory
trace-viewer list

# List traces in specific directory
trace-viewer list ./my_traces

# List traces with absolute path
trace-viewer list /home/user/project/traces
```

#### Output Format

```
Found 3 trace(s):
  [PASS] Login Test
      Path: ./traces/login_test_20250120_143022
      Duration: 2500ms
      Keywords: 12
  [FAIL] Checkout Test
      Path: ./traces/checkout_test_20250120_143045
      Duration: 5200ms
      Keywords: 24
      Error: Element not found: id=submit
  [PASS] Search Test
      Path: ./traces/search_test_20250120_143100
      Duration: 1800ms
      Keywords: 8
```

---

### info

Display detailed information about a specific trace.

```bash
trace-viewer info <trace_path>
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `trace_path` | Yes | Path to the trace directory |

#### Examples

```bash
trace-viewer info ./traces/login_test_20250120_143022
```

#### Output Format

```
Trace Information
=================
Test Name: Login Test
Full Name: Tests.Login.Login Test
Suite: Login
Status: PASS

Timing
------
Start: 2025-01-20 14:30:22
End: 2025-01-20 14:30:24
Duration: 2500ms

Capture
-------
Keywords: 12
Screenshots: 12
DOM Snapshots: 12
Network Requests: 45
Console Logs: 3

Tags
----
- smoke
- login

Path: ./traces/login_test_20250120_143022
```

---

### export

Export a trace directory as a portable ZIP archive.

```bash
trace-viewer export <trace_path> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `trace_path` | Yes | Path to the trace directory |

#### Options

| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--output` | `-o` | No | `<trace_name>.zip` | Output path for ZIP archive |

#### Examples

```bash
# Export with auto-generated name
trace-viewer export ./traces/login_test_20250120_143022

# Export with custom name
trace-viewer export ./traces/login_test_20250120_143022 -o login_trace.zip

# Export to specific directory
trace-viewer export ./traces/login_test_20250120_143022 -o /tmp/archives/trace.zip
```

#### Output

```
Trace exported to: login_trace.zip
Archive size: 1,234,567 bytes
```

---

### compare

Compare two traces and generate a diff report.

```bash
trace-viewer compare <trace1_path> <trace2_path> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `trace1_path` | Yes | Path to the first (baseline) trace |
| `trace2_path` | Yes | Path to the second (current) trace |

#### Options

| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--output` | `-o` | No | `comparison.html` | Output path for comparison HTML |

#### Examples

```bash
# Compare two traces
trace-viewer compare ./baseline/test_login_* ./current/test_login_*

# Compare with custom output
trace-viewer compare ./v1/test_checkout ./v2/test_checkout -o checkout_diff.html
```

#### Output

```
Comparing traces:
  Trace 1: ./baseline/test_login_20250119
  Trace 2: ./current/test_login_20250120

Comparison Summary:
  Total keywords: 24
  Matched: 20
  Modified: 2
  Added: 1
  Removed: 1
  Variable changes: 5

Comparison report generated: comparison.html
```

---

### stats

Generate a statistics dashboard for multiple traces.

```bash
trace-viewer stats [traces_directory] [OPTIONS]
```

#### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `traces_directory` | No | `./traces` | Directory containing traces |

#### Options

| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--output` | `-o` | No | `dashboard.html` | Output path for dashboard HTML |
| `--open` | `-O` | No | False | Open dashboard in browser after generation |

#### Examples

```bash
# Generate dashboard with defaults
trace-viewer stats

# Generate dashboard for specific directory
trace-viewer stats ./my_traces

# Generate and open in browser
trace-viewer stats ./traces -o report.html -O

# Custom output path
trace-viewer stats ./traces -o /var/www/html/dashboard.html
```

#### Output

```
Scanning traces in: ./traces

Found 50 trace(s):
  42 passed, 6 failed, 2 skipped
  Pass rate: 84.0%

Dashboard generated: dashboard.html
```

---

### export-rp

Export traces to ReportPortal for centralized reporting.

```bash
trace-viewer export-rp [traces_directory] [OPTIONS]
```

#### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `traces_directory` | No | `./traces` | Directory containing traces |

#### Options

| Option | Short | Required | Env Var | Description |
|--------|-------|----------|---------|-------------|
| `--endpoint` | `-e` | Yes | `RP_ENDPOINT` | ReportPortal server URL |
| `--project` | `-p` | Yes | `RP_PROJECT` | ReportPortal project name |
| `--api-key` | `-k` | Yes | `RP_API_KEY` | ReportPortal API key |
| `--launch-name` | `-n` | No | - | Custom name for the launch |
| `--no-screenshots` | - | No | - | Skip uploading screenshots |

#### Examples

```bash
# Using command line options
trace-viewer export-rp ./traces \
  -e https://rp.example.com \
  -p my_project \
  -k abc123-def456-ghi789

# Using environment variables
export RP_ENDPOINT=https://rp.example.com
export RP_PROJECT=my_project
export RP_API_KEY=abc123-def456-ghi789
trace-viewer export-rp ./traces

# Custom launch name
trace-viewer export-rp ./traces \
  -e https://rp.example.com \
  -p my_project \
  -k abc123 \
  -n "Release 2.0 Tests"

# Skip screenshots for faster upload
trace-viewer export-rp ./traces \
  -e https://rp.example.com \
  -p my_project \
  -k abc123 \
  --no-screenshots
```

#### Output

```
Exporting traces to ReportPortal...
  Endpoint: https://rp.example.com
  Project: my_project

Starting launch: Robot Framework Traces

Exporting traces:
  [1/10] test_login_20250120 ... OK
  [2/10] test_checkout_20250120 ... OK
  [3/10] test_search_20250120 ... OK
  ...

Export completed:
  Total: 10
  Exported: 10
  Failed: 0

Launch URL: https://rp.example.com/ui/#my_project/launches/all/12345
```

#### Requirements

ReportPortal integration requires the `reportportal-client` package:

```bash
pip install reportportal-client
```

---

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |

---

## Environment Variables

| Variable | Command | Description |
|----------|---------|-------------|
| `RP_ENDPOINT` | `export-rp` | ReportPortal server URL |
| `RP_PROJECT` | `export-rp` | ReportPortal project name |
| `RP_API_KEY` | `export-rp` | ReportPortal API key |

---

## Listener Usage

The trace listener is used with the `robot` command:

```bash
robot --listener trace_viewer.TraceListener[:options] tests/
```

### Listener Options

| Option | Default | Description |
|--------|---------|-------------|
| `output_dir` | `./traces` | Directory where traces are saved |
| `capture_mode` | `full` | Capture mode: `full`, `on_failure`, `none` |

### Examples

```bash
# Default options
robot --listener trace_viewer.TraceListener tests/

# Custom output directory
robot --listener trace_viewer.TraceListener:output_dir=./my_traces tests/

# Capture only on failure
robot --listener "trace_viewer.TraceListener:capture_mode=on_failure" tests/

# Multiple options
robot --listener "trace_viewer.TraceListener:output_dir=./traces:capture_mode=full" tests/

# With Pabot
pabot --listener trace_viewer.TraceListener:output_dir=./traces tests/
```
