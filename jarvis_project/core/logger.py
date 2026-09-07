"""
core/logger.py
──────────────
Centralised logging configuration.
All modules should do:
    from core.logger import get_logger
    log = get_logger(__name__)
"""

import logging
import sys
from pathlib import Path

_LOG_FILE = Path("data/alex.log")
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FMT = "%H:%M:%S"


def _configure_root() -> None:
    root = logging.getLogger()
    if root.handlers:
        return  # already configured
    root.setLevel(logging.DEBUG)

    # Console – INFO and above, coloured by level
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(_FMT, _DATE_FMT))
    root.addHandler(ch)

    # File – DEBUG and above
    fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_FMT, _DATE_FMT))
    root.addHandler(fh)


_configure_root()


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (call once per module at the top)."""
    return logging.getLogger(name)