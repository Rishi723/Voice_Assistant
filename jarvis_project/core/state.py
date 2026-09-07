"""
core/state.py
─────────────
One place for all shared mutable runtime state.
Import `state` (the singleton) everywhere instead of using bare globals.

Usage:
    from core.state import state
    state.is_speaking = True
    state.music_playing = False
"""

import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AppState:
    # ── Conversation memory ──────────────────────────────────────────────────
    memory: list[str] = field(default_factory=list)

    # ── TTS flags ────────────────────────────────────────────────────────────
    stop_speaking: bool = False
    is_speaking:   bool = False

    # ── Music playback ───────────────────────────────────────────────────────
    music_playing: bool = False
    music_paused:  bool = False
    playlist:      list[str] = field(default_factory=list)
    playlist_pos:  int  = 0
    music_lock:    threading.Lock = field(default_factory=threading.Lock)

    # ── App databases (populated at startup) ────────────────────────────────
    installed_programs: dict[str, str] = field(default_factory=dict)
    store_apps:         dict[str, str] = field(default_factory=dict)
    music_index:        dict[str, str] = field(default_factory=dict)

    # ── Session ──────────────────────────────────────────────────────────────
    assistant_active: bool = False


# Module-level singleton – import this object, don't instantiate AppState again.
state = AppState()