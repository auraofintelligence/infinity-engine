"""Offline voice, no installs, no cloud.

Text-to-speech uses Windows' built-in System.Speech (SAPI) through
PowerShell, so it works on a fresh Windows box with nothing to install and
nothing leaving the machine. On other platforms it degrades to a no-op so
callers do not break.

Speech-to-text (talking back) is the declared NEXT step: it needs a local
model such as Whisper or Vosk. `stt_available()` reports honestly that it
is not wired yet, so the UI can show it as coming rather than pretend.
"""
from __future__ import annotations

import subprocess
import sys

# Read the whole spoken text from stdin so nothing is interpolated into the
# command line (no quoting or injection worries).
_PS = ("Add-Type -AssemblyName System.Speech;"
       "$v = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
       "$v.Rate = 0;"
       "$v.Speak([Console]::In.ReadToEnd())")


def tts_available() -> bool:
    return sys.platform == "win32"


def stt_available() -> bool:
    # Declared step, not built: needs a local Whisper/Vosk model.
    return False


def say(text: str) -> bool:
    """Speak text aloud. Returns True if it was spoken."""
    text = (text or "").strip()
    if not text or not tts_available():
        return False
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", _PS],
                       input=text, text=True, timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
