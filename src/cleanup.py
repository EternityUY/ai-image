"""Cleanup — remove output folders older than max_age_days."""

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


def clean_old_folders(cfg: dict[str, Any] | None = None, output_dir: str | None = None) -> list[str]:
    """Delete output subfolders older than max_age_days.

    Args:
        cfg: Config dict. If None, defaults are used.
        output_dir: Override output directory path.

    Returns:
        List of deleted folder paths.
    """
    max_age_days = (cfg or {}).get("cleanup", {}).get("max_age_days", 7)
    max_age_seconds = max_age_days * 24 * 3600
    now = time.time()
    target_dir = Path(output_dir or _OUTPUT_DIR)

    if not target_dir.is_dir():
        return []

    deleted: list[str] = []
    for entry in sorted(target_dir.iterdir()):
        if not entry.is_dir():
            continue
        try:
            mtime = entry.stat().st_mtime
        except OSError:
            continue
        age = now - mtime
        if age > max_age_seconds:
            shutil.rmtree(str(entry), ignore_errors=True)
            if not entry.exists():
                deleted.append(str(entry))

    if deleted:
        logger.info("Cleaned %d old folder(s).", len(deleted))
    return deleted
