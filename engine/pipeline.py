"""The operational loop: turn one analysed song into a runnable job.

The seven moves the engine makes for every piece:

  1. grab data      read the note (lyrics, the LLM's line-by-line read,
                    motifs, story seed, audio features if ingested)
  2. grab model     pick an open-weight model from providers.yaml by the
                    job kind and tier
  3. align compute  pick the runner (local box / rented pod / hosted) for
                    that tier from config.default_runners
  4. give direction assemble the shot list and style block from the
                    analysis, the actual prompt the worker renders
  5. output lands   write the job folder (spec.json + results/), the only
                    thing that ever travels to a GPU worker
  6. evaluate       a human gate: review the results that land back
  7. next move      advance the song's status, or reroll the job

This module owns moves 1-5 (assembling the payload). The worker owns the
render; `engine advance` owns move 7. Move 6 is Luke.
"""
from __future__ import annotations

# Job kind -> which model family in providers.yaml renders it.
KIND_CATEGORY = {
    "panels": "image",
    "keyframes": "image",
    "video": "video",
    "tts": "tts",
    "lipsync": "lipsync",
    "avatar": "avatar",
}

# A clean render of this kind advances the song to this status.
KIND_NEXT_STATUS = {
    "panels": "panels",
    "keyframes": "keyframes",
    "video": "video",
}

# Kinds that need the LLM's read before they mean anything.
NEEDS_ANALYSIS = {"panels", "keyframes", "video"}

TIER_ORDER = ["draft", "standard", "premium"]


class PipelineError(Exception):
    """A job can't be assembled (missing analysis, unknown kind, ...)."""


def pick_model(providers: dict, category: str, tier: str) -> tuple[str, dict]:
    """Return (tier_used, model_dict). Falls back to the nearest tier that
    actually exists for this category, so `avatar` (premium-only) still
    resolves when asked for standard."""
    family = (providers.get("models") or {}).get(category)
    if not family:
        raise PipelineError(f"no models for '{category}' in providers.yaml")
    if tier in family and isinstance(family[tier], dict):
        return tier, family[tier]
    # Nearest available tier, searching out from the one asked for.
    order = [t for t in TIER_ORDER if isinstance(family.get(t), dict)]
    if not order:
        raise PipelineError(f"no usable tier for '{category}'")
    want = TIER_ORDER.index(tier) if tier in TIER_ORDER else 1
    order.sort(key=lambda t: abs(TIER_ORDER.index(t) - want))
    return order[0], family[order[0]]


def pick_runner(cfg: dict, providers: dict, tier: str) -> tuple[str, dict]:
    name = (cfg.get("default_runners") or {}).get(tier, "local")
    runner = (providers.get("runners") or {}).get(name, {})
    return name, dict(runner)


def build_direction(note, kind: str) -> dict:
    """Move 4: assemble the direction from the analysis. Shots come from
    the LLM's per-line read; the style block frames every shot."""
    m = note.meta
    shots = []
    for i, item in enumerate(m.get("line_ideas") or [], 1):
        if isinstance(item, dict) and item.get("idea"):
            shots.append({"n": i, "lyric": item.get("lyric", ""),
                          "direction": item["idea"]})
    style = {
        "mood": m.get("mood"),
        "visual_world": m.get("album_visual_world"),
        "story_seed": m.get("story_seed"),
        "emotional_arc": m.get("emotional_arc"),
        "motifs": (m.get("visual_motifs") or [])[:6],
        "themes": m.get("themes") or [],
    }
    audio = m.get("audio")
    beat = None
    if isinstance(audio, dict):
        beat = {"tempo_bpm": audio.get("tempo_bpm"),
                "duration_s": audio.get("duration_s"),
                "arrangement": audio.get("arrangement")}
    return {"shots": shots, "style": {k: v for k, v in style.items() if v},
            "beat": beat}


def plan_job(cfg: dict, providers: dict, note, kind: str,
             tier: str) -> dict:
    """Assemble the full plan WITHOUT writing anything. Returns a dict that
    describes each of the seven moves, plus the spec ready for create_job."""
    if kind not in KIND_CATEGORY:
        raise PipelineError(
            f"unknown kind '{kind}'; known: {', '.join(KIND_CATEGORY)}")
    if kind in NEEDS_ANALYSIS and note.status == "ingested":
        raise PipelineError(
            f"{note.slug} is not analysed yet; run: engine brief "
            f"{note.slug} --run-claude")

    category = KIND_CATEGORY[kind]
    tier_used, model = pick_model(providers, category, tier)
    runner_name, runner = pick_runner(cfg, providers, tier_used)
    direction = build_direction(note, kind)

    spec = {
        "kind": kind,
        "tier": tier_used,
        "runner": runner_name,
        "model": {"name": model.get("name"),
                  "licence": model.get("licence"),
                  "vram_gb": model.get("vram_gb")},
        "data": {
            "song": note.meta.get("title", note.slug),
            "album": note.meta.get("album"),
            "lyrics_ref": f"vault/{note.slug}.md",
            "has_audio": bool(note.meta.get("audio")),
        },
        "direction": direction,
        "poster_lines": note.meta.get("poster_lines") or [],
    }
    return {
        "kind": kind,
        "tier_asked": tier,
        "tier_used": tier_used,
        "category": category,
        "model": model,
        "runner_name": runner_name,
        "runner": runner,
        "shot_count": len(direction["shots"]),
        "next_status": KIND_NEXT_STATUS.get(kind),
        "spec": spec,
    }
