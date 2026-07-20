"""Runner abstraction: where a job payload actually executes.

Local box, rented GPU pod, or a SaaS endpoint are interchangeable.
Which runner a tier uses is config (providers.yaml + config.yaml);
workflow code only ever calls get_runner(name).submit(job_dir).
"""
from __future__ import annotations

from pathlib import Path


class Runner:
    """A runner takes a job folder, executes it, and fills results/."""

    def __init__(self, settings: dict):
        self.settings = settings

    def submit(self, job_dir: Path) -> None:
        raise NotImplementedError


def get_runner(name: str, providers: dict) -> Runner:
    from .local import LocalRunner
    from .remote_pod import RemotePodRunner
    from .saas import SaasRunner

    kinds = {"local": LocalRunner, "remote_pod": RemotePodRunner,
             "saas": SaasRunner}
    settings = (providers.get("runners") or {}).get(name)
    if settings is None:
        raise KeyError(f"runner '{name}' not defined in providers.yaml")
    kind = settings.get("kind", name)
    if kind not in kinds:
        raise KeyError(f"unknown runner kind '{kind}'")
    return kinds[kind](settings)
