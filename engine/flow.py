"""The guided flow: given a song's real state, what is the ONE next step.

This is the brain behind "Guide me" mode. It turns the eight engine verbs
into a plain four-beat story per song and works out which beat you are on,
so the GUI can show a single obvious button instead of a wall of controls.

The guided path deliberately does one well-supported thing: comic panels
at draft quality. Every choice is removed; Expert mode keeps the knobs.
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import resolve

GUIDE_KIND = "panels"
GUIDE_TIER = "draft"


def _panels_jobs(jobs_dir: Path, slug: str) -> list[Path]:
    if not jobs_dir.exists():
        return []
    pref = f"{slug}-{GUIDE_KIND}-"
    return sorted(p for p in jobs_dir.iterdir()
                  if p.is_dir() and p.name.startswith(pref))


def _job_state(jobs: list[Path]) -> tuple[bool, bool, bool]:
    """(has_plan, previewed, rendered) across a song's panels jobs."""
    has_plan = previewed = rendered = False
    for j in jobs:
        if (j / "spec.json").exists():
            has_plan = True
        man = j / "results" / "manifest.json"
        if man.exists():
            try:
                m = json.loads(man.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            shots = m.get("shots", [])
            if any(s.get("rendered") for s in shots):
                rendered = True
            elif shots:
                previewed = True
    return has_plan, previewed, rendered


def song_steps(cfg: dict, note, gpu_alive: bool) -> dict:
    """Return the four guided steps for a song, each with done-state and the
    exact /api/run body for its action. `current` is the first unfinished
    step; `all_done` when the picture is made and only publishing remains."""
    jobs_dir = resolve(cfg, "jobs_dir")
    slug = note.slug
    analysed = bool(note.meta.get("line_ideas"))
    has_plan, previewed, rendered = _job_state(_panels_jobs(jobs_dir, slug))

    if gpu_alive:
        pics_help = ("Draws every panel on your connected GPU. This is the "
                     "step that makes real pictures.")
        pics_action = {"cmd": "work"}
        pics_button = "Make the pictures"
    else:
        pics_help = ("No GPU is connected, so this writes the exact plan for "
                     "each panel instead of drawing it. To make real "
                     "pictures, connect a GPU (see the note above), then come "
                     "back and press this.")
        pics_action = {"cmd": "work", "flag": "--offline"}
        pics_button = "Preview the plan (no pictures yet)"

    steps = [
        {"key": "read", "title": "Read the song",
         "help": "Claude reads the whole lyric and writes a shot-by-shot "
                 "plan. Takes about a minute.",
         "done": analysed,
         "action": {"cmd": "brief", "slug": slug},
         "button": "Read the song"},
        {"key": "plan", "title": "Plan the comic panels",
         "help": "Turns the reading into a numbered list of panels to draw "
                 "and picks a model. Instant.",
         "done": has_plan,
         "action": {"cmd": "make", "slug": slug,
                    "kind": GUIDE_KIND, "tier": GUIDE_TIER},
         "button": "Plan the panels"},
        {"key": "pictures", "title": "Make the pictures",
         "help": pics_help,
         "done": rendered or previewed,
         "note": ("preview only so far, connect a GPU for real pictures"
                  if previewed and not rendered else ""),
         "action": pics_action,
         "button": pics_button},
        {"key": "publish", "title": "Show it on the site",
         "help": "Rebuilds your site so this song's page is up to date.",
         "done": False,
         "action": {"cmd": "site"},
         "button": "Show it on the site"},
    ]

    current = next((i for i, s in enumerate(steps) if not s["done"]), len(steps) - 1)
    for i, s in enumerate(steps):
        s["current"] = (i == current)
    return {"slug": slug, "title": note.meta.get("title", slug),
            "steps": steps, "current": current,
            "made": rendered or previewed}


def next_song(cfg: dict, notes: list, gpu_alive: bool):
    """The first song that still needs work (its picture is not made yet).
    Falls back to the first song so the button always does something."""
    for note in notes:
        plan = song_steps(cfg, note, gpu_alive)
        if not plan["made"]:
            return note.slug
    return notes[0].slug if notes else None
