# Features Guide

This guide provides detailed documentation for all features of Robot Framework Trace Viewer.

## Table of Contents

- [Screenshot Capture](#screenshot-capture)
- [DOM Snapshots](#dom-snapshots)
- [Network Request Capture](#network-request-capture)
- [Console Logs Capture](#console-logs-capture)
- [Variable Tracking](#variable-tracking)
- [Trace Comparison](#trace-comparison)
- [Statistics Dashboard](#statistics-dashboard)
- [ZIP Export](#zip-export)
- [Pabot Support](#pabot-support)

---

## Screenshot Capture

Screenshots are automatically captured at the end of each keyword execution when a browser is active.

### How It Works

1. The listener detects active browser sessions from SeleniumLibrary or Browser Library
2. At the end of each keyword, a screenshot is captured
3. Screenshots are saved as PNG files in the keyword directory

### Supported Libraries

| Library | Method | Notes |
|---------|--------|-------|
| SeleniumLibrary | `driver.get_screenshot_as_png()` | Uses Selenium WebDriver |
| Browser Library | `Take Screenshot` keyword | Uses Playwright |

### Configuration

Screenshots can be controlled via the `capture_mode` listener option:

```bash
# Capture at every keyword (default)
robot --listener "trace_viewer.TraceListener:capture_mode=full" tests/

# Capture only on failure
robot --listener "trace_viewer.TraceListener:capture_mode=on_failure" tests/

# Disable screenshot capture
robot --listener "trace_viewer.TraceListener:capture_mode=none" tests/
```

### Graceful Handling

If no browser is open or screenshot capture fails:
- The keyword is still recorded
- No screenshot file is created
- No error is raised (silent skip)

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

### Example Output

```html
<html lang="en">
<head>
  <title>Example Domain</title>
  <style>body { background: #eee; }</style>
</head>
<body>
  <div>
    <h1>Example Domain</h1>
    <p>This domain is for use in documentation.</p>
  </div>
</body>
</html>
```

### Use Cases

- Debug layout issues by inspecting DOM state
- Compare page structure between test runs
- Verify dynamic content rendering

---

## Network Request Capture

Network requests are captured using Chrome DevTools Protocol (CDP) for comprehensive HTTP monitoring.

### How It Works

1. CDP is enabled at the start of the test via `Network.enable`
2. Performance logs are collected during keyword execution
3. Request/response data is extracted and saved as `network.json`

### Supported Browsers

| Browser | Support | Notes |
|---------|---------|-------|
| Chrome | Full | Native CDP support |
| Chromium | Full | Native CDP support |
| Edge | Full | Chromium-based, CDP support |
| Firefox | Limited | CDP not fully supported |
| Safari | None | No CDP support |

### Captured Data

Each network request includes:

```json
{
  "requests": [
    {
      "request_id": "ABC123",
      "url": "https://api.example.com/data",
      "method": "GET",
      "request_headers": {
        "User-Agent": "Mozilla/5.0...",
        "Accept": "application/json"
      },
      "resource_type": "XHR",
      "timestamp": 1705750800.123,
      "status": 200,
      "response_headers": {
        "content-type": "application/json",
        "content-length": "1234"
      },
      "size": 1234,
      "duration_ms": 150,
      "mime_type": "application/json"
    }
  ]
}
```

### Resource Types

- `Document` - HTML pages
- `Script` - JavaScript files
- `Stylesheet` - CSS files
- `Image` - Images
- `Font` - Web fonts
- `XHR` - XMLHttpRequest calls
- `Fetch` - Fetch API calls
- `WebSocket` - WebSocket connections

### Header Truncation

For privacy and storage efficiency, headers are truncated:
- Maximum 10 headers per request/response
- Maximum 200 characters per header value

### Use Cases

- Debug API calls and responses
- Verify request payloads
- Identify slow network requests
- Monitor resource loading

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

### Example Output

```json
{
  "logs": [
    {
      "level": "INFO",
      "message": "Application initialized",
      "source": "console-api",
      "timestamp": 1705750800123
    },
    {
      "level": "WARNING",
      "message": "Deprecated API usage",
      "source": "console-api",
      "timestamp": 1705750800456
    },
    {
      "level": "ERROR",
      "message": "Uncaught TypeError: Cannot read property 'x' of undefined",
      "source": "javascript",
      "timestamp": 1705750800789
    }
  ]
}
```

### Viewer Display

In the HTML viewer, console logs are displayed with color coding:
- INFO: Gray
- WARNING: Orange
- ERROR: Red

### Use Cases

- Debug JavaScript errors
- Track application state changes
- Verify API responses logged to console

---

## Variable Tracking

Robot Framework variables are captured at each keyword execution with automatic sensitive data masking.

### How It Works

1. All RF variables are retrieved via BuiltIn library
2. Variables are categorized (scalar, list, dict)
3. Sensitive values are masked
4. Variables are saved as `variables.json`

### Variable Types

| Prefix | Type | Example |
|--------|------|---------|
| `$` | Scalar | `${USERNAME}` |
| `@` | List | `@{ITEMS}` |
| `&` | Dictionary | `&{CONFIG}` |

### Sensitive Data Masking

Variables matching these patterns are automatically masked:

- `password`
- `secret`
- `token`
- `key`
- `credential`
- `auth`
- `api_key`

Example:
```json
{
  "scalars": {
    "USERNAME": "admin",
    "PASSWORD": "***MASKED***",
    "API_KEY": "***MASKED***",
    "BASE_URL": "https://example.com"
  }
}
```

### Value Truncation

Long values are truncated to prevent excessive storage:
- Maximum 1000 characters per value
- Truncated values end with `... [truncated]`

### Example Output

```json
{
  "scalars": {
    "BROWSER": "chrome",
    "URL": "https://example.com",
    "TIMEOUT": "30s"
  },
  "lists": {
    "USERS": ["alice", "bob", "charlie"]
  },
  "dicts": {
    "CONFIG": {
      "env": "production",
      "debug": false
    }
  }
}
```

---

## Trace Comparison

Compare two traces to identify differences in test execution.

### How It Works

1. Both traces are loaded and their keywords are extracted
2. Keywords are aligned using sequence matching
3. Differences are categorized (matched, modified, added, removed)
4. An HTML comparison report is generated

### Keyword States

| State | Description |
|-------|-------------|
| Matched | Same keyword name, same position |
| Modified | Same keyword name, different arguments or status |
| Added | Keyword exists only in trace 2 |
| Removed | Keyword exists only in trace 1 |

### CLI Usage

```bash
trace-viewer compare ./baseline/test_login_* ./current/test_login_* -o comparison.html
```

### Options

| Option | Description |
|--------|-------------|
| `-o, --output` | Output path for comparison HTML |

### Comparison Report Contents

The HTML report includes:
- Summary statistics (total, matched, modified, added, removed)
- Side-by-side keyword comparison
- Variable differences highlighted
- Screenshot comparison (if available)

### Use Cases

- Regression testing: Compare baseline vs current
- Debug failures: Compare passing vs failing runs
- Performance analysis: Compare execution times

---

## Statistics Dashboard

Generate aggregated statistics across multiple traces.

### How It Works

1. All traces in the specified directory are scanned
2. Metadata is extracted from each manifest.json
3. Statistics are calculated (pass rate, durations, etc.)
4. An HTML dashboard is generated

### CLI Usage

```bash
# Generate dashboard
trace-viewer stats ./traces -o dashboard.html

# Generate and open in browser
trace-viewer stats ./traces -o dashboard.html -O
```

### Options

| Option | Description |
|--------|-------------|
| `-o, --output` | Output path for dashboard HTML |
| `-O, --open` | Open dashboard in browser after generation |

### Statistics Included

#### Summary
- Total tests
- Passed / Failed / Skipped counts
- Pass rate percentage

#### Duration Statistics
- Minimum duration
- Maximum duration
- Average duration
- Median duration
- 95th percentile (P95)

#### Slowest Tests
- Top 10 slowest tests with durations
- Links to individual trace viewers

#### Flaky Tests
- Tests with inconsistent results (same name, different outcomes)
- Failure count and total runs

### Example Output

```
Statistics Dashboard
====================

Summary
-------
Total Tests: 150
Passed: 142 (94.7%)
Failed: 6 (4.0%)
Skipped: 2 (1.3%)

Duration Statistics
-------------------
Min: 0.5s
Max: 45.2s
Average: 5.3s
Median: 3.8s
P95: 15.2s

Slowest Tests
-------------
1. Test Full Checkout Flow (45.2s)
2. Test Data Import (32.1s)
3. Test Report Generation (28.5s)
...

Flaky Tests
-----------
- Test Login (2 failures / 10 runs)
- Test Search (1 failure / 5 runs)
```

---

## ZIP Export

Export traces as portable ZIP archives for sharing or archiving.

### How It Works

1. The trace directory is compressed into a ZIP file
2. All files are included (viewer, screenshots, data)
3. Directory structure is preserved

### CLI Usage

```bash
trace-viewer export ./traces/test_login_20250120 -o login_trace.zip
```

### Options

| Option | Description |
|--------|-------------|
| `-o, --output` | Output path for ZIP archive |

### Archive Contents

```
login_trace.zip
├── manifest.json
├── viewer.html
└── keywords/
    ├── 001_open_browser/
    │   ├── metadata.json
    │   ├── screenshot.png
    │   ├── dom.html
    │   ├── network.json
    │   ├── console.json
    │   └── variables.json
    └── ...
```

### Use Cases

- Share traces with team members
- Archive traces for later analysis
- Upload to bug tracking systems

---

## Pabot Support

Full support for parallel test execution with Pabot.

### How It Works

1. Pabot sets environment variables for each worker process
2. The listener detects these variables automatically
3. Trace directory names include the worker ID to prevent conflicts

### Environment Variables

| Variable | Description |
|----------|-------------|
| `PABOTQUEUEINDEX` | Worker queue index (0, 1, 2, ...) |
| `PABOTEXECUTIONPOOLID` | Execution pool identifier |
| `PABOT_QUEUE_INDEX` | Alternative queue index variable |

### Trace Naming

Standard execution:
```
traces/test_login_20250120_143022/
```

Pabot execution:
```
traces/test_login_20250120_143022_pabot0/
traces/test_login_20250120_143022_pabot1/
```

### CLI Usage

```bash
# Install Pabot
pip install robotframework-pabot

# Run tests in parallel
pabot --processes 4 --listener trace_viewer.TraceListener:output_dir=./traces tests/
```

### Listing Parallel Traces

```bash
trace-viewer list ./traces
```

Output:
```
Found 8 trace(s):
  [PASS] Login Test (pabot0)
      Path: ./traces/login_test_20250120_143022_pabot0
  [PASS] Login Test (pabot1)
      Path: ./traces/login_test_20250120_143022_pabot1
  ...
```

### Use Cases

- Run large test suites faster
- Distribute tests across CI workers
- Maintain trace isolation in parallel runs
