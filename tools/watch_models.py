"""Recon watcher: scan Hugging Face for new and surging models per
category and drop the notable ones into recon-queue.yaml.

No dependencies beyond PyYAML (already required) and the standard
library. Uses the public HF API, no auth needed for public models.
Designed to run on a schedule (see docs/RECON-WATCHER.md). It never
touches the active registry; it only proposes candidates for you to vet.

Run:  python tools/watch_models.py
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "recon-queue.yaml"
SEEN = ROOT / "catalog" / ".seen.json"
MODELS = ROOT / "catalog" / "models.yaml"

# Category -> Hugging Face pipeline tag. Extend as the stack grows.
CATEGORIES = {
    "video": "text-to-video",
    "image": "text-to-image",
    "tts": "text-to-speech",
    "stt": "automatic-speech-recognition",
    "lipsync": "audio-to-video",
}

TOP_N = 25           # how many top-by-likes to pull per category
SURGE = 150          # likes gained since last run to count as a star-surge
NEW_FLOOR = 120      # a brand-new model needs at least this many likes to flag


def _fetch(pipeline_tag: str) -> list[dict]:
    url = (f"https://huggingface.co/api/models?pipeline_tag={pipeline_tag}"
           f"&sort=likes&direction=-1&limit={TOP_N}")
    req = urllib.request.Request(url, headers={"User-Agent": "infinity-engine"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _load_yaml(path: Path, key: str) -> list:
    if not path.exists():
        return []
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get(key, [])


def main() -> int:
    # First run establishes a baseline of what's already popular WITHOUT
    # flagging it. Everything looks "new" against an empty history, so a
    # cold start would otherwise flood the queue with established models.
    first_run = not SEEN.exists()
    seen = json.loads(SEEN.read_text(encoding="utf-8")) if SEEN.exists() else {}
    queue = _load_yaml(QUEUE, "queue")
    known_ids = {q.get("id") for q in queue}
    known_ids |= {m.get("hf", "").split("/")[-1].lower()
                  for m in _load_yaml(MODELS, "models")}
    today = date.today().isoformat()
    added = 0

    for category, tag in CATEGORIES.items():
        try:
            hits = _fetch(tag)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"[{category}] fetch failed: {exc}")
            continue
        for h in hits:
            hf_id = h.get("id", "")
            likes = int(h.get("likes", 0) or 0)
            slug = hf_id.split("/")[-1].lower()
            prev = seen.get(hf_id)
            seen[hf_id] = likes
            if first_run or slug in known_ids or hf_id in known_ids:
                continue
            reason = None
            if prev is None and likes >= NEW_FLOOR:
                reason = "new"
            elif prev is not None and likes - prev >= SURGE:
                reason = "star-surge"
            if not reason:
                continue
            queue.append({
                "id": slug,
                "name": hf_id,
                "category": category,
                "flagged_reason": reason,
                "flagged_date": today,
                "link": f"https://huggingface.co/{hf_id}",
                "status": "new",
                "notes": f"{likes} HF likes at flag. Auto-flagged by the watcher.",
            })
            known_ids.add(slug)
            added += 1
            print(f"[{category}] flagged {hf_id} ({reason}, {likes} likes)")

    QUEUE.write_text(
        "# Recon queue. Auto-appended by tools/watch_models.py; hand-edit "
        "freely.\n# Vet each candidate, then promote into catalog/models.yaml "
        "or reject.\n\n"
        + yaml.safe_dump({"queue": queue}, sort_keys=False, allow_unicode=True),
        encoding="utf-8")
    SEEN.parent.mkdir(exist_ok=True)
    SEEN.write_text(json.dumps(seen, indent=1), encoding="utf-8")
    if first_run:
        print(f"\nBaseline established: {len(seen)} models tracked. Future "
              "runs will flag genuinely new and surging models.")
    else:
        print(f"\n{added} new candidate(s) added; {len(seen)} models tracked.")
        print("Regenerate the site to see them: python -m engine site")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
