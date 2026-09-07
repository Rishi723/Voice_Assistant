"""
services/music_service.py
──────────────────────────
Music playback engine: indexing, fuzzy search, play/pause/skip, volume.

All public functions are self-contained – they speak their own feedback.
"""

import difflib
import os
import random
import threading

import pygame

from config import settings
from core import get_logger, state
from speech import speak

log = get_logger(__name__)


# ── Index builder ─────────────────────────────────────────────────────────────

def build_music_index() -> None:
    """Scan MUSIC_SCAN_ROOTS and populate state.music_index."""
    state.music_index.clear()
    for root_path in settings.MUSIC_SCAN_ROOTS:
        if not os.path.isdir(root_path):
            continue
        for dirpath, _, files in os.walk(root_path):
            for f in files:
                if f.lower().endswith(settings.SUPPORTED_AUDIO):
                    full        = os.path.join(dirpath, f)
                    name_no_ext = os.path.splitext(f)[0].lower()
                    state.music_index[name_no_ext] = full
                    state.music_index[f.lower()]   = full
    log.info("Music index: %d tracks found.", len(state.music_index))


def find_song(query: str) -> tuple[str | None, str | None]:
    """Return (matched_name, path) or (None, None)."""
    query = query.lower().strip()
    if query in state.music_index:
        return query, state.music_index[query]
    matches = difflib.get_close_matches(
        query, state.music_index.keys(), n=1, cutoff=settings.MUSIC_FUZZY_CUTOFF
    )
    if matches:
        return matches[0], state.music_index[matches[0]]
    for name in state.music_index:
        if query in name or name in query:
            return name, state.music_index[name]
    return None, None


# ── Internal playback helpers ─────────────────────────────────────────────────

def _play_track(path: str) -> str | None:
    """Load and play a single track.  Returns display name or None on error."""
    try:
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        state.music_playing = True
        state.music_paused  = False
        name = os.path.splitext(os.path.basename(path))[0]
        log.info("[Music] Now playing: %s", name)
        return name
    except Exception:
        log.exception("[Music] Failed to play %s", path)
        return None


def _music_watcher() -> None:
    """Background thread: auto-advance to next track when current ends."""
    while state.music_playing:
        import time; time.sleep(1)
        if state.music_playing and not state.music_paused:
            if not pygame.mixer.music.get_busy():
                with state.music_lock:
                    if state.playlist:
                        state.playlist_pos = (state.playlist_pos + 1) % len(state.playlist)
                        _play_track(state.playlist[state.playlist_pos])


def _start_watcher() -> None:
    threading.Thread(target=_music_watcher, daemon=True).start()


# ── Public commands ───────────────────────────────────────────────────────────

def play_all(shuffle: bool = True) -> None:
    """Start playing all indexed tracks, optionally shuffled."""
    with state.music_lock:
        paths = list(set(state.music_index.values()))
        if not paths:
            speak("I couldn't find any music files on your computer.")
            return
        if shuffle:
            random.shuffle(paths)
        state.playlist     = paths
        state.playlist_pos = 0
        name = _play_track(state.playlist[0])
        if name:
            speak(f"Playing {name}")
    _start_watcher()


def play_song(query: str) -> None:
    """Find and play a specific song, queue the rest."""
    name, path = find_song(query)
    if not path:
        speak(f"I couldn't find a song called {query}.")
        return
    with state.music_lock:
        others = [p for p in set(state.music_index.values()) if p != path]
        random.shuffle(others)
        state.playlist     = [path] + others
        state.playlist_pos = 0
        _play_track(path)
        speak(f"Playing {name}")
    _start_watcher()


def stop() -> None:
    pygame.mixer.music.stop()
    state.music_playing = False
    state.music_paused  = False
    speak("Music stopped.")


def pause() -> None:
    if state.music_playing and not state.music_paused:
        pygame.mixer.music.pause()
        state.music_paused = True
        speak("Music paused.")
    else:
        speak("Nothing is playing right now.")


def resume() -> None:
    if state.music_paused:
        pygame.mixer.music.unpause()
        state.music_paused = False
        speak("Resuming music.")
    else:
        speak("Music is already playing.")


def next_track() -> None:
    with state.music_lock:
        if not state.playlist:
            speak("No playlist loaded. Say play music first.")
            return
        state.playlist_pos = (state.playlist_pos + 1) % len(state.playlist)
        name = _play_track(state.playlist[state.playlist_pos])
        if name:
            speak(f"Next: {name}")


def previous_track() -> None:
    with state.music_lock:
        if not state.playlist:
            speak("No playlist loaded. Say play music first.")
            return
        state.playlist_pos = (state.playlist_pos - 1) % len(state.playlist)
        name = _play_track(state.playlist[state.playlist_pos])
        if name:
            speak(f"Previous: {name}")


def current_track() -> None:
    if not state.music_playing:
        speak("No music is playing right now.")
        return
    if state.playlist and 0 <= state.playlist_pos < len(state.playlist):
        name = os.path.splitext(os.path.basename(state.playlist[state.playlist_pos]))[0]
        speak(f"Currently playing: {name}")


def volume_up() -> None:
    new_vol = min(1.0, pygame.mixer.music.get_volume() + settings.MUSIC_VOLUME_STEP)
    pygame.mixer.music.set_volume(new_vol)
    speak("Music volume increased.")


def volume_down() -> None:
    new_vol = max(0.0, pygame.mixer.music.get_volume() - settings.MUSIC_VOLUME_STEP)
    pygame.mixer.music.set_volume(new_vol)
    speak("Music volume decreased.")