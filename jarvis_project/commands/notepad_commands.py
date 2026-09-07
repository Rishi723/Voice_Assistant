"""
commands/notepad_commands.py
─────────────────────────────
All Notepad-related voice commands:
  - write text inline
  - dictation mode
  - write + save to Desktop
  - clear notepad
  - _parse_notepad_command (pattern extractor)
"""

import os
import re
import subprocess
import time

import pyautogui
import pygetwindow as gw

from config import settings
from core import get_logger
from speech import speak

log = get_logger(__name__)

# ── Trigger word lists ────────────────────────────────────────────────────────

_DICTATE_TRIGGERS = [
    "write in notepad", "type in notepad",
    "notepad write", "notepad type",
    "open notepad and write", "open notepad and type",
    "dictate in notepad", "notepad dictate",
    "write something in notepad",
    "write a notepad", "write a note in notepad",
    "write a note on notepad",
    "write in notepad and save", "type in notepad and save",
]

_PARSE_PATTERNS = [
    r'^(?:write|type|save)\s+in\s+notepad\s+(.+)$',
    r'^notepad\s+(?:write|type|save)\s+(.+)$',
    r'^open\s+notepad\s+and\s+(?:write|type)\s+(.+)$',
    r'^(?:write|type)\s+(.+?)\s+in\s+notepad$',
    r'^in\s+notepad\s+(?:write|type)\s+(.+)$',
]

_CLEAR_COMMANDS = (
    "clear notepad", "erase notepad", "delete notepad text",
    "clear the notepad", "empty notepad",
)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_or_open_notepad() -> bool:
    """Focus an existing Notepad window, or open a new one. Returns True on success."""
    for w in gw.getAllWindows():
        if "notepad" in w.title.lower():
            try:
                w.activate()
            except Exception:
                pass
            time.sleep(settings.NOTEPAD_ACTIVATE_SLEEP)
            return True

    subprocess.Popen(["notepad.exe"])
    deadline = time.time() + settings.NOTEPAD_OPEN_WAIT_SECS
    while time.time() < deadline:
        time.sleep(settings.NOTEPAD_POLL_INTERVAL)
        for w in gw.getAllWindows():
            if "notepad" in w.title.lower():
                try:
                    w.activate()
                except Exception:
                    pass
                time.sleep(settings.NOTEPAD_ACTIVATE_SLEEP)
                return True
    return False


def _parse_notepad_command(command: str) -> str | None:
    """Extract dictated text from an inline notepad-write command, or None."""
    for pat in _PARSE_PATTERNS:
        m = re.match(pat, command.strip(), re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


# ── Public functions ──────────────────────────────────────────────────────────

def write_in_notepad(text: str) -> bool:
    if not text.strip():
        speak("What should I write? Please say the text.")
        return False
    if not _get_or_open_notepad():
        speak("Sorry, I couldn't open Notepad.")
        return False

    pyautogui.hotkey("ctrl", "End")
    time.sleep(settings.NOTEPAD_PASTE_SLEEP)
    try:
        import pyperclip
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
    except ImportError:
        pyautogui.typewrite(text, interval=0.04)

    speak("Done! I wrote that in Notepad.")
    return True


def write_in_notepad_and_save(text: str, filename: str | None = None) -> bool:
    if not write_in_notepad(text):
        return False
    time.sleep(0.3)
    if filename:
        if not filename.endswith(".txt"):
            filename += ".txt"
        save_path = os.path.join(settings.NOTEPAD_DESKTOP_SAVE_DIR, filename)
        pyautogui.hotkey("ctrl", "shift", "s")
        time.sleep(settings.NOTEPAD_SAVE_SLEEP)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.typewrite(save_path, interval=0.04)
        pyautogui.press("enter")
        time.sleep(0.5)
        pyautogui.press("enter")
        speak(f"Saved as {filename} on your Desktop.")
    else:
        pyautogui.hotkey("ctrl", "s")
        time.sleep(0.5)
        speak("Notepad saved.")
    return True


def clear_notepad() -> bool:
    found = any("notepad" in w.title.lower() for w in gw.getAllWindows())
    if not found:
        speak("Notepad is not open.")
        return False
    for w in gw.getAllWindows():
        if "notepad" in w.title.lower():
            try:
                w.activate()
            except Exception:
                pass
            break
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    speak("Notepad cleared.")
    return True


def handle_notepad_commands(command: str, listen_long_fn) -> bool:
    """
    Dispatch all Notepad voice commands.
    listen_long_fn: callable matching speech.recognizer.listen_long signature.
    Returns True if handled.
    """
    # Inline text: "write in notepad Hello World"
    inline_text = _parse_notepad_command(command)
    if inline_text:
        write_in_notepad(inline_text)
        return True

    # Dictation mode: trigger phrase with no inline text
    if any(t in command for t in _DICTATE_TRIGGERS):
        speak("Sure! What should I write? Go ahead and speak.")
        dictated = listen_long_fn()
        if dictated:
            write_in_notepad(dictated)
        else:
            speak("I didn't catch that. Please try again.")
        return True

    # Write + save
    if "notepad" in command and "save" in command and ("write" in command or "type" in command):
        speak("What should I write and save?")
        dictated = listen_long_fn()
        if dictated:
            write_in_notepad_and_save(dictated)
        else:
            speak("I didn't catch that. Please try again.")
        return True

    # Clear
    if command in _CLEAR_COMMANDS:
        clear_notepad()
        return True

    return False
