"""The local assistant: plain answers to "where are we up to", "what's
next", "what's due", and "explain this step".

Text first, on purpose. The answers are computed from the vault, the jobs
and your saved place, plus two editable files (catalog/targets.yaml for
milestones, catalog/lessons.yaml for the just-in-time explainers). Voice
(engine/voice.py) reads these answers aloud; speech-in is a later step.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import yaml

from . import flow, studio_state, vault
from .config import resolve


def _yaml(root: Path, name: str) -> dict:
    p = root / name
    if p.exists():
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {}


def progress(cfg: dict) -> dict:
    """Counts across the whole catalogue, in one pass over the jobs dir."""
    notes = vault.all_notes(resolve(cfg, "vault_dir"))
    analysed = sum(1 for n in notes if n.meta.get("line_ideas"))
    planned, made = set(), set()
    jobs_dir = resolve(cfg, "jobs_dir")
    if jobs_dir.exists():
        for j in jobs_dir.iterdir():
            if not j.is_dir() or "-panels-" not in j.name:
                continue
            slug = j.name.split("-panels-")[0]
            if (j / "spec.json").exists():
                planned.add(slug)
            man = j / "results" / "manifest.json"
            if man.exists():
                try:
                    m = json.loads(man.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                if m.get("shots"):
                    made.add(slug)
    return {"total": len(notes), "analysed": analysed,
            "planned": len(planned), "made": len(made)}


def _focus_note(cfg: dict):
    last = studio_state.load(cfg).get("last_song")
    if not last:
        return None
    return next((n for n in vault.all_notes(resolve(cfg, "vault_dir"))
                 if n.slug == last), None)


def where_are_we(cfg: dict) -> str:
    p = progress(cfg)
    bits = [f"{p['analysed']} of {p['total']} songs read, "
            f"{p['planned']} with a panel plan, "
            f"{p['made']} with pictures or previews."]
    note = _focus_note(cfg)
    if note:
        plan = flow.song_steps(cfg, note, False)
        cur = plan["steps"][plan["current"]]
        bits.append(f"You are on {note.meta.get('title', note.slug)}. "
                    f"Next: {cur['title'].lower()}.")
    trail = studio_state.load(cfg).get("trail") or []
    if trail:
        t = trail[0]
        bits.append("Last thing you did: " + t["what"].lower()
                    + (f" on {t['song']}." if t.get("song") else "."))
    return " ".join(bits)


def whats_next(cfg: dict, note=None) -> str:
    note = note or _focus_note(cfg)
    if not note:
        return "Pick a song to work on, then I can tell you the next step."
    plan = flow.song_steps(cfg, note, False)
    cur = plan["steps"][plan["current"]]
    return (f"On {note.meta.get('title', note.slug)}, your next step is: "
            f"{cur['title']}. {cur['help']}")


def whats_due(cfg: dict) -> str:
    data = _yaml(cfg["_root"], "catalog/targets.yaml")
    today = date.today()
    pending = []
    for m in data.get("milestones", []):
        if m.get("done"):
            continue
        try:
            by = date.fromisoformat(str(m.get("by")))
        except ValueError:
            continue
        pending.append((by, m.get("name", "?")))
    if not pending:
        return "Nothing on the calendar. Add milestones in targets.yaml."
    pending.sort()
    lines = []
    for by, name in pending:
        days = (by - today).days
        when = ("overdue" if days < 0 else "due today" if days == 0
                else f"in {days} day{'s' if days != 1 else ''}")
        lines.append(f"{name}: {when} ({by.isoformat()}).")
    overdue = sum(1 for by, _ in pending if (by - today).days < 0)
    head = (f"{overdue} milestone{'s' if overdue != 1 else ''} overdue. "
            if overdue else "")
    return head + " ".join(lines)


def lesson(cfg: dict, step_key: str | None) -> str:
    lessons = _yaml(cfg["_root"], "catalog/lessons.yaml")
    return (lessons.get(step_key) or lessons.get("general")
            or "No lesson yet for this step.").strip()


def answer(cfg: dict, q: str, note=None, step_key=None) -> str:
    if q == "where":
        return where_are_we(cfg)
    if q == "next":
        return whats_next(cfg, note)
    if q == "due":
        return whats_due(cfg)
    if q == "explain":
        return lesson(cfg, step_key)
    return "I can tell you where we are, what's next, or what's due."
