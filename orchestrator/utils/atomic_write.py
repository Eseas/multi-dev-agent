"""Atomic file write operations to prevent race conditions."""

import os
import json
import tempfile
from pathlib import Path
from typing import Any, Union


def atomic_write(file_path: Union[str, Path], content: Union[str, dict], mode: str = 'w') -> None:
    """
    Write content to a file atomically using temp file + rename pattern.

    Args:
        file_path: Target file path
        content: Content to write (string or dict for JSON)
        mode: Write mode ('w' for text, 'wb' for binary)

    Raises:
        OSError: If write or rename fails
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Create temp file in the same directory to ensure same filesystem
    fd, tmp_path = tempfile.mkstemp(
        dir=file_path.parent,
        prefix=f'.{file_path.name}.',
        suffix='.tmp'
    )

    try:
        with os.fdopen(fd, mode) as f:
            if isinstance(content, dict):
                json.dump(content, f, indent=2, ensure_ascii=False)
            else:
                f.write(content)

        # Atomic rename
        os.replace(tmp_path, file_path)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
