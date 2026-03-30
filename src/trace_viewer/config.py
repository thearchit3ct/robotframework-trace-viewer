"""Configuration management for Robot Framework Trace Viewer.

Supports loading from trace-viewer.yml files, environment variables,
and CLI arguments with a clear precedence order:
CLI args > env vars > config file > defaults.
"""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CompressionConfig:
    """Compression settings for screenshots and DOM snapshots."""

    format: str = "png"  # png | webp
    quality: int = 80
    max_dom_size_kb: int = 500


@dataclass
class RetentionConfig:
    """Retention policy for trace data."""

    days: int = 30
    max_traces: int = 100


@dataclass
class TraceConfig:
    """Main configuration for Trace Viewer.

    Attributes:
        output_dir: Directory where trace data will be saved.
        capture_mode: When to capture - full | on_failure | disabled.
        screenshot_mode: Screenshot type - viewport | full_page.
        buffer_size: Number of keywords to keep in ring buffer for on_failure mode.
        masking_patterns: List of patterns to mask in variable values.
        compression: Compression settings.
        retention: Retention policy settings.
        ci_mode: Enable CI/CD optimizations.
    """

    output_dir: str = "traces"
    capture_mode: str = "full"
    screenshot_mode: str = "viewport"
    buffer_size: int = 10
    masking_patterns: list[str] = field(
        default_factory=lambda: [
            "password",
            "secret",
            "token",
            "key",
            "credential",
            "auth",
            "api_key",
        ]
    )
    compression: CompressionConfig = field(default_factory=CompressionConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)
    ci_mode: bool = False


def _find_config_file(start_dir: Path | None = None) -> Path | None:
    """Search for trace-viewer.yml in standard locations.

    Search order:
    1. ./trace-viewer.yml (current or specified directory)
    2. ~/.trace-viewer.yml (user home)

    Args:
        start_dir: Directory to start searching from. Defaults to cwd.

    Returns:
        Path to config file if found, None otherwise.
    """
    if start_dir is None:
        start_dir = Path.cwd()

    # Check local config
    local_config = start_dir / "trace-viewer.yml"
    if local_config.exists():
        return local_config

    # Check home directory
    home_config = Path.home() / ".trace-viewer.yml"
    if home_config.exists():
        return home_config

    return None


def _load_yaml_file(path: Path) -> dict[str, Any]:
    """Load and parse a YAML file.

    Args:
        path: Path to the YAML file.

    Returns:
        Parsed YAML content as dictionary.
    """
    try:
        import yaml
    except ImportError as err:
        raise ImportError(
            "PyYAML is required for config file support. " "Install with: pip install pyyaml"
        ) from err

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data if isinstance(data, dict) else {}


def _apply_env_vars(config: TraceConfig) -> TraceConfig:
    """Override config values from TRACE_VIEWER_* environment variables.

    Supported env vars:
        TRACE_VIEWER_OUTPUT_DIR
        TRACE_VIEWER_CAPTURE_MODE
        TRACE_VIEWER_SCREENSHOT_MODE
        TRACE_VIEWER_BUFFER_SIZE
        TRACE_VIEWER_CI_MODE
        TRACE_VIEWER_COMPRESSION_FORMAT
        TRACE_VIEWER_COMPRESSION_QUALITY

    Args:
        config: Config to override.

    Returns:
        Config with env var overrides applied.
    """
    if val := os.environ.get("TRACE_VIEWER_OUTPUT_DIR"):
        config.output_dir = val
    if (val := os.environ.get("TRACE_VIEWER_CAPTURE_MODE")) and val in (
        "full",
        "on_failure",
        "disabled",
    ):
        config.capture_mode = val
    if (val := os.environ.get("TRACE_VIEWER_SCREENSHOT_MODE")) and val in ("viewport", "full_page"):
        config.screenshot_mode = val
    if val := os.environ.get("TRACE_VIEWER_BUFFER_SIZE"):
        with contextlib.suppress(ValueError):
            config.buffer_size = int(val)
    if val := os.environ.get("TRACE_VIEWER_CI_MODE"):
        config.ci_mode = val.lower() in ("1", "true", "yes")
    if (val := os.environ.get("TRACE_VIEWER_COMPRESSION_FORMAT")) and val in ("png", "webp"):
        config.compression.format = val
    if val := os.environ.get("TRACE_VIEWER_COMPRESSION_QUALITY"):
        with contextlib.suppress(ValueError):
            config.compression.quality = int(val)

    return config


def _dict_to_config(data: dict[str, Any]) -> TraceConfig:
    """Convert a dictionary (from YAML) to TraceConfig.

    Args:
        data: Dictionary from parsed YAML.

    Returns:
        TraceConfig populated from dictionary values.
    """
    compression_data = data.get("compression", {})
    compression = CompressionConfig(
        format=compression_data.get("format", "png"),
        quality=compression_data.get("quality", 80),
        max_dom_size_kb=compression_data.get("max_dom_size_kb", 500),
    )

    retention_data = data.get("retention", {})
    retention = RetentionConfig(
        days=retention_data.get("days", 30),
        max_traces=retention_data.get("max_traces", 100),
    )

    masking = data.get("masking_patterns")
    if masking is not None and not isinstance(masking, list):
        masking = None

    return TraceConfig(
        output_dir=data.get("output_dir", "traces"),
        capture_mode=data.get("capture_mode", "full"),
        screenshot_mode=data.get("screenshot_mode", "viewport"),
        buffer_size=data.get("buffer_size", 10),
        masking_patterns=masking if masking is not None else TraceConfig().masking_patterns,
        compression=compression,
        retention=retention,
        ci_mode=data.get("ci_mode", False),
    )


def load_config(
    config_path: str | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> TraceConfig:
    """Load configuration with full precedence chain.

    Precedence (highest to lowest):
    1. CLI arguments (cli_overrides)
    2. Environment variables (TRACE_VIEWER_*)
    3. Config file (trace-viewer.yml)
    4. Defaults

    Args:
        config_path: Explicit path to config file. If None, auto-discovers.
        cli_overrides: Dictionary of CLI argument overrides.

    Returns:
        Fully resolved TraceConfig.
    """
    # Start with defaults
    config = TraceConfig()

    # Load from config file
    path = Path(config_path) if config_path else _find_config_file()
    if path and path.exists():
        data = _load_yaml_file(path)
        config = _dict_to_config(data)

    # Apply environment variable overrides
    config = _apply_env_vars(config)

    # Apply CLI overrides
    if cli_overrides:
        for key, value in cli_overrides.items():
            if value is not None and hasattr(config, key):
                setattr(config, key, value)

    return config


def generate_default_config() -> str:
    """Generate default trace-viewer.yml content.

    Returns:
        YAML string with default configuration and comments.
    """
    return """# Robot Framework Trace Viewer Configuration
# Place this file as ./trace-viewer.yml or ~/.trace-viewer.yml

# Output directory for traces
output_dir: traces

# Capture mode: full | on_failure | disabled
capture_mode: full

# Screenshot mode: viewport | full_page
screenshot_mode: viewport

# Ring buffer size for on_failure mode (number of keywords to keep)
buffer_size: 10

# Patterns to mask in captured variables (case-insensitive substring match)
masking_patterns:
  - password
  - secret
  - token
  - key
  - credential
  - auth
  - api_key

# Compression settings
compression:
  format: png          # png | webp
  quality: 80          # WebP quality (1-100)
  max_dom_size_kb: 500 # Truncate DOM snapshots larger than this

# Retention policy
retention:
  days: 30             # Delete traces older than N days
  max_traces: 100      # Maximum number of traces to keep

# CI/CD mode (enables on_failure capture + CI-friendly output)
ci_mode: false
"""
