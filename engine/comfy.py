"""ComfyUI graph building and a thin HTTP client.

The worker runs ON the GPU box next to a ComfyUI server. It builds an
API-format graph (a dict of nodes) from a shot's direction and the recipe
in catalog/comfy.yaml, POSTs it to /prompt, polls /history, and pulls the
rendered image back. Only stdlib is used, so the worker has no pip
dependencies beyond PyYAML (already required for config).

Graph builders are keyed by the recipe's `graph` field so a new model
family is a new builder plus a recipe, never a change to the worker loop.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# One prompt is a "positive" (what to render) and the recipe's negative.


def build_prompt_text(shot: dict, style: dict) -> str:
    """Fold the shot direction and the song's style block into one positive
    prompt. The line read is the subject; the style frames every shot so a
    song holds together visually."""
    parts = [shot.get("direction", "").strip()]
    if style.get("mood"):
        parts.append(f"mood: {style['mood']}")
    if style.get("visual_world"):
        parts.append(f"world: {style['visual_world']}")
    motifs = style.get("motifs") or []
    if motifs:
        parts.append("recurring motifs: " + "; ".join(motifs[:3]))
    parts.append("cinematic, single frame, no text, no captions")
    return ". ".join(p for p in parts if p)


def sd_txt2img(recipe: dict, positive: str, width: int, height: int,
               seed: int, prefix: str) -> dict:
    """The classic CheckpointLoaderSimple text-to-image graph, in ComfyUI
    API format. Works with any SD/SDXL-class checkpoint; Qwen-Image and
    FLUX.2 get their own builders (different loader nodes)."""
    return {
        "4": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": recipe["ckpt_name"]}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"text": positive, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode",
              "inputs": {"text": recipe.get("negative", ""), "clip": ["4", 1]}},
        "3": {"class_type": "KSampler",
              "inputs": {"seed": seed, "steps": recipe.get("steps", 25),
                         "cfg": recipe.get("cfg", 4.0),
                         "sampler_name": recipe.get("sampler_name", "euler"),
                         "scheduler": recipe.get("scheduler", "normal"),
                         "denoise": 1.0, "model": ["4", 0],
                         "positive": ["6", 0], "negative": ["7", 0],
                         "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode",
              "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"images": ["8", 0], "filename_prefix": prefix}},
    }


BUILDERS = {"sd_txt2img": sd_txt2img}


def build_graph(recipe: dict, positive: str, width: int, height: int,
                seed: int, prefix: str) -> dict:
    builder = BUILDERS.get(recipe.get("graph", "sd_txt2img"))
    if builder is None:
        raise ValueError(f"no graph builder for '{recipe.get('graph')}'")
    return builder(recipe, positive, width, height, seed, prefix)


class ComfyClient:
    """Minimal ComfyUI HTTP client. Talks to a server that is already up;
    starting ComfyUI itself is the pod's job."""

    def __init__(self, server: str, timeout: int = 5):
        self.server = server.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> dict:
        with urllib.request.urlopen(f"{self.server}{path}",
                                    timeout=self.timeout) as r:
            return json.loads(r.read())

    def alive(self) -> bool:
        try:
            self._get("/system_stats")
            return True
        except (urllib.error.URLError, OSError):
            return False

    def submit(self, graph: dict) -> str:
        body = json.dumps({"prompt": graph}).encode()
        req = urllib.request.Request(f"{self.server}/prompt", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())["prompt_id"]

    def wait(self, prompt_id: str, poll: float = 2.0,
             max_wait: float = 600) -> dict:
        waited = 0.0
        while waited < max_wait:
            history = self._get(f"/history/{prompt_id}")
            if prompt_id in history:
                return history[prompt_id]
            time.sleep(poll)
            waited += poll
        raise TimeoutError(f"ComfyUI job {prompt_id} did not finish")

    def fetch_images(self, history: dict, out_dir: Path) -> list[str]:
        saved = []
        for node in (history.get("outputs") or {}).values():
            for img in node.get("images", []):
                q = urllib.parse.urlencode(
                    {"filename": img["filename"], "subfolder": img.get("subfolder", ""),
                     "type": img.get("type", "output")})
                with urllib.request.urlopen(f"{self.server}/view?{q}",
                                            timeout=30) as r:
                    dest = out_dir / img["filename"]
                    dest.write_bytes(r.read())
                    saved.append(dest.name)
        return saved
