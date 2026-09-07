"""
config/settings.py
──────────────────
Single source of truth for every tunable constant in Alex Assistant.
Edit values here; no other file should hard-code them.
"""

import os

# ── Wake word ────────────────────────────────────────────────────────────────
WAKE_WORD = "friday"

# ── Speech recognition ───────────────────────────────────────────────────────
SR_PAUSE_THRESHOLD       = 0.8
SR_ENERGY_THRESHOLD      = 300
SR_DYNAMIC_ENERGY        = True
SR_LISTEN_TIMEOUT        = 5
SR_LISTEN_PHRASE_LIMIT   = 5
SR_LONG_TIMEOUT          = 10
SR_LONG_PHRASE_LIMIT     = 15
SR_CALIBRATION_DURATION  = 1.5
SR_INTERRUPT_TIMEOUT     = 2
SR_INTERRUPT_PHRASE_LIMIT = 2

# ── TTS ──────────────────────────────────────────────────────────────────────
TTS_VOICE          = "en-US-AriaNeural"
TTS_TEMP_PREFIX    = "voice_"
TTS_TEMP_SUFFIX    = ".mp3"
TTS_PYGAME_CHANNELS = 8
TTS_CHANNEL_INDEX  = 0
TTS_MUSIC_DUCK_VOL = 0.2          # volume while TTS is speaking
TTS_STARTUP_DELAY  = 0.2

# ── LLM / Ollama ─────────────────────────────────────────────────────────────
LLM_BASE_URL      = "http://localhost:11434/api/generate"
LLM_MODEL         = "qwen3:4b"
LLM_TIMEOUT       = 100
LLM_MAX_WORDS     = 120
LLM_MEMORY_MAX    = 20
LLM_MEMORY_WINDOW = 6

# ── Intent Classifier ────────────────────────────────────────────────────────
# Uses the same Ollama endpoint but a tighter timeout and no memory window.
LLM_CLASSIFIER_MODEL   = "qwen3:4b"
LLM_CLASSIFIER_TIMEOUT = 90

# ── Music ─────────────────────────────────────────────────────────────────────
SUPPORTED_AUDIO = (".mp3", ".wav", ".ogg", ".flac", ".m4a")
MUSIC_SCAN_ROOTS = [
    os.path.expanduser("~/Music"),
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/OneDrive/Music"),
]
MUSIC_FUZZY_CUTOFF  = 0.4
MUSIC_VOLUME_STEP   = 0.2

# ── App scanning ─────────────────────────────────────────────────────────────
APP_FUZZY_CUTOFF        = 0.45
STORE_APP_FUZZY_CUTOFF  = 0.4
PROCESS_MATCH_RATIO     = 0.5
PROCESS_KILL_TIMEOUT    = 3        # seconds before escalating to SIGKILL

# ── Shutdown timer ───────────────────────────────────────────────────────────
SHUTDOWN_DELAY_SECS = 10
SHUTDOWN_LISTEN_TIMEOUT = 8

# ── Notepad ───────────────────────────────────────────────────────────────────
NOTEPAD_OPEN_WAIT_SECS   = 3.0     # max wait for notepad window to appear
NOTEPAD_POLL_INTERVAL    = 0.2
NOTEPAD_ACTIVATE_SLEEP   = 0.4
NOTEPAD_PASTE_SLEEP      = 0.1
NOTEPAD_SAVE_SLEEP       = 1.0
NOTEPAD_DESKTOP_SAVE_DIR = os.path.expanduser("~/Desktop")

# ── Registry paths ────────────────────────────────────────────────────────────
# Hive is inferred: None = HKLM, "HCU" = HKEY_CURRENT_USER
REGISTRY_UNINSTALL_PATHS = [
    (None, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),          # HKLM 64-bit
    (None, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),  # HKLM 32-bit
    ("HCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),         # HKEY_CURRENT_USER
]