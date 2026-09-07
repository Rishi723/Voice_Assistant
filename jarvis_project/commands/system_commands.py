"""
commands/system_commands.py
────────────────────────────
System-level voice commands:
  volume up/down/mute, tab switch, lock, shutdown, restart, sleep,
  refresh app database.
"""

import os

import pyautogui

from config import settings
from core import get_logger
from services.app_service import build_program_database
from speech import speak, listen

log = get_logger(__name__)


def volume_up() -> None:
    speak("Increasing volume")
    pyautogui.press("volumeup", presses=5)


def volume_down() -> None:
    speak("Decreasing volume")
    pyautogui.press("volumedown", presses=5)


def mute() -> None:
    speak("Toggling mute")
    pyautogui.press("volumemute")


def switch_tab() -> None:
    speak("Switching tab")
    pyautogui.hotkey("ctrl", "tab")


def lock_screen() -> None:
    speak("Locking screen protocol activated")
    os.system("rundll32.exe user32.dll,LockWorkStation")


def shutdown() -> None:
    speak(f"Shutting down in {settings.SHUTDOWN_DELAY_SECS} seconds. Say cancel to abort.")
    os.system(f"shutdown /s /t {settings.SHUTDOWN_DELAY_SECS}")
    if "cancel" in listen(timeout=settings.SHUTDOWN_LISTEN_TIMEOUT, phrase_limit=3):
        os.system("shutdown /a")
        speak("Shutdown cancelled.")


def restart() -> None:
    speak(f"Restarting in {settings.SHUTDOWN_DELAY_SECS} seconds. Say cancel to abort.")
    os.system(f"shutdown /r /t {settings.SHUTDOWN_DELAY_SECS}")
    if "cancel" in listen(timeout=settings.SHUTDOWN_LISTEN_TIMEOUT, phrase_limit=3):
        os.system("shutdown /a")
        speak("Restart cancelled.")


def sleep() -> None:
    speak("Going to sleep")
    os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")


def refresh_apps() -> None:
    speak("Rescanning all installed apps...")
    build_program_database()
    speak("Done. App database updated.")


def handle_system_commands(command: str) -> bool:
    """Dispatch system voice commands. Returns True if handled."""
    if "increase the volume" in command or "volume up" in command:
        volume_up();   return True
    if "decrease the volume" in command or "volume down" in command:
        volume_down(); return True
    if "mute" in command:
        mute();        return True
    if "switch tab" in command:
        switch_tab();  return True
    if any(w in command for w in ["lock", "lock screen", "lock the screen"]):
        lock_screen(); return True
    if any(w in command for w in ["shut down", "turn off"]):
        shutdown();    return True
    if any(w in command for w in ["restart", "reboot"]):
        restart();     return True
    if "sleep" in command:
        sleep();       return True
    if "refresh apps" in command or "rescan apps" in command:
        refresh_apps(); return True

    return False
