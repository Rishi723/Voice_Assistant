"""
commands/router.py
───────────────────
AI Agent dispatcher – routes classified intents to tools or conversation.

Flow:
    1. Intent Classifier (LLM) decides: tool OR conversation
    2a. tool        → Your existing tools.executor → command handlers
    2b. conversation → Ollama LLM pipeline (ask) → speak_async

Everything integrates with your existing tools/ module and command handlers.
"""

import threading

from core import get_logger
from llm.intent_classifier import classify
from llm.ollama_client import ask
from speech import speak, speak_async
from tools import execute_tool  # ← Your existing tools module

log = get_logger(__name__)


def run_command(command: str) -> bool:
    """
    Classify *command* and dispatch accordingly.

    Args:
        command: Raw user voice input

    Returns:
        bool: Always True (command was processed)
        
    Note: Handles BOTH tool execution and conversation internally.
          main.py should NOT fall back to ask() after calling this.
    """
    if not command or not command.strip():
        return False

    # ── Classify the intent ───────────────────────────────────────────────────
    intent = classify(command)
    mode = intent.get("mode", "conversation")

    log.debug("Intent: mode=%s, tool=%s, args=%s", 
              mode, intent.get("tool"), intent.get("arguments"))

    if mode == "tool":
        tool_name = intent.get("tool", "")
        arguments = intent.get("arguments", {})
        
        if tool_name:
            # ── Use your existing tools.executor ────────────────────────────
            executed = execute_tool(tool_name, arguments)
            if executed:
                log.info("Tool '%s' executed successfully", tool_name)
                return True
            else:
                log.warning("Tool '%s' failed or unknown – routing to conversation", tool_name)
                # Fall through to conversation mode below
        else:
            log.warning("Tool mode but no tool name in intent – routing to conversation")
            # Fall through to conversation mode below

    # ── Conversation mode (or tool fallback) ──────────────────────────────────
    return _handle_conversation(command)


def _handle_conversation(command: str) -> bool:
    """
    Ollama conversational pipeline.
    Sends to LLM, speaks async with streaming.
    """
    try:
        speak("Let me think...")
        reply = ask(command)
        
        if reply:
            # Speak response asynchronously
            speak_thread = threading.Thread(
                target=lambda: speak_async(reply),
                daemon=True
            )
            speak_thread.start()
            speak_thread.join()
        
        return True
    
    except Exception as e:
        log.exception("Conversation handler error: %s", e)
        speak("Sorry, I encountered an error. Please try again.")
        return True  # Still consumed, don't re-raise