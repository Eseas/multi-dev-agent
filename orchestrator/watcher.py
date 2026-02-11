"""Directory watcher for monitoring file changes."""

import time
import logging
from pathlib import Path
from typing import Callable, Optional, Set, Dict
from datetime import datetime
import hashlib


logger = logging.getLogger(__name__)


class DirectoryWatcher:
    """
    Watches a directory for file changes using polling.
    Falls back to polling if watchdog is not available.
    """

    def __init__(
        self,
        watch_path: Path,
        patterns: Optional[list] = None,
        poll_interval: float = 1.0
    ):
        """
        Initialize the directory watcher.

        Args:
            watch_path: Path to watch
            patterns: List of file patterns to watch (e.g., ['*.json', '*.md'])
            poll_interval: Polling interval in seconds
        """
        self.watch_path = Path(watch_path)
        self.patterns = patterns or ['*']
        self.poll_interval = poll_interval
        self._running = False
        self._file_states: Dict[Path, dict] = {}
        self._use_watchdog = False

        # Try to use watchdog if available
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            self._use_watchdog = True
            self._observer = None
            logger.info("Using watchdog for file monitoring")
        except ImportError:
            logger.info("Watchdog not available, using polling")

    def start(self, on_change: Callable[[Path, str], None]) -> None:
        """
        Start watching for file changes.

        Args:
            on_change: Callback function(file_path, event_type)
                      event_type: 'created', 'modified', 'deleted'
        """
        self._running = True

        if self._use_watchdog:
            self._start_watchdog(on_change)
        else:
            self._start_polling(on_change)

    def stop(self) -> None:
        """Stop watching."""
        self._running = False

        if self._use_watchdog and self._observer:
            self._observer.stop()
            self._observer.join()

    def _start_watchdog(self, on_change: Callable[[Path, str], None]) -> None:
        """Start watchdog-based monitoring."""
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class ChangeHandler(FileSystemEventHandler):
            def __init__(self, callback, patterns):
                self.callback = callback
                self.patterns = patterns

            def _matches_pattern(self, path):
                from fnmatch import fnmatch
                path_obj = Path(path)
                return any(fnmatch(path_obj.name, pattern) for pattern in self.patterns)

            def on_created(self, event):
                if not event.is_directory and self._matches_pattern(event.src_path):
                    self.callback(Path(event.src_path), 'created')

            def on_modified(self, event):
                if not event.is_directory and self._matches_pattern(event.src_path):
                    self.callback(Path(event.src_path), 'modified')

            def on_deleted(self, event):
                if not event.is_directory and self._matches_pattern(event.src_path):
                    self.callback(Path(event.src_path), 'deleted')

        event_handler = ChangeHandler(on_change, self.patterns)
        self._observer = Observer()
        self._observer.schedule(event_handler, str(self.watch_path), recursive=True)
        self._observer.start()

        logger.info(f"Started watchdog monitoring: {self.watch_path}")

        # Keep the watcher alive
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def _start_polling(self, on_change: Callable[[Path, str], None]) -> None:
        """Start polling-based monitoring."""
        logger.info(f"Started polling monitoring: {self.watch_path}")

        # Initialize file states
        self._scan_directory()

        try:
            while self._running:
                time.sleep(self.poll_interval)
                self._check_changes(on_change)
        except KeyboardInterrupt:
            self.stop()

    def _scan_directory(self) -> None:
        """Scan directory and record current file states."""
        if not self.watch_path.exists():
            return

        from fnmatch import fnmatch

        for file_path in self.watch_path.rglob('*'):
            if file_path.is_file():
                # Check if file matches any pattern
                if any(fnmatch(file_path.name, pattern) for pattern in self.patterns):
                    self._file_states[file_path] = self._get_file_state(file_path)

    def _get_file_state(self, file_path: Path) -> dict:
        """Get current state of a file."""
        try:
            stat = file_path.stat()
            return {
                'mtime': stat.st_mtime,
                'size': stat.st_size,
                'exists': True
            }
        except FileNotFoundError:
            return {'exists': False}

    def _check_changes(self, on_change: Callable[[Path, str], None]) -> None:
        """Check for file changes and invoke callback."""
        from fnmatch import fnmatch

        current_files = {}

        # Scan current files
        if self.watch_path.exists():
            for file_path in self.watch_path.rglob('*'):
                if file_path.is_file():
                    if any(fnmatch(file_path.name, pattern) for pattern in self.patterns):
                        current_files[file_path] = self._get_file_state(file_path)

        # Check for new and modified files
        for file_path, state in current_files.items():
            if file_path not in self._file_states:
                # New file
                on_change(file_path, 'created')
            elif state['mtime'] != self._file_states[file_path]['mtime']:
                # Modified file
                on_change(file_path, 'modified')

        # Check for deleted files
        for file_path in list(self._file_states.keys()):
            if file_path not in current_files:
                on_change(file_path, 'deleted')

        # Update state
        self._file_states = current_files


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
