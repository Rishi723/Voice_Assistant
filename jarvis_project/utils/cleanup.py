"""
utils/cleanup.py
─────────────────
Registers an atexit handler to remove any leftover TTS temp files
(voice_*.mp3) that were not cleaned up during the session.
"""

import atexit
import glob
import os

from config import settings
from core import get_logger

log = get_logger(__name__)


def _cleanup_temp_files() -> None:
    pattern = f"{settings.TTS_TEMP_PREFIX}*{settings.TTS_TEMP_SUFFIX}"
    for f in glob.glob(pattern):
        try:
            os.remove(f)
        except Exception:
            pass


def register() -> None:
    """Call once at startup to arm the cleanup hook."""
    atexit.register(_cleanup_temp_files)
    log.debug("TTS temp-file cleanup registered.")
