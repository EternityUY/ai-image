"""Music selector — randomly picks a music file from a configured folder."""

import logging
import os
import random

logger = logging.getLogger(__name__)

# Supported audio extensions
_AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"}


def list_music_files(music_dir: str) -> list[str]:
    """List all supported audio files in the given directory (non-recursive).

    Args:
        music_dir: Path to the directory containing music files.

    Returns:
        Sorted list of absolute paths to audio files.

    Raises:
        FileNotFoundError: If the directory does not exist.
    """
    if not os.path.isdir(music_dir):
        raise FileNotFoundError(f"Music directory not found: {music_dir}")

    files = []
    for fname in os.listdir(music_dir):
        ext = os.path.splitext(fname)[1].lower()
        if ext in _AUDIO_EXTS:
            files.append(os.path.abspath(os.path.join(music_dir, fname)))

    files.sort()
    return files


def select_random_music(music_dir: str) -> str:
    """Randomly pick a music file from the directory.

    Args:
        music_dir: Path to music directory.

    Returns:
        Absolute path to the selected music file.

    Raises:
        FileNotFoundError: If no audio files found.
    """
    files = list_music_files(music_dir)
    if not files:
        raise FileNotFoundError(
            f"No audio files found in '{music_dir}'. "
            f"Supported formats: {', '.join(_AUDIO_EXTS)}"
        )

    selected = random.choice(files)
    logger.info("Selected music: %s (from %d available file(s))", selected, len(files))
    return selected
