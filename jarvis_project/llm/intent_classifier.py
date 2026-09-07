"""
llm/intent_classifier.py
─────────────────────────
AI Intent Classifier – the brain of the Agent layer.

Responsibility (ONLY):
    Decide whether the user's input is a TOOL request or a CONVERSATION.

It makes ONE lightweight LLM call with a strict system prompt that forces
the model to return ONLY a JSON object – never prose.

Return value is always a plain dict:
    {"mode": "tool", "tool": "open_app", "arguments": {"app": "spotify"}}
    {"mode": "conversation"}

This module has NO side effects. It classifies; it does not execute.
"""

import json
import re

import requests

from config import settings
from core import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# System prompt – injected on every classifier call.
# Kept here (not in settings) because it is tightly coupled to the registry.
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are an intent classifier for a Windows voice assistant.
Your ONLY job is to output a single JSON object. Never write English prose.

Available tools:
  open_app(app: str)                    - open any application
  close_app(app: str)                   - close / kill a running application
  minimize_app(app: str)                - minimize an application window
  play_music(query: str)                - play music; "" means play all/shuffle
  stop_music()                          - stop music
  pause_music()                         - pause music
  resume_music()                        - resume / unpause music
  next_track()                          - skip to next song
  previous_track()                      - go to previous song
  current_track()                       - say what song is playing
  music_volume_up()                     - increase music volume
  music_volume_down()                   - decrease music volume
  volume_up()                           - increase system volume
  volume_down()                         - decrease system volume
  mute()                                - toggle system mute
  switch_tab()                          - switch browser/app tab
  lock_screen()                         - lock the computer
  shutdown_pc()                         - shut down the computer
  restart_pc()                          - restart the computer
  sleep_pc()                            - put computer to sleep
  refresh_apps()                        - rescan installed applications
  write_notepad(text: str, filename: str) - write text in Notepad
  clear_notepad()                       - clear all text in Notepad

RULES FOR YOUR RESPONSE:
1. If user wants to execute any tool above → return ONLY:
   {"mode":"tool","tool":"<name>","arguments":{<args>}}

2. If user is asking a question, having a conversation, or requesting 
   information → return ONLY:
   {"mode":"conversation"}

3. Output ONLY the JSON object. No markdown. No explanation. No extra text.

EXAMPLES:
User: "open spotify"                         → {"mode":"tool","tool":"open_app","arguments":{"app":"spotify"}}
User: "play love me like you do"             → {"mode":"tool","tool":"play_music","arguments":{"query":"love me like you do"}}
User: "what is the capital of france"        → {"mode":"conversation"}
User: "pause music"                          → {"mode":"tool","tool":"pause_music","arguments":{}}
"""


def classify(user_input: str) -> dict:
    """
    Classify *user_input* as a tool call or conversation.

    Args:
        user_input: Raw voice input from user

    Returns:
        dict with guaranteed keys:
        - {"mode": "conversation"}  ← for non-tool requests
        - {"mode": "tool", "tool": "<name>", "arguments": {...}}  ← for tool requests
        
        Never raises – falls back to {"mode": "conversation"} on any error.
    """
    if not user_input.strip():
        return {"mode": "conversation"}

    prompt = f"{_SYSTEM_PROMPT}\n\nUser: {user_input}"

    payload = {
        "model":  settings.LLM_CLASSIFIER_MODEL,
        "prompt": prompt,
        "stream": False,
    }

    try:
        response = requests.post(
            settings.LLM_BASE_URL,
            json=payload,
            timeout=settings.LLM_CLASSIFIER_TIMEOUT,
        )
        response.raise_for_status()
        raw = response.json().get("response", "").strip()

        # Strip markdown fences if the model wraps anyway (defensive)
        raw = re.sub(r"^```(?:json)?\n?|\n?```$", "", raw, flags=re.MULTILINE).strip()

        result = json.loads(raw)

        # Validate response structure
        if not isinstance(result, dict):
            raise ValueError("Response is not a JSON object")
        
        if "mode" not in result:
            raise ValueError("Missing 'mode' key in classifier response")
        
        if result["mode"] not in ("tool", "conversation"):
            raise ValueError(f"Invalid mode: {result['mode']}")

        # Validate tool mode has tool and arguments
        if result["mode"] == "tool":
            if "tool" not in result:
                raise ValueError("Tool mode missing 'tool' key")
            if "arguments" not in result:
                result["arguments"] = {}

        return result

    except requests.exceptions.ConnectionError:
        log.error("Ollama not reachable at %s – falling back to conversation mode", settings.LLM_BASE_URL)
    except requests.exceptions.Timeout:
        log.warning("Classifier timed out (%ss) – falling back to conversation mode", settings.LLM_CLASSIFIER_TIMEOUT)
    except json.JSONDecodeError as e:
        log.warning("Classifier returned invalid JSON (%s) – falling back to conversation mode", e)
    except ValueError as e:
        log.warning("Classifier validation failed (%s) – falling back to conversation mode", e)
    except Exception as e:
        log.exception("Unexpected classifier error – falling back to conversation mode")

    return {"mode": "conversation"}