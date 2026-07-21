"""The render worker: turn a queued job folder into rendered frames.

This is what runs on the GPU box. It reads spec.json (the only thing that
travelled from the trusted machine), builds one ComfyUI graph per shot
from the recipe in catalog/comfy.yaml, submits them to a local ComfyUI
server, and lands the images in the job's results/ folder with a manifest.

Offline mode needs no GPU and no ComfyUI: it writes the exact graphs it
WOULD submit into results/graphs/, so the whole loop is inspectable and
testable on any machine. Drop --offline on the pod and the same code runs
for real.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from . import comfy

# Which recipe family and output aspect each job kind renders with.
KIND_RECIPE = {"panels": ("image", "square"),
               "keyframes": ("image", "vertical")}


def load_comfy_config(root: Path) -> dict:
    path = root / "catalog" / "comfy.yaml"
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _seed(job_id: str, n: int) -> int:
    """Deterministic per-shot seed from the job id, so a rerun reproduces
    unless the spec changes. (No RNG: reproducibility over surprise.)"""
    return (abs(hash(job_id)) + n * 1000003) % (2 ** 32)


def run_job(root: Path, job_dir: Path, *, offline: bool = False,
            on_status=None) -> dict:
    """Render every shot in a job. Returns a manifest dict; also writes it
    to results/manifest.json. Raises on a real render failure."""
    spec = json.loads((job_dir / "spec.json").read_text(encoding="utf-8"))
    kind = spec.get("kind")
    if kind not in KIND_RECIPE:
        raise ValueError(f"worker has no render path for kind '{kind}' yet")
    category, aspect = KIND_RECIPE[kind]

    ccfg = load_comfy_config(root)
    recipe = (ccfg.get("recipes", {}).get(category, {})).get(spec.get("tier"))
    if not recipe:
        raise ValueError(
            f"no comfy recipe for {category}/{spec.get('tier')} in comfy.yaml")
    width, height = ccfg.get("sizes", {}).get(aspect, [1024, 1024])

    direction = spec.get("direction", {})
    shots = direction.get("shots") or []
    style = direction.get("style") or {}
    results = job_dir / "results"
    results.mkdir(exist_ok=True)

    client = None
    if not offline:
        client = comfy.ComfyClient(ccfg.get("server", "http://127.0.0.1:8188"))
        if not client.alive():
            raise ConnectionError(
                f"no ComfyUI at {client.server}; start it on the pod or pass "
                "offline=True to emit graphs without rendering")
    else:
        (results / "graphs").mkdir(exist_ok=True)

    entries = []
    for shot in shots:
        n = shot.get("n", len(entries) + 1)
        positive = comfy.build_prompt_text(shot, style)
        prefix = f"{spec['id']}_shot{n:02d}"
        graph = comfy.build_graph(recipe, positive, width, height,
                                  _seed(spec["id"], n), prefix)
        entry = {"shot": n, "lyric": shot.get("lyric", ""), "prompt": positive}
        if offline:
            gpath = results / "graphs" / f"shot{n:02d}.json"
            gpath.write_text(json.dumps(graph, indent=2), encoding="utf-8")
            entry["graph"] = f"graphs/{gpath.name}"
            entry["rendered"] = False
        else:
            pid = client.submit(graph)
            hist = client.wait(pid)
            files = client.fetch_images(hist, results)
            entry["files"] = files
            entry["rendered"] = bool(files)
        entries.append(entry)
        if on_status:
            on_status(n, len(shots))

    manifest = {"job": spec["id"], "song": spec.get("data", {}).get("song"),
                "kind": kind, "tier": spec.get("tier"),
                "model": spec.get("model", {}).get("name"),
                "size": [width, height], "offline": offline,
                "shots": entries}
    (results / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
