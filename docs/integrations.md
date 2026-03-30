# Integrations Guide

This guide covers integrations with external tools and services.

## Table of Contents

- [ReportPortal](#reportportal)
- [Pabot (Parallel Execution)](#pabot-parallel-execution)
- [Pabot Merge Timeline](#pabot-merge-timeline)
- [CI/CD Integration](#cicd-integration)
- [CI/CD Publishing](#cicd-publishing)
- [Browser Libraries](#browser-libraries)

---

## ReportPortal

[ReportPortal](https://reportportal.io/) is an open-source test automation reporting platform. The trace viewer can upload traces to ReportPortal for centralized reporting and analysis.

### Prerequisites

1. Install the ReportPortal client:

```bash
pip install reportportal-client
```

2. Have access to a ReportPortal server with:
   - Server URL (endpoint)
   - Project name
   - API key (UUID token)

### Getting Your API Key

1. Log in to your ReportPortal instance
2. Go to **User Profile** (click your avatar)
3. Navigate to **API Keys** tab
4. Click **Generate API Key**
5. Copy the generated key

### CLI Usage

```bash
trace-viewer export-rp ./traces \
  -e https://reportportal.example.com \
  -p my_project \
  -k your-api-key-uuid
```

### Environment Variables

For security, use environment variables instead of command-line arguments:

```bash
export RP_ENDPOINT=https://reportportal.example.com
export RP_PROJECT=my_project
export RP_API_KEY=your-api-key-uuid

trace-viewer export-rp ./traces
```

### Hierarchy Mapping

| Robot Framework | ReportPortal | Description |
|-----------------|--------------|-------------|
| Trace export session | Launch | Container for all tests |
| Test case | Test | Individual test item |
| Keyword | Step | Nested step within test |
| Screenshot | Attachment | Uploaded as log attachment |
| Tags | Attributes | Key-value pairs on test |

### Programmatic Usage

```python
from trace_viewer.integrations import ReportPortalExporter

exporter = ReportPortalExporter(
    endpoint="https://reportportal.example.com",
    project="my_project",
    api_key="your-api-key-uuid",
    launch_name="Nightly Tests",
)

results = exporter.export_traces(
    traces_dir=Path("./traces"),
    include_screenshots=True,
)
print(f"Exported: {results['exported']}/{results['total']}")
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| `ImportError: ReportPortal client not installed` | Run `pip install reportportal-client` |
| `401 Unauthorized` | Check API key is valid and not expired |
| `404 Project not found` | Verify project name matches exactly |
| `Connection refused` | Check endpoint URL and network access |

---

## Pabot (Parallel Execution)

[Pabot](https://pabot.org/) enables parallel execution of Robot Framework tests. The trace viewer fully supports Pabot with automatic conflict prevention.

### Installation

```bash
pip install robotframework-pabot
```

### Usage

```bash
pabot --processes 4 --listener trace_viewer.TraceListener:output_dir=./traces tests/
```

### How It Works

1. Pabot spawns multiple robot processes
2. Each process sets environment variables (`PABOTQUEUEINDEX`, etc.)
3. The trace listener detects these variables
4. Trace directories include the worker ID suffix

### Trace Naming

| Execution Type | Directory Name |
|----------------|----------------|
| Standard robot | `test_login_20250120_143022` |
| Pabot worker 0 | `test_login_20250120_143022_pabot0` |
| Pabot worker 1 | `test_login_20250120_143022_pabot1` |

### Environment Variables Detected

| Variable | Description |
|----------|-------------|
| `PABOTQUEUEINDEX` | Primary worker index |
| `PABOT_QUEUE_INDEX` | Alternative index variable |
| `PABOTEXECUTIONPOOLID` | Execution pool identifier |

---

## Pabot Merge Timeline

After parallel execution, merge all Pabot traces into a unified Gantt-style timeline.

### CLI Usage

```bash
# After parallel test execution
pabot --processes 4 --listener trace_viewer.TraceListener:output_dir=./traces tests/

# Merge traces into timeline
trace-viewer merge ./traces -o merged/
```

### What It Produces

The merge command creates a directory with:

- `timeline.html`: Interactive Gantt chart with swimlanes per worker
- `manifest.json`: Aggregated metadata from all traces
- Links to individual trace viewers

### Timeline Features

- Horizontal swimlanes per Pabot worker (pabot0, pabot1, etc.)
- Test bars sized proportionally to duration
- Color coding: green (PASS), red (FAIL)
- Test names and durations on hover
- Chronological ordering by start time

### Programmatic Usage

```python
from trace_viewer.integrations.pabot_merger import PabotMerger

merger = PabotMerger(traces_dir)
traces = merger.scan_traces()
# traces: [{"test_name": "Login", "worker_id": "pabot0", "start_time": ..., "duration_ms": ...}]

output_dir = merger.merge(output=Path("merged/"))
```

---

## CI/CD Integration

### GitHub Actions

```yaml
name: Robot Framework Tests

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

      - name: Install Chrome
        uses: browser-actions/setup-chrome@latest

      - name: Install dependencies
        run: |
          pip install robotframework robotframework-seleniumlibrary
          pip install robotframework-trace-viewer[media]

      - name: Run tests with traces
        run: |
          robot --listener "trace_viewer.TraceListener:capture_mode=on_failure" tests/

      - name: Generate reports
        if: always()
        run: |
          trace-viewer compress ./traces --quality 80
          trace-viewer suite ./traces -o traces/suite.html
          trace-viewer publish ./traces --format jenkins -o trace-reports/

      - name: Upload traces
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-traces
          path: traces/
          retention-days: 30

      - name: Export to ReportPortal
        if: always()
        env:
          RP_ENDPOINT: ${{ secrets.RP_ENDPOINT }}
          RP_PROJECT: ${{ secrets.RP_PROJECT }}
          RP_API_KEY: ${{ secrets.RP_API_KEY }}
        run: |
          pip install reportportal-client
          trace-viewer export-rp ./traces -n "CI Build ${{ github.run_number }}"
```

### GitLab CI

```yaml
stages:
  - test
  - report

test:
  stage: test
  image: python:3.11
  services:
    - selenium/standalone-chrome:latest
  variables:
    SELENIUM_REMOTE_URL: http://selenium:4444/wd/hub
    TRACE_VIEWER_CAPTURE_MODE: on_failure
  script:
    - pip install robotframework robotframework-seleniumlibrary
    - pip install robotframework-trace-viewer[media]
    - robot --listener trace_viewer.TraceListener:output_dir=./traces tests/
  artifacts:
    when: always
    paths:
      - traces/
    expire_in: 1 week

report:
  stage: report
  image: python:3.11
  needs:
    - test
  script:
    - pip install robotframework-trace-viewer[media]
    - trace-viewer compress ./traces --quality 80
    - trace-viewer suite ./traces -o traces/suite.html
    - trace-viewer publish ./traces --format gitlab -o trace-reports/
    - cat trace-reports/trace-summary.md
  artifacts:
    when: always
    paths:
      - traces/suite.html
      - trace-reports/
```

### Jenkins

```groovy
pipeline {
    agent any

    stages {
        stage('Setup') {
            steps {
                sh '''
                    python -m venv venv
                    . venv/bin/activate
                    pip install robotframework robotframework-seleniumlibrary
                    pip install robotframework-trace-viewer[media]
                '''
            }
        }

        stage('Test') {
            steps {
                sh '''
                    . venv/bin/activate
                    robot --listener "trace_viewer.TraceListener:capture_mode=on_failure" tests/
                '''
            }
            post {
                always {
                    sh '''
                        . venv/bin/activate
                        trace-viewer compress ./traces --quality 80
                        trace-viewer suite ./traces -o traces/suite.html
                        trace-viewer publish ./traces --format jenkins -o trace-reports/
                    '''
                    archiveArtifacts artifacts: 'traces/**/*', allowEmptyArchive: true
                    publishHTML([
                        reportDir: 'trace-reports',
                        reportFiles: 'index.html',
                        reportName: 'Trace Report'
                    ])
                }
            }
        }
    }
}
```

### Azure DevOps

```yaml
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.11'

  - script: |
      pip install robotframework robotframework-seleniumlibrary
      pip install robotframework-trace-viewer[media]
    displayName: 'Install dependencies'

  - script: |
      robot --listener "trace_viewer.TraceListener:capture_mode=on_failure" tests/
    displayName: 'Run tests'
    continueOnError: true

  - script: |
      trace-viewer compress ./traces --quality 80
      trace-viewer suite ./traces -o traces/suite.html
      trace-viewer publish ./traces --format jenkins -o trace-reports/
    displayName: 'Generate reports'
    condition: always()

  - task: PublishBuildArtifacts@1
    inputs:
      pathToPublish: 'traces'
      artifactName: 'test-traces'
    condition: always()
```

---

## CI/CD Publishing

The `trace-viewer publish` command generates platform-specific output for CI systems.

### Jenkins Publishing

```bash
trace-viewer publish ./traces --format jenkins -o trace-reports/
```

Creates `trace-reports/index.html` with:
- Summary stats (total, passed, failed, pass rate)
- Test table with status, duration, and links to viewers
- Compatible with Jenkins HTML Publisher Plugin

### GitLab Publishing

```bash
trace-viewer publish ./traces --format gitlab -o trace-reports/
```

Creates `trace-reports/trace-summary.md` with:
- Markdown table with test results
- Status icons (checkmark/cross)
- Summary line with pass/fail counts
- Suitable for posting as MR comments

### CI Mode

Enable CI-optimized behavior in the listener:

```yaml
# trace-viewer.yml
ci_mode: true
```

Or via environment variable:

```bash
export TRACE_VIEWER_CI_MODE=true
```

CI mode enables:
- `on_failure` capture mode (reduces storage)
- CI-friendly output paths
- Compact trace format

---

## Browser Libraries

### SeleniumLibrary

Full support with all capture features:

```robot
*** Settings ***
Library    SeleniumLibrary

*** Test Cases ***
Test With Selenium
    Open Browser    https://example.com    chrome
    Input Text    id=search    test query
    Click Button    id=submit
    [Teardown]    Close Browser
```

Captured data:
- Screenshots via WebDriver
- DOM via `page_source`
- Network via CDP (Chrome/Chromium/Edge)
- Console via `get_log('browser')`
- Variables via BuiltIn

### Browser Library (Playwright)

Full support with Playwright-based automation:

```robot
*** Settings ***
Library    Browser

*** Test Cases ***
Test With Playwright
    New Browser    chromium    headless=false
    New Page    https://example.com
    Fill Text    id=search    test query
    Click    id=submit
    [Teardown]    Close Browser
```

Captured data:
- Screenshots via `Take Screenshot`
- DOM via `Get Page Source`
- Network via Playwright page events (native capture)
- Variables via BuiltIn

### Automatic Detection

The trace listener automatically detects which library is active:

1. Checks for SeleniumLibrary instance
2. Falls back to Browser Library
3. Gracefully handles missing browser

### Mixed Usage

You can use both libraries in the same suite:

```robot
*** Settings ***
Library    SeleniumLibrary
Library    Browser

*** Test Cases ***
Test With Selenium
    Open Browser    https://example.com    chrome
    # ... selenium actions
    Close Browser

Test With Playwright
    New Browser    chromium
    New Page    https://example.com
    # ... playwright actions
    Close Browser
```

The trace listener will use whichever library has an active browser session.
