import speech_recognition as sr
import requests
import os
import pyautogui
import time
import edge_tts
import asyncio
import pygame
import uuid
import glob
import atexit
import threading
import subprocess
import winreg
import difflib
import psutil
import pythoncom
import win32com.client
import json
import shutil
import random
import pygetwindow as gw
import re

# ─────────────────────────────────────────
#  Initialization
# ─────────────────────────────────────────
pygame.mixer.init()
pygame.mixer.set_num_channels(8)
TTS_CHANNEL = pygame.mixer.Channel(0)

memory = []
recognizer = sr.Recognizer()
recognizer.pause_threshold = 0.8
recognizer.energy_threshold = 300
recognizer.dynamic_energy_threshold = True

mic = sr.Microphone()
WAKE_WORD = "alex"

# Shared flags
stop_speaking = False
is_speaking   = False
INSTALLED_PROGRAMS = {}
STORE_APPS         = {}
MUSIC_INDEX   = {}
playlist      = []
playlist_pos  = 0
music_playing = False
music_paused  = False
music_lock    = threading.Lock()
SUPPORTED_AUDIO = (".mp3", ".wav", ".ogg", ".flac", ".m4a")
MUSIC_SCAN_ROOTS = [
    os.path.expanduser("~/Music"),
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/OneDrive/Music"),
]


# ═══════════════════════════════════════════════════════════
#  NOTEPAD WRITER  ── NEW FEATURE
# ═══════════════════════════════════════════════════════════

def _get_or_open_notepad():
    """Return a focused Notepad window, opening one if needed."""
    # Check if already open
    for w in gw.getAllWindows():
        if "notepad" in w.title.lower():
            try:
                w.activate()
            except Exception:
                pass
            time.sleep(0.4)
            return True

    # Open a new Notepad
    subprocess.Popen(["notepad.exe"])
    for _ in range(15):           # wait up to 3 s
        time.sleep(0.2)
        for w in gw.getAllWindows():
            if "notepad" in w.title.lower():
                try:
                    w.activate()
                except Exception:
                    pass
                time.sleep(0.3)
                return True

    return False  # couldn't find/open Notepad


def write_in_notepad(text):
    """
    Opens (or focuses) Notepad and types the given text.

    Voice examples:
        "write in notepad Hello World"
        "type in notepad My shopping list"
        "notepad write Today is a good day"
        "write Today is a good day in notepad"
        "open notepad and write Meeting at 3 PM"
    """
    if not text.strip():
        speak("What should I write? Please say the text.")
        return False

    if not _get_or_open_notepad():
        speak("Sorry, I couldn't open Notepad.")
        return False

    # Move caret to end of any existing content
    pyautogui.hotkey("ctrl", "End")
    time.sleep(0.1)

    # Use clipboard paste for reliable unicode support
    try:
        import pyperclip
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
    except ImportError:
        # Fallback: typewrite (ASCII only, slower)
        pyautogui.typewrite(text, interval=0.04)

    speak("Done! I wrote that in Notepad.")
    return True


def write_in_notepad_and_save(text, filename=None):
    """
    Writes text to Notepad then saves.
    If filename is given, uses Save-As to Desktop/<filename>.txt
    """
    if not write_in_notepad(text):
        return False

    time.sleep(0.3)
    if filename:
        if not filename.endswith(".txt"):
            filename += ".txt"
        save_path = os.path.join(os.path.expanduser("~/Desktop"), filename)
        pyautogui.hotkey("ctrl", "shift", "s")   # Save As
        time.sleep(1.0)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.typewrite(save_path, interval=0.04)
        pyautogui.press("enter")
        time.sleep(0.5)
        pyautogui.press("enter")   # confirm overwrite if prompted
        speak(f"Saved as {filename} on your Desktop.")
    else:
        pyautogui.hotkey("ctrl", "s")
        time.sleep(0.5)
        speak("Notepad saved.")
    return True


def clear_notepad():
    """Select-all and delete all text in the open Notepad window."""
    found = False
    for w in gw.getAllWindows():
        if "notepad" in w.title.lower():
            found = True
            try:
                w.activate()
            except Exception:
                pass
            break

    if not found:
        speak("Notepad is not open.")
        return False

    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    speak("Notepad cleared.")
    return True


def _parse_notepad_command(command):
    """
    Extracts the dictated text from inline notepad-write commands.
    Returns the text string, or None if the command doesn't match.

    Supported patterns:
        "write in notepad <text>"
        "type in notepad <text>"
        "save in notepad <text>"
        "notepad write <text>"
        "notepad type <text>"
        "open notepad and write <text>"
        "open notepad and type <text>"
        "write <text> in notepad"
        "type <text> in notepad"
        "in notepad write <text>"
    """
    patterns = [
        r'^(?:write|type|save)\s+in\s+notepad\s+(.+)$',
        r'^notepad\s+(?:write|type|save)\s+(.+)$',
        r'^open\s+notepad\s+and\s+(?:write|type)\s+(.+)$',
        r'^(?:write|type)\s+(.+?)\s+in\s+notepad$',
        r'^in\s+notepad\s+(?:write|type)\s+(.+)$',
    ]
    for pat in patterns:
        m = re.match(pat, command.strip(), re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


# ─────────────────────────────────────────
#  Music functions
# ─────────────────────────────────────────
def build_music_index():
    global MUSIC_INDEX
    MUSIC_INDEX.clear()
    for root_path in MUSIC_SCAN_ROOTS:
        if not os.path.isdir(root_path):
            continue
        for dirpath, _, files in os.walk(root_path):
            for f in files:
                if f.lower().endswith(SUPPORTED_AUDIO):
                    full = os.path.join(dirpath, f)
                    name_no_ext = os.path.splitext(f)[0].lower()
                    MUSIC_INDEX[name_no_ext] = full
                    MUSIC_INDEX[f.lower()] = full
    print(f"Music index: {len(MUSIC_INDEX)} tracks found.")


def find_song(query):
    query = query.lower().strip()
    if query in MUSIC_INDEX:
        return query, MUSIC_INDEX[query]
    matches = difflib.get_close_matches(query, MUSIC_INDEX.keys(), n=1, cutoff=0.4)
    if matches:
        return matches[0], MUSIC_INDEX[matches[0]]
    for name in MUSIC_INDEX:
        if query in name or name in query:
            return name, MUSIC_INDEX[name]
    return None, None


def _play_track(path):
    global music_playing, music_paused
    try:
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        music_playing = True
        music_paused  = False
        song_name = os.path.splitext(os.path.basename(path))[0]
        print(f"[Music] Now playing: {song_name}")
        return song_name
    except Exception as e:
        print(f"[Music Error]: {e}")
        return None


def _music_watcher():
    global playlist_pos, music_playing
    while music_playing:
        time.sleep(1)
        if music_playing and not music_paused:
            if not pygame.mixer.music.get_busy():
                with music_lock:
                    if playlist:
                        playlist_pos = (playlist_pos + 1) % len(playlist)
                        _play_track(playlist[playlist_pos])


def music_play_all(shuffle=True):
    global playlist, playlist_pos
    with music_lock:
        paths = list(set(MUSIC_INDEX.values()))
        if not paths:
            speak("I couldn't find any music files on your computer.")
            return
        if shuffle:
            random.shuffle(paths)
        playlist     = paths
        playlist_pos = 0
        name = _play_track(playlist[playlist_pos])
        if name:
            speak(f"Playing {name}")
    threading.Thread(target=_music_watcher, daemon=True).start()


def music_play_song(query):
    global playlist, playlist_pos
    name, path = find_song(query)
    if not path:
        speak(f"I couldn't find a song called {query}.")
        return
    with music_lock:
        others = [p for p in set(MUSIC_INDEX.values()) if p != path]
        random.shuffle(others)
        playlist     = [path] + others
        playlist_pos = 0
        _play_track(path)
        speak(f"Playing {name}")
    threading.Thread(target=_music_watcher, daemon=True).start()


def music_stop():
    global music_playing, music_paused
    pygame.mixer.music.stop()
    music_playing = False
    music_paused  = False
    speak("Music stopped.")


def music_pause():
    global music_paused
    if music_playing and not music_paused:
        pygame.mixer.music.pause()
        music_paused = True
        speak("Music paused.")
    else:
        speak("Nothing is playing right now.")


def music_resume():
    global music_paused
    if music_paused:
        pygame.mixer.music.unpause()
        music_paused = False
        speak("Resuming music.")
    else:
        speak("Music is already playing.")


def music_next():
    global playlist_pos
    with music_lock:
        if not playlist:
            speak("No playlist loaded. Say play music first.")
            return
        playlist_pos = (playlist_pos + 1) % len(playlist)
        name = _play_track(playlist[playlist_pos])
        if name:
            speak(f"Next: {name}")


def music_previous():
    global playlist_pos
    with music_lock:
        if not playlist:
            speak("No playlist loaded. Say play music first.")
            return
        playlist_pos = (playlist_pos - 1) % len(playlist)
        name = _play_track(playlist[playlist_pos])
        if name:
            speak(f"Previous: {name}")


def music_current():
    if not music_playing:
        speak("No music is playing right now.")
        return
    if playlist and 0 <= playlist_pos < len(playlist):
        name = os.path.splitext(os.path.basename(playlist[playlist_pos]))[0]
        speak(f"Currently playing: {name}")


def music_volume_up():
    pygame.mixer.music.set_volume(min(1.0, pygame.mixer.music.get_volume() + 0.2))
    speak("Music volume increased.")


def music_volume_down():
    pygame.mixer.music.set_volume(max(0.0, pygame.mixer.music.get_volume() - 0.2))
    speak("Music volume decreased.")


def handle_music_commands(command):
    """Handle all music voice commands. Returns True if handled."""
    TELUGU_PLAY_TRIGGERS = [
        "oka paata vesoku", "paata vesoku", "paata veyyi",
        "music vesoku", "paata petthu", "oka paata petthu",
        "paata start cheyyi", "music start cheyyi", "paata play cheyyi",
    ]
    TELUGU_STOP_TRIGGERS  = ["paata aaphu", "music aaphu", "aaphu", "paata band cheyyi"]
    TELUGU_NEXT_TRIGGERS  = ["next paata", "paata marcheyyi", "vere paata vesoku", "inka okati vesoku"]
    TELUGU_PAUSE_TRIGGERS = ["paata pause cheyyi", "konchem aaphu"]

    if any(t in command for t in TELUGU_PLAY_TRIGGERS):  music_play_all(shuffle=True); return True
    if any(t in command for t in TELUGU_STOP_TRIGGERS):  music_stop();  return True
    if any(t in command for t in TELUGU_NEXT_TRIGGERS):  music_next();  return True
    if any(t in command for t in TELUGU_PAUSE_TRIGGERS): music_pause(); return True

    telugu_keywords = ["paata", "pata", "paatha", "vesoku", "vesko", "vesuko", "petthu", "pettu"]
    if sum(1 for w in telugu_keywords if w in command) >= 2:
        music_play_all(shuffle=True); return True

    if any(w in command for w in ["stop music", "stop the music", "stop song"]):   music_stop();    return True
    if any(w in command for w in ["pause music", "pause the music", "pause song"]): music_pause();  return True
    if any(w in command for w in ["resume music", "continue music", "unpause"]):    music_resume(); return True
    if any(w in command for w in ["next song", "next track", "skip song", "skip track"]): music_next(); return True
    if any(w in command for w in ["previous song", "previous track", "last song", "go back"]): music_previous(); return True
    if any(w in command for w in ["what song", "what's playing", "current song", "song name"]): music_current(); return True
    if "music volume up" in command or "louder" in command:   music_volume_up();   return True
    if "music volume down" in command or "quieter" in command: music_volume_down(); return True

    if command.startswith("play "):
        song_query = command[5:].strip()
        SHUFFLE_KEYWORDS = (
            "music", "all", "all songs", "songs", "",
            "random", "any", "any song", "anything",
            "something", "shuffle", "random song",
            "any music", "whatever", "surprise me"
        )
        if song_query in SHUFFLE_KEYWORDS:
            music_play_all(shuffle=True); return True
        if any(w in song_query for w in ["random", "any", "shuffle", "whatever", "surprise"]):
            music_play_all(shuffle=True); return True
        music_play_song(song_query); return True

    if command in ("music", "play music", "start music"):
        music_play_all(shuffle=True); return True

    return False


# ─────────────────────────────────────────
#  App shortcuts & aliases
# ─────────────────────────────────────────
SPECIAL_APPS = {
    "word":                 "start winword",
    "microsoft word":       "start winword",
    "excel":                "start excel",
    "microsoft excel":      "start excel",
    "powerpoint":           "start powerpnt",
    "microsoft powerpoint": "start powerpnt",
    "outlook":              "start outlook",
    "microsoft outlook":    "start outlook",
    "onenote":              "start onenote",
    "microsoft onenote":    "start onenote",
    "access":               "start msaccess",
    "settings":             "start ms-settings:",
    "windows settings":     "start ms-settings:",
    "control panel":        "start control",
    "task manager":         "start taskmgr",
    "file explorer":        "start explorer",
    "explorer":             "start explorer",
    "paint":                "start mspaint",
    "notepad":              "start notepad",
    "calculator":           "start calc",
    "cmd":                  "start cmd",
    "command prompt":       "start cmd",
    "powershell":           "start powershell",
    "snipping tool":        "start snippingtool",
    "chrome":               "start chrome",
    "google chrome":        "start chrome",
    "edge":                 "start msedge",
    "microsoft edge":       "start msedge",
    "firefox":              "start firefox",
    "camera":               "start microsoft.windows.camera:",
    "mail":                 "start outlookmail:",
    "calendar":             "start outlookcal:",
    "maps":                 "start bingmaps:",
    "store":                "start ms-windows-store:",
    "microsoft store":      "start ms-windows-store:",
    "xbox":                 "start xbox:",
    "photos":               "start ms-photos:",
    "clock":                "start ms-clock:",
    "weather":              "start bingweather:",
    "sticky notes":         "start ms-stickynotes:",
    "teams":                "start msteams:",
    "youtube":              "start https://www.youtube.com",
    "google":               "start https://www.google.com",
    "whatsapp web":         "start https://web.whatsapp.com",
}

PROCESS_ALIASES = {
    "vs code": "code.exe", "vscode": "code.exe",
    "visual studio code": "code.exe", "visual studio": "devenv.exe",
    "word": "winword.exe", "excel": "excel.exe",
    "powerpoint": "powerpnt.exe", "outlook": "outlook.exe",
    "teams": "teams.exe", "chrome": "chrome.exe",
    "firefox": "firefox.exe", "edge": "msedge.exe",
    "spotify": "spotify.exe", "discord": "discord.exe",
    "steam": "steam.exe", "notepad": "notepad.exe",
    "paint": "mspaint.exe", "calculator": "calculatorapp.exe",
    "task manager": "taskmgr.exe", "file explorer": "explorer.exe",
    "vlc": "vlc.exe", "zoom": "zoom.exe", "obs": "obs64.exe",
    "telegram": "telegram.exe", "whatsapp": "whatsapp.exe",
    "postman": "postman.exe", "pycharm": "pycharm64.exe",
    "android studio": "studio64.exe", "blender": "blender.exe",
    "photoshop": "photoshop.exe", "premiere": "premiere.exe",
    "after effects": "afterfx.exe", "figma": "figma.exe",
    "notion": "notion.exe", "slack": "slack.exe",
}


# ─────────────────────────────────────────
#  Program Database Scanning
# ─────────────────────────────────────────
def _scan_registry(hive, reg_path):
    results = {}
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
                                exe = raw; break
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


def _scan_start_menu():
    results = {}
    start_dirs = [
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
    ]
    pythoncom.CoInitialize()
    shell = win32com.client.Dispatch("WScript.Shell")
    for start_dir in start_dirs:
        for root, dirs, files in os.walk(start_dir):
            for fname in files:
                if fname.endswith(".lnk"):
                    lnk_path = os.path.join(root, fname)
                    try:
                        shortcut = shell.CreateShortCut(lnk_path)
                        target   = shortcut.Targetpath
                        if target and target.endswith(".exe") and os.path.exists(target):
                            results[fname[:-4].lower()] = target
                    except Exception:
                        pass
    return results


def _scan_appdata_apps():
    results = {}
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


def _scan_store_apps():
    results = {}
    try:
        ps_cmd = (
            'powershell -Command "Get-AppxPackage | '
            'Select-Object Name, PackageFamilyName | ConvertTo-Json -Compress"'
        )
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
    except Exception as e:
        print(f"[Store scan error]: {e}")
    return results


def build_program_database():
    global INSTALLED_PROGRAMS
    INSTALLED_PROGRAMS.clear()
    STORE_APPS.clear()
    print("Scanning installed programs...")
    for hive, path in [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]:
        INSTALLED_PROGRAMS.update(_scan_registry(hive, path))
    INSTALLED_PROGRAMS.update(_scan_start_menu())
    INSTALLED_PROGRAMS.update(_scan_appdata_apps())
    STORE_APPS.update(_scan_store_apps())
    print(f"Found {len(INSTALLED_PROGRAMS)} desktop apps + {len(STORE_APPS)} Store apps.")


def find_desktop_program(query):
    query = query.lower().strip()
    if query in INSTALLED_PROGRAMS:
        return query, INSTALLED_PROGRAMS[query]
    matches = difflib.get_close_matches(query, list(INSTALLED_PROGRAMS.keys()), n=1, cutoff=0.45)
    if matches:
        return matches[0], INSTALLED_PROGRAMS[matches[0]]
    for name in INSTALLED_PROGRAMS:
        if query in name or name in query:
            return name, INSTALLED_PROGRAMS[name]
    return None, None


def find_store_app(query):
    query = query.lower().strip()
    if query in STORE_APPS:
        return query, STORE_APPS[query]
    matches = difflib.get_close_matches(query, list(STORE_APPS.keys()), n=1, cutoff=0.4)
    if matches:
        return matches[0], STORE_APPS[matches[0]]
    for name in STORE_APPS:
        if query in name or name in query:
            return name, STORE_APPS[name]
    return None, None


def close_program(query):
    query_lower = query.lower().strip()
    target_exe  = PROCESS_ALIASES.get(query_lower, None)
    killed = 0
    for p in psutil.process_iter(['name', 'pid']):
        try:
            pname = p.name().lower()
            if target_exe:
                match = (pname == target_exe)
            else:
                score = difflib.SequenceMatcher(None, query_lower, pname.replace(".exe", "")).ratio()
                match = score > 0.5 or query_lower in pname
            if match:
                try:
                    p.terminate(); p.wait(timeout=3)
                except psutil.TimeoutExpired:
                    p.kill()
                except psutil.AccessDenied:
                    os.system(f"taskkill /f /pid {p.pid}")
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if killed == 0:
        if os.system(f"taskkill /f /im {query_lower}.exe") == 0:
            killed = 1
    return killed > 0


# ─────────────────────────────────────────
#  Cleanup on exit
# ─────────────────────────────────────────
def cleanup_temp_files():
    for f in glob.glob("voice_*.mp3"):
        try:
            os.remove(f)
        except Exception:
            pass

atexit.register(cleanup_temp_files)


# ─────────────────────────────────────────
#  Speak
# ─────────────────────────────────────────
def speak(text):
    global stop_speaking, is_speaking
    stop_speaking = False
    is_speaking   = True
    print(f"Assistant: {text}")
    was_playing = pygame.mixer.music.get_busy() and not music_paused
    if was_playing:
        pygame.mixer.music.set_volume(0.2)

    async def run():
        filename = f"voice_{uuid.uuid4()}.mp3"
        try:
            communicate = edge_tts.Communicate(text=text, voice="en-US-AriaNeural")
            await communicate.save(filename)
            await asyncio.sleep(0.2)
            sound = pygame.mixer.Sound(filename)
            TTS_CHANNEL.play(sound)
            while TTS_CHANNEL.get_busy():
                if stop_speaking:
                    TTS_CHANNEL.stop()
                    print("[Speech interrupted]")
                    break
                await asyncio.sleep(0.05)
        except Exception as e:
            print(f"[TTS Error]: {e}")
        finally:
            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except Exception:
                pass

    asyncio.run(run())
    is_speaking = False
    if was_playing:
        pygame.mixer.music.set_volume(1.0)


def speak_async(text):
    t = threading.Thread(target=speak, args=(text,), daemon=True)
    t.start()
    return t


# ─────────────────────────────────────────
#  Interrupt Listener
# ─────────────────────────────────────────
def listen_for_interrupt():
    global stop_speaking, is_speaking
    ir = sr.Recognizer()
    ir.energy_threshold = 300
    ir.dynamic_energy_threshold = True
    while is_speaking:
        try:
            with sr.Microphone() as source:
                audio = ir.listen(source, timeout=2, phrase_time_limit=2)
            word = ir.recognize_google(audio).lower()
            print(f"[Interrupt heard]: {word}")
            if "stop" in word:
                stop_speaking = True
                speak("[Stop command detected — interrupting speech]")
                break
        except sr.WaitTimeoutError:
            continue
        except sr.UnknownValueError:
            continue
        except Exception:
            continue


# ─────────────────────────────────────────
#  Listen helpers
# ─────────────────────────────────────────
def calibrate_mic():
    print("Calibrating microphone...")
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=1.5)
    print("Calibration done. Say 'Alex' to activate.\n")


def listen(timeout=5, phrase_limit=5):
    with mic as source:
        print("Listening...")
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
        except sr.WaitTimeoutError:
            return ""
        except Exception as e:
            print(f"[Listen Error]: {e}")
            return ""
    try:
        command = recognizer.recognize_google(audio).lower()
        print(f"You: {command}")
        return command
    except sr.UnknownValueError:
        print("Could not understand.")
        return ""
    except sr.RequestError:
        print("Network error.")
        return ""


def listen_long(timeout=10, phrase_limit=15):
    """Longer listen specifically for dictation."""
    with mic as source:
        print("Listening for dictation...")
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
        except sr.WaitTimeoutError:
            return ""
        except Exception as e:
            print(f"[Listen Error]: {e}")
            return ""
    try:
        text = recognizer.recognize_google(audio)   # preserve original capitalisation
        print(f"Dictated: {text}")
        return text
    except sr.UnknownValueError:
        return ""
    except sr.RequestError:
        return ""


# ─────────────────────────────────────────
#  AI Query
# ─────────────────────────────────────────
def ask_ai(prompt):
    if not prompt.strip():
        return "I didn't receive any input. Please try again."

    memory.append(f"User: {prompt}")
    if len(memory) > 20:
        memory[:] = memory[-20:]

    context = "\n".join(memory[-6:])
    url     = "http://localhost:11434/api/generate"
    payload = {"model": "llama3", "prompt": context, "stream": False}

    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        reply = response.json().get("response", "No response received.")
        words = reply.split()
        if len(words) > 120:
            reply = " ".join(words[:120]) + "...Would you like me to continue?"
        memory.append(f"Assistant: {reply}")
        return reply
    except requests.exceptions.ConnectionError:
        return "Sorry, the AI server is not running. Please start Ollama."
    except requests.exceptions.Timeout:
        return "The question needs more time"
    except Exception as e:
        return f"Error contacting AI: {e}"


# ─────────────────────────────────────────
#  Window Management
# ─────────────────────────────────────────
def minimize_app(query):
    query_lower = query.lower().strip()
    try:
        all_windows = [w for w in gw.getAllWindows() if w.title.strip() and w.width > 0]
        for w in all_windows:
            if query_lower in w.title.lower():
                w.minimize(); speak(f"{query} minimized."); return True
        titles  = [w.title.lower() for w in all_windows]
        matches = difflib.get_close_matches(query_lower, titles, n=1, cutoff=0.4)
        if matches:
            for w in all_windows:
                if w.title.lower() == matches[0]:
                    w.minimize(); speak(f"{w.title} minimized."); return True
        for w in all_windows:
            if any(word in w.title.lower() for word in query_lower.split()):
                w.minimize(); speak(f"{w.title} minimized."); return True
        speak(f"I couldn't find {query} open.")
        return False
    except Exception as e:
        print(f"[Minimize error]: {e}")
        speak(f"Couldn't minimize {query}.")
        return False


# ─────────────────────────────────────────
#  Command Router
# ─────────────────────────────────────────
def run_command(command):
    if not command:
        return False

    # ── Music ────────────────────────────────────────────────────────
    if handle_music_commands(command):
        return True

    # ── NOTEPAD: inline text ─────────────────────────────────────────
    # e.g. "write in notepad Hello World"  →  writes "Hello World"
    text_to_write = _parse_notepad_command(command)
    if text_to_write:
        write_in_notepad(text_to_write)
        return True

    # ── NOTEPAD: dictation mode (no inline text) ─────────────────────
    # e.g. "write in notepad"  →  Alex asks "What should I write?"
    NOTEPAD_DICTATE_TRIGGERS = [
        "write in notepad", "type in notepad",
        "notepad write", "notepad type",
        "open notepad and write", "open notepad and type",
        "dictate in notepad", "notepad dictate",
        "write something in notepad",
        "write a notepad", "write a note in notepad",
        "write a note in notepad", "write a note on notepad",
        "write in notepad and save", "type in notepad and save",

    ]
    if any(t in command for t in NOTEPAD_DICTATE_TRIGGERS):
        speak("Sure! What should I write? Go ahead and speak.")
        dictated = listen_long(timeout=10, phrase_limit=15)
        if dictated:
            write_in_notepad(dictated)
        else:
            speak("I didn't catch that. Please try again.")
        return True

    # ── NOTEPAD: write and save ──────────────────────────────────────
    # e.g. "write in notepad and save"
    if "notepad" in command and "save" in command and (
            "write" in command or "type" in command):
        speak("What should I write and save?")
        dictated = listen_long(timeout=10, phrase_limit=15)
        if dictated:
            write_in_notepad_and_save(dictated)
        else:
            speak("I didn't catch that. Please try again.")
        return True

    # ── NOTEPAD: clear ───────────────────────────────────────────────
    if command in ("clear notepad", "erase notepad", "delete notepad text",
                   "clear the notepad", "empty notepad"):
        clear_notepad()
        return True

    # ── CLOSE ────────────────────────────────────────────────────────
    if command.startswith("close "):
        app_query = command[6:].strip()
        success   = close_program(app_query)
        speak(f"Closed {app_query}" if success else f"I couldn't find {app_query} running.")
        return True

    # ── MINIMIZE ─────────────────────────────────────────────────────
    if command.startswith("minimize ") or command.startswith("minimise "):
        app_query = command[9:].strip()
        minimize_app(app_query)
        return True

    # ── OPEN ─────────────────────────────────────────────────────────
    if command.startswith("open "):
        app_query = command[5:].strip()
        if app_query in SPECIAL_APPS:
            speak(f"Opening {app_query}"); os.system(SPECIAL_APPS[app_query]); return True
        for key, cmd in SPECIAL_APPS.items():
            if key in app_query or app_query in key:
                speak(f"Opening {key}"); os.system(cmd); return True

        name, path = find_desktop_program(app_query)
        if path:
            speak(f"Opening {name}")
            try:
                subprocess.Popen([path])
            except Exception:
                os.startfile(path)
            return True

        sname, pfn = find_store_app(app_query)
        if pfn:
            speak(f"Opening {sname}")
            launched = False
            for app_id in ["!App", f"!{app_query.capitalize()}", "!Spotify", "!NONE"]:
                try:
                    r = subprocess.run(
                        ["powershell", "-Command",
                         f'Start-Process "shell:AppsFolder\\{pfn}{app_id}"'],
                        capture_output=True, timeout=5
                    )
                    if r.returncode == 0:
                        launched = True; break
                except Exception:
                    continue
            if not launched:
                _, path2 = find_desktop_program(app_query)
                if path2:
                    subprocess.Popen([path2])
                else:
                    os.system(f"start {app_query}")
            return True

        speak(f"Trying to open {app_query}")
        os.system(f"start {app_query}")
        return True

    # ── Volume ───────────────────────────────────────────────────────
    if "increase the volume" in command or "volume up" in command:
        speak("Increasing volume"); pyautogui.press("volumeup", presses=5); return True
    if "decrease the volume" in command or "volume down" in command:
        speak("Decreasing volume"); pyautogui.press("volumedown", presses=5); return True
    if "mute" in command:
        speak("Toggling mute"); pyautogui.press("volumemute"); return True

    # ── Tabs ─────────────────────────────────────────────────────────
    if "switch tab" in command:
        speak("Switching tab"); pyautogui.hotkey("ctrl", "tab"); return True

    # ── System ───────────────────────────────────────────────────────
    if any(w in command for w in ["lock", "lock screen", "lock the screen"]):
        speak("Locking screen protocol activated")
        os.system("rundll32.exe user32.dll,LockWorkStation"); return True

    if any(w in command for w in ["shut down", "turn off"]):
        speak("Shutting down in 10 seconds. Say cancel to abort.")
        os.system("shutdown /s /t 10")
        if "cancel" in listen(timeout=8, phrase_limit=3):
            os.system("shutdown /a"); speak("Shutdown cancelled.")
        return True

    if any(w in command for w in ["restart", "reboot"]):
        speak("Restarting in 10 seconds. Say cancel to abort.")
        os.system("shutdown /r /t 10")
        if "cancel" in listen(timeout=8, phrase_limit=3):
            os.system("shutdown /a"); speak("Restart cancelled.")
        return True

    if "sleep" in command:
        speak("Going to sleep")
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0"); return True

    if "refresh apps" in command or "rescan apps" in command:
        speak("Rescanning all installed apps...")
        build_program_database()
        speak("Done. App database updated."); return True

    return False


# ─────────────────────────────────────────
#  Main Loop
# ─────────────────────────────────────────
def main():
    global stop_speaking
    build_program_database()
    build_music_index()
    calibrate_mic()
    speak("Alex assistant activated. Say Alex to begin.")

    assistant_active = False

    while True:
        command = listen()
        if not command:
            continue

        # ── STOP ────────────────────────────────────────────────────
        if "stop" in command:
            if music_playing:
                music_stop()
            elif is_speaking:
                stop_speaking = True
                print("[Stopping speech...]")
            else:
                speak("Nothing is playing right now.")
            continue

        # ── EXIT ────────────────────────────────────────────────────
        if "exit" in command or "shutdown" in command:
            speak("ShuttingdownSir!....")
            break

        # ── WAKE WORD ───────────────────────────────────────────────
        if WAKE_WORD in command:
            after_wake = command.split(WAKE_WORD)[-1].strip()
            if after_wake:
                command = after_wake
            else:
                speak("Yes Boss?")
                assistant_active = True
                continue

        # ── PROCESS COMMAND ─────────────────────────────────────────
        if assistant_active or WAKE_WORD in command:
            handled = run_command(command)
            if not handled:
                speak("Let me think...")
                reply = ask_ai(command)
                if reply:
                    speak_thread    = speak_async(reply)
                    interrupt_thread = threading.Thread(
                        target=listen_for_interrupt, daemon=True
                    )
                    interrupt_thread.start()
                    speak_thread.join()
 

if __name__ == "__main__":
    main()
# WITHOUT WHATSAPP THIS IS THE MAIN FILE FOR OPTIMIZATION PROJECT.