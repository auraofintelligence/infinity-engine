"""Configuration loading for the Infinity Engine.

Everything the pipeline needs to know about this machine lives in
config.yaml; everything model-specific lives in providers.yaml; the tag
vocabulary lives in ontology.yaml. Code never hard-codes any of it.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install -r requirements.txt")

ROOT = Path(__file__).resolve().parent.parent


def _load_yaml(name: str) -> dict:
    path = ROOT / name
    if not path.exists():
        sys.exit(f"Missing {name} in {ROOT}")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_config() -> dict:
    cfg = _load_yaml("config.yaml")
    cfg["_root"] = ROOT
    return cfg


def load_ontology() -> dict:
    return _load_yaml("ontology.yaml")


def load_providers() -> dict:
    return _load_yaml("providers.yaml")


def resolve(cfg: dict, key: str) -> Path:
    """Resolve a path from config relative to the repo root."""
    value = cfg[key]
    path = Path(value)
    return path if path.is_absolute() else cfg["_root"] / path
