# Integrations Guide

This guide covers integrations with external tools and services.

## Table of Contents

- [ReportPortal](#reportportal)
- [Pabot (Parallel Execution)](#pabot-parallel-execution)
- [CI/CD Integration](#cicd-integration)
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

Robot Framework concepts are mapped to ReportPortal as follows:

| Robot Framework | ReportPortal | Description |
|-----------------|--------------|-------------|
| Trace export session | Launch | Container for all tests |
| Test case | Test | Individual test item |
| Keyword | Step | Nested step within test |
| Screenshot | Attachment | Uploaded as log attachment |
| Tags | Attributes | Key-value pairs on test |

### Attributes

The following attributes are automatically added to tests:

| Attribute | Source |
|-----------|--------|
| `suite` | Suite name from manifest |
| `tag` | Each tag from test tags |
| `rf_version` | Robot Framework version |

### Programmatic Usage

You can also use the exporter directly in Python:

```python
from trace_viewer.integrations import ReportPortalExporter

# Create exporter
exporter = ReportPortalExporter(
    endpoint="https://reportportal.example.com",
    project="my_project",
    api_key="your-api-key-uuid",
    launch_name="Nightly Tests",
    launch_description="Automated test run",
)

# Export single trace
result = exporter.export_trace(
    trace_dir=Path("./traces/test_login_20250120"),
    include_screenshots=True,
)
print(f"Test UUID: {result['test_uuid']}")

# Export all traces in directory
results = exporter.export_traces(
    traces_dir=Path("./traces"),
    include_screenshots=True,
)
print(f"Exported: {results['exported']}/{results['total']}")
```

### Launch Management

By default, a new launch is created for each export. For more control:

```python
# Manual launch management
exporter.start_launch(
    name="Release 2.0 Tests",
    description="Full regression suite",
    attributes=[
        {"key": "version", "value": "2.0.0"},
        {"key": "environment", "value": "staging"},
    ],
)

# Export multiple traces to same launch
for trace_dir in trace_dirs:
    exporter.export_trace(trace_dir)

# Finish launch
exporter.finish_launch()
```

### Error Handling

```python
try:
    exporter.export_traces(traces_dir)
except ImportError:
    print("Install reportportal-client: pip install reportportal-client")
except FileNotFoundError as e:
    print(f"Trace not found: {e}")
except Exception as e:
    print(f"Export failed: {e}")
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

### Collecting Results

After parallel execution, all traces are in the same directory:

```bash
trace-viewer list ./traces
```

```
Found 8 trace(s):
  [PASS] Login Test (pabot0) - 2.5s
  [PASS] Login Test (pabot1) - 2.6s
  [PASS] Checkout Test (pabot0) - 3.2s
  [PASS] Checkout Test (pabot1) - 3.1s
  ...
```

### Statistics Across Workers

Generate combined statistics:

```bash
trace-viewer stats ./traces -o parallel_results.html
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
          pip install robotframework-trace-viewer

      - name: Run tests with traces
        run: |
          robot --listener trace_viewer.TraceListener:output_dir=./traces tests/

      - name: Generate statistics
        if: always()
        run: |
          trace-viewer stats ./traces -o traces/dashboard.html

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
  script:
    - pip install robotframework robotframework-seleniumlibrary robotframework-trace-viewer
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
    - pip install robotframework-trace-viewer
    - trace-viewer stats ./traces -o traces/dashboard.html
  artifacts:
    when: always
    paths:
      - traces/dashboard.html

reportportal:
  stage: report
  image: python:3.11
  needs:
    - test
  variables:
    RP_ENDPOINT: $RP_ENDPOINT
    RP_PROJECT: $RP_PROJECT
    RP_API_KEY: $RP_API_KEY
  script:
    - pip install robotframework-trace-viewer reportportal-client
    - trace-viewer export-rp ./traces -n "Pipeline $CI_PIPELINE_ID"
  only:
    - main
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
                    pip install robotframework-trace-viewer
                '''
            }
        }

        stage('Test') {
            steps {
                sh '''
                    . venv/bin/activate
                    robot --listener trace_viewer.TraceListener:output_dir=./traces tests/
                '''
            }
            post {
                always {
                    sh '''
                        . venv/bin/activate
                        trace-viewer stats ./traces -o traces/dashboard.html
                    '''
                    archiveArtifacts artifacts: 'traces/**/*', allowEmptyArchive: true
                    publishHTML([
                        reportDir: 'traces',
                        reportFiles: 'dashboard.html',
                        reportName: 'Test Statistics'
                    ])
                }
            }
        }

        stage('Report') {
            when {
                branch 'main'
            }
            steps {
                withCredentials([
                    string(credentialsId: 'rp-endpoint', variable: 'RP_ENDPOINT'),
                    string(credentialsId: 'rp-project', variable: 'RP_PROJECT'),
                    string(credentialsId: 'rp-api-key', variable: 'RP_API_KEY')
                ]) {
                    sh '''
                        . venv/bin/activate
                        pip install reportportal-client
                        trace-viewer export-rp ./traces -n "Build ${BUILD_NUMBER}"
                    '''
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
      pip install robotframework-trace-viewer
    displayName: 'Install dependencies'

  - script: |
      robot --listener trace_viewer.TraceListener:output_dir=./traces tests/
    displayName: 'Run tests'
    continueOnError: true

  - script: |
      trace-viewer stats ./traces -o traces/dashboard.html
    displayName: 'Generate statistics'
    condition: always()

  - task: PublishBuildArtifacts@1
    inputs:
      pathToPublish: 'traces'
      artifactName: 'test-traces'
    condition: always()

  - script: |
      pip install reportportal-client
      trace-viewer export-rp ./traces -n "Build $(Build.BuildNumber)"
    displayName: 'Export to ReportPortal'
    condition: and(always(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))
    env:
      RP_ENDPOINT: $(RP_ENDPOINT)
      RP_PROJECT: $(RP_PROJECT)
      RP_API_KEY: $(RP_API_KEY)
```

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
- Variables via BuiltIn

Note: Network and console capture use different mechanisms with Browser Library.

### Automatic Detection

The trace listener automatically detects which library is active:

1. Checks for SeleniumLibrary instance
2. Falls back to Browser Library
3. Gracefully handles missing browser

```python
# Internal detection logic
def _get_browser_library(self):
    try:
        return BuiltIn().get_library_instance('SeleniumLibrary')
    except RuntimeError:
        pass

    try:
        return BuiltIn().get_library_instance('Browser')
    except RuntimeError:
        pass

    return None
```

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
