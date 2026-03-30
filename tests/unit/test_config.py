"""Tests for trace_viewer.config module."""

import os
from unittest.mock import patch

from trace_viewer.config import (
    TraceConfig,
    _apply_env_vars,
    _dict_to_config,
    _find_config_file,
    generate_default_config,
    load_config,
)


class TestTraceConfigDefaults:
    """Test TraceConfig default values."""

    def test_default_values(self):
        config = TraceConfig()
        assert config.output_dir == "traces"
        assert config.capture_mode == "full"
        assert config.screenshot_mode == "viewport"
        assert config.buffer_size == 10
        assert "password" in config.masking_patterns
        assert "token" in config.masking_patterns
        assert config.ci_mode is False

    def test_compression_defaults(self):
        config = TraceConfig()
        assert config.compression.format == "png"
        assert config.compression.quality == 80
        assert config.compression.max_dom_size_kb == 500

    def test_retention_defaults(self):
        config = TraceConfig()
        assert config.retention.days == 30
        assert config.retention.max_traces == 100


class TestFindConfigFile:
    """Test config file discovery."""

    def test_find_local_config(self, tmp_path):
        config_file = tmp_path / "trace-viewer.yml"
        config_file.write_text("output_dir: custom")
        result = _find_config_file(tmp_path)
        assert result == config_file

    def test_no_config_found(self, tmp_path):
        result = _find_config_file(tmp_path)
        assert result is None

    def test_home_config_fallback(self, tmp_path):
        with patch("trace_viewer.config.Path.home", return_value=tmp_path):
            config_file = tmp_path / ".trace-viewer.yml"
            config_file.write_text("output_dir: home")
            # Use a dir without local config
            empty_dir = tmp_path / "empty"
            empty_dir.mkdir()
            result = _find_config_file(empty_dir)
            assert result == config_file


class TestDictToConfig:
    """Test YAML dict to TraceConfig conversion."""

    def test_empty_dict(self):
        config = _dict_to_config({})
        assert config.output_dir == "traces"
        assert config.capture_mode == "full"

    def test_full_dict(self):
        data = {
            "output_dir": "custom_traces",
            "capture_mode": "on_failure",
            "screenshot_mode": "full_page",
            "buffer_size": 20,
            "masking_patterns": ["password", "secret", "custom_pattern"],
            "compression": {"format": "webp", "quality": 60, "max_dom_size_kb": 200},
            "retention": {"days": 7, "max_traces": 50},
            "ci_mode": True,
        }
        config = _dict_to_config(data)
        assert config.output_dir == "custom_traces"
        assert config.capture_mode == "on_failure"
        assert config.screenshot_mode == "full_page"
        assert config.buffer_size == 20
        assert "custom_pattern" in config.masking_patterns
        assert config.compression.format == "webp"
        assert config.compression.quality == 60
        assert config.retention.days == 7
        assert config.ci_mode is True

    def test_invalid_masking_patterns(self):
        data = {"masking_patterns": "not_a_list"}
        config = _dict_to_config(data)
        # Should fallback to defaults
        assert isinstance(config.masking_patterns, list)
        assert "password" in config.masking_patterns


class TestApplyEnvVars:
    """Test environment variable overrides."""

    def test_output_dir_override(self):
        config = TraceConfig()
        with patch.dict(os.environ, {"TRACE_VIEWER_OUTPUT_DIR": "/tmp/traces"}):
            config = _apply_env_vars(config)
        assert config.output_dir == "/tmp/traces"

    def test_capture_mode_override(self):
        config = TraceConfig()
        with patch.dict(os.environ, {"TRACE_VIEWER_CAPTURE_MODE": "on_failure"}):
            config = _apply_env_vars(config)
        assert config.capture_mode == "on_failure"

    def test_invalid_capture_mode_ignored(self):
        config = TraceConfig()
        with patch.dict(os.environ, {"TRACE_VIEWER_CAPTURE_MODE": "invalid"}):
            config = _apply_env_vars(config)
        assert config.capture_mode == "full"

    def test_buffer_size_override(self):
        config = TraceConfig()
        with patch.dict(os.environ, {"TRACE_VIEWER_BUFFER_SIZE": "25"}):
            config = _apply_env_vars(config)
        assert config.buffer_size == 25

    def test_invalid_buffer_size_ignored(self):
        config = TraceConfig()
        with patch.dict(os.environ, {"TRACE_VIEWER_BUFFER_SIZE": "not_a_number"}):
            config = _apply_env_vars(config)
        assert config.buffer_size == 10

    def test_ci_mode_override(self):
        config = TraceConfig()
        with patch.dict(os.environ, {"TRACE_VIEWER_CI_MODE": "true"}):
            config = _apply_env_vars(config)
        assert config.ci_mode is True


class TestLoadConfig:
    """Test full config loading chain."""

    def test_defaults_without_file(self):
        config = load_config()
        assert config.output_dir == "traces"

    def test_cli_overrides(self):
        config = load_config(cli_overrides={"output_dir": "cli_traces", "buffer_size": 5})
        assert config.output_dir == "cli_traces"
        assert config.buffer_size == 5

    def test_config_file(self, tmp_path):
        config_file = tmp_path / "trace-viewer.yml"
        config_file.write_text("output_dir: file_traces\ncapture_mode: on_failure\n")
        config = load_config(config_path=str(config_file))
        assert config.output_dir == "file_traces"
        assert config.capture_mode == "on_failure"

    def test_cli_overrides_config_file(self, tmp_path):
        config_file = tmp_path / "trace-viewer.yml"
        config_file.write_text("output_dir: file_traces\n")
        config = load_config(
            config_path=str(config_file),
            cli_overrides={"output_dir": "cli_wins"},
        )
        assert config.output_dir == "cli_wins"


class TestGenerateDefaultConfig:
    """Test default config generation."""

    def test_generates_yaml_string(self):
        content = generate_default_config()
        assert "output_dir: traces" in content
        assert "capture_mode: full" in content
        assert "masking_patterns:" in content
        assert "compression:" in content
        assert "retention:" in content

    def test_valid_yaml(self):
        import yaml

        content = generate_default_config()
        data = yaml.safe_load(content)
        assert isinstance(data, dict)
        assert data["output_dir"] == "traces"
