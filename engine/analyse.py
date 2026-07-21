"""Cheap text ideation before expensive generation.

The brief command emits a self-contained prompt packet per song. That
packet can go to any LLM: pasted into a chat, piped through the claude
CLI, or run against a local model. The merge command folds the JSON
answer back into the note's frontmatter and advances its status.

Keeping this as text-in/text-out means the ideation layer is
model-agnostic for free.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .vault import Note, note_path, read_note, write_note

PROMPT_TEMPLATE = """You are the lyrical intelligence layer of the Infinity Engine,
reading one whole song from the i C. infinity universe like a director
looking for images to shoot. Read the ENTIRE lyric below and respond with
a director's read, not a word-frequency summary.

Hard rules:
- Every image and idea must trace to a SPECIFIC line or phrase in this
  lyric. Quote or paraphrase the line it comes from.
- Be concrete and filmable: a place, an object, a gesture, a light, a
  camera move. No abstractions ("hope", "journey"), no generic stock
  ("person walking"), no imagery the song does not actually support.
- Specific to THIS song and the album's visual world. If two songs would
  get the same idea, it is too generic; go deeper into the actual words.
- It is fine to notice tension, contradiction, or subtext and shoot
  against the lyric, not only with it.
- Never use em dashes (the long dash). Use commas, colons or full stops.

Respond with ONLY a JSON object, no prose, using exactly these keys:

{{
  "themes": [..],              // 2-4, choose only from: {themes}
  "mood": "..",                // choose one from: {moods}
  "emotional_arc": "..",       // one sentence: where the song starts vs ends
  "story_seed": "..",          // 2-3 sentences: a concrete micro-drama premise
                               // rooted in this song's actual images
  "visual_motifs": [..],       // 5-8 concrete images that ACTUALLY appear or
                               // are strongly implied in the lyric
  "poster_lines": [..],        // 5-8 of the strongest STANDALONE phrases,
                               // verbatim, that would work on a poster or a
                               // t-shirt: short, punchy, quotable, no context
                               // needed. These sell as merch.
  "line_ideas": [              // the heart of this: read line by line and
    {{                          // give 10-16 of the strongest moments
      "lyric": "..",           // the exact line or short phrase, verbatim
      "idea": ".."             // a specific visual, observation or direction
                               // for that moment (image, action, camera, colour)
    }}
  ]
}}

Song: {title}
Album: {album}
Album visual world: {visual_world}
Existing meaning note: {meaning}

Full lyrics:
{lyrics}
"""

ANALYSIS_KEYS = ("themes", "mood", "emotional_arc", "story_seed",
                 "visual_motifs", "poster_lines", "line_ideas")


def build_prompt(note: Note, ontology: dict) -> str:
    return PROMPT_TEMPLATE.format(
        themes=", ".join(ontology["themes"]),
        moods=", ".join(ontology["moods"]),
        title=note.meta.get("title", note.slug),
        album=note.meta.get("album", "?"),
        visual_world=note.meta.get("album_visual_world", "not specified"),
        meaning=note.meta.get("meaning", "none"),
        lyrics=note.body.strip(),
    )


def write_prompt_packet(note: Note, ontology: dict, prompts_dir: Path) -> Path:
    prompts_dir.mkdir(parents=True, exist_ok=True)
    path = prompts_dir / f"{note.slug}.prompt.txt"
    path.write_text(build_prompt(note, ontology), encoding="utf-8")
    return path


def run_claude(prompt: str) -> str:
    """Run the packet through the local claude CLI (claude -p)."""
    result = subprocess.run(
        ["claude", "-p", prompt], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=600, shell=False)
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr.strip()}")
    return result.stdout


def parse_analysis(raw: str) -> dict:
    """Extract the JSON object from an LLM response, tolerating fences."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in response")
    return json.loads(text[start:end + 1])


def merge_analysis(vault_dir: Path, slug: str, analysis: dict) -> Note:
    note = read_note(note_path(vault_dir, slug))
    for key in ANALYSIS_KEYS:
        if key in analysis:
            note.meta[key] = analysis[key]
    if note.meta.get("status") == "ingested":
        note.meta["status"] = "analysed"
    write_note(vault_dir, note)
    return note
