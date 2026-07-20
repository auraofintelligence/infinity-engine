"""Run a job against a hosted per-output API (fal.ai, Replicate, ...).

Placeholder in Phase 0: the shape exists so workflow code never has to
change when a SaaS target is wired in. Each SaaS provider gets a small
adapter here keyed by settings['service'].
"""
from __future__ import annotations

from pathlib import Path

from . import Runner


class SaasRunner(Runner):
    def submit(self, job_dir: Path) -> None:
        service = self.settings.get("service", "unset")
        raise NotImplementedError(
            f"SaaS runner for '{service}' not wired yet. Phase 1 adds "
            "adapters (fal.ai first) that POST spec.json + assets and "
            "save outputs into results/.")
