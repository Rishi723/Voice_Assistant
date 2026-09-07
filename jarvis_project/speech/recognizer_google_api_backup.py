"""
speech/recognizer.py
────────────────────
Microphone input and Google speech-to-text helpers.

Public API
──────────
    calibrate()              – ambient-noise calibration (call once at startup)
    listen(timeout, phrase)  – short listen, returns lowercase string
    listen_long(...)         – longer dictation listen, preserves capitalisation
    listen_for_interrupt()   – blocking loop that sets state.stop_speaking on "stop"
"""

import speech_recognition as sr

from config import settings
from core import get_logger, state

log = get_logger(__name__)

# ── Shared recognizer and mic ────────────────────────────────────────────────
_recognizer = sr.Recognizer()
_recognizer.pause_threshold        = settings.SR_PAUSE_THRESHOLD
_recognizer.energy_threshold       = settings.SR_ENERGY_THRESHOLD
_recognizer.dynamic_energy_threshold = settings.SR_DYNAMIC_ENERGY

_mic = sr.Microphone()


# ── Public API ───────────────────────────────────────────────────────────────

def calibrate() -> None:
    """Calibrate for ambient noise once at startup."""
    log.info("Calibrating microphone…")
    with _mic as source:
        _recognizer.adjust_for_ambient_noise(source, duration=settings.SR_CALIBRATION_DURATION)
    log.info("Calibration done. Say '%s' to activate.", settings.WAKE_WORD)


def listen(
    timeout:      int = settings.SR_LISTEN_TIMEOUT,
    phrase_limit: int = settings.SR_LISTEN_PHRASE_LIMIT,
) -> str:
    """Short listen.  Returns a lowercase string or '' on failure."""
    with _mic as source:
        log.debug("Listening…")
        try:
            audio = _recognizer.listen(source, timeout=timeout,
                                       phrase_time_limit=phrase_limit)
        except sr.WaitTimeoutError:
            return ""
        except Exception:
            log.exception("Listen error")
            return ""

    try:
        command = _recognizer.recognize_google(audio).lower()
        log.info("You: %s", command)
        return command
    except sr.UnknownValueError:
        log.info("Could not understand audio.")
        return ""
    except sr.RequestError:
        log.warning("Google STT network error.")
        return ""


def listen_long(
    timeout:      int = settings.SR_LONG_TIMEOUT,
    phrase_limit: int = settings.SR_LONG_PHRASE_LIMIT,
) -> str:
    """Longer dictation listen.  Preserves original capitalisation."""
    with _mic as source:
        log.debug("Listening for dictation…")
        try:
            audio = _recognizer.listen(source, timeout=timeout,
                                       phrase_time_limit=phrase_limit)
        except sr.WaitTimeoutError:
            return ""
        except Exception:
            log.exception("Long-listen error")
            return ""

    try:
        text = _recognizer.recognize_google(audio)
        log.info("Dictated: %s", text)
        return text
    except sr.UnknownValueError:
        return ""
    except sr.RequestError:
        log.warning("Google STT network error (dictation).")
        return ""


def listen_for_interrupt() -> None:
    """
    Blocking loop that monitors microphone while TTS is active.
    Sets state.stop_speaking=True if the user says "stop".
    Run this in a daemon thread alongside speak_async().
    """
    ir = sr.Recognizer()
    ir.energy_threshold        = settings.SR_ENERGY_THRESHOLD
    ir.dynamic_energy_threshold = settings.SR_DYNAMIC_ENERGY

    while state.is_speaking:
        try:
            with sr.Microphone() as source:
                audio = ir.listen(
                    source,
                    timeout=settings.SR_INTERRUPT_TIMEOUT,
                    phrase_time_limit=settings.SR_INTERRUPT_PHRASE_LIMIT,
                )
            word = ir.recognize_google(audio).lower()
            log.debug("Interrupt heard: %s", word)
            if "stop" in word:
                state.stop_speaking = True
                log.info("Stop command detected – interrupting speech.")
                break
        except sr.WaitTimeoutError:
            continue
        except sr.UnknownValueError:
            continue
        except Exception:
            continue