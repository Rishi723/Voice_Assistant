"""
speech/recognizer.py
────────────────────
Microphone input and Faster-Whisper speech-to-text helpers.

Public API
──────────
    calibrate()              – ambient-noise calibration (call once at startup)
    listen(timeout, phrase)  – short listen, returns lowercase string
    listen_long(...)         – longer dictation listen, preserves capitalisation
    listen_for_interrupt()   – blocking loop that sets state.stop_speaking on "stop"
"""

import speech_recognition as sr
from faster_whisper import WhisperModel
import tempfile
import os
import wave

from config import settings
from core import get_logger, state

log = get_logger(__name__)

# ── Shared recognizer and mic ────────────────────────────────────────────────
_recognizer = sr.Recognizer()
_recognizer.pause_threshold          = settings.SR_PAUSE_THRESHOLD
_recognizer.energy_threshold         = settings.SR_ENERGY_THRESHOLD
_recognizer.dynamic_energy_threshold = settings.SR_DYNAMIC_ENERGY

_mic = sr.Microphone()

# ── Faster-Whisper model (loaded once) ───────────────────────────────────────
_whisper_model = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8"
)


def _transcribe_whisper(audio) -> str:
    """
    Convert SpeechRecognition AudioData -> text using Faster-Whisper.
    Returns empty string on any failure.
    """
    wav_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            wav_path = tmp.name

        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(audio.sample_width)
            wf.setframerate(audio.sample_rate)
            wf.writeframes(audio.get_wav_data())

        segments, _ = _whisper_model.transcribe(
            wav_path,
            language="en",   # auto-detect Telugu / English
            beam_size=5
        )

        return " ".join(seg.text for seg in segments).strip()

    except Exception:
        log.exception("Whisper transcription error")
        return ""

    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)


# ── Public API ────────────────────────────────────────────────────────────────

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
    """Short listen. Returns a lowercase string or '' on failure."""
    try:
        with _mic as source:
            log.info("Listening…")
            audio = _recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=phrase_limit,
            )
    except sr.WaitTimeoutError:
        return ""
    except Exception:
        log.exception("Listen error")
        return ""

    result = _transcribe_whisper(audio).lower()
    if result:
        log.info("You: %s", result)
    return result


def listen_long(
    timeout:      int = settings.SR_LONG_TIMEOUT,
    phrase_limit: int = settings.SR_LONG_PHRASE_LIMIT,
) -> str:
    """Longer dictation listen. Preserves original capitalisation."""
    try:
        with _mic as source:
            log.debug("Listening for dictation…")
            audio = _recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=phrase_limit,
            )
    except sr.WaitTimeoutError:
        return ""
    except Exception:
        log.exception("Long-listen error")
        return ""

    result = _transcribe_whisper(audio)
    if result:
        log.info("Dictated: %s", result)
    return result


def listen_for_interrupt() -> None:
    """
    Blocking loop that monitors the microphone while TTS is active.
    Sets state.stop_speaking=True if the user says "stop".
    Run this in a daemon thread alongside speak_async().
    """
    ir = sr.Recognizer()
    ir.energy_threshold          = settings.SR_ENERGY_THRESHOLD
    ir.dynamic_energy_threshold  = settings.SR_DYNAMIC_ENERGY

    # Reuse a single mic instance for the whole interrupt session
    with sr.Microphone() as interrupt_source:
        while state.is_speaking:
            try:
                audio = ir.listen(
                    interrupt_source,
                    timeout=settings.SR_INTERRUPT_TIMEOUT,
                    phrase_time_limit=settings.SR_INTERRUPT_PHRASE_LIMIT,
                )
                word = _transcribe_whisper(audio).lower()
                log.debug("Interrupt heard: %s", word)
                if "stop" in word:
                    state.stop_speaking = True
                    log.info("Stop command detected – interrupting speech.")
                    break
            except sr.WaitTimeoutError:
                continue
            except Exception:
                continue