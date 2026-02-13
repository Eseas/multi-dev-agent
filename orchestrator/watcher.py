"""File wait helpers for monitoring file events."""

import time
import logging
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


class FileWaitHelper:
    """Helper class for waiting on specific file events."""

    @staticmethod
    def wait_for_file(
        file_path: Path,
        timeout: float = 60.0,
        poll_interval: float = 0.5
    ) -> bool:
        """
        Wait for a file to be created.

        Args:
            file_path: Path to wait for
            timeout: Maximum wait time in seconds
            poll_interval: Check interval in seconds

        Returns:
            True if file was created, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if file_path.exists():
                return True
            time.sleep(poll_interval)

        return False

    @staticmethod
    def wait_for_file_content(
        file_path: Path,
        expected_key: str,
        timeout: float = 60.0,
        poll_interval: float = 0.5
    ) -> Optional[dict]:
        """
        Wait for a JSON file with specific key to be created/updated.

        Args:
            file_path: Path to JSON file
            expected_key: Key that must exist in the JSON
            timeout: Maximum wait time
            poll_interval: Check interval

        Returns:
            Parsed JSON content if found, None if timeout
        """
        import json

        start_time = time.time()

        while time.time() - start_time < timeout:
            if file_path.exists():
                try:
                    content = json.loads(file_path.read_text())
                    if expected_key in content:
                        return content
                except (json.JSONDecodeError, OSError):
                    pass

            time.sleep(poll_interval)

        return None
