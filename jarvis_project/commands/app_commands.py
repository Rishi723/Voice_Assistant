"""
commands/app_commands.py
─────────────────────────
Handles open / close / minimize voice commands.
"""

import difflib
import os
import subprocess

import pygetwindow as gw

from config.settings.app_registry import SPECIAL_APPS
from core import get_logger
from services.app_service import (
    find_desktop_program, find_store_app, close_program,
)
from speech import speak

log = get_logger(__name__)


def handle_open(app_query: str) -> bool:
    """Open an application by name. Returns True always (best-effort)."""
    # 1. Exact / substring match in SPECIAL_APPS
    if app_query in SPECIAL_APPS:
        speak(f"Opening {app_query}")
        os.system(SPECIAL_APPS[app_query])
        return True
    for key, cmd in SPECIAL_APPS.items():
        if key in app_query or app_query in key:
            speak(f"Opening {key}")
            os.system(cmd)
            return True

    # 2. Desktop program (registry / start-menu)
    name, path = find_desktop_program(app_query)
    if path:
        speak(f"Opening {name}")
        try:
            subprocess.Popen([path])
        except Exception:
            os.startfile(path)
        return True

    # 3. Microsoft Store app
    sname, pfn = find_store_app(app_query)
    if pfn:
        speak(f"Opening {sname}")
        launched = False
        for app_id in ["!App", f"!{app_query.capitalize()}", "!NONE"]:
            try:
                r = subprocess.run(
                    ["powershell", "-Command",
                     f'Start-Process "shell:AppsFolder\\{pfn}{app_id}"'],
                    capture_output=True, timeout=5,
                )
                if r.returncode == 0:
                    launched = True
                    break
            except Exception:
                continue
        if not launched:
            _, path2 = find_desktop_program(app_query)
            if path2:
                subprocess.Popen([path2])
            else:
                os.system(f"start {app_query}")
        return True

    # 4. Last-resort shell open
    speak(f"Trying to open {app_query}")
    os.system(f"start {app_query}")
    return True


def handle_close(app_query: str) -> bool:
    success = close_program(app_query)
    speak(f"Closed {app_query}" if success else f"I couldn't find {app_query} running.")
    return True


def handle_minimize(app_query: str) -> bool:
    query_lower = app_query.lower().strip()
    try:
        all_windows = [w for w in gw.getAllWindows() if w.title.strip() and w.width > 0]

        for w in all_windows:
            if query_lower in w.title.lower():
                w.minimize()
                speak(f"{app_query} minimized.")
                return True

        titles  = [w.title.lower() for w in all_windows]
        matches = difflib.get_close_matches(query_lower, titles, n=1, cutoff=0.4)
        if matches:
            for w in all_windows:
                if w.title.lower() == matches[0]:
                    w.minimize()
                    speak(f"{w.title} minimized.")
                    return True

        for w in all_windows:
            if any(word in w.title.lower() for word in query_lower.split()):
                w.minimize()
                speak(f"{w.title} minimized.")
                return True

        speak(f"I couldn't find {app_query} open.")
    except Exception:
        log.exception("Minimize error for %s", app_query)
        speak(f"Couldn't minimize {app_query}.")
    return True
