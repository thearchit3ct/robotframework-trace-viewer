"""ReportPortal integration module for uploading trace data.

This module provides the ReportPortalExporter class which uploads
Robot Framework trace data to a ReportPortal server for centralized
test result reporting and analysis.

Note: Requires the 'reportportal-client' package to be installed.
Install with: pip install reportportal-client
"""

import json
import logging
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ReportPortalExporter:
    """Exports Robot Framework traces to ReportPortal.

    The ReportPortalExporter uploads test traces to a ReportPortal server,
    including test results, keyword steps, screenshots, and logs.

    ReportPortal hierarchy mapping:
    - Launch: Test suite or collection of traces
    - Test: Individual test case
    - Step: Keywords within the test

    Attributes:
        endpoint: ReportPortal server URL.
        project: ReportPortal project name.
        api_key: API key for authentication.
        launch_name: Name for the launch in ReportPortal.

    Example:
        >>> exporter = ReportPortalExporter(
        ...     endpoint="https://reportportal.example.com",
        ...     project="robot_framework",
        ...     api_key="your_api_key"
        ... )
        >>> exporter.export_trace(Path("./traces/test_20250120"))
    """

    def __init__(
        self,
        endpoint: str,
        project: str,
        api_key: str,
        launch_name: Optional[str] = None,
        launch_description: Optional[str] = None,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize ReportPortalExporter.

        Args:
            endpoint: ReportPortal server URL (e.g., https://rp.example.com).
            project: ReportPortal project name.
            api_key: API key for authentication (UUID or token).
            launch_name: Optional name for the launch. Defaults to 'Robot Framework Traces'.
            launch_description: Optional description for the launch.
            verify_ssl: Whether to verify SSL certificates. Defaults to True.

        Raises:
            ImportError: If reportportal-client is not installed.
        """
        self.endpoint = endpoint.rstrip("/")
        self.project = project
        self.api_key = api_key
        self.launch_name = launch_name or "Robot Framework Traces"
        self.launch_description = launch_description or ""
        self.verify_ssl = verify_ssl

        self._service: Optional[Any] = None
        self._launch_uuid: Optional[str] = None
        self._check_dependencies()

    def _check_dependencies(self) -> None:
        """Check if reportportal-client is installed.

        Raises:
            ImportError: If reportportal-client is not available.
        """
        try:
            from reportportal_client import RPClient  # type: ignore[import-not-found]  # noqa: F401
        except ImportError:
            raise ImportError(
                "ReportPortal client not installed. "
                "Install with: pip install reportportal-client"
            ) from None

    def _get_client(self) -> Any:
        """Get or create ReportPortal client instance.

        Returns:
            RPClient instance.
        """
        if self._service is None:
            from reportportal_client import RPClient  # type: ignore[import-not-found]

            self._service = RPClient(
                endpoint=self.endpoint,
                project=self.project,
                api_key=self.api_key,
                verify_ssl=self.verify_ssl,
            )
        return self._service

    def start_launch(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        attributes: Optional[list[dict[str, str]]] = None,
    ) -> str:
        """Start a new launch in ReportPortal.

        Args:
            name: Launch name. Defaults to configured launch_name.
            description: Launch description.
            attributes: Optional list of attributes (key-value pairs).

        Returns:
            Launch UUID.
        """
        client = self._get_client()

        self._launch_uuid = client.start_launch(
            name=name or self.launch_name,
            start_time=self._get_timestamp(),
            description=description or self.launch_description,
            attributes=attributes or [],
        )

        return self._launch_uuid

    def finish_launch(self) -> None:
        """Finish the current launch in ReportPortal."""
        if self._service is not None and self._launch_uuid is not None:
            self._service.finish_launch(end_time=self._get_timestamp())
            self._service.terminate()
            self._service = None
            self._launch_uuid = None

    def export_trace(
        self,
        trace_dir: Path,
        launch_uuid: Optional[str] = None,
        include_screenshots: bool = True,
    ) -> dict[str, Any]:
        """Export a single trace to ReportPortal.

        Uploads the test results from a trace directory to ReportPortal,
        including keywords as steps and screenshots as attachments.

        Args:
            trace_dir: Path to the trace directory.
            launch_uuid: Optional launch UUID. If not provided, uses current launch
                or creates a new one.
            include_screenshots: Whether to upload screenshots. Defaults to True.

        Returns:
            Dictionary with export results including test UUID and step count.

        Raises:
            FileNotFoundError: If trace_dir doesn't exist or has no manifest.
        """
        trace_dir = Path(trace_dir)

        if not trace_dir.exists():
            raise FileNotFoundError(f"Trace directory not found: {trace_dir}")

        manifest_path = trace_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        # Load trace data
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        # Ensure launch exists
        if launch_uuid is None:
            if self._launch_uuid is None:
                self.start_launch()
            launch_uuid = self._launch_uuid

        client = self._get_client()

        # Start test item
        test_name = manifest.get("test_name", "Unknown Test")
        test_status = manifest.get("status", "UNKNOWN")
        test_start = manifest.get("start_time", "")
        test_message = manifest.get("message", "")

        test_uuid = client.start_test_item(
            name=test_name,
            start_time=self._parse_timestamp(test_start),
            item_type="TEST",
            description=manifest.get("doc", ""),
            attributes=self._build_attributes(manifest),
        )

        # Process keywords as steps
        steps_count = 0
        keywords_dir = trace_dir / "keywords"
        if keywords_dir.exists():
            keyword_dirs = sorted(keywords_dir.iterdir())
            for kw_dir in keyword_dirs:
                if not kw_dir.is_dir():
                    continue

                self._export_keyword(client, kw_dir, test_uuid, include_screenshots)
                steps_count += 1

        # Finish test item
        rp_status = self._map_status(test_status)
        client.finish_test_item(
            item_id=test_uuid,
            end_time=self._get_timestamp(),
            status=rp_status,
            issue=self._build_issue(test_status, test_message) if rp_status == "FAILED" else None,
        )

        return {
            "test_uuid": test_uuid,
            "test_name": test_name,
            "status": test_status,
            "steps_count": steps_count,
        }

    def export_traces(
        self,
        traces_dir: Path,
        include_screenshots: bool = True,
    ) -> dict[str, Any]:
        """Export all traces from a directory to ReportPortal.

        Creates a new launch and exports all trace directories found
        within the specified directory.

        Args:
            traces_dir: Path to the directory containing trace folders.
            include_screenshots: Whether to upload screenshots.

        Returns:
            Dictionary with export summary including total tests and status counts.
        """
        traces_dir = Path(traces_dir)

        if not traces_dir.exists():
            raise FileNotFoundError(f"Traces directory not found: {traces_dir}")

        # Find all trace directories
        trace_dirs = []
        for item in traces_dir.iterdir():
            if item.is_dir() and (item / "manifest.json").exists():
                trace_dirs.append(item)

        if not trace_dirs:
            return {
                "total": 0,
                "exported": 0,
                "failed": 0,
                "errors": [],
            }

        # Start launch
        self.start_launch(description=f"Exported {len(trace_dirs)} traces from {traces_dir.name}")

        results = {
            "total": len(trace_dirs),
            "exported": 0,
            "failed": 0,
            "errors": [],
            "tests": [],
        }

        # Export each trace
        for trace_dir in trace_dirs:
            try:
                result = self.export_trace(
                    trace_dir,
                    launch_uuid=self._launch_uuid,
                    include_screenshots=include_screenshots,
                )
                results["exported"] += 1  # type: ignore[operator]
                results["tests"].append(result)  # type: ignore[attr-defined]
            except Exception as e:
                results["failed"] += 1  # type: ignore[operator]
                results["errors"].append(  # type: ignore[attr-defined]
                    {"trace": str(trace_dir), "error": str(e)}
                )
                logger.warning(f"Failed to export trace {trace_dir}: {e}")

        # Finish launch
        self.finish_launch()

        return results

    def _export_keyword(
        self,
        client: Any,
        kw_dir: Path,
        parent_uuid: str,
        include_screenshots: bool,
    ) -> None:
        """Export a single keyword as a step in ReportPortal.

        Args:
            client: ReportPortal client instance.
            kw_dir: Path to the keyword directory.
            parent_uuid: UUID of the parent test item.
            include_screenshots: Whether to upload screenshots.
        """
        metadata_path = kw_dir / "metadata.json"
        if not metadata_path.exists():
            return

        with open(metadata_path, encoding="utf-8") as f:
            metadata = json.load(f)

        kw_name = metadata.get("name", "Unknown")
        kw_status = metadata.get("status", "UNKNOWN")
        kw_message = metadata.get("message", "")

        # Start step
        step_uuid = client.start_test_item(
            name=kw_name,
            start_time=self._parse_timestamp(metadata.get("start_time", "")),
            item_type="STEP",
            parent_item_id=parent_uuid,
            description=self._build_step_description(metadata),
        )

        # Log keyword arguments
        args = metadata.get("args", [])
        if args:
            client.log(
                time=self._get_timestamp(),
                message=f"Arguments: {', '.join(str(a) for a in args)}",
                level="INFO",
                item_id=step_uuid,
            )

        # Log keyword message if present
        if kw_message:
            level = "ERROR" if kw_status == "FAIL" else "INFO"
            client.log(
                time=self._get_timestamp(),
                message=kw_message,
                level=level,
                item_id=step_uuid,
            )

        # Upload screenshot
        if include_screenshots:
            screenshot_path = kw_dir / "screenshot.png"
            if screenshot_path.exists():
                self._upload_attachment(client, step_uuid, screenshot_path, "Screenshot")

        # Finish step
        client.finish_test_item(
            item_id=step_uuid,
            end_time=self._get_timestamp(),
            status=self._map_status(kw_status),
        )

    def _upload_attachment(
        self,
        client: Any,
        item_uuid: str,
        file_path: Path,
        description: str,
    ) -> None:
        """Upload a file as an attachment to ReportPortal.

        Args:
            client: ReportPortal client instance.
            item_uuid: UUID of the test item.
            file_path: Path to the file to upload.
            description: Description for the attachment.
        """
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            mime_type = "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                content = f.read()

            client.log(
                time=self._get_timestamp(),
                message=description,
                level="INFO",
                item_id=item_uuid,
                attachment={
                    "name": file_path.name,
                    "data": content,
                    "mime": mime_type,
                },
            )
        except Exception as e:
            logger.debug(f"Failed to upload attachment {file_path}: {e}")

    def _map_status(self, rf_status: str) -> str:
        """Map Robot Framework status to ReportPortal status.

        Args:
            rf_status: Robot Framework status string.

        Returns:
            ReportPortal status string.
        """
        status_map = {
            "PASS": "PASSED",
            "FAIL": "FAILED",
            "SKIP": "SKIPPED",
            "NOT RUN": "SKIPPED",
            "NOT_RUN": "SKIPPED",
        }
        return status_map.get(rf_status.upper(), "FAILED")

    def _build_attributes(self, manifest: dict[str, Any]) -> list[dict[str, str]]:
        """Build attributes list from manifest data.

        Args:
            manifest: Trace manifest dictionary.

        Returns:
            List of attribute dictionaries with 'key' and 'value'.
        """
        attributes = []

        if manifest.get("suite_name"):
            attributes.append({"key": "suite", "value": manifest["suite_name"]})

        if manifest.get("tags"):
            for tag in manifest["tags"]:
                attributes.append({"key": "tag", "value": str(tag)})

        if manifest.get("rf_version"):
            attributes.append({"key": "rf_version", "value": manifest["rf_version"]})

        return attributes

    def _build_step_description(self, metadata: dict[str, Any]) -> str:
        """Build step description from keyword metadata.

        Args:
            metadata: Keyword metadata dictionary.

        Returns:
            Description string.
        """
        parts = []

        if metadata.get("library"):
            parts.append(f"Library: {metadata['library']}")

        if metadata.get("duration_ms"):
            parts.append(f"Duration: {metadata['duration_ms']}ms")

        return " | ".join(parts) if parts else ""

    def _build_issue(self, status: str, message: str) -> Optional[dict[str, Any]]:
        """Build issue info for failed tests.

        Args:
            status: Test status.
            message: Test failure message.

        Returns:
            Issue dictionary or None.
        """
        if status != "FAIL":
            return None

        return {
            "issue_type": "TI001",  # To Investigate
            "comment": message[:1000] if message else "Test failed",
        }

    def _get_timestamp(self) -> str:
        """Get current timestamp in ReportPortal format.

        Returns:
            Timestamp string in milliseconds.
        """
        return str(int(datetime.now().timestamp() * 1000))

    def _parse_timestamp(self, iso_string: str) -> str:
        """Parse ISO timestamp to ReportPortal format.

        Args:
            iso_string: ISO 8601 timestamp string.

        Returns:
            Timestamp string in milliseconds.
        """
        if not iso_string:
            return self._get_timestamp()

        try:
            # Handle various ISO formats
            if iso_string.endswith("Z"):
                iso_string = iso_string[:-1] + "+00:00"

            dt = datetime.fromisoformat(iso_string)
            return str(int(dt.timestamp() * 1000))
        except (ValueError, TypeError):
            return self._get_timestamp()
