"""
tools/registry.py
──────────────────
Central tool registry.

Every tool is a plain callable registered under a unique string name.
All implementations live in the existing command/service modules –
nothing is duplicated here; we only map names to functions.

To add a new tool:
    1. Implement the logic in the appropriate commands/ or services/ module.
    2. Add one entry to REGISTRY below.
"""

from commands.app_commands     import handle_open, handle_close, handle_minimize
from commands.system_commands  import (
    volume_up, volume_down, mute, switch_tab,
    lock_screen, shutdown, restart, sleep, refresh_apps,
)
from services.music_service    import (
    play_all, play_song, stop, pause, resume,
    next_track, previous_track, current_track,
    volume_up   as music_vol_up,
    volume_down as music_vol_down,
)
from commands.notepad_commands import (
    write_in_notepad, write_in_notepad_and_save, clear_notepad,
)

# ---------------------------------------------------------------------------
# Thin adapter wrappers
# The registry stores zero-argument callables OR callables that accept only
# the keyword arguments passed by the executor.  Where existing functions
# take positional arguments we wrap them so the executor can call them with
# **arguments uniformly.
# ---------------------------------------------------------------------------

def _open_app(app: str = "") -> bool:
    return handle_open(app)

def _close_app(app: str = "") -> bool:
    return handle_close(app)

def _minimize_app(app: str = "") -> bool:
    return handle_minimize(app)

def _play_music(query: str = "") -> None:
    if query:
        play_song(query)
    else:
        play_all()

def _write_notepad(text: str = "", filename: str = "") -> bool:
    if filename:
        return write_in_notepad_and_save(text, filename)
    return write_in_notepad(text)

# ---------------------------------------------------------------------------
# REGISTRY  –  tool_name → callable
# ---------------------------------------------------------------------------

REGISTRY: dict[str, callable] = {
    # ── App management ───────────────────────────────────────────────────────
    "open_app":      _open_app,
    "close_app":     _close_app,
    "minimize_app":  _minimize_app,

    # ── Music ────────────────────────────────────────────────────────────────
    "play_music":       _play_music,
    "stop_music":       lambda **_: stop(),
    "pause_music":      lambda **_: pause(),
    "resume_music":     lambda **_: resume(),
    "next_track":       lambda **_: next_track(),
    "previous_track":   lambda **_: previous_track(),
    "current_track":    lambda **_: current_track(),
    "music_volume_up":  lambda **_: music_vol_up(),
    "music_volume_down":lambda **_: music_vol_down(),

    # ── System volume ────────────────────────────────────────────────────────
    "volume_up":    lambda **_: volume_up(),
    "volume_down":  lambda **_: volume_down(),
    "mute":         lambda **_: mute(),
    "switch_tab":   lambda **_: switch_tab(),

    # ── System power ─────────────────────────────────────────────────────────
    "lock_screen":   lambda **_: lock_screen(),
    "shutdown_pc":   lambda **_: shutdown(),
    "restart_pc":    lambda **_: restart(),
    "sleep_pc":      lambda **_: sleep(),
    "refresh_apps":  lambda **_: refresh_apps(),

    # ── Notepad ──────────────────────────────────────────────────────────────
    "write_notepad": _write_notepad,
    "clear_notepad": lambda **_: clear_notepad(),
}
