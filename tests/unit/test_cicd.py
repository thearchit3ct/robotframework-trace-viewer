"""Tests for trace_viewer.integrations.cicd module."""

import json
import os
from pathlib import Path
from unittest.mock import patch

from trace_viewer.integrations.cicd import CICDPublisher, get_ci_environment


def _create_trace(traces_dir: Path, name: str, status: str = "PASS") -> Path:
    """Create a fake trace directory."""
    trace_dir = traces_dir / name
    trace_dir.mkdir(parents=True)
    manifest = {
        "test_name": name.replace("_", " ").title(),
        "status": status,
        "duration_ms": 1000,
        "start_time": "2025-01-20T10:00:00+00:00",
    }
    (trace_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    # Create a minimal viewer.html
    (trace_dir / "viewer.html").write_text("<html><body>viewer</body></html>", encoding="utf-8")
    return trace_dir


class TestGetCIEnvironment:
    """Test CI environment detection."""

    def test_jenkins(self):
        with patch.dict(os.environ, {"JENKINS_URL": "https://jenkins.example.com"}, clear=False):
            result = get_ci_environment()
            assert result == "jenkins"

    def test_gitlab(self):
        with patch.dict(os.environ, {"GITLAB_CI": "true"}, clear=False):
            result = get_ci_environment()
            assert result == "gitlab"

    def test_github(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=False):
            result = get_ci_environment()
            assert result == "github"

    def test_no_ci(self):
        env = {
            k: v
            for k, v in os.environ.items()
            if k
            not in ("JENKINS_URL", "BUILD_NUMBER", "GITLAB_CI", "CI_PROJECT_ID", "GITHUB_ACTIONS")
        }
        with patch.dict(os.environ, env, clear=True):
            result = get_ci_environment()
            assert result is None


class TestCICDPublisherJenkins:
    """Test Jenkins publishing."""

    def test_publish_jenkins(self, tmp_path):
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        _create_trace(traces_dir, "test_login", "PASS")
        _create_trace(traces_dir, "test_checkout", "FAIL")

        publisher = CICDPublisher(traces_dir, format="jenkins")
        output = publisher.publish()
        assert output.exists()
        index_html = output / "index.html"
        assert index_html.exists()
        content = index_html.read_text(encoding="utf-8")
        assert "PASS" in content or "pass" in content.lower()

    def test_custom_output(self, tmp_path):
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        _create_trace(traces_dir, "test_one", "PASS")

        output_dir = tmp_path / "custom_output"
        publisher = CICDPublisher(traces_dir, format="jenkins")
        result = publisher.publish(output_dir)
        assert result == output_dir
        assert output_dir.exists()


class TestCICDPublisherGitlab:
    """Test GitLab publishing."""

    def test_publish_gitlab(self, tmp_path):
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        _create_trace(traces_dir, "test_login", "PASS")
        _create_trace(traces_dir, "test_checkout", "FAIL")

        publisher = CICDPublisher(traces_dir, format="gitlab")
        output = publisher.publish()
        assert output.exists()
        # Should have a markdown summary
        md_files = list(output.glob("*.md"))
        assert len(md_files) >= 1

    def test_no_traces(self, tmp_path):
        traces_dir = tmp_path / "empty"
        traces_dir.mkdir()
        publisher = CICDPublisher(traces_dir, format="jenkins")
        output = publisher.publish()
        assert output.exists()
