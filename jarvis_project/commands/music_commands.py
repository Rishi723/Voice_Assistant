"""
commands/music_commands.py
──────────────────────────
Voice command handler for all music-related phrases.
Covers English and Telugu trigger words.
Returns True if the command was handled.
"""

from services.music_service import (
    play_all, play_song, stop, pause, resume,
    next_track, previous_track, current_track,
    volume_up, volume_down,
)

_TELUGU_PLAY   = [
    "oka paata vesoku", "paata vesoku", "paata veyyi",
    "music vesoku", "paata petthu", "oka paata petthu",
    "paata start cheyyi", "music start cheyyi", "paata play cheyyi",
]
_TELUGU_STOP   = ["paata aaphu", "music aaphu", "aaphu", "paata band cheyyi"]
_TELUGU_NEXT   = ["next paata", "paata marcheyyi", "vere paata vesoku", "inka okati vesoku"]
_TELUGU_PAUSE  = ["paata pause cheyyi", "konchem aaphu"]

_TELUGU_KW     = ["paata", "pata", "paatha", "vesoku", "vesko", "vesuko", "petthu", "pettu"]

_SHUFFLE_KW    = {
    "music", "all", "all songs", "songs", "",
    "random", "any", "any song", "anything",
    "something", "shuffle", "random song",
    "any music", "whatever", "surprise me",
}


def handle_music_commands(command: str) -> bool:
    """Dispatch all music voice commands. Returns True if handled."""
    # ── Telugu triggers ───────────────────────────────────────────────────────
    if any(t in command for t in _TELUGU_PLAY):  play_all();        return True
    if any(t in command for t in _TELUGU_STOP):  stop();            return True
    if any(t in command for t in _TELUGU_NEXT):  next_track();      return True
    if any(t in command for t in _TELUGU_PAUSE): pause();           return True

    if sum(1 for w in _TELUGU_KW if w in command) >= 2:
        play_all(); return True

    # ── English triggers ──────────────────────────────────────────────────────
    if any(w in command for w in ["stop music", "stop the music", "stop song"]):
        stop();    return True
    if any(w in command for w in ["pause music", "pause the music", "pause song"]):
        pause();   return True
    if any(w in command for w in ["resume music", "continue music", "unpause"]):
        resume();  return True
    if any(w in command for w in ["next song", "next track", "skip song", "skip track"]):
        next_track();     return True
    if any(w in command for w in ["previous song", "previous track", "last song", "go back"]):
        previous_track(); return True
    if any(w in command for w in ["what song", "what's playing", "current song", "song name"]):
        current_track();  return True
    if "music volume up" in command or "louder" in command:
        volume_up();   return True
    if "music volume down" in command or "quieter" in command:
        volume_down(); return True

    # ── play <query> ──────────────────────────────────────────────────────────
    if command.startswith("play "):
        query = command[5:].strip()
        if query in _SHUFFLE_KW or any(w in query for w in ["random", "any", "shuffle", "whatever", "surprise"]):
            play_all(); return True
        play_song(query); return True

    if command in ("music", "play music", "start music"):
        play_all(); return True

    return False
