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

from .structure import structure_digest
from .vault import Note, note_path, read_note, write_note

PROMPT_TEMPLATE = """You are the lyrical intelligence layer of the Infinity Engine,
analysing one song from the i C. infinity universe so visuals can be
made from it. Work from the SONG STRUCTURE below, not just the words:
verses, chorus, bridge each want their own look and energy. Ground every
image in the actual lyrics and the album's visual world; do not invent
imagery the song does not support. Respond with ONLY a JSON object, no
prose, using exactly these keys:

{{
  "themes": [..],              // choose only from: {themes}
  "mood": "..",                // choose one from: {moods}
  "narrative_structure": "..", // choose one from: {structures}
  "visual_motifs": [..],       // 4-8 concrete filmable images that recur (use the motifs below)
  "emotional_arc": "..",       // one sentence, start state to end state
  "story_seed": "..",          // 2-3 sentences: a micro-drama premise for this song
  "section_plan": [            // ONE entry per section below, in order:
    {{
      "section": "..",         // echo the section label (verse 1, chorus, ...)
      "topic": "..",           // what this part is actually about, in a phrase
      "set": "..",             // the location/environment this section lives in
      "scene": "..",           // the action or image on screen through it
      "energy": "..",          // low | building | high | falling  (the flow)
      "transition": ".."       // how it hands off to the next section
    }}
  ],
  "panel_beats": [..]          // 8-12 one-line comic panels, following the section flow
}}

Song: {title}
Album: {album}
Album visual world: {visual_world}
Existing meaning note: {meaning}

SONG STRUCTURE (parsed; keys are salient words per section):
{structure}

Full lyrics:
{lyrics}
"""

ANALYSIS_KEYS = ("themes", "mood", "narrative_structure", "visual_motifs",
                 "emotional_arc", "story_seed", "section_plan", "panel_beats")


def build_prompt(note: Note, ontology: dict) -> str:
    structure = {"sections": note.meta.get("structure") or [],
                 "motifs": note.meta.get("motifs") or []}
    return PROMPT_TEMPLATE.format(
        themes=", ".join(ontology["themes"]),
        moods=", ".join(ontology["moods"]),
        structures=", ".join(ontology["narrative_structures"]),
        title=note.meta.get("title", note.slug),
        album=note.meta.get("album", "?"),
        visual_world=note.meta.get("album_visual_world", "not specified"),
        meaning=note.meta.get("meaning", "none"),
        structure=structure_digest(structure),
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
        timeout=600, shell=False)
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
