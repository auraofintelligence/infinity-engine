"""Run a job on a rented GPU pod over SSH.

The pod is treated as a stateless, untrusted worker: we push the job
folder up, run one command, pull results/ back, and nothing else ever
leaves the trusted machine. Works with any host that gives you SSH
(Vast.ai, RunPod pods, TensorDock, a mate's box).

providers.yaml example:

  runners:
    remote_pod:
      kind: remote_pod
      host: root@1.2.3.4        # or set at runtime: engine run --host ...
      port: 22
      remote_dir: /workspace/jobs
      command: "cd {remote_job_dir} && python /workspace/worker.py --spec spec.json --out results"
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import Runner


class RemotePodRunner(Runner):
    def _ssh_base(self) -> list[str]:
        port = str(self.settings.get("port", 22))
        return ["-p", port, self.settings["host"]]

    def submit(self, job_dir: Path) -> None:
        host = self.settings.get("host")
        if not host:
            raise RuntimeError(
                "remote_pod runner needs 'host' in providers.yaml "
                "(set it when you spin up the pod)")
        port = str(self.settings.get("port", 22))
        remote_dir = self.settings.get("remote_dir", "/workspace/jobs")
        remote_job_dir = f"{remote_dir}/{job_dir.name}"

        subprocess.run(["ssh", *self._ssh_base(),
                        f"mkdir -p {remote_job_dir}"], check=True)
        subprocess.run(["scp", "-P", port, "-r", f"{job_dir}/.",
                        f"{host}:{remote_job_dir}/"], check=True)
        command = self.settings["command"].format(
            remote_job_dir=remote_job_dir)
        subprocess.run(["ssh", *self._ssh_base(), command], check=True)
        subprocess.run(["scp", "-P", port, "-r",
                        f"{host}:{remote_job_dir}/results/.",
                        str(job_dir / "results")], check=True)
