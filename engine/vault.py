"""Vault notes: one markdown file per song, YAML frontmatter + lyrics.

The vault is the brain of the pipeline. Plain files and git, no app
lock-in. Frontmatter fields follow ontology.yaml; the validate command
enforces that.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)

# Fields the ingest step owns and may refresh on re-ingest. Everything
# else (mood, themes once analysed, visual_motifs, status past
# 'ingested') belongs to analysis or to Luke, and re-ingest must not
# clobber it.
INGEST_OWNED = {"title", "album", "track", "source", "release_url", "song_date"}


@dataclass
class Note:
    slug: str
    meta: dict = field(default_factory=dict)
    body: str = ""

    @property
    def status(self) -> str:
        return self.meta.get("status", "ingested")


def note_path(vault_dir: Path, slug: str) -> Path:
    return vault_dir / f"{slug}.md"


def read_note(path: Path) -> Note:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return Note(slug=path.stem, meta={}, body=text)
    meta = yaml.safe_load(match.group(1)) or {}
    return Note(slug=path.stem, meta=meta, body=text[match.end():])


def write_note(vault_dir: Path, note: Note) -> Path:
    vault_dir.mkdir(parents=True, exist_ok=True)
    front = yaml.safe_dump(note.meta, sort_keys=False, allow_unicode=True,
                           default_flow_style=False).strip()
    path = note_path(vault_dir, note.slug)
    path.write_text(f"---\n{front}\n---\n{note.body}", encoding="utf-8")
    return path


def all_notes(vault_dir: Path) -> list[Note]:
    if not vault_dir.exists():
        return []
    return [read_note(p) for p in sorted(vault_dir.glob("*.md"))]


def validate_note(note: Note, ontology: dict) -> list[str]:
    """Return a list of problems; empty list means the note is clean."""
    problems = []
    meta = note.meta
    for required in ("title", "album", "status"):
        if not meta.get(required):
            problems.append(f"missing {required}")
    if meta.get("status") and meta["status"] not in ontology["statuses"]:
        problems.append(f"unknown status: {meta['status']}")
    for theme in meta.get("themes") or []:
        if theme not in ontology["themes"]:
            problems.append(f"unknown theme: {theme}")
    mood = meta.get("mood")
    if mood and mood not in ontology["moods"]:
        problems.append(f"unknown mood: {mood}")
    ns = meta.get("narrative_structure")
    if ns and ns not in ontology["narrative_structures"]:
        problems.append(f"unknown narrative_structure: {ns}")
    for lane in meta.get("lanes") or []:
        if lane not in ontology["lanes"]:
            problems.append(f"unknown lane: {lane}")
    return problems
