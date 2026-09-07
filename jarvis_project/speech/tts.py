"""
speech/tts.py
─────────────
Text-to-speech using edge_tts + pygame.

Public API
──────────
    speak(text)         – blocking, waits until audio finishes (or is interrupted)
    speak_async(text)   – non-blocking, returns the Thread
"""

import asyncio
import os
import threading
import uuid

import edge_tts
import pygame

from config import settings
from core import get_logger, state

log = get_logger(__name__)

# ── pygame mixer bootstrap ───────────────────────────────────────────────────
pygame.mixer.init()
pygame.mixer.set_num_channels(settings.TTS_PYGAME_CHANNELS)
_TTS_CHANNEL = pygame.mixer.Channel(settings.TTS_CHANNEL_INDEX)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _tmp_filename() -> str:
    return f"{settings.TTS_TEMP_PREFIX}{uuid.uuid4()}{settings.TTS_TEMP_SUFFIX}"


async def _async_speak(text: str) -> None:
    filename = _tmp_filename()
    try:
        communicate = edge_tts.Communicate(text=text, voice=settings.TTS_VOICE)
        await communicate.save(filename)
        await asyncio.sleep(settings.TTS_STARTUP_DELAY)

        sound = pygame.mixer.Sound(filename)
        _TTS_CHANNEL.play(sound)

        while _TTS_CHANNEL.get_busy():
            if state.stop_speaking:
                _TTS_CHANNEL.stop()
                log.debug("Speech interrupted by stop flag.")
                break
            await asyncio.sleep(0.05)

    except Exception:
        log.exception("TTS error for text: %.60s", text)
    finally:
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except OSError:
            pass


# ── Public API ───────────────────────────────────────────────────────────────

def speak(text: str) -> None:
    """Blocking TTS.  Ducks background music while speaking."""
    state.stop_speaking = False
    state.is_speaking   = True
    log.info("Assistant: %s", text)

    was_playing = pygame.mixer.music.get_busy() and not state.music_paused
    if was_playing:
        pygame.mixer.music.set_volume(settings.TTS_MUSIC_DUCK_VOL)

    asyncio.run(_async_speak(text))

    state.is_speaking = False
    if was_playing:
        pygame.mixer.music.set_volume(1.0)


def speak_async(text: str) -> threading.Thread:
    """Non-blocking TTS.  Returns the thread so callers can .join() if needed."""
    t = threading.Thread(target=speak, args=(text,), daemon=True)
    t.start()
    return t