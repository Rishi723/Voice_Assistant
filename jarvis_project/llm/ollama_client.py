"""
llm/ollama_client.py
─────────────────────
Thin wrapper around the local Ollama REST API.

Public API
──────────
    ask(prompt: str) -> str   – sends prompt + rolling memory, returns reply
"""

import requests

from config import settings
from core import get_logger, state

log = get_logger(__name__)


def ask(prompt: str) -> str:
    """
    Send *prompt* to Ollama with rolling conversation memory.
    
    Args:
        prompt: User input or question
        
    Returns:
        str: Model's reply (truncated to LLM_MAX_WORDS if needed).
             Returns error message if Ollama is unavailable.
    """
    if not prompt.strip():
        return "I didn't receive any input. Please try again."

    # ── Update rolling memory window ─────────────────────────────────────────
    state.memory.append(f"User: {prompt}")
    
    # Keep only the most recent N messages to limit context size
    if len(state.memory) > settings.LLM_MEMORY_MAX:
        state.memory[:] = state.memory[-settings.LLM_MEMORY_MAX:]

    # Build context from last N messages (sliding window for quality)
    context = "\n".join(state.memory[-settings.LLM_MEMORY_WINDOW:])

    payload = {
        "model":  settings.LLM_MODEL,
        "prompt": context,
        "stream": False,
    }

    try:
        log.debug("Sending prompt to Ollama: %s", settings.LLM_BASE_URL)
        response = requests.post(
            settings.LLM_BASE_URL,
            json=payload,
            timeout=settings.LLM_TIMEOUT,
        )
        response.raise_for_status()
        
        reply = response.json().get("response", "").strip()
        
        if not reply:
            log.warning("Ollama returned empty response")
            return "I couldn't generate a response. Please try again."

        # ── Truncate very long answers ───────────────────────────────────────
        words = reply.split()
        if len(words) > settings.LLM_MAX_WORDS:
            reply = " ".join(words[:settings.LLM_MAX_WORDS]) + "… Would you like me to continue?"
            log.debug("Truncated response from %d to %d words", len(words), settings.LLM_MAX_WORDS)

        # ── Store reply in memory ────────────────────────────────────────────
        state.memory.append(f"Assistant: {reply}")
        
        log.debug("Ollama replied successfully (%d words)", len(words))
        return reply

    except requests.exceptions.ConnectionError as e:
        log.error("Ollama not reachable at %s (%s)", settings.LLM_BASE_URL, e)
        return "Sorry, the AI server is not running. Please start Ollama."
    
    except requests.exceptions.Timeout:
        log.warning("Ollama request timed out after %s seconds", settings.LLM_TIMEOUT)
        return "The question needs more time. Please try again."
    
    except requests.exceptions.HTTPError as e:
        log.error("Ollama returned HTTP error: %s", e)
        return "The AI server returned an error. Please check your Ollama setup."
    
    except Exception as e:
        log.exception("Unexpected error contacting Ollama: %s", e)
        return "Error contacting AI. Please check the logs."