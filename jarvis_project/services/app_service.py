"""
services/app_service.py
────────────────────────
Scans the Windows program database (registry, Start Menu, AppData, Store)
and provides fuzzy lookup + launch / close helpers.
"""

import difflib
import json
import os
import subprocess

import psutil
import pythoncom
import win32com.client
import winreg

from config import settings
from config.settings.app_registry import PROCESS_ALIASES
from core import get_logger, state

log = get_logger(__name__)


# ── Registry scanner ──────────────────────────────────────────────────────────

def _scan_registry(hive: int, reg_path: str) -> dict[str, str]:
    results: dict[str, str] = {}
    try:
        key = winreg.OpenKey(hive, reg_path)
        for i in range(winreg.QueryInfoKey(key)[0]):
            try:
                sub_name = winreg.EnumKey(key, i)
                sub_key  = winreg.OpenKey(key, sub_name)
                try:
                    name = winreg.QueryValueEx(sub_key, "DisplayName")[0].strip().lower()
                    exe  = None
                    for field in ("DisplayIcon", "InstallLocation"):
                        try:
                            raw = winreg.QueryValueEx(sub_key, field)[0]
                            raw = raw.split(",")[0].strip().strip('"')
                            if raw.endswith(".exe") and os.path.exists(raw):
                                exe = raw
                                break
                        except Exception:
                            pass
                    if name and exe:
                        results[name] = exe
                except Exception:
                    pass
                finally:
                    sub_key.Close()
            except Exception:
                continue
        key.Close()
    except Exception:
        pass
    return results


def _scan_start_menu() -> dict[str, str]:
    results: dict[str, str] = {}
    start_dirs = [
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
    ]
    pythoncom.CoInitialize()
    shell = win32com.client.Dispatch("WScript.Shell")
    for start_dir in start_dirs:
        for root, _, files in os.walk(start_dir):
            for fname in files:
                if fname.endswith(".lnk"):
                    try:
                        shortcut = shell.CreateShortCut(os.path.join(root, fname))
                        target   = shortcut.Targetpath
                        if target and target.endswith(".exe") and os.path.exists(target):
                            results[fname[:-4].lower()] = target
                    except Exception:
                        pass
    return results


def _scan_appdata_apps() -> dict[str, str]:
    results: dict[str, str] = {}
    for base in [os.path.expandvars(r"%LOCALAPPDATA%"), os.path.expandvars(r"%APPDATA%")]:
        if not os.path.isdir(base):
            continue
        for folder in os.listdir(base):
            folder_path = os.path.join(base, folder)
            if not os.path.isdir(folder_path):
                continue
            exe_path = os.path.join(folder_path, folder + ".exe")
            if os.path.exists(exe_path):
                results[folder.lower()] = exe_path
                continue
            try:
                for sub in os.listdir(folder_path):
                    sub_exe = os.path.join(folder_path, sub, sub + ".exe")
                    if os.path.exists(sub_exe):
                        results[sub.lower()] = sub_exe
            except Exception:
                pass
    return results


def _scan_store_apps() -> dict[str, str]:
    results: dict[str, str] = {}
    ps_cmd = (
        'powershell -Command "Get-AppxPackage | '
        'Select-Object Name, PackageFamilyName | ConvertTo-Json -Compress"'
    )
    try:
        output = subprocess.check_output(
            ps_cmd, shell=True, timeout=20, stderr=subprocess.DEVNULL
        ).decode(errors="ignore")
        apps = json.loads(output)
        if isinstance(apps, dict):
            apps = [apps]
        for app in apps:
            raw_name = app.get("Name", "")
            pfn      = app.get("PackageFamilyName", "")
            if not raw_name or not pfn:
                continue
            results[raw_name.lower()] = pfn
            clean = raw_name.lower()
            for prefix in ["microsoft.", "windows.", "ms-", "xboxgame"]:
                clean = clean.replace(prefix, "")
            clean = clean.replace(".", " ").strip()
            if clean and clean != raw_name.lower():
                results[clean] = pfn
    except Exception:
        log.exception("Store app scan failed.")
    return results


# ── Build database ────────────────────────────────────────────────────────────

def build_program_database() -> None:
    """Populate state.installed_programs and state.store_apps."""
    state.installed_programs.clear()
    state.store_apps.clear()
    log.info("Scanning installed programs…")

    for hive, path in [
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]:
        state.installed_programs.update(_scan_registry(hive, path))

    state.installed_programs.update(_scan_start_menu())
    state.installed_programs.update(_scan_appdata_apps())
    state.store_apps.update(_scan_store_apps())

    log.info(
        "Found %d desktop apps + %d Store apps.",
        len(state.installed_programs),
        len(state.store_apps),
    )


# ── Fuzzy lookup ──────────────────────────────────────────────────────────────

def find_desktop_program(query: str) -> tuple[str | None, str | None]:
    query = query.lower().strip()
    if query in state.installed_programs:
        return query, state.installed_programs[query]
    matches = difflib.get_close_matches(
        query, list(state.installed_programs.keys()),
        n=1, cutoff=settings.APP_FUZZY_CUTOFF,
    )
    if matches:
        return matches[0], state.installed_programs[matches[0]]
    for name in state.installed_programs:
        if query in name or name in query:
            return name, state.installed_programs[name]
    return None, None


def find_store_app(query: str) -> tuple[str | None, str | None]:
    query = query.lower().strip()
    if query in state.store_apps:
        return query, state.store_apps[query]
    matches = difflib.get_close_matches(
        query, list(state.store_apps.keys()),
        n=1, cutoff=settings.STORE_APP_FUZZY_CUTOFF,
    )
    if matches:
        return matches[0], state.store_apps[matches[0]]
    for name in state.store_apps:
        if query in name or name in query:
            return name, state.store_apps[name]
    return None, None


# ── Close program ─────────────────────────────────────────────────────────────

def close_program(query: str) -> bool:
    """Kill all processes matching *query*.  Returns True if at least one killed."""
    query_lower = query.lower().strip()
    target_exe  = PROCESS_ALIASES.get(query_lower)
    killed      = 0

    for proc in psutil.process_iter(["name", "pid"]):
        try:
            pname = proc.name().lower()
            if target_exe:
                match = pname == target_exe
            else:
                ratio = difflib.SequenceMatcher(
                    None, query_lower, pname.replace(".exe", "")
                ).ratio()
                match = ratio > settings.PROCESS_MATCH_RATIO or query_lower in pname

            if match:
                try:
                    proc.terminate()
                    proc.wait(timeout=settings.PROCESS_KILL_TIMEOUT)
                except psutil.TimeoutExpired:
                    proc.kill()
                except psutil.AccessDenied:
                    os.system(f"taskkill /f /pid {proc.pid}")
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if killed == 0:
        if os.system(f"taskkill /f /im {query_lower}.exe") == 0:
            killed = 1

    return killed > 0