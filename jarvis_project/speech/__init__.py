"""speech – TTS and STT helpers."""
from .tts        import speak, speak_async
from .recognizer import calibrate, listen, listen_long, listen_for_interrupt