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
  cleanup         Clean up old traces based on retention policy.
  compare         Compare two traces and generate a diff report.
  compare-visual  Compare screenshots between two traces visually (pixel diff).
  compress        Compress trace screenshots from PNG to WebP.
  export          Export a trace directory as a ZIP archive.
  export-pdf      Export a trace as a PDF report.
  export-rp       Export traces to ReportPortal.
  info            Display detailed information about a trace.
  init            Generate a default trace-viewer.yml configuration file.
  list            List all traces in a directory.
  merge           Merge Pabot parallel traces into a unified timeline.
  open            Open a trace in the default browser.
  publish         Publish traces for CI/CD integration (Jenkins/GitLab).
  replay          Generate a GIF or HTML slideshow replay from trace screenshots.
  stats           Generate statistics dashboard for traces.
  suite           Generate a suite-level summary viewer from multiple traces.
```

---

## Commands

### init

Generate a default configuration file.

```bash
trace-viewer init [OPTIONS]
```

#### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output` | `-o` | `./trace-viewer.yml` | Output path for the config file |

#### Examples

```bash
# Generate default config in current directory
trace-viewer init

# Generate config at custom location
trace-viewer init -o /path/to/trace-viewer.yml
```

#### Behavior

1. Checks if target file already exists (refuses to overwrite)
2. Generates a YAML file with all settings and explanatory comments
3. Config file is immediately usable by the listener

#### Generated Config

```yaml
# Robot Framework Trace Viewer Configuration
output_dir: traces
capture_mode: full
screenshot_mode: viewport
buffer_size: 10
masking_patterns:
  - password
  - secret
  - token
  - key
  - credential
  - auth
  - api_key
compression:
  format: png
  quality: 80
  max_dom_size_kb: 500
retention:
  days: 30
  max_traces: 100
ci_mode: false
```

---

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

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output` | `-o` | `<trace_name>.zip` | Output path for ZIP archive |

#### Examples

```bash
# Export with auto-generated name
trace-viewer export ./traces/login_test_20250120_143022

# Export with custom name
trace-viewer export ./traces/login_test_20250120_143022 -o login_trace.zip
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

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output` | `-o` | `comparison.html` | Output path for comparison HTML |

#### Examples

```bash
# Compare two traces
trace-viewer compare ./baseline/test_login_* ./current/test_login_*

# Compare with custom output
trace-viewer compare ./v1/test_checkout ./v2/test_checkout -o checkout_diff.html
```

---

### compare-visual

Compare screenshots between two traces visually using pixel-level diff.

```bash
trace-viewer compare-visual <trace1_path> <trace2_path> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `trace1_path` | Yes | Path to the baseline trace |
| `trace2_path` | Yes | Path to the candidate trace |

#### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output` | `-o` | auto-generated | Output path for comparison HTML |
| `--open` | `-O` | False | Open report in browser after generation |

#### Examples

```bash
# Compare screenshots between two traces
trace-viewer compare-visual ./baseline/login_test ./current/login_test

# Generate and open report
trace-viewer compare-visual ./v1/checkout ./v2/checkout -o visual_diff.html -O
```

#### Output

The report includes:
- Side-by-side screenshots for each keyword (Baseline vs Candidate)
- Diff overlay image highlighting changed pixels in red
- Similarity score per keyword (0.0 = completely different, 1.0 = identical)
- Changed pixel count and total pixel count

#### Requirements

Requires Pillow: `pip install robotframework-trace-viewer[media]`

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

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output` | `-o` | `dashboard.html` | Output path for dashboard HTML |
| `--open` | `-O` | False | Open dashboard in browser after generation |

#### Examples

```bash
# Generate dashboard with defaults
trace-viewer stats

# Generate and open in browser
trace-viewer stats ./traces -o report.html -O
```

---

### suite

Generate a suite-level summary viewer from multiple traces.

```bash
trace-viewer suite <traces_directory> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `traces_directory` | Yes | Directory containing trace folders |

#### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output` | `-o` | `suite_viewer.html` | Output path for suite HTML |
| `--open` | `-O` | False | Open viewer in browser after generation |

#### Examples

```bash
# Generate suite viewer
trace-viewer suite ./traces

# Generate and open
trace-viewer suite ./traces -o suite.html -O
```

#### Output

The suite viewer includes:
- Stats bar: total tests, passed, failed, pass rate
- Sidebar with all tests (name, status badge, duration)
- Click on a test to open its individual trace viewer
- For >30 tests, links to viewers instead of embedding

---

### replay

Generate a GIF or HTML slideshow replay from trace screenshots.

```bash
trace-viewer replay <trace_dir> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `trace_dir` | Yes | Path to a trace directory |

#### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--format` | `-f` | `html` | Output format: `gif` or `html` |
| `--fps` | | `2` | Frames per second (GIF only) |
| `--width` | | `800` | Maximum width in pixels (GIF only) |
| `--output` | `-o` | auto-generated | Output file path |

#### Examples

```bash
# Generate HTML slideshow (default)
trace-viewer replay ./traces/login_test

# Generate animated GIF
trace-viewer replay ./traces/login_test --format gif --fps 3 --width 1024

# Custom output path
trace-viewer replay ./traces/login_test -f gif -o replay.gif
```

#### HTML Slideshow Controls

- Play/Pause button
- Step forward/backward
- Progress bar
- Keyboard: Space (play/pause), Left/Right arrows (step)

#### Requirements

GIF format requires Pillow: `pip install robotframework-trace-viewer[media]`

---

### compress

Compress trace screenshots from PNG to WebP for storage efficiency.

```bash
trace-viewer compress <traces_directory> [OPTIONS]
```

#### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `traces_directory` | No | `./traces` | Directory containing traces |

#### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--quality` | `-q` | `80` | WebP quality (1-100) |

#### Examples

```bash
# Compress with default quality
trace-viewer compress ./traces

# Compress with lower quality for more savings
trace-viewer compress ./traces --quality 60
```

#### Output

```
Compressing screenshots in: ./traces
Converted 24 file(s) to WebP
Original size: 12.5 MB
Compressed size: 3.2 MB
Savings: 74.4%
```

#### Notes

- Replaces `screenshot.png` with `screenshot.webp` in each keyword directory
- Viewer HTML auto-detects both formats
- Typical savings: 60-80% vs PNG

#### Requirements

Requires Pillow: `pip install robotframework-trace-viewer[media]`

---

### cleanup

Clean up old traces based on retention policy.

```bash
trace-viewer cleanup <traces_directory> [OPTIONS]
```

#### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `traces_directory` | No | `./traces` | Directory containing traces |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--days` | `30` | Delete traces older than N days |
| `--max-traces` | `100` | Maximum number of traces to keep |

#### Examples

```bash
# Delete traces older than 30 days
trace-viewer cleanup ./traces --days 30

# Keep only the 50 most recent traces
trace-viewer cleanup ./traces --max-traces 50

# Combined: delete old + cap at max
trace-viewer cleanup ./traces --days 14 --max-traces 100
```

#### Output

```
Cleaning up traces in: ./traces
Deleted 12 trace(s) older than 30 days
Remaining: 38 trace(s)
```

---

### export-pdf

Export a trace as a professional PDF report.

```bash
trace-viewer export-pdf <trace_dir> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `trace_dir` | Yes | Path to the trace directory |

#### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output` | `-o` | `<trace_dir>/report.pdf` | Output path for PDF |
| `--screenshots-only` | | False | Only include screenshots (skip variables/details) |

#### Examples

```bash
# Full PDF report
trace-viewer export-pdf ./traces/login_test

# Screenshots-only report
trace-viewer export-pdf ./traces/login_test --screenshots-only -o login_screenshots.pdf
```

#### Report Contents

- **Cover page**: Test name, suite, status, date, duration
- **Per-keyword pages**: Screenshot (resized), arguments, variables, status
- **Summary**: Total keywords, pass/fail count

#### Requirements

Requires weasyprint: `pip install robotframework-trace-viewer[pdf]`

---

### merge

Merge Pabot parallel traces into a unified timeline.

```bash
trace-viewer merge <traces_directory> [OPTIONS]
```

#### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `traces_directory` | No | `./traces` | Directory with Pabot trace folders |

#### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output` | `-o` | `<traces_dir>/merged/` | Output directory |

#### Examples

```bash
# Merge parallel traces
trace-viewer merge ./traces

# Custom output directory
trace-viewer merge ./traces -o ./merged_results/
```

#### Output

Creates a directory with:
- `timeline.html`: Gantt-style visualization with swimlanes per worker
- `manifest.json`: Merged metadata from all traces
- Links to individual trace viewers

#### How It Works

1. Scans for trace directories with Pabot suffixes (`_pabot0`, `_pabot1`, etc.)
2. Extracts worker ID and timing information from manifests
3. Builds a chronological timeline ordered by start time
4. Generates HTML with horizontal bars per worker showing test execution

---

### publish

Publish traces for CI/CD integration.

```bash
trace-viewer publish <traces_directory> [OPTIONS]
```

#### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `traces_directory` | No | `./traces` | Directory containing traces |

#### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--format` | `-f` | `jenkins` | CI platform: `jenkins` or `gitlab` |
| `--output` | `-o` | auto-generated | Output directory |

#### Examples

```bash
# Publish for Jenkins (HTML Publisher)
trace-viewer publish ./traces --format jenkins -o trace-reports/

# Publish for GitLab (MR comment)
trace-viewer publish ./traces --format gitlab -o trace-reports/
```

#### Jenkins Output

Creates `index.html` in the output directory, compatible with the Jenkins HTML Publisher Plugin:

```groovy
publishHTML([
    reportDir: 'trace-reports',
    reportFiles: 'index.html',
    reportName: 'Trace Report'
])
```

#### GitLab Output

Creates `trace-summary.md` in the output directory, suitable for merge request comments:

```yaml
script:
  - trace-viewer publish ./traces --format gitlab -o trace-reports/
  - cat trace-reports/trace-summary.md
```

The markdown includes:
- Summary table with pass/fail counts
- Test list with status icons and durations
- Links to individual trace viewers

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
```

#### Requirements

Requires the `reportportal-client` package:

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

### Configuration

| Variable | Description |
|----------|-------------|
| `TRACE_VIEWER_OUTPUT_DIR` | Override output directory |
| `TRACE_VIEWER_CAPTURE_MODE` | Override capture mode (full/on_failure/disabled) |
| `TRACE_VIEWER_SCREENSHOT_MODE` | Override screenshot mode (viewport/full_page) |
| `TRACE_VIEWER_BUFFER_SIZE` | Override ring buffer size |
| `TRACE_VIEWER_CI_MODE` | Enable CI mode (1/true/yes) |
| `TRACE_VIEWER_COMPRESSION_FORMAT` | Compression format (png/webp) |
| `TRACE_VIEWER_COMPRESSION_QUALITY` | WebP quality (1-100) |

### ReportPortal

| Variable | Description |
|----------|-------------|
| `RP_ENDPOINT` | ReportPortal server URL |
| `RP_PROJECT` | ReportPortal project name |
| `RP_API_KEY` | ReportPortal API key |

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
| `capture_mode` | `full` | Capture mode: `full`, `on_failure`, `disabled` |
| `screenshot_mode` | `viewport` | Screenshot mode: `viewport`, `full_page` |
| `buffer_size` | `10` | Ring buffer size for `on_failure` mode |

### Examples

```bash
# Default options
robot --listener trace_viewer.TraceListener tests/

# Custom output directory
robot --listener trace_viewer.TraceListener:output_dir=./my_traces tests/

# Capture only on failure (CI optimized)
robot --listener "trace_viewer.TraceListener:capture_mode=on_failure:buffer_size=15" tests/

# Full-page screenshots
robot --listener "trace_viewer.TraceListener:screenshot_mode=full_page" tests/

# Multiple options
robot --listener "trace_viewer.TraceListener:output_dir=./traces:capture_mode=full:screenshot_mode=full_page" tests/

# With Pabot
pabot --listener trace_viewer.TraceListener:output_dir=./traces tests/
```
