"""
main.py
────────
Alex Voice Assistant – entry point.

Responsibilities (only):
  - Application startup and dependency wiring
  - One-time initialization (program DB, music index, mic calibration)
  - Main event loop with wake-word gating
  - Command routing dispatch
  - Top-level error handling
"""

import sys

from config import settings
from core import get_logger, state
from speech import speak, listen, calibrate
from services.app_service import build_program_database
from services.music_service import build_music_index
from services.music_service import stop as music_stop
from commands import run_command
from utils import register_cleanup

log = get_logger(__name__)


# ── Initialization ────────────────────────────────────────────────────────────

def _initialize() -> None:
    """Run all startup tasks before entering the main loop."""
    register_cleanup()
    log.info("Building program database…")
    build_program_database()
    log.info("Building music index…")
    build_music_index()
    log.info("Calibrating microphone…")
    calibrate()
    speak("Friday assistant activated. Say Friday to begin.")


# ── Stop command handler ──────────────────────────────────────────────────────

def _handle_stop() -> None:
    """Handle the 'stop' command – stop music or speech."""
    if state.music_playing:
        music_stop()
    elif state.is_speaking:
        state.stop_speaking = True
        log.info("Stopping speech…")
    else:
        speak("Nothing is playing right now.")


# ── Main event loop ───────────────────────────────────────────────────────────

def main() -> None:
    """Main event loop: listen → classify → dispatch via router."""
    try:
        _initialize()
    except Exception:
        log.exception("Initialization failed.")
        sys.exit(1)

    while True:
        try:
            command = listen()
            if not command or not command.strip():
                continue

            # ── Hard stop (local override) ───────────────────────────────────
            if "stop" in command.lower():
                _handle_stop()
                # Deactivate assistant after handling stop
                state.assistant_active = False
                continue

            # ── Exit / Shutdown ──────────────────────────────────────────────
            if any(word in command.lower() for word in ["exit", "shutdown", "goodbye", "bye"]):
                speak("Shutting down Sir!")
                break

            # ── Wake word detection ──────────────────────────────────────────
            wake_detected = settings.WAKE_WORD.lower() in command.lower()
            if wake_detected:
                # Extract text after wake word
                idx = command.lower().find(settings.WAKE_WORD.lower())
                after_wake = command[idx + len(settings.WAKE_WORD):].strip()
                
                if not after_wake:
                    # Wake word alone → activate and wait for next command
                    speak("Yes Boss?")
                    state.assistant_active = True
                    continue
                else:
                    # Wake word + inline command → process immediately
                    command = after_wake
                    state.assistant_active = False  # single-shot mode

            # ── Dispatch only when active or wake word was just detected ─────
            if not (state.assistant_active or wake_detected):
                continue

            # ── Route to command dispatcher ──────────────────────────────────
            # run_command() handles BOTH classification and execution.
            # It returns True if the command was processed (tool or conversation).
            # No fallback needed – it handles everything internally.
            run_command(command)

            # ── Deactivate after single command if not in persistent mode ────
            if wake_detected and after_wake:
                # Inline command after wake word → deactivate
                state.assistant_active = False
            # else: stay active if user said just the wake word

        except KeyboardInterrupt:
            log.info("KeyboardInterrupt – shutting down.")
            break
        except Exception:
            log.exception("Unhandled error in main loop – continuing.")
            continue

    # ── Cleanup on exit ──────────────────────────────────────────────────────
    if state.music_playing:
        music_stop()
    log.info("Alex Assistant shut down gracefully.")


if __name__ == "__main__":
    main()