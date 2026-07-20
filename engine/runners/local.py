"""Run a job on this machine via a command template from providers.yaml.

The command template receives {job_dir}, {spec} and {results_dir}.
Example in providers.yaml:

  runners:
    local:
      kind: local
      command: "python worker.py --spec {spec} --out {results_dir}"
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import Runner


class LocalRunner(Runner):
    def submit(self, job_dir: Path) -> None:
        template = self.settings.get("command")
        if not template:
            raise RuntimeError("local runner has no 'command' in providers.yaml")
        cmd = template.format(job_dir=job_dir, spec=job_dir / "spec.json",
                              results_dir=job_dir / "results")
        subprocess.run(cmd, shell=True, check=True)
