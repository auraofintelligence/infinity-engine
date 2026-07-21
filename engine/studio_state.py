"""Wayfinding state: so you never lose your place.

The whole studio is built to be a well-lit city, not a forest you get lost
in. That needs memory of where you were. This module persists a tiny local
file (jobs/studio-state.json, gitignored) holding:

  - last_song   : the song you last touched, so the app reopens on it
  - comfy_server: the GPU box you connected, so it stays connected
  - trail       : a breadcrumb log of recent actions ("Read the song", ...)

Everything here is local and disposable; deleting the file just forgets
your place, it never loses work (the vault and jobs are the real record).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import resolve

TRAIL_MAX = 40


def _path(cfg: dict) -> Path:
    return resolve(cfg, "jobs_dir") / "studio-state.json"


def load(cfg: dict) -> dict:
    p = _path(cfg)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            data.setdefault("last_song", None)
            data.setdefault("comfy_server", None)
            data.setdefault("trail", [])
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"last_song": None, "comfy_server": None, "trail": []}


def save(cfg: dict, state: dict) -> None:
    p = _path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")


def record(cfg: dict, *, song: str | None = None, song_title: str | None = None,
           what: str | None = None) -> dict:
    """Drop a breadcrumb. Updates last_song when a song is named, and prepends
    a trail entry when `what` is given."""
    state = load(cfg)
    if song:
        state["last_song"] = song
    if what:
        state["trail"].insert(0, {
            "t": datetime.now().isoformat(timespec="seconds"),
            "what": what, "song": song_title or ""})
        state["trail"] = state["trail"][:TRAIL_MAX]
    save(cfg, state)
    return state


def set_server(cfg: dict, server: str | None) -> dict:
    state = load(cfg)
    state["comfy_server"] = server or None
    save(cfg, state)
    return state
